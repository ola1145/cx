"""WS1 Ingest Lambda — CH-1 through CH-7.

Receives webhooks from Telegram, Telnyx/WhatsApp and the voice worker.
1. Verifies the webhook signature (CH-1)
2. De-duplicates via idempotency table (CH-2)
3. Normalises to InboundEvent / C1 (CH-3)
4. Rate-limits per identity (CH-4)
5. Cleans text: escapes [system] prefix, redacts card numbers (CH-5)
6. Resolves or creates the session / identity (CH-6)
7. Writes to the inbox; conditionally resumes the spine (CH-7)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

# ── Lazy imports (resolved at cold-start) ───────────────────────────────────
def _ddb():
    import sys
    sys.path.insert(0, "/var/task")
    from cx_lib.ddb import to_ddb, from_ddb, get_table
    return to_ddb, from_ddb, get_table

# ── Constants ────────────────────────────────────────────────────────────────
RATE_LIMIT_PER_MIN = int(os.environ.get("RATE_LIMIT_PER_MIN", "20"))
MAX_TURNS = int(os.environ.get("MAX_TURNS_PER_SESSION", "300"))
# Luhn check regex for card number redaction (CH-5)
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")

# ── Webhook verification helpers ─────────────────────────────────────────────

def _verify_telegram(headers: dict, body: bytes) -> bool:
    """CH-1: Telegram — compare X-Telegram-Bot-Api-Secret-Token in constant time."""
    from cx_lib.secrets import get_secret
    env = os.environ.get("CX_ENV", "sandbox")
    try:
        secret = get_secret(f"cx/{env}/telegram")["webhook_secret"]
    except Exception:
        return False
    incoming = headers.get("x-telegram-bot-api-secret-token", "")
    return hmac.compare_digest(incoming, secret)


def _verify_telnyx(headers: dict, body: bytes) -> bool:
    """CH-1: Telnyx — ed25519 signature with 5-minute timestamp window."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.exceptions import InvalidSignature
        import base64
        from cx_lib.secrets import get_secret
        env = os.environ.get("CX_ENV", "sandbox")
        pub_key_pem = get_secret(f"cx/{env}/telnyx")["public_key"]
        ts_str = headers.get("telnyx-timestamp", "")
        sig_b64 = headers.get("telnyx-signature-ed25519-v1", "")
        if not ts_str or not sig_b64:
            return False
        # 5-minute window
        if abs(time.time() - int(ts_str)) > 300:
            return False
        signed_payload = ts_str.encode() + b"|" + body
        pub_key = load_pem_public_key(pub_key_pem.encode())
        assert isinstance(pub_key, Ed25519PublicKey)
        pub_key.verify(base64.b64decode(sig_b64), signed_payload)
        return True
    except (InvalidSignature, Exception):
        return False


