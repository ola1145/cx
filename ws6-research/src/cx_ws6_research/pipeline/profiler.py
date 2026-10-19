"""WS6 Profiler — RS-8: prefill every research slot from checked facts (≥0.7 confidence)."""
from __future__ import annotations
from typing import Any


def build_profile(session_id: str, all_facts: list[dict]) -> dict[str, Any]:
    """Prefill all C3 research fields. Every value needs a quote containing the claimed fact."""
    profile: dict[str, Any] = {
        "session_id": session_id,
        "facts": [],
        "status": "partial",
    }
    high_conf = [f for f in all_facts if f.get("confidence", 0) >= 0.7]
    for fact in high_conf:
        # Verify the quote contains the claimed value (D2 fix)
        quote = fact.get("quote", "")
        value = str(fact.get("value", ""))
        if value and value.lower() in quote.lower():
            profile["facts"].append(fact)

    if profile["facts"]:
        profile["status"] = "ready"
    return profile
