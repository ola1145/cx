"""C10: Tenant config handed to the live agent."""
from __future__ import annotations
from pydantic import BaseModel, Field
from .c03_slots import ServiceHours, Service, Address

class EscalationConfig(BaseModel):
    phone: str
    instructions: str = ""
    always_on: bool = False

class TenantConfig(BaseModel):
    tenant_id: str
    business_name: str
    vertical: str
    owner_name: str
    owner_mobile: str
    services: list[Service] = Field(default_factory=list)
    hours: ServiceHours
    timezone: str
    greeting: str
    tone: str = "professional"
    languages: list[str] = Field(default_factory=lambda: ["en"])
    address: Address | None = None
    escalation: EscalationConfig | None = None
    approved_facts: dict[str, object] = Field(default_factory=dict)
    research_subject_id: str | None = None
    day_one_mode: bool = True
    number_e164: str | None = None
    ai_disclosure: str = "You've reached the AI assistant for {business_name}."
    recording_notice: str = "This call may be recorded."