def _verify_voice(headers: dict, body: bytes) -> bool:
    """CH-1: Voice worker — HMAC-SHA256 with timestamp in header."""
    try:
        from cx_lib.secrets import get_secret
        env = os.environ.get("CX_ENV", "sandbox")
        secret = get_secret(f"cx/{env}/voice-worker")["hmac_secret"]
        ts_str = headers.get("x-cx-timestamp", "")
        sig = headers.get("x-cx-signature", "")
        if not ts_str or not sig:
            return False
        if abs(time.time() - int(ts_str)) > 300:
            return False
        expected = hmac.new(secret.encode(), ts_str.encode() + b"|" + body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


# ── Card number redaction ─────────────────────────────────────────────────────

def _luhn(digits: str) -> bool:
    """Return True if digits pass the Luhn check."""
    total = 0
    rev = digits[::-1]
    for i, d in enumerate(rev):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def redact_card_numbers(text: str) -> str:
    """CH-5: Replace card-number patterns that pass Luhn with [REDACTED]."""
    def replace(m: re.Match) -> str:
        digits = re.sub(r"[ -]", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            return "[REDACTED]"
        return m.group()
    return _CARD_RE.sub(replace, text)


# ── Main handler ──────────────────────────────────────────────────────────────

def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for all inbound webhook paths."""
    to_ddb, from_ddb, get_table = _ddb()
    env = os.environ.get("CX_ENV", "sandbox")

    path = event.get("rawPath") or event.get("path", "/unknown")
    body_raw: bytes = (event.get("body") or "").encode()
    if event.get("isBase64Encoded"):
        import base64
        body_raw = base64.b64decode(event.get("body", ""))
    headers: dict = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    body: dict = json.loads(body_raw) if body_raw else {}

    # ── CH-1: verify ────────────────────────────────────────────────────────
    if "/telegram" in path:
        channel = "telegram"
        if not _verify_telegram(headers, body_raw):
            return {"statusCode": 401, "body": "Unauthorized"}
    elif "/voice" in path:
        channel = "voice"
        if not _verify_voice(headers, body_raw):
            return {"statusCode": 401, "body": "Unauthorized"}
    else:
        channel = "whatsapp"
        if not _verify_telnyx(headers, body_raw):
            return {"statusCode": 401, "body": "Unauthorized"}

    # ── Normalise to (address, text, msg_id, kind) ───────────────────────────
    address, text, msg_id, kind, media_url = _normalise(channel, body)
    if not msg_id:
        return {"statusCode": 200, "body": "ignored"}

    # ── CH-3: Telegram private-chat only; skip edited messages ───────────────
    if channel == "telegram":
        if "edited_message" in body:
            return {"statusCode": 200, "body": "ignored"}
        chat_type = (body.get("message") or {}).get("chat", {}).get("type", "")
        if chat_type != "private":
            return {"statusCode": 200, "body": "ignored"}

    # ── CH-5: clean text ─────────────────────────────────────────────────────
    if text:
        if text.startswith("[system]"):
            text = "\\[system]" + text[8:]
        text = redact_card_numbers(text)

    # ── CH-2: idempotency ────────────────────────────────────────────────────
    idempotency_tbl = get_table("IDEMPOTENCY_TABLE_NAME")
    idempotency_key = f"{channel}#{msg_id}"
    try:
        idempotency_tbl.put_item(
            Item=to_ddb({
                "providerMsgId": idempotency_key,
                "state": "received",
                "firstSeen": int(time.time()),
                "expires_at": int(time.time()) + 86400,
            }),
            ConditionExpression="attribute_not_exists(providerMsgId) OR #s = :received",
            ExpressionAttributeNames={"#s": "state"},
            ExpressionAttributeValues={":received": "received"},
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {"statusCode": 200, "body": "duplicate"}
        raise

    try:
        # ── CH-6: resolve identity + session ─────────────────────────────────
        identities_tbl = get_table("IDENTITIES_TABLE_NAME")
        sessions_tbl = get_table("SESSIONS_TABLE_NAME")
        channel_address = f"{channel}:{address}"
        session_id = _resolve_session(channel_address, channel, address, identities_tbl, sessions_tbl, to_ddb, from_ddb)

        # ── CH-4: rate limit ─────────────────────────────────────────────────
        if not _check_rate_limit(session_id, get_table("COUNTERS_TABLE_NAME"), to_ddb):
            return {"statusCode": 429, "body": "Rate limit exceeded"}

        # ── CH-7: write inbox ────────────────────────────────────────────────
        inbox_tbl = get_table("INBOX_TABLE_NAME")
        ts = datetime.now(timezone.utc).isoformat()
        inbox_item = {
            "sessionId": session_id,
            "tsMsgId": f"{ts}#{msg_id}",
            "channel": channel,
            "kind": kind,
            "text": text,
            "mediaKey": media_url,
            "state": "queued",
            "receivedAt": ts,
            "source": "owner",
            "expires_at": int(time.time()) + 7 * 86400,
        }
        inbox_tbl.put_item(Item=to_ddb(inbox_item))

        # Mark idempotency record done
        idempotency_tbl.update_item(
            Key={"providerMsgId": idempotency_key},
            UpdateExpression="SET #s = :done",
            ExpressionAttributeNames={"#s": "state"},
            ExpressionAttributeValues={":done": "done"},
        )

        # ── Conditionally resume spine (CH-7) ─────────────────────────────
        _maybe_resume_spine(session_id, sessions_tbl, from_ddb)

        return {"statusCode": 200, "body": "ok"}
    except Exception:
        # Leave idempotency record as 'received' so provider retries (B7)
        raise


def _normalise(channel: str, body: dict) -> tuple[str, str | None, str | None, str, str | None]:
    """Return (address, text, msg_id, kind, media_url)."""
    if channel == "telegram":
        msg = body.get("message") or {}
        address = str(msg.get("from", {}).get("id", ""))
        msg_id = str(msg.get("message_id", ""))
        text = msg.get("text")
        photo = msg.get("photo")
        voice = msg.get("voice") or msg.get("audio")
        if photo:
            return address, None, msg_id, "image", None
        if voice:
            return address, None, msg_id, "audio", None
        if not text:
            return address, None, msg_id, "other", None
        return address, text, msg_id, "text", None
    elif channel == "whatsapp":
        data = body.get("data", {}).get("payload", {})
        address = data.get("from", "")
        msg_id = data.get("id", "")
        kind = data.get("type", "text")
        text = data.get("payload", {}).get("payload", {}).get("text") if kind == "text" else None
        return address, text, msg_id, kind, None
    else:  # voice
        address = body.get("caller_id", "")
        msg_id = body.get("turn_id", "")
        text = body.get("transcript")
        return address, text, msg_id, "text", None


def _resolve_session(channel_address: str, channel: str, address: str,
                     identities_tbl: Any, sessions_tbl: Any,
                     to_ddb: Any, from_ddb: Any) -> str:
    """CH-6: Resolve or create session. Conditional write prevents duplicate sessions."""
    import uuid
    resp = identities_tbl.get_item(Key={"channelAddress": channel_address})
    identity = from_ddb(resp.get("Item")) if resp.get("Item") else None
    if identity and identity.get("sessionId"):
        return identity["sessionId"]
    session_id = f"sess_{uuid.uuid4().hex[:16]}"
    try:
        identities_tbl.put_item(
            Item=to_ddb({
                "channelAddress": channel_address,
                "sessionId": session_id,
                "channel": channel,
                "address": address,
                "verified": False,
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "expires_at": int(time.time()) + 30 * 86400,
            }),
            ConditionExpression="attribute_not_exists(channelAddress)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            resp2 = identities_tbl.get_item(Key={"channelAddress": channel_address})
            return from_ddb(resp2["Item"])["sessionId"]
        raise
    sessions_tbl.put_item(Item=to_ddb({
        "sessionId": session_id,
        "status": "new",
        "channel": channel,
        "channelAddress": channel_address,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "slots": {},
    }))
    return session_id


def _check_rate_limit(session_id: str, counters_tbl: Any, to_ddb: Any) -> bool:
    """CH-4: Token-bucket rate limit. Returns False if limit exceeded."""
    window = int(time.time() // 60)
    key = f"rate#{session_id}#{window}"
    try:
        resp = counters_tbl.update_item(
            Key={"kindScopeWindow": key},
            UpdateExpression="ADD #c :one SET expires_at = :exp",
            ExpressionAttributeNames={"#c": "count"},
            ExpressionAttributeValues=to_ddb({":one": 1, ":exp": int(time.time()) + 120}),
            ReturnValues="UPDATED_NEW",
        )
        count = int(resp["Attributes"]["count"])
        return count <= RATE_LIMIT_PER_MIN
    except Exception:
        return True  # allow on error


def _maybe_resume_spine(session_id: str, sessions_tbl: Any, from_ddb: Any) -> None:
    """CH-7: If a task token is waiting, claim it and send it to Step Functions."""
    resp = sessions_tbl.get_item(Key={"sessionId": session_id})
    session = from_ddb(resp.get("Item") or {})
    task_token = session.get("taskToken")
    if not task_token:
        return
    sfn = boto3.client("stepfunctions", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    try:
        sfn.send_task_success(taskToken=task_token, output=json.dumps({"resumed": True}))
        # Clear the token so the next message doesn't double-resume
        sessions_tbl.update_item(
            Key={"sessionId": session_id},
            UpdateExpression="REMOVE taskToken",
        )
    except sfn.exceptions.TaskTimedOut:
        pass
    except Exception:
        pass
