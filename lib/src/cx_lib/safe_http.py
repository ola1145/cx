"""SSRF-safe HTTP client — fixes S7.

Resolves DNS and blocks loopback, private, link-local, CGN and
unique-local addresses on EVERY redirect hop. Never reaches port
other than 80 or 443. Honours robots.txt (server error = do not crawl).

Usage::

    from cx_lib.safe_http import safe_get, SafeHttpError, RobotsBlocked

    html = await safe_get("https://example.com/menu")
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.parse
import urllib.robotparser
from typing import NamedTuple

__all__ = ["safe_get", "SafeHttpError", "RobotsBlocked", "is_private_host"]

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # loopback
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("10.0.0.0/8"),         # private
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),     # link-local
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("100.64.0.0/10"),      # CGN (S7)
    ipaddress.ip_network("fc00::/7"),           # unique-local (S7)
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::ffff:0:0/96"),      # IPv4-mapped
]


class SafeHttpError(Exception):
    """Raised when a request is blocked for safety reasons."""


class RobotsBlocked(SafeHttpError):
    """Raised when robots.txt disallows the path."""


def is_private_host(hostname: str) -> bool:
    """Return True if *hostname* resolves to a private/loopback/internal IP."""
    try:
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return True  # cannot resolve → treat as blocked
    for _family, _type, _proto, _canonname, sockaddr in infos:
        addr_str = sockaddr[0]
        try:
            addr = ipaddress.ip_address(addr_str)
        except ValueError:
            continue
        for net in _BLOCKED_NETWORKS:
            if addr in net:
                return True
    return False


def _check_port(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    port = parsed.port
    if port is None:
        return  # default (80 for http, 443 for https)
    if port not in (80, 443):
        raise SafeHttpError(f"Port {port} is not allowed (only 80/443): {url}")


def _check_scheme(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SafeHttpError(f"Scheme {parsed.scheme!r} is not allowed: {url}")


def _check_host(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if is_private_host(parsed.hostname or ""):
        raise SafeHttpError(f"Host resolves to a private/blocked address: {url}")


def safe_get(
    url: str,
    *,
    max_redirects: int = 5,
    timeout: int = 10,
    user_agent: str = "1145cx-scout/1.0 (+https://1145.ai)",
    check_robots: bool = True,
) -> str:
    """Fetch *url* safely, following up to *max_redirects* redirects.

    Each hop is checked against the blocked-address list.
    Returns the response body as a string.

    Raises:
        SafeHttpError: if any check fails.
        RobotsBlocked: if robots.txt disallows the path.
    """
    import urllib.request

    _check_scheme(url)
    _check_port(url)
    _check_host(url)

    if check_robots:
        _check_robots(url, user_agent=user_agent)

    redirects = 0
    current_url = url
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
            return None

    no_redirect_opener = urllib.request.build_opener(_NoRedirect())

    while redirects <= max_redirects:
        req = urllib.request.Request(current_url, headers={"User-Agent": user_agent})
        try:
            with no_redirect_opener.open(req, timeout=timeout) as resp:
                if resp.status in (301, 302, 303, 307, 308):
                    location = resp.getheader("Location", "")
                    if not location:
                        raise SafeHttpError("Redirect with no Location header")
                    next_url = urllib.parse.urljoin(current_url, location)
                    _check_scheme(next_url)
                    _check_port(next_url)
                    _check_host(next_url)
                    current_url = next_url
                    redirects += 1
                    continue
                return resp.read().decode("utf-8", errors="replace")
        except SafeHttpError:
            raise
        except Exception as exc:
            raise SafeHttpError(f"Request failed: {exc}") from exc

    raise SafeHttpError(f"Too many redirects (max {max_redirects}): {url}")


def _check_robots(url: str, *, user_agent: str) -> None:
    """Fetch and check robots.txt; a server error means do not crawl."""
    parsed = urllib.parse.urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser(robots_url)
    try:
        rp.read()
    except Exception:
        # Server error reading robots.txt → do not crawl (RS-2)
        raise RobotsBlocked(f"Cannot read robots.txt for {parsed.netloc} — blocked")
    if not rp.can_fetch(user_agent, url):
        raise RobotsBlocked(f"robots.txt disallows {url}")


class HostSet(NamedTuple):
    """Canonical set of hosts for a site (bare + www + redirect target)."""

    primary: str
    www: str | None
    redirect: str | None

    @classmethod
    def from_url(cls, url: str) -> "HostSet":
        host = urllib.parse.urlparse(url).hostname or ""
        www = f"www.{host}" if not host.startswith("www.") else None
        bare = host[4:] if host.startswith("www.") else None
        return cls(primary=host, www=www or bare, redirect=None)

    def contains(self, host: str) -> bool:
        return host in (self.primary, self.www, self.redirect)
