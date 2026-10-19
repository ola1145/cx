"""LiveKit room manager for 1145cx.

Handles:
- Creating rooms per tenant for voice/video sessions
- Generating access tokens for agents and owners
- Room webhooks (participant joined/left, room ended)
- Cleanup of idle rooms
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

import boto3
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from cx_lib.logging import get_logger
from cx_lib.secrets import get_secret

log = get_logger("livekit")

STAGE = os.environ.get("STAGE", "sandbox")
LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")
LIVEKIT_API_KEY_SECRET = os.environ.get("LIVEKIT_API_KEY_SECRET", f"cx/{STAGE}/livekit_api_key")
LIVEKIT_API_SECRET_SECRET = os.environ.get("LIVEKIT_API_SECRET_SECRET", f"cx/{STAGE}/livekit_api_secret")
TENANTS_TABLE = os.environ.get("TENANTS_TABLE", f"cx-{STAGE}-tenants")
SESSIONS_TABLE = os.environ.get("SESSIONS_TABLE", f"cx-{STAGE}-sessions")

_dynamodb = boto3.resource("dynamodb")

app = FastAPI(title="1145cx LiveKit Manager", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dashboard.1145.ai", "https://*.1145.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ─────────────────────────────────────────────────────────────────────
class CreateRoomRequest(BaseModel):
    tenant_id: str
    session_id: str | None = None
    room_type: str = "voice"  # voice | video | screen_share


class JoinRoomRequest(BaseModel):
    room_name: str
    participant_name: str
    participant_identity: str
    grants: dict[str, bool] = {"canPublish": True, "canSubscribe": True}


class TokenResponse(BaseModel):
    token: str
    room_name: str
    livekit_url: str


# ── Helpers ─────────────────────────────────────────────────────────────────────
def _get_livekit_creds() -> tuple[str, str]:
    api_key = get_secret(LIVEKIT_API_KEY_SECRET)
    api_secret = get_secret(LIVEKIT_API_SECRET_SECRET)
    return api_key, api_secret


def _make_room_name(tenant_id: str, room_type: str = "voice") -> str:
    prefix = tenant_id[:8]
    ts = int(time.time())
    return f"{prefix}-{room_type}-{ts}"


def _generate_token(
    api_key: str,
    api_secret: str,
    room_name: str,
    identity: str,
    name: str,
    grants: dict,
    ttl: int = 3600,
) -> str:
    """Generate a LiveKit JWT access token.
    Uses livekit-server-sdk when available, otherwise builds manually.
    """
    try:
        from livekit.api import AccessToken, VideoGrants
        video_grants = VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=grants.get("canPublish", True),
            can_subscribe=grants.get("canSubscribe", True),
        )
        token = (
            AccessToken(api_key, api_secret)
            .with_identity(identity)
            .with_name(name)
            .with_grants(video_grants)
            .with_ttl(ttl)
            .to_jwt()
        )
        return token
    except ImportError:
        # Fallback: build JWT manually (compatible with livekit-server 1.x)
        return _build_jwt_manual(api_key, api_secret, room_name, identity, name, grants, ttl)


def _build_jwt_manual(
    api_key: str,
    api_secret: str,
    room_name: str,
    identity: str,
    name: str,
    grants: dict,
    ttl: int,
) -> str:
    import base64
    import hmac
    import struct

    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": api_key,
        "sub": identity,
        "name": name,
        "iat": now,
        "nbf": now,
        "exp": now + ttl,
        "video": {
            "roomJoin": True,
            "room": room_name,
            "canPublish": grants.get("canPublish", True),
            "canSubscribe": grants.get("canSubscribe", True),
        },
    }

    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    h = b64url(json.dumps(header, separators=(",", ":")).encode())
    p = b64url(json.dumps(payload, separators=(",", ":")).encode())
    msg = f"{h}.{p}".encode()
    sig = hmac.new(api_secret.encode(), msg, hashlib.sha256).digest()
    return f"{h}.{p}.{b64url(sig)}"


# ── Endpoints ──────────────────────────────────────────────────────────────────
@app.get("/health")
def health() -> dict:
    return {"status": "ok", "livekit_url": LIVEKIT_URL}


@app.post("/rooms", response_model=dict)
async def create_room(req: CreateRoomRequest) -> dict:
    """Create a new LiveKit room for a tenant."""
    # Verify tenant exists
    tenants_table = _dynamodb.Table(TENANTS_TABLE)
    resp = tenants_table.get_item(Key={"tenant_id": req.tenant_id})
    if not resp.get("Item"):
        raise HTTPException(status_code=404, detail="Tenant not found")

    room_name = _make_room_name(req.tenant_id, req.room_type)

    # Optionally create the room via LiveKit server API
    try:
        from livekit.api import LiveKitAPI, CreateRoomRequest as LKCreateRoom
        api_key, api_secret = _get_livekit_creds()
        async with LiveKitAPI(url=LIVEKIT_URL, api_key=api_key, api_secret=api_secret) as lk:
            await lk.room.create_room(
                LKCreateRoom(
                    name=room_name,
                    max_participants=10,
                    empty_timeout=300,  # 5 min idle TTL
                )
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("livekit.create_room.skipped", error=str(exc))

    # Record in sessions table if session_id provided
    if req.session_id:
        sessions_table = _dynamodb.Table(SESSIONS_TABLE)
        sessions_table.update_item(
            Key={"session_id": req.session_id},
            UpdateExpression="SET livekit_room = :r, updated_at = :now",
            ExpressionAttributeValues={":r": room_name, ":now": int(time.time())},
        )

    log.info("livekit.room_created", room=room_name, tenant=req.tenant_id)
    return {"room_name": room_name, "tenant_id": req.tenant_id, "livekit_url": LIVEKIT_URL}


@app.post("/rooms/{room_name}/token", response_model=TokenResponse)
async def join_room(room_name: str, req: JoinRoomRequest) -> TokenResponse:
    """Generate an access token for a participant to join a room."""
    api_key, api_secret = _get_livekit_creds()
    token = _generate_token(
        api_key=api_key,
        api_secret=api_secret,
        room_name=room_name,
        identity=req.participant_identity,
        name=req.participant_name,
        grants=req.grants,
        ttl=3600,
    )
    return TokenResponse(token=token, room_name=room_name, livekit_url=LIVEKIT_URL)


@app.post("/rooms/{room_name}/agent-token", response_model=TokenResponse)
async def agent_token(room_name: str, tenant_id: str) -> TokenResponse:
    """Generate an agent token with publish+subscribe grants."""
    api_key, api_secret = _get_livekit_creds()
    token = _generate_token(
        api_key=api_key,
        api_secret=api_secret,
        room_name=room_name,
        identity=f"agent-{tenant_id}",
        name="1145 AI Agent",
        grants={"canPublish": True, "canSubscribe": True},
        ttl=7200,
    )
    return TokenResponse(token=token, room_name=room_name, livekit_url=LIVEKIT_URL)


@app.post("/webhook")
async def livekit_webhook(
    request: Request,
    authorization: str = Header(None),
) -> dict:
    """Receive LiveKit webhook events (room_started, room_finished, participant_joined, etc.)"""
    body = await request.body()
    event = json.loads(body)
    event_type = event.get("event", "")

    log.info("livekit.webhook", event_type=event_type)

    if event_type == "room_finished":
        room = event.get("room", {})
        room_name = room.get("name", "")
        log.info("livekit.room_finished", room=room_name)
        # Could trigger cleanup, transcript processing, etc.

    elif event_type == "participant_left":
        participant = event.get("participant", {})
        log.info("livekit.participant_left", identity=participant.get("identity"))

    return {"received": True}
