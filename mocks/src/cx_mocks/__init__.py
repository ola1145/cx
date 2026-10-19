"""cx_mocks -- In-memory fakes for all 13 contracts.

Usage in tests:
    from cx_mocks import (
        MockSessionStore, MockInboxStore, MockIdentityStore,
        MockConsentStore, MockBillingStore, MockNumberStore,
        MockTenantStore, MockDeliveryBus, MockOpsEventBus,
    )
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Any

from cx_contracts.c01_inbound_event import InboundEvent
from cx_contracts.c02_inbox_turn import InboxItem, TurnRecord
from cx_contracts.c03_slots import OnboardingSlots
from cx_contracts.c06_identity import Identity
from cx_contracts.c07_consent import Consent, ConsentType
from cx_contracts.c08_billing import BillingRecord
from cx_contracts.c09_numbers import NumberOffer, NumberOrder, RoutingRecord
from cx_contracts.c10_tenant_config import TenantConfig
from cx_contracts.c11_delivery import DeliveryRequest, DeliveryResult
from cx_contracts.c13_ops_events import OpsEvent


class MockSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}

    def create(self, session_id: str | None = None, **kwargs: Any) -> dict:
        sid = session_id or str(uuid.uuid4())
        record = {
            "session_id": sid,
            "status": "collecting",
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
            **kwargs,
        }
        self._sessions[sid] = record
        return record

    def get(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)

    def update(self, session_id: str, **kwargs: Any) -> dict:
        s = self._sessions[session_id]
        s.update(kwargs)
        s["updated_at"] = int(time.time())
        return s

    def all(self) -> list[dict]:
        return list(self._sessions.values())


class MockInboxStore:
    def __init__(self) -> None:
        self._items: dict[str, list[InboxItem]] = defaultdict(list)

    def push(self, session_id: str, item: InboxItem) -> None:
        self._items[session_id].append(item)

    def drain(self, session_id: str) -> list[InboxItem]:
        items = self._items.pop(session_id, [])
        return items

    def peek(self, session_id: str) -> list[InboxItem]:
        return list(self._items.get(session_id, []))

    def depth(self, session_id: str) -> int:
        return len(self._items.get(session_id, []))


class MockTurnStore:
    def __init__(self) -> None:
        self._turns: dict[str, list[TurnRecord]] = defaultdict(list)

    def append(self, session_id: str, turn: TurnRecord) -> None:
        self._turns[session_id].append(turn)

    def last_n(self, session_id: str, n: int = 12) -> list[TurnRecord]:
        return self._turns.get(session_id, [])[-n:]


class MockIdentityStore:
    def __init__(self) -> None:
        self._records: dict[str, Identity] = {}

    def put(self, identity: Identity) -> None:
        self._records[identity.identity_key] = identity

    def get(self, identity_key: str) -> Identity | None:
        return self._records.get(identity_key)

    def get_by_channel(self, channel: str, address: str) -> Identity | None:
        key = f"{channel}:{address}"
        return self._records.get(key)


class MockConsentStore:
    def __init__(self) -> None:
        self._consents: dict[str, dict[str, Consent]] = defaultdict(dict)

    def record(self, subject: str, consent: Consent) -> None:
        self._consents[subject][consent.consent_type.value] = consent

    def has(self, subject: str, consent_type: ConsentType) -> bool:
        c = self._consents.get(subject, {}).get(consent_type.value)
        if c is None:
            return False
        if c.revoked_at is not None:
            return False
        return True

    def get(self, subject: str, consent_type: ConsentType) -> Consent | None:
        return self._consents.get(subject, {}).get(consent_type.value)


class MockBillingStore:
    def __init__(self) -> None:
        self._records: dict[str, BillingRecord] = {}

    def put(self, record: BillingRecord) -> None:
        self._records[record.tenant_id] = record

    def get(self, tenant_id: str) -> BillingRecord | None:
        return self._records.get(tenant_id)

    def can_order_number(self, tenant_id: str) -> bool:
        r = self._records.get(tenant_id)
        if r is None:
            return False
        return r.status in ("trialing", "active") and r.card_on_file


class MockNumberStore:
    def __init__(self) -> None:
        self._offers: dict[str, NumberOffer] = {}
        self._orders: dict[str, NumberOrder] = {}
        self._routing: dict[str, RoutingRecord] = {}

    def add_offer(self, offer: NumberOffer) -> None:
        self._offers[offer.offer_id] = offer

    def get_offer(self, offer_id: str) -> NumberOffer | None:
        return self._offers.get(offer_id)

    def place_order(self, order: NumberOrder) -> None:
        self._orders[order.order_id] = order

    def get_order(self, order_id: str) -> NumberOrder | None:
        return self._orders.get(order_id)

    def set_routing(self, record: RoutingRecord) -> None:
        self._routing[record.e164] = record

    def get_routing(self, e164: str) -> RoutingRecord | None:
        return self._routing.get(e164)


class MockTenantStore:
    def __init__(self) -> None:
        self._tenants: dict[str, TenantConfig] = {}

    def put(self, config: TenantConfig) -> None:
        self._tenants[config.tenant_id] = config

    def get(self, tenant_id: str) -> TenantConfig | None:
        return self._tenants.get(tenant_id)


class MockDeliveryBus:
    """Captures all delivery requests; tests can assert on sent messages."""

    def __init__(self) -> None:
        self.sent: list[DeliveryRequest] = []
        self.results: dict[str, DeliveryResult] = {}

    def send(self, req: DeliveryRequest) -> DeliveryResult:
        self.sent.append(req)
        result = DeliveryResult(
            request_id=req.request_id or str(uuid.uuid4()),
            status="delivered",
            channel=req.channel,
        )
        self.results[result.request_id] = result
        return result

    def last(self) -> DeliveryRequest | None:
        return self.sent[-1] if self.sent else None

    def all_to(self, identity_key: str) -> list[DeliveryRequest]:
        return [r for r in self.sent if r.identity_key == identity_key]


class MockOpsEventBus:
    def __init__(self) -> None:
        self.events: list[OpsEvent] = []

    def emit(self, event: OpsEvent) -> None:
        self.events.append(event)

    def of_kind(self, kind: str) -> list[OpsEvent]:
        return [e for e in self.events if e.kind.value == kind]
