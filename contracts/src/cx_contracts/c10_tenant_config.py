"""C10 -- Tenant Config contract (frozen v1)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DayHours(BaseModel):
    open: str = "09:00"   # HH:MM
    close: str = "17:00"
    closed: bool = False


class BusinessHours(BaseModel):
    days: dict[str, DayHours] = Field(default_factory=dict)


class ServiceEntry(BaseModel):
    name: str
    description: str = ""
    price_type: Literal["fixed", "from", "range", "quote"] = "quote"
    price_min: float | None = None
    price_max: float | None = None
    duration_minutes: int | None = None
    deposit_required: bool = False
    add_ons: list[str] = Field(default_factory=list)


class EscalationConfig(BaseModel):
    phone: str = ""
    transfer_phrase: str = "Let me transfer you."


class TenantConfig(BaseModel):
    tenant_id: str
    business_name: str
    business_address: dict[str, Any] = Field(default_factory=dict)
    timezone: str = "America/New_York"
    languages: list[str] = Field(default_factory=lambda: ["en"])
    tone: Literal["professional", "friendly", "casual", "formal"] = "professional"
    greeting: str
    services: list[ServiceEntry] = Field(default_factory=list)
    hours: BusinessHours = Field(default_factory=BusinessHours)
    escalation: EscalationConfig = Field(default_factory=EscalationConfig)
    booking_enabled: bool = False
    calendar_connected: bool = False
    ai_disclosure_in_greeting: bool = True
    recording_notice_in_greeting: bool = True
    version: int = 1
