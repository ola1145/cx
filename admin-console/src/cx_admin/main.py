"""Admin Console -- FastAPI app for internal operators.

Endpoints:
  GET  /health
  GET  /tenants                 -- list all tenants (paginated)
  GET  /tenants/{tenant_id}     -- get single tenant
  POST /tenants/{tenant_id}/status  -- update status (lapsed, cancelled, live)
  GET  /sessions                -- list recent sessions
  GET  /sessions/{session_id}   -- inspect a session
  POST /sessions/{session_id}/abort  -- abort a stuck session
  GET  /numbers                 -- list number orders
  POST /numbers/{order_id}/release  -- manually release a hold
  GET  /metrics                 -- system metrics summary
  GET  /ops-events              -- recent ops events (EventBridge history)
"""
from __future__ import annotations

import os
import time
from typing import Annotated, Any

import boto3
from boto3.dynamodb.conditions import Attr
from fastapi import FastAPI, HTTPException, Query, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cx_lib.ddb import DDB
from cx_lib.logging import get_logger

log = get_logger("admin")

STAGE = os.environ.get("STAGE", "sandbox")
TENANTS_TABLE = os.environ.get("TENANTS_TABLE", f"cx-{STAGE}-tenants")
SESSIONS_TABLE = os.environ.get("SESSIONS_TABLE", f"cx-{STAGE}-sessions")
NUMBER_ORDERS_TABLE = os.environ.get("NUMBER_ORDERS_TABLE", f"cx-{STAGE}-number-orders")
ADMIN_TOKEN_SECRET = os.environ.get("ADMIN_TOKEN_SECRET", f"cx/{STAGE}/admin_token")
OPS_BUS = os.environ.get("OPS_BUS", f"1145cx-{STAGE}-ops")

_ddb = DDB()
_dynamodb = boto3.resource("dynamodb")
_secretsmanager = boto3.client("secretsmanager")
_sfn = boto3.client("stepfunctions")

app = FastAPI(
    title="1145cx Admin Console",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://admin.1145.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer = HTTPBearer()


def _verify_admin(creds: HTTPAuthorizationCredentials = Security(bearer)) -> str:
    """Verify the bearer token against Secrets Manager."""
    try:
        resp = _secretsmanager.get_secret_value(SecretId=ADMIN_TOKEN_SECRET)
        expected = resp["SecretString"].strip()
        if creds.credentials != expected:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")
        return creds.credentials
    except _secretsmanager.exceptions.ResourceNotFoundException:
        raise HTTPException(status_code=503, detail="Admin token not configured")


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/health")
def health() -> dict:
    return {"status": "ok", "stage": STAGE, "ts": int(time.time())}


# ── Tenants ────────────────────────────────────────────────────────────────────
@app.get("/tenants")
def list_tenants(
    _: str = Security(_verify_admin),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    last_key: str | None = None,
) -> dict:
    table = _dynamodb.Table(TENANTS_TABLE)
    kwargs: dict[str, Any] = {"Limit": limit}
    if status_filter:
        kwargs["FilterExpression"] = Attr("status").eq(status_filter)
    if last_key:
        import json
        kwargs["ExclusiveStartKey"] = json.loads(last_key)

    resp = table.scan(**kwargs)
    items = [_ddb.from_item(i) for i in resp.get("Items", [])]
    next_key = resp.get("LastEvaluatedKey")

    return {
        "items": items,
        "count": len(items),
        "next_key": str(next_key) if next_key else None,
    }


@app.get("/tenants/{tenant_id}")
def get_tenant(tenant_id: str, _: str = Security(_verify_admin)) -> dict:
    table = _dynamodb.Table(TENANTS_TABLE)
    resp = table.get_item(Key={"tenant_id": tenant_id})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _ddb.from_item(item)


@app.post("/tenants/{tenant_id}/status")
def update_tenant_status(
    tenant_id: str,
    body: dict,
    _: str = Security(_verify_admin),
) -> dict:
    allowed = {"live", "day_one", "lapsed", "cancelled", "suspended"}
    new_status = body.get("status")
    if new_status not in allowed:
        raise HTTPException(status_code=422, detail=f"status must be one of {allowed}")

    table = _dynamodb.Table(TENANTS_TABLE)
    now = int(time.time())
    table.update_item(
        Key={"tenant_id": tenant_id},
        UpdateExpression="SET #st = :st, updated_at = :now",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":st": new_status, ":now": now},
    )
    log.info("admin.tenant_status_updated", tenant_id=tenant_id, new_status=new_status)
    return {"tenant_id": tenant_id, "status": new_status}


