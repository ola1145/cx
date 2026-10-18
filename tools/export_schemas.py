#!/usr/bin/env python3
"""Export Pydantic v2 models to JSON Schema in contracts/schemas/.
Usage: python tools/export_schemas.py [--check]
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCHEMAS_DIR = ROOT / "contracts" / "schemas"

def _models() -> dict[str, type]:
    sys.path.insert(0, str(ROOT / "contracts" / "src"))
    from cx_contracts.c01_inbound_event import InboundEvent
    from cx_contracts.c02_inbox_turn import InboxItem, TurnRecord
    from cx_contracts.c03_slots import OnboardingSlots, Service
    from cx_contracts.c04_agent_turn import AgentTurnInput, AgentTurnOutput
    from cx_contracts.c05_profile import BusinessProfile
    from cx_contracts.c06_identity import IdentityRecord
    from cx_contracts.c07_consent import ConsentRecord
    from cx_contracts.c08_billing import BillingRecord
    from cx_contracts.c09_numbers import NumberOffer, NumberOrder, RoutingRecord
    from cx_contracts.c10_tenant_config import TenantConfig
    from cx_contracts.c11_delivery import DeliveryRequest, DeliveryResult
    from cx_contracts.c13_ops_events import OpsEvent
    return {
        "c01-inbound-event": InboundEvent,
        "c02-inbox-item": InboxItem, "c02-turn-record": TurnRecord,
        "c03-onboarding-slots": OnboardingSlots, "c03-service": Service,
        "c04-agent-turn-input": AgentTurnInput, "c04-agent-turn-output": AgentTurnOutput,
        "c05-business-profile": BusinessProfile,
        "c06-identity": IdentityRecord, "c07-consent": ConsentRecord,
        "c08-billing": BillingRecord,
        "c09-number-offer": NumberOffer, "c09-number-order": NumberOrder, "c09-routing": RoutingRecord,
        "c10-tenant-config": TenantConfig,
        "c11-delivery-request": DeliveryRequest, "c11-delivery-result": DeliveryResult,
        "c13-ops-event": OpsEvent,
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    models = _models()
    changed: list[str] = []
    for name, model in models.items():
        text = json.dumps(model.model_json_schema(), indent=2)
        path = SCHEMAS_DIR / f"{name}.schema.json"
        if path.exists() and path.read_text() == text:
            continue
        if args.check:
            changed.append(name)
        else:
            path.write_text(text)
            print(f"  wrote {path.name}")
    if args.check and changed:
        print(f"Schema drift: {', '.join(changed)}", file=sys.stderr)
        sys.exit(1)
    elif not args.check:
        print(f"Exported {len(models)} schemas to {SCHEMAS_DIR}")

if __name__ == "__main__":
    main()
