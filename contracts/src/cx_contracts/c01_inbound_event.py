"""C1: Inbound event — normalized message from any channel."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class Channel(str, Enum):
    whatsapp = "whatsapp"
    telegram = "telegram"
    web = "web"
    voice = "voice"


class MessageKind(str, Enum):
    text = "text"
    image = "image"
    audio = "audio"
    contact = "contact"
    other = "other"


class InboundEvent(BaseModel):
    channel: Channel
    address: str = Field(..., description="Sender address: E.164 phone or Telegram user ID")
    session_id: str
    kind: MessageKind = MessageKind.text
    text: str | None = None
    media_key: str | None = None  # S3 key for image/audio
    msg_id: str  # provider message ID for idempotency
    received_at: datetime
    source: Literal["owner", "image", "audio", "event"] = "owner"
