"""WS3 Phone verification — ID-1 through ID-5."""
from __future__ import annotations
import hashlib, hmac, os, secrets, time
from typing import Any


def verify_whatsapp(channel_address: str) -> bool:
    """ID-1: WhatsApp — possession verified by inbound message."""
    return True  # ingest already confirmed inbound from this number


def send_telegram_contact_request(chat_id: str) -> bool:
    """ID-1: Ask owner to share their number via Telegram button."""
    import json, urllib.request
    from cx_lib.secrets import get_secret
    env = os.environ.get("CX_ENV", "sandbox")
    token = get_secret(f"cx/{env}/telegram")["bot_token"]
    keyboard = {"keyboard": [[{"text": "Share my phone number", "request_contact": True}]],
                "one_time_keyboard": True, "resize_keyboard": True}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": "Please share your phone number to verify your identity.",
                          "reply_markup": keyboard}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status == 200


def check_telegram_contact(contact: dict, sender_user_id: int) -> bool:
    """ID-1: Telegram contact valid only if contact.user_id == sender.user_id."""
    return contact.get("user_id") == sender_user_id


def send_callback_code(phone: str, session_id: str, callback_table: Any) -> str:
    """ID-1 web/voice: generate 6-digit code, store with 5-min expiry, 3 attempts."""
    code = str(secrets.randbelow(1000000)).zfill(6)
    exp = int(time.time()) + 300  # 5 minutes
    callback_table.put_item(Item={
        "sessionId": session_id,
        "code": hashlib.sha256(code.encode()).hexdigest(),
        "attempts": 0,
        "expiresAt": exp,
        "expires_at": exp,
    })
    return code


def verify_callback_code(session_id: str, entered: str, callback_table: Any) -> bool:
    """Verify the 6-digit callback code."""
    resp = callback_table.get_item(Key={"sessionId": session_id})
    item = resp.get("Item")
    if not item:
        return False
    if int(item.get("expiresAt", 0)) < time.time():
        return False
    if int(item.get("attempts", 0)) >= 3:
        return False
    # Increment attempts
    callback_table.update_item(
        Key={"sessionId": session_id},
        UpdateExpression="SET attempts = attempts + :one",
        ExpressionAttributeValues={":one": 1},
    )
    expected = item.get("code", "")
    return hmac.compare_digest(expected, hashlib.sha256(entered.encode()).hexdigest())


def generate_signin_link(tenant_id: str, user_id: str, channel: str) -> str:
    """ID-5: Single-use 10-min sign-in link — never logs the full token."""
    from cx_lib.secrets import get_secret
    env = os.environ.get("CX_ENV", "sandbox")
    signing_key = get_secret(f"cx/{env}/signin")["link_signing_key"]
    token = secrets.token_urlsafe(32)
    exp = int(time.time()) + 600
    # Sign: hmac(key, token+tenant+user+exp)
    msg = f"{token}:{tenant_id}:{user_id}:{exp}"
    sig = hmac.new(signing_key.encode(), msg.encode(), hashlib.sha256).hexdigest()
    app_domain = os.environ.get("APP_DOMAIN", "app.1145.ai")
    return f"https://{app_domain}/signin?t={token}&sig={sig[:16]}&exp={exp}"
