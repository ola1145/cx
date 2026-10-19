"""WS9 Data Layer -- DynamoDB table management Lambda.

Handles:
- Schema migrations / table bootstrapping
- Reconciliation sweeper (run every 15 min via EventBridge)
- Number hold expiry (release stale holds)
- Tenant number release after grace period
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from cx_lib.ddb import DDB
from cx_lib.logging import get_logger

log = get_logger("ws9.data")

# ── env ──────────────────────────────────────────────────────────────────────
SESSIONS_TABLE = os.environ.get("SESSIONS_TABLE", "cx-sessions")
TENANTS_TABLE = os.environ.get("TENANTS_TABLE", "cx-tenants")
NUMBER_ORDERS_TABLE = os.environ.get("NUMBER_ORDERS_TABLE", "cx-number-orders")
ROUTING_TABLE = os.environ.get("ROUTING_TABLE", "cx-routing")
COUNTERS_TABLE = os.environ.get("COUNTERS_TABLE", "cx-counters")
OPS_BUS = os.environ.get("OPS_BUS", "1145cx-ops")

_ddb = DDB()
_dynamodb = boto3.resource("dynamodb")
_events = boto3.client("events")


def handler(event: dict, context: Any) -> dict:
    """Dispatch on event source."""
    source = event.get("source", "")
    detail_type = event.get("detail-type", "")

    if source == "aws.events" or detail_type == "Scheduled Event":
        return _run_reconciliation()
    elif event.get("action") == "migrate":
        return _run_migrations()
    elif event.get("action") == "counter_increment":
        return _counter_increment(
            event["counter_id"],
            event.get("delta", 1),
        )
    elif event.get("action") == "counter_get":
        return _counter_get(event["counter_id"])
    else:
        log.warning("unknown_event", event=event)
        return {"status": "noop"}


# ── reconciliation ────────────────────────────────────────────────────────────
def _run_reconciliation() -> dict:
    """Run every 15 min via EventBridge.
    - Finish pending number orders (delegate to WS7 via event)
    - Release expired number holds
    - Release numbers of lapsed/cancelled tenants after grace period
    - Expire stuck sessions (30-min silence → parked, 24h → failed)
    """
    now = int(time.time())
    results = {
        "expired_holds": 0,
        "released_numbers": 0,
        "timed_out_sessions": 0,
    }

    # ── expire number holds older than 10 min ──
    orders_table = _dynamodb.Table(NUMBER_ORDERS_TABLE)
    try:
        resp = orders_table.scan(
            FilterExpression=Attr("status").eq("held") & Attr("hold_expires_at").lt(now),
            ProjectionExpression="order_id, tenant_id, #n",
            ExpressionAttributeNames={"#n": "number"},
        )
        for item in resp.get("Items", []):
            _release_hold(orders_table, item, now)
            results["expired_holds"] += 1
    except Exception as exc:  # noqa: BLE001
        log.error("reconcile.holds.error", error=str(exc))

    # ── release numbers for lapsed tenants past grace period ──
    tenants_table = _dynamodb.Table(TENANTS_TABLE)
    grace_cutoff = now - (14 * 86400)  # 14-day grace period
    try:
        resp = tenants_table.scan(
            FilterExpression=(
                Attr("billing_status").is_in(["lapsed", "cancelled"])
                & Attr("lapsed_at").lt(grace_cutoff)
                & Attr("number_released").not_exists()
            ),
            ProjectionExpression="tenant_id, e164",
        )
        for item in resp.get("Items", []):
            _release_tenant_number(tenants_table, item, now)
            results["released_numbers"] += 1
    except Exception as exc:  # noqa: BLE001
        log.error("reconcile.numbers.error", error=str(exc))

    # ── time out stuck sessions ──
    sessions_table = _dynamodb.Table(SESSIONS_TABLE)
    park_cutoff = now - (30 * 60)   # 30 min → parked
    fail_cutoff = now - (24 * 3600)  # 24h → failed
    try:
        resp = sessions_table.scan(
            FilterExpression=(
                Attr("status").is_in(["collecting", "reviewing"])
                & Attr("last_activity_at").lt(park_cutoff)
            ),
            ProjectionExpression="session_id, #st, last_activity_at",
            ExpressionAttributeNames={"#st": "status"},
        )
        for item in resp.get("Items", []):
            last = int(item.get("last_activity_at", 0))
            new_status = "failed" if last < fail_cutoff else "parked"
            try:
                sessions_table.update_item(
                    Key={"session_id": item["session_id"]},
                    UpdateExpression="SET #st = :st, updated_at = :now",
                    ConditionExpression=Attr("status").eq(item["#st"]),
                    ExpressionAttributeNames={"#st": "status"},
                    ExpressionAttributeValues={":st": new_status, ":now": now},
                )
                results["timed_out_sessions"] += 1
            except ClientError as e:
                if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                    raise
    except Exception as exc:  # noqa: BLE001
        log.error("reconcile.sessions.error", error=str(exc))

    log.info("reconciliation.complete", **results)
    return results


def _release_hold(table: Any, item: dict, now: int) -> None:
    try:
        table.update_item(
            Key={"order_id": item["order_id"]},
            UpdateExpression="SET #st = :st, updated_at = :now",
            ConditionExpression=Attr("status").eq("held"),
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":st": "hold_expired", ":now": now},
        )
        # Emit event for WS7 to release the hold on the carrier
        _events.put_events(Entries=[{
            "Source": "1145cx.ws9",
            "DetailType": "NumberHoldExpired",
            "Detail": json.dumps({
                "order_id": item["order_id"],
                "tenant_id": item.get("tenant_id"),
                "number": item.get("number"),
            }),
            "EventBusName": OPS_BUS,
        }])
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            log.warning("release_hold.failed", order_id=item["order_id"], error=str(e))


def _release_tenant_number(table: Any, item: dict, now: int) -> None:
    try:
        table.update_item(
            Key={"tenant_id": item["tenant_id"]},
            UpdateExpression="SET number_released = :now, updated_at = :now",
            ExpressionAttributeValues={":now": now},
        )
        if item.get("e164"):
            _events.put_events(Entries=[{
                "Source": "1145cx.ws9",
                "DetailType": "TenantNumberReleased",
                "Detail": json.dumps({
                    "tenant_id": item["tenant_id"],
                    "e164": item["e164"],
                }),
                "EventBusName": OPS_BUS,
            }])
        log.info("tenant_number.released", tenant_id=item["tenant_id"])
    except Exception as exc:  # noqa: BLE001
        log.warning("release_number.failed", tenant_id=item.get("tenant_id"), error=str(exc))


# ── migrations ────────────────────────────────────────────────────────────────
def _run_migrations() -> dict:
    """Idempotent schema migration runner.
    Each migration is identified by a version string stored in the Counters table.
    """
    applied = []
    migrations = [
        ("v1_counters_seed", _migrate_v1_seed_counters),
    ]
    for version, fn in migrations:
        already = _migration_applied(version)
        if not already:
            fn()
            _mark_migration(version)
            applied.append(version)
            log.info("migration.applied", version=version)
        else:
            log.debug("migration.skipped", version=version)
    return {"applied": applied}


def _migration_applied(version: str) -> bool:
    table = _dynamodb.Table(COUNTERS_TABLE)
    resp = table.get_item(Key={"counter_id": f"migration#{version}"})
    return "Item" in resp


def _mark_migration(version: str) -> None:
    table = _dynamodb.Table(COUNTERS_TABLE)
    table.put_item(Item={
        "counter_id": f"migration#{version}",
        "applied_at": int(time.time()),
    })


def _migrate_v1_seed_counters() -> None:
    """Seed baseline counters."""
    table = _dynamodb.Table(COUNTERS_TABLE)
    seeds = [
        {"counter_id": "global#sessions_created", "value": 0},
        {"counter_id": "global#tenants_live", "value": 0},
        {"counter_id": "global#numbers_ordered", "value": 0},
    ]
    for item in seeds:
        try:
            table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(counter_id)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise


# ── counter helpers ───────────────────────────────────────────────────────────
def _counter_increment(counter_id: str, delta: int = 1) -> dict:
    table = _dynamodb.Table(COUNTERS_TABLE)
    resp = table.update_item(
        Key={"counter_id": counter_id},
        UpdateExpression="ADD #v :delta",
        ExpressionAttributeNames={"#v": "value"},
        ExpressionAttributeValues={":delta": delta},
        ReturnValues="UPDATED_NEW",
    )
    return {"counter_id": counter_id, "value": int(resp["Attributes"]["value"])}


def _counter_get(counter_id: str) -> dict:
    table = _dynamodb.Table(COUNTERS_TABLE)
    resp = table.get_item(Key={"counter_id": counter_id})
    item = resp.get("Item", {})
    return {"counter_id": counter_id, "value": int(item.get("value", 0))}