# ── Sessions ────────────────────────────────────────────────────────────────────
@app.get("/sessions")
def list_sessions(
    _: str = Security(_verify_admin),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, le=200),
) -> dict:
    table = _dynamodb.Table(SESSIONS_TABLE)
    kwargs: dict[str, Any] = {"Limit": limit}
    if status_filter:
        kwargs["FilterExpression"] = Attr("status").eq(status_filter)
    resp = table.scan(**kwargs)
    items = [_ddb.from_item(i) for i in resp.get("Items", [])]
    return {"items": items, "count": len(items)}


@app.get("/sessions/{session_id}")
def get_session(session_id: str, _: str = Security(_verify_admin)) -> dict:
    table = _dynamodb.Table(SESSIONS_TABLE)
    resp = table.get_item(Key={"session_id": session_id})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Session not found")
    return _ddb.from_item(item)


@app.post("/sessions/{session_id}/abort")
def abort_session(session_id: str, _: str = Security(_verify_admin)) -> dict:
    """Abort the Step Functions execution for this session."""
    table = _dynamodb.Table(SESSIONS_TABLE)
    resp = table.get_item(Key={"session_id": session_id})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Session not found")

    execution_arn = item.get("execution_arn")
    if execution_arn:
        try:
            _sfn.stop_execution(
                executionArn=execution_arn,
                cause="Manual abort by admin",
            )
        except _sfn.exceptions.ExecutionDoesNotExist:
            pass

    now = int(time.time())
    table.update_item(
        Key={"session_id": session_id},
        UpdateExpression="SET #st = :st, aborted_by_admin = :now, updated_at = :now",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":st": "failed", ":now": now},
    )
    log.warning("admin.session_aborted", session_id=session_id)
    return {"session_id": session_id, "status": "failed"}


# ── Numbers ────────────────────────────────────────────────────────────────────
@app.get("/numbers")
def list_numbers(
    _: str = Security(_verify_admin),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, le=200),
) -> dict:
    table = _dynamodb.Table(NUMBER_ORDERS_TABLE)
    kwargs: dict[str, Any] = {"Limit": limit}
    if status_filter:
        kwargs["FilterExpression"] = Attr("status").eq(status_filter)
    resp = table.scan(**kwargs)
    items = [_ddb.from_item(i) for i in resp.get("Items", [])]
    return {"items": items, "count": len(items)}


@app.post("/numbers/{order_id}/release")
def release_number_hold(order_id: str, _: str = Security(_verify_admin)) -> dict:
    table = _dynamodb.Table(NUMBER_ORDERS_TABLE)
    now = int(time.time())
    table.update_item(
        Key={"order_id": order_id},
        UpdateExpression="SET #st = :st, admin_released_at = :now, updated_at = :now",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":st": "admin_released", ":now": now},
    )
    log.info("admin.hold_released", order_id=order_id)
    return {"order_id": order_id, "status": "admin_released"}


# ── Metrics ────────────────────────────────────────────────────────────────────
@app.get("/metrics")
def get_metrics(_: str = Security(_verify_admin)) -> dict:
    results: dict[str, Any] = {}
    try:
        t = _dynamodb.Table(TENANTS_TABLE)
        results["live_tenants"] = t.scan(
            Select="COUNT",
            FilterExpression=Attr("status").eq("live"),
        ).get("Count", 0)
        results["total_tenants"] = t.scan(Select="COUNT").get("Count", 0)
    except Exception:  # noqa: BLE001
        results["tenants_error"] = True

    try:
        s = _dynamodb.Table(SESSIONS_TABLE)
        results["active_sessions"] = s.scan(
            Select="COUNT",
            FilterExpression=Attr("status").is_in(
                ["collecting", "reviewing", "billing", "numbering"]
            ),
        ).get("Count", 0)
    except Exception:  # noqa: BLE001
        results["sessions_error"] = True

    return {"ts": int(time.time()), **results}
