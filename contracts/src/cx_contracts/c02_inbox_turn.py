"""C2: Inbox item and turn record."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class InboxState(str, Enum):
    queued = "queued"
    consumed = "consumed"


class InboxItem(BaseModel):
    session_id: str
    ts_msg_id: str  # sort key: ts#msgId
    channel: str
    kind: str = "text"
    text: str | None = None
    media_key: str | None = None
    state: InboxState = InboxState.queued
    received_at: datetime
    source: str = "owner"


class TurnSpeaker(str, Enum):
    owner = "owner"
    agent = "agent"
    event = "event"


class TurnRecord(BaseModel):
    session_id: str
    turn_seq: str  # sort key: turn#NNN
    speaker: TurnSpeaker
    text: str
    channel: str | None = None
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
