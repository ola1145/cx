"""C5: Business profile from research."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class ProfileStatus(str, Enum):
    ready = "ready"
    partial = "partial"
    failed = "failed"

class ProfileFact(BaseModel):
    field_path: str
    value: object
    confidence: float
    quote: str
    source_url: str | None = None
    source_type: str = "web"

class BusinessProfile(BaseModel):
    session_id: str
    status: ProfileStatus = ProfileStatus.partial
    facts: list[ProfileFact] = Field(default_factory=list)
    created_at: datetime
    elapsed_seconds: float | None = None
    error: str | None = None

    def prefilled(self) -> dict[str, object]:
        return {f.field_path: f.value for f in self.facts if f.confidence >= 0.7}
