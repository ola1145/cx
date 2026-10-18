"""C4: Agent turn input/output."""
from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from .c02_inbox_turn import InboxItem, TurnRecord
from .c03_slots import OnboardingSlots

class AgentIntent(str, Enum):
    ask = "ask"
    readback = "readback"
    confirm = "confirm"
    exit = "exit"

class SlotProposal(BaseModel):
    field_path: str
    value: Any
    confidence: float = 1.0
    evidence: str | None = None

class AgentTurnInput(BaseModel):
    session_id: str
    inbox_items: list[InboxItem]
    last_turns: list[TurnRecord] = Field(default_factory=list)
    slots: OnboardingSlots
    profile_hints: dict[str, Any] = Field(default_factory=dict)
    last_validation_errors: list[str] = Field(default_factory=list)
    channel_rules: dict[str, Any] = Field(default_factory=dict)
    owner_language: str = "en"
    events: list[dict[str, Any]] = Field(default_factory=list)

class AgentTurnOutput(BaseModel):
    reply: str
    slot_proposals: list[SlotProposal] = Field(default_factory=list)
    intent: AgentIntent = AgentIntent.ask
    language: str = "en"
    metadata: dict[str, Any] = Field(default_factory=dict)
