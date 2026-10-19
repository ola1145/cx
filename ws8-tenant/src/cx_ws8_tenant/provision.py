"""WS8 Provision Lambda -- idempotent tenant provisioning.

Triggered by Step Functions after confirmed slots + billing card on file.
Builds the full TenantConfig, writes Tenants table, seeds dashboard,
sends go-live message via C11 delivery Lambda.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import boto3
from botocore.exceptions import ClientError

from cx_contracts.c03_slots import OnboardingSlots, Service
from cx_contracts.c10_tenant_config import (
    TenantConfig, BusinessHours, DayHours, ServiceEntry, EscalationConfig,
)
from cx_contracts.c11_delivery import DeliveryRequest
from cx_contracts.c13_ops_events import OpsEvent, OpsEventKind
from cx_lib.ddb import DDB
from cx_lib.logging import get_logger

log = get_logger("ws8.provision")

TENANTS_TABLE = os.environ["TENANTS_TABLE"]
SESSIONS_TABLE = os.environ["SESSIONS_TABLE"]
OPS_BUS = os.environ.get("OPS_BUS", "1145cx-ops")
DELIVERY_FUNCTION = os.environ.get("DELIVERY_FUNCTION", "")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://dashboard.1145.ai")

_ddb = DDB()
_dynamodb = boto3.resource("dynamodb")
_lambda_client = boto3.client("lambda")
_events = boto3.client("events")


def handler(event: dict, context: Any) -> dict:
    """
    Input: session_id, slots (C3 dict), identity_key, billing_status
    Output: tenant_id, config_version, status
    """
    session_id: str = event["session_id"]
    raw_slots: dict = event["slots"]
    identity_key: str = event["identity_key"]
    billing_status: str = event.get("billing_status", "trialing")

    log.info("provision.start", session_id=session_id)

    existing = _get_existing_tenant(session_id)
    if existing:
        log.info("provision.idempotent", tenant_id=existing["tenant_id"])
        return {
            "tenant_id": existing["tenant_id"],
            "config_version": existing.get("config_version", 1),
            "status": existing.get("status", "day_one"),
        }

    slots = OnboardingSlots.model_validate(raw_slots)
    tenant_id = str(uuid.uuid4())
    now = int(time.time())
    config = _build_config(tenant_id, slots)

    tenants_table = _dynamodb.Table(TENANTS_TABLE)
    sessions_table = _dynamodb.Table(SESSIONS_TABLE)

    item = {
        "tenant_id": tenant_id,
        "session_id": session_id,
        "identity_key": identity_key,
        "billing_status": billing_status,
        "status": "day_one",
        "config_version": 1,
        "config": _ddb.to_item(config.model_dump()),
        "created_at": now,
        "updated_at": now,
        "plan": "trial",
    }

    try:
        tenants_table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(tenant_id)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {"tenant_id": tenant_id, "config_version": 1, "status": "day_one"}
        raise

    sessions_table.update_item(
        Key={"session_id": session_id},
        UpdateExpression="SET tenant_id = :tid, #st = :st, updated_at = :now",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":tid": tenant_id, ":st": "provisioned", ":now": now},
    )

    _emit_ops_event(OpsEventKind.session_live, tenant_id, session_id)
    _send_welcome(tenant_id, identity_key, slots)

    log.info("provision.complete", tenant_id=tenant_id)
    return {"tenant_id": tenant_id, "config_version": 1, "status": "day_one"}


def _get_existing_tenant(session_id: str) -> dict | None:
    sessions_table = _dynamodb.Table(SESSIONS_TABLE)
    resp = sessions_table.get_item(Key={"session_id": session_id})
    item = resp.get("Item")
    if item and "tenant_id" in item:
        tenants_table = _dynamodb.Table(TENANTS_TABLE)
        t = tenants_table.get_item(Key={"tenant_id": item["tenant_id"]}).get("Item")
        return _ddb.from_item(t) if t else None
    return None


def _build_config(tenant_id: str, slots: OnboardingSlots) -> TenantConfig:
    services = [
        ServiceEntry(
            name=s.name,
            description=s.description or "",
            price_type=s.price_type.value,
            price_min=float(s.price_min) if s.price_min is not None else None,
            price_max=float(s.price_max) if s.price_max is not None else None,
            duration_minutes=s.duration_minutes,
            deposit_required=bool(s.deposit),
        )
        for s in (slots.services or [])
    ]

    # Convert ServiceHours to DayHours dict
    hours: dict[str, DayHours] = {}
    sh = slots.hours
    day_map = {
        "mon": "monday", "tue": "tuesday", "wed": "wednesday",
        "thu": "thursday", "fri": "friday", "sat": "saturday", "sun": "sunday",
    }
    for short, long in day_map.items():
        intervals = getattr(sh, long, []) if sh else []
        if intervals:
            first = intervals[0]
            hours[short] = DayHours(open=first[0], close=first[1], closed=False)
        else:
            hours[short] = DayHours(closed=True)

    escalation = EscalationConfig(
        phone=slots.escalation_number or "",
    )
    biz_name = slots.business_name or "Your Business"

    return TenantConfig(
        tenant_id=tenant_id,
        business_name=biz_name,
        business_address=slots.address.model_dump() if slots.address else {},
        timezone=slots.timezone or "America/New_York",
        languages=slots.languages or ["en"],
        tone=slots.greeting_tone or "professional",
        greeting=_default_greeting(biz_name),
        services=services,
        hours=BusinessHours(days=hours),
        escalation=escalation,
        version=1,
    )


def _default_greeting(biz_name: str) -> str:
    return (
        f"Hi, thanks for calling {biz_name}. This is an AI assistant. "
        "Your call may be recorded for quality purposes. How can I help you today?"
    )


def _emit_ops_event(kind: OpsEventKind, tenant_id: str, session_id: str) -> None:
    try:
        ev = OpsEvent(kind=kind, tenant_id=tenant_id, session_id=session_id)
        _events.put_events(Entries=[{
            "Source": "1145cx.ws8",
            "DetailType": kind.value,
            "Detail": json.dumps(ev.model_dump(mode="json")),
            "EventBusName": OPS_BUS,
        }])
    except Exception as exc:  # noqa: BLE001
        log.warning("ops_event.failed", error=str(exc))


def _send_welcome(tenant_id: str, identity_key: str, slots: OnboardingSlots) -> None:
    if not DELIVERY_FUNCTION:
        return
    try:
        sign_in_link = f"{DASHBOARD_URL}/auth/magic?tenant={tenant_id}"
        biz = slots.business_name or "your business"
        text = (
            f"🎉 Your 1145 AI account is ready!\n\n"
            f"Business: {biz}\n"
            f"Sign in to your dashboard: {sign_in_link}\n\n"
            "We'll send your business phone number as soon as it's assigned."
        )
        _lambda_client.invoke(
            FunctionName=DELIVERY_FUNCTION,
            InvocationType="Event",
            Payload=json.dumps({
                "tenant_id": tenant_id,
                "identity_key": identity_key,
                "text": text,
            }).encode(),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("welcome_message.failed", error=str(exc))
