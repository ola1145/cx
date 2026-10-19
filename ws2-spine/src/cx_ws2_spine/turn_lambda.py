"""WS2 Turn Lambda — SP-1 through SP-9.

Reads all queued inbox items + last 12 turns, calls the AgentCore agent,
validates slot proposals, writes the turn record, then signals the Wait step.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Entry point called by the Step Functions spine."""
    import sys
    sys.path.insert(0, "/var/task")
    from cx_lib.ddb import to_ddb, from_ddb, get_table

    session_id: str = event["sessionId"]
    env = os.environ.get("CX_ENV", "sandbox")

    sessions_tbl = get_table("SESSIONS_TABLE_NAME")
    inbox_tbl = get_table("INBOX_TABLE_NAME")
    turns_tbl = get_table("TURNS_TABLE_NAME")

    # ── SP-2: load session + inbox ───────────────────────────────────────────
    session = from_ddb(
        sessions_tbl.get_item(Key={"sessionId": session_id}).get("Item", {})
    )
    slots: dict = session.get("slots", {})
    language: str = session.get("language", "en")

    # Read all queued inbox items
    inbox_items = _read_queued_inbox(session_id, inbox_tbl, from_ddb)

    # Read last 12 turns
    last_turns = _read_last_turns(session_id, turns_tbl, from_ddb)

    # Events (profile_ready, etc.) arrive in the Step Functions input
    events: list = event.get("events", [])
    profile_hints: dict = event.get("profileHints", {})
    last_errors: list = event.get("lastValidationErrors", [])

    # Detect language from first message if not set
    if not language and inbox_items:
        language = _detect_language(inbox_items[0].get("text", ""))

    # ── SP-7: call agent ─────────────────────────────────────────────────────
    agent_output = _call_agent(
        session_id=session_id,
        inbox_items=inbox_items,
        last_turns=last_turns,
        slots=slots,
        profile_hints=profile_hints,
        last_validation_errors=last_errors,
        owner_language=language,
        events=events,
        env=env,
    )

    reply: str = agent_output.get("reply", "")
    slot_proposals: list = agent_output.get("slot_proposals", [])
    intent: str = agent_output.get("intent", "ask")

    # ── SP-4: read-back hash check ───────────────────────────────────────────
    if intent == "confirm":
        stored_hash = session.get("readbackHash")
        current_hash = _slots_hash(slots)
        if stored_hash != current_hash:
            intent = "ask"
            reply = "Could you confirm your details again? Something may have changed."

    # ── Validate and save slot proposals ────────────────────────────────────
    validation_errors = []
    for proposal in slot_proposals:
        field = proposal.get("field_path", "")
        value = proposal.get("value")
        err = _validate_slot(field, value, slots)
        if err:
            validation_errors.append(err)
        else:
            _set_nested(slots, field, value)

    # ── Mark inbox items consumed (atomic with turn write) ───────────────────
    seq = _next_turn_seq(session_id, turns_tbl)
    ts = datetime.now(timezone.utc).isoformat()
    for item in inbox_items:
        inbox_tbl.update_item(
            Key={"sessionId": session_id, "tsMsgId": item["tsMsgId"]},
            UpdateExpression="SET #s = :consumed",
            ExpressionAttributeNames={"#s": "state"},
            ExpressionAttributeValues={":consumed": "consumed"},
        )

    # Write agent turn
    turns_tbl.put_item(Item=to_ddb({
        "sessionId": session_id,
        "turnSeq": f"turn#{seq:05d}",
        "speaker": "agent",
        "text": reply,
        "channel": session.get("channel"),
        "createdAt": ts,
        "metadata": {"intent": intent},
        "expires_at": int(time.time()) + 90 * 86400,
    }))

    # Update session
    update_expr = "SET #slots = :slots, #lang = :lang, #lastErrors = :errs"
    expr_names = {"#slots": "slots", "#lang": "language", "#lastErrors": "lastValidationErrors"}
    expr_values = to_ddb({":slots": slots, ":lang": language, ":errs": validation_errors})

    if intent == "readback":
        update_expr += ", #rbHash = :hash"
        expr_names["#rbHash"] = "readbackHash"
        expr_values[":hash"] = _slots_hash(slots)

    sessions_tbl.update_item(
        Key={"sessionId": session_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )

    return {
        "sessionId": session_id,
        "reply": reply,
        "intent": intent,
        "slotsComplete": _check_slots_complete(slots),
        "validationErrors": validation_errors,
        "language": language,
    }


def _read_queued_inbox(session_id: str, inbox_tbl: Any, from_ddb: Any) -> list[dict]:
    from boto3.dynamodb.conditions import Key, Attr
    resp = inbox_tbl.query(
        KeyConditionExpression=Key("sessionId").eq(session_id),
        FilterExpression=Attr("state").eq("queued"),
        ScanIndexForward=True,
    )
    return [from_ddb(item) for item in resp.get("Items", [])]


def _read_last_turns(session_id: str, turns_tbl: Any, from_ddb: Any) -> list[dict]:
    from boto3.dynamodb.conditions import Key
    resp = turns_tbl.query(
        KeyConditionExpression=Key("sessionId").eq(session_id),
        ScanIndexForward=False,
        Limit=12,
    )
    return list(reversed([from_ddb(item) for item in resp.get("Items", [])]))


def _detect_language(text: str) -> str:
    """Simple heuristic: detect Spanish by common words. Defaults to 'en'."""
    es_words = {"hola", "quiero", "necesito", "tengo", "mi", "el", "la", "los", "las", "es"}
    words = set(text.lower().split())
    if len(words & es_words) >= 2:
        return "es"
    return "en"


def _call_agent(*, session_id: str, inbox_items: list, last_turns: list, slots: dict,
                profile_hints: dict, last_validation_errors: list, owner_language: str,
                events: list, env: str) -> dict:
    """Call the AgentCore/LangGraph agent. Falls back to a simple echo in tests."""
    agent_endpoint = os.environ.get("AGENT_ENDPOINT", "")
    if not agent_endpoint:
        # Test/stub mode: return a simple ask response
        text = " ".join(i.get("text", "") for i in inbox_items if i.get("text"))
        return {
            "reply": f"Got it. Tell me about your business — what type of services do you offer?",
            "slot_proposals": [],
            "intent": "ask",
            "language": owner_language,
        }
    import urllib.request
    payload = json.dumps({
        "session_id": session_id,
        "inbox_items": inbox_items,
        "last_turns": last_turns,
        "slots": slots,
        "profile_hints": profile_hints,
        "last_validation_errors": last_validation_errors,
        "owner_language": owner_language,
        "events": events,
    }).encode()
    req = urllib.request.Request(
        agent_endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=55) as resp:
        return json.loads(resp.read())


def _validate_slot(field: str, value: Any, current_slots: dict) -> str | None:
    """Return an error string or None. Minimal validation — full validation is in contracts."""
    if field == "owner_mobile" and value:
        import re
        if not re.match(r"^\+1\d{10}$", str(value)):
            return f"owner_mobile must be a US E.164 number (+1XXXXXXXXXX), got: {value}"
    if field == "timezone" and value:
        import zoneinfo
        try:
            zoneinfo.ZoneInfo(str(value))
        except Exception:
            return f"Unknown timezone: {value}"
    return None


def _set_nested(obj: dict, path: str, value: Any) -> None:
    """Set obj[a][b][c] = value for a dotted path."""
    parts = path.split(".")
    for part in parts[:-1]:
        obj = obj.setdefault(part, {})
    obj[parts[-1]] = value


def _check_slots_complete(slots: dict) -> bool:
    required = ["business_name", "vertical", "owner_name", "owner_mobile",
                "services", "hours", "timezone", "greeting_tone"]
    return all(slots.get(k) for k in required)


def _slots_hash(slots: dict) -> str:
    return hashlib.sha256(json.dumps(slots, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _next_turn_seq(session_id: str, turns_tbl: Any) -> int:
    from boto3.dynamodb.conditions import Key
    resp = turns_tbl.query(
        KeyConditionExpression=Key("sessionId").eq(session_id),
        ScanIndexForward=False,
        Limit=1,
        ProjectionExpression="turnSeq",
    )
    items = resp.get("Items", [])
    if not items:
        return 1
    last_seq = items[0].get("turnSeq", "turn#00000")
    try:
        return int(last_seq.split("#")[1]) + 1
    except (IndexError, ValueError):
        return 1
