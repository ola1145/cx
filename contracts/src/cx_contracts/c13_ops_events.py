"""C13: Ops events, metric names and alarm names."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class OpsEventKind(str, Enum):
    session_failed = "session_failed"
    session_started = "session_started"
    session_live = "session_live"
    number_pending = "number_pending"
    number_assigned = "number_assigned"
    billing_lapsed = "billing_lapsed"
    research_failed = "research_failed"
    sweeper_restarted = "sweeper_restarted"

class OpsEvent(BaseModel):
    kind: OpsEventKind
    session_id: str | None = None
    tenant_id: str | None = None
    detail: dict[str, object] = Field(default_factory=dict)
    emitted_at: datetime = Field(default_factory=datetime.utcnow)

METRIC_NAMES = {
    "onboarding_funnel": "cx/OnboardingFunnel",
    "webhook_errors": "cx/WebhookErrors",
    "turn_latency": "cx/TurnLatencyMs",
    "research_duration": "cx/ResearchDurationMs",
    "number_pending_age": "cx/NumberPendingAgeMin",
}

ALARM_NAMES = {
    "failed_executions": "cx-FailedExecutions",
    "stuck_sessions": "cx-StuckSessions",
    "numbers_pending": "cx-NumbersPendingOver1h",
    "webhook_error_spike": "cx-WebhookErrorSpike",
    "bedrock_throttle": "cx-BedrockThrottling",
    "spend_cap_hit": "cx-SpendCapHit",
}
