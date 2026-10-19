"""WS2 AgentCore entrypoint — wraps the LangGraph turn graph."""
from __future__ import annotations
import json, os
from typing import Any


def run_turn(payload: dict[str, Any]) -> dict[str, Any]:
    """Stateless turn: receives full context, returns reply + slot proposals."""
    from langchain_aws import ChatBedrockConverse
    from graph import TurnState, build_turn_graph

    model = ChatBedrockConverse(
        model_id=os.environ.get("AGENT_MODEL_ID", "us.amazon.nova-lite-v1:0"),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    graph = build_turn_graph(model)
    state = TurnState(**payload)
    result = graph.invoke(state)
    return {
        "reply": result.reply,
        "slot_proposals": result.slot_proposals,
        "intent": result.intent,
        "language": result.owner_language,
    }


def handler(event: dict, context: Any) -> dict:
    """Lambda handler for direct invocation from Turn Lambda."""
    return run_turn(event)
