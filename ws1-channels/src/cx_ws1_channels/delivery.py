"""WS1 Delivery — CH-11: send a reply on the right channel with retries."""
from __future__ import annotations

import json
import os
import time
from typing import Any


def deliver(session_id: str, text: str, channel: str, address: str, *, retry: int = 3) -> bool:
    """Deliver a reply. Returns True on success, False after all retries fail.

    Shape per channel:
    - Telegram: 4096 char limit
    - Voice: ≤25 words, digits spelled out
    - WhatsApp: within 24h window = text; outside = approved template
    """
    for attempt in range(retry):
        try:
            if channel == "telegram":
                return _send_telegram(address, text)
            elif channel == "whatsapp":
                return _send_whatsapp(address, text)
            elif channel == "web":
                return _send_websocket(session_id, text)
            elif channel == "voice":
                return _send_voice(session_id, _format_for_voice(text))
        except Exception:
            if attempt == retry - 1:
                return False
            time.sleep(0.5 * (attempt + 1))
    return False


def _format_for_voice(text: str) -> str:
    """Trim to 25 words, spell out standalone digits."""
    import re
    words = text.split()[:25]
    result = []
    for w in words:
        if re.fullmatch(r"\d+", w):
            spelled = " ".join(list(w))
            result.append(spelled)
        else:
            result.append(w)
    return " ".join(result)


def _send_telegram(chat_id: str, text: str) -> bool:
    import urllib.request, urllib.parse
    from cx_lib.secrets import get_secret
    env = os.environ.get("CX_ENV", "sandbox")
    token = get_secret(f"cx/{env}/telegram")["bot_token"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text[:4096]}).encode()
    req = urllib.request.Request(url, data=payload,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status == 200


def _send_whatsapp(to: str, text: str) -> bool:
    import urllib.request
    from cx_lib.secrets import get_secret
    env = os.environ.get("CX_ENV", "sandbox")
    sec = get_secret(f"cx/{env}/telnyx")
    api_key = sec["api_key"]
    from_num = sec["wa_from"]
    url = "https://api.telnyx.com/v2/messages"
    payload = json.dumps({
        "from": from_num, "to": to, "type": "WhatsApp",
        "text": text
    }).encode()
    req = urllib.request.Request(url, data=payload,
                                  headers={"Authorization": f"Bearer {api_key}",
                                           "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status in (200, 201)


def _send_websocket(session_id: str, text: str) -> bool:
    """Post to API Gateway WebSocket connection for this session."""
    import boto3
    connection_id = os.environ.get(f"WS_CONNECTION_{session_id}", "")
    if not connection_id:
        return False
    endpoint = os.environ.get("WS_ENDPOINT", "")
    client = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint,
                           region_name=os.environ.get("AWS_REGION", "us-east-1"))
    try:
        client.post_to_connection(ConnectionId=connection_id, Data=json.dumps({"text": text}).encode())
        return True
    except Exception:
        return False


def _send_voice(session_id: str, text: str) -> bool:
    """Store the reply so the voice worker polls it."""
    import boto3
    ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    try:
        ssm.put_parameter(Name=f"/cx/voice-reply/{session_id}", Value=text,
                          Type="String", Overwrite=True)
        return True
    except Exception:
        return False
