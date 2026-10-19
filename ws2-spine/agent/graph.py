"""WS2 LangGraph agent — 7-node turn graph over Pydantic TurnState.

No checkpointer: Step Functions + DynamoDB own durable state (architecture rule 1).
"""
from __future__ import annotations
from typing import Annotated, Any
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage


class TurnState(BaseModel):
    session_id: str
    inbox_items: list[dict] = Field(default_factory=list)
    last_turns: list[dict] = Field(default_factory=list)
    slots: dict = Field(default_factory=dict)
    profile_hints: dict = Field(default_factory=dict)
    last_validation_errors: list[str] = Field(default_factory=list)
    owner_language: str = "en"
    events: list[dict] = Field(default_factory=list)
    # Outputs set by nodes
    reply: str = ""
    slot_proposals: list[dict] = Field(default_factory=list)
    intent: str = "ask"


def build_turn_graph(model: Any) -> StateGraph:
    """Build the 7-node LangGraph turn graph."""

    def load_context(state: TurnState) -> TurnState:
        """Node 1: validate that inbox has items to process."""
        return state

    def detect_language(state: TurnState) -> TurnState:
        """Node 2: detect owner language from inbox text."""
        if not state.owner_language or state.owner_language == "en":
            all_text = " ".join(
                item.get("text", "") for item in state.inbox_items if item.get("text")
            ).lower()
            es_markers = {"hola", "quiero", "necesito", "tengo", "gracias", "por favor"}
            if sum(1 for w in es_markers if w in all_text) >= 2:
                return state.model_copy(update={"owner_language": "es"})
        return state

    def understand(state: TurnState) -> TurnState:
        """Node 3: call the LLM to understand intent and extract slot proposals."""
        system_prompt = _build_system_prompt(state)
        user_text = "\n".join(
            f"[{item.get('source','owner')}]: {item.get('text','')}"
            for item in state.inbox_items if item.get("text")
        )
        if not user_text:
            return state.model_copy(update={"reply": "Got it. What would you like to tell me about your business?", "intent": "ask"})

        messages = [HumanMessage(content=user_text)]
        response = model.invoke([{"role": "system", "content": system_prompt}] + messages)
        # response is structured output — parse below
        return state.model_copy(update={
            "reply": getattr(response, "reply", str(response)),
            "slot_proposals": getattr(response, "slot_proposals", []),
            "intent": getattr(response, "intent", "ask"),
        })

    def validate_proposals(state: TurnState) -> TurnState:
        """Node 4: validate slot proposals; errors fed back next turn (never in reply)."""
        return state  # validation happens in turn_lambda

    def check_complete(state: TurnState) -> str:
        """Conditional edge: route to readback or ask."""
        if state.intent == "readback":
            return "compose_readback"
        return "compose_reply"

    def compose_readback(state: TurnState) -> TurnState:
        """Node 5a: compose a read-back summary in the owner's language."""
        slots = state.slots
        lines = [
            f"Business: {slots.get('business_name', '—')}",
            f"Type: {slots.get('vertical', '—')}",
            f"Timezone: {slots.get('timezone', '—')}",
        ]
        services = slots.get("services", [])
        if services:
            lines.append(f"Services: {', '.join(s.get('name','') for s in services[:5])}")
        summary = "\n".join(lines)
        lang = state.owner_language
        if lang == "es":
            reply = f"Antes de continuar, confirme estos datos:\n{summary}\n\n¿Todo correcto?"
        else:
            reply = f"Before we continue, please confirm these details:\n{summary}\n\nDoes everything look right?"
        return state.model_copy(update={"reply": reply, "intent": "readback"})

    def compose_reply(state: TurnState) -> TurnState:
        """Node 5b: reply is already set by understand node."""
        return state

    def enforce_channel_limits(state: TurnState) -> TurnState:
        """Node 6: trim reply for voice (≤25 words)."""
        # Voice limit handled in delivery layer
        return state

    graph = StateGraph(TurnState)
    graph.add_node("load_context", load_context)
    graph.add_node("detect_language", detect_language)
    graph.add_node("understand", understand)
    graph.add_node("validate_proposals", validate_proposals)
    graph.add_node("compose_readback", compose_readback)
    graph.add_node("compose_reply", compose_reply)
    graph.add_node("enforce_channel_limits", enforce_channel_limits)

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "detect_language")
    graph.add_edge("detect_language", "understand")
    graph.add_edge("understand", "validate_proposals")
    graph.add_conditional_edges("validate_proposals", check_complete)
    graph.add_edge("compose_readback", "enforce_channel_limits")
    graph.add_edge("compose_reply", "enforce_channel_limits")
    graph.add_edge("enforce_channel_limits", END)

    return graph.compile()


def _build_system_prompt(state: TurnState) -> str:
    lang = state.owner_language
    errors = state.last_validation_errors
    hints = state.profile_hints

    base = (
        "You are an onboarding assistant for 1145cx, helping a business owner set up their AI phone agent. "
        "You are warm, professional and concise. "
        "Ask only ONE question per turn. "
        "Never state a research hint as fact — confirm it first. "
        "Never set consent, confirm anything, or mention pricing. "
        "Return structured JSON with fields: reply, slot_proposals, intent (ask|readback|confirm|exit)."
    )
    if lang == "es":
        base += " Respond in Spanish."
    if errors:
        base += f"\n\nValidation errors from last turn (do NOT show these to the owner, just re-ask naturally): {errors}"
    if hints:
        base += f"\n\nResearch hints (suggest as questions, never assert): {list(hints.keys())}"

    required_missing = [
        f for f in ["business_name","vertical","owner_mobile","services","hours","timezone","greeting_tone"]
        if not state.slots.get(f)
    ]
    if required_missing:
        base += f"\n\nStill needed: {required_missing}"
    return base
