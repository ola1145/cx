"""C8: Billing status and can_order_number gate."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel

class BillingStatus(str, Enum):
    none = "none"
    setup = "setup"
    trialing = "trialing"
    active = "active"
    past_due = "past_due"
    lapsed = "lapsed"
    canceled = "canceled"

class BillingRecord(BaseModel):
    tenant_id: str
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    billing_status: BillingStatus = BillingStatus.none
    card_on_file: bool = False
    trial_end: datetime | None = None
    current_period_end: datetime | None = None
    updated_at: datetime | None = None

def can_order_number(billing: BillingRecord) -> bool:
    """True only when trialing/active AND card on file (S4)."""
    return billing.billing_status in (BillingStatus.trialing, BillingStatus.active) and billing.card_on_file
