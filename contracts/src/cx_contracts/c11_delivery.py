"""C11: Delivery API."""
from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class DeliveryChannel(str, Enum):
    whatsapp = "whatsapp"
    telegram = "telegram"
    web = "web"
    voice = "voice"

class DeliveryPayload(BaseModel):
    text: str | None = None
    media_url: str | None = None
    template_name: str | None = None
    template_params: dict[str, str] = Field(default_factory=dict)

class DeliveryRequest(BaseModel):
    session_id: str
    payload: DeliveryPayload
    channel: DeliveryChannel | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class DeliveryResult(BaseModel):
    success: bool
    channel_used: DeliveryChannel | None = None
    provider_msg_id: str | None = None
    error: str | None = None
