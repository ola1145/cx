"""C6: Identity record and verification API."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class VerifyMethod(str, Enum):
    whatsapp_possession = "whatsapp_possession"
    telegram_contact = "telegram_contact"
    callback_code = "callback_code"

class IdentityRecord(BaseModel):
    channel_address: str
    session_id: str | None = None
    tenant_id: str | None = None
    verified: bool = False
    verify_method: VerifyMethod | None = None
    verified_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: int | None = None

def is_verified(channel_address: str, identity: IdentityRecord | None) -> bool:
    if identity is None:
        return False
    return identity.channel_address == channel_address and identity.verified
