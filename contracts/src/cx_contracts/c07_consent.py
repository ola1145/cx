"""C7: Consent record and has_consent API."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class ConsentType(str, Enum):
    terms = "terms"
    privacy = "privacy"
    research = "research"
    calls_and_alerts = "calls_and_alerts"
    marketing = "marketing"

class ConsentRecord(BaseModel):
    subject_id: str
    type_ts: str
    consent_type: ConsentType
    version: str
    content_hash: str
    prompt_shown: str
    reply: str
    channel: str
    msg_id: str
    recorded_at: datetime = Field(default_factory=datetime.utcnow)
    withdrawn_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None

def has_consent(subject_id: str, consent_type: ConsentType, records: list[ConsentRecord]) -> bool:
    matching = [r for r in records if r.subject_id == subject_id and r.consent_type == consent_type]
    if not matching:
        return False
    latest = max(matching, key=lambda r: r.recorded_at)
    return latest.withdrawn_at is None
