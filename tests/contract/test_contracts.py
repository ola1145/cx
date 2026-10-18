"""Contract tests: valid fixtures pass, invalid fixtures raise ValidationError."""
from __future__ import annotations
import json, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "contracts" / "src"))
VALID = ROOT / "contracts" / "fixtures" / "valid"
INVALID = ROOT / "contracts" / "fixtures" / "invalid"

def _model_for(stem: str):
    from cx_contracts.c01_inbound_event import InboundEvent
    from cx_contracts.c02_inbox_turn import InboxItem
    from cx_contracts.c06_identity import IdentityRecord
    from cx_contracts.c07_consent import ConsentRecord
    from cx_contracts.c08_billing import BillingRecord
    from cx_contracts.c10_tenant_config import TenantConfig
    mapping = {
        "c01_inbound_event": InboundEvent, "c02_inbox_item": InboxItem,
        "c06_identity": IdentityRecord, "c07_consent": ConsentRecord,
        "c08_billing": BillingRecord, "c10_tenant_config": TenantConfig,
    }
    for key, m in mapping.items():
        if key in stem:
            return m
    pytest.skip(f"No model mapped for {stem}")

@pytest.mark.parametrize("p", list(VALID.glob("*.json")))
def test_valid_fixture(p: Path) -> None:
    _model_for(p.stem).model_validate(json.loads(p.read_text()))

@pytest.mark.parametrize("p", list(INVALID.glob("*.json")))
def test_invalid_fixture(p: Path) -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        _model_for(p.stem).model_validate(json.loads(p.read_text()))
