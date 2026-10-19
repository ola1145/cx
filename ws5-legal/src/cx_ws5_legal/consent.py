"""WS5 Consent ledger — LG-1 through LG-7."""
from __future__ import annotations
import hashlib, time
from datetime import datetime, timezone
from typing import Any

CONSENT_KEYWORDS = {
    "terms": {"AGREE", "I AGREE"},
    "privacy": {"AGREE", "I AGREE"},
    "research": {"YES"},
    "calls_and_alerts": {"YES"},
    "marketing": {"YES"},
}

STOP_KEYWORDS = {"STOP", "STOP ALERTS", "UNSUBSCRIBE", "OPT OUT"}


def record_consent(subject_id: str, consent_type: str, version: str,
                   document_hash: str, prompt_shown: str, reply: str,
                   channel: str, msg_id: str, consents_tbl: Any,
                   ip: str | None = None, ua: str | None = None) -> bool:
    """LG-2: Record consent only for exact keyword or button reply. Never from model output."""
    allowed = CONSENT_KEYWORDS.get(consent_type, set())
    normalized = reply.strip().upper()
    if normalized not in allowed:
        return False  # not a valid consent signal (S9)

    ts = datetime.now(timezone.utc).isoformat()
    sort_key = f"{consent_type}#{ts}"
    item = {
        "subjectId": subject_id,
        "typeTs": sort_key,
        "consentType": consent_type,
        "version": version,
        "contentHash": document_hash,
        "promptShown": prompt_shown,
        "reply": reply,
        "channel": channel,
        "msgId": msg_id,
        "recordedAt": ts,
    }
    if ip:
        item["ipAddress"] = ip
    if ua:
        item["userAgent"] = ua
    consents_tbl.put_item(Item=item)
    return True


def check_consent(subject_id: str, consent_type: str, consents_tbl: Any) -> bool:
    """LG-2: Check if active (not withdrawn) consent exists."""
    from boto3.dynamodb.conditions import Key, Attr
    resp = consents_tbl.query(
        KeyConditionExpression=Key("subjectId").eq(subject_id) & Key("typeTs").begins_with(consent_type),
        FilterExpression=Attr("withdrawnAt").not_exists(),
        ScanIndexForward=False,
        Limit=1,
    )
    return len(resp.get("Items", [])) > 0


def record_withdrawal(subject_id: str, consent_type: str, consents_tbl: Any) -> None:
    """LG-4: Record opt-out / STOP."""
    from boto3.dynamodb.conditions import Key, Attr
    ts = datetime.now(timezone.utc).isoformat()
    # Find the active record and mark withdrawn
    resp = consents_tbl.query(
        KeyConditionExpression=Key("subjectId").eq(subject_id) & Key("typeTs").begins_with(consent_type),
        FilterExpression=Attr("withdrawnAt").not_exists(),
        Limit=1,
    )
    for item in resp.get("Items", []):
        consents_tbl.update_item(
            Key={"subjectId": item["subjectId"], "typeTs": item["typeTs"]},
            UpdateExpression="SET withdrawnAt = :ts",
            ExpressionAttributeValues={":ts": ts},
        )


def is_stop_signal(text: str) -> bool:
    """Detect opt-out signals (LG-4)."""
    return text.strip().upper() in STOP_KEYWORDS


def validate_greeting(greeting: str) -> list[str]:
    """LG-5: Refuse a greeting without AI disclosure and recording notice."""
    errors = []
    if "ai assistant" not in greeting.lower() and "artificial intelligence" not in greeting.lower():
        errors.append("Greeting must include AI disclosure (e.g. 'AI assistant')")
    return errors
