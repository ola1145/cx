"""WS6 Site scout — RS-2, RS-3: safe-fetch up to 12 pages, parse schema.org JSON-LD."""
from __future__ import annotations
import json
import re
import urllib.parse
from typing import Any


def scout_site(url: str, max_pages: int = 12) -> dict[str, Any]:
    """Fetch up to max_pages from a site and extract structured facts (RS-3)."""
    from cx_lib.safe_http import safe_get, SafeHttpError, HostSet

    host_set = HostSet.from_url(url)
    visited: set[str] = set()
    queue = [url]
    facts: list[dict] = []
    pages_fetched = 0

    while queue and pages_fetched < max_pages:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        try:
            html = safe_get(current)
        except SafeHttpError:
            continue
        pages_fetched += 1
        page_facts = _extract_schema_org(html, current)
        facts.extend(page_facts)
        for link in _extract_links(html, current):
            parsed = urllib.parse.urlparse(link)
            if host_set.contains(parsed.hostname or "") and link not in visited:
                queue.append(link)

    return {"url": url, "pages_fetched": pages_fetched, "facts": facts}


def _extract_schema_org(html: str, source_url: str) -> list[dict]:
    """Parse schema.org JSON-LD blocks deterministically — no model call (D3)."""
    facts = []
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(m.group(1))
            items = data if isinstance(data, list) else [data]
            for item in items:
                facts.extend(_parse_schema_item(item, source_url))
        except Exception:
            continue
    return facts


def _parse_schema_item(item: dict, source_url: str) -> list[dict]:
    def f(field: str, value: Any, quote: str) -> dict:
        return {"field_path": field, "value": value, "confidence": 0.9,
                "quote": quote, "source_url": source_url, "source_type": "schema_org"}

    facts = []
    if "name" in item:
        facts.append(f("business_name", item["name"], f"name: {item['name']}"))
    if "telephone" in item:
        facts.append(f("owner_mobile", item["telephone"], f"telephone: {item['telephone']}"))
    if "address" in item and isinstance(item["address"], dict):
        city = item["address"].get("addressLocality", "")
        if city:
            facts.append(f("address.city", city, f"addressLocality: {city}"))
    if "openingHours" in item or "openingHoursSpecification" in item:
        hours = item.get("openingHours") or item.get("openingHoursSpecification", [])
        facts.append(f("hours", hours, f"openingHours: {hours}"))
    if "priceRange" in item:
        facts.append(f("price_range", item["priceRange"], f"priceRange: {item['priceRange']}"))
    return facts


def _extract_links(html: str, base_url: str) -> list[str]:
    links = []
    for m in re.finditer(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE):
        href = m.group(1)
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        full = urllib.parse.urljoin(base_url, href)
        if full.startswith("http"):
            links.append(full)
    return links[:50]
