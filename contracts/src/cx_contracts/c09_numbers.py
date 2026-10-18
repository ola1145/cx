"""C9: Number offer, order record, routing record."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field

class NumberProvider(str, Enum):
    telnyx = "telnyx"
    twilio = "twilio"

class NumberOffer(BaseModel):
    e164: str
    area_code: str
    city: str | None = None
    state: str | None = None
    monthly_usd: Decimal
    setup_usd: Decimal = Decimal("0")
    provider: NumberProvider = NumberProvider.telnyx
    reservation_id: str | None = None
    expires_at: datetime | None = None

class OrderState(str, Enum):
    ordering = "ordering"
    ordered = "ordered"
    assigning = "assigning"
    assigned = "assigned"
    failed = "failed"
    released = "released"

class NumberOrder(BaseModel):
    tenant_id: str
    reference: str
    provider: NumberProvider
    e164: str
    state: OrderState = OrderState.ordering
    provider_order_id: str | None = None
    reservation_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_reconciled_at: datetime | None = None

class RoutingRecord(BaseModel):
    e164: str
    tenant_id: str
    provider: NumberProvider
    provider_number_id: str
    voice_connection_id: str | None = None
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
