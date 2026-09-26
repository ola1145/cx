# Carrier Interface (seam) — v0.1

**Protected seam.** After Stage 0, changes only through an owner-approved contract-diff PR.
The telephony lane codes against THIS interface; it never mocks another lane's internals.

Telnyx is the **default** carrier (instant DID per tenant, one Call Control app, fleet
webhook, tenant resolved from dialed number). Twilio is **failover behind the same
interface**. Amazon Connect stays out of the DID path.

## Operations

```
searchNumbers(criteria: NumberSearch) -> AvailableNumber[]
orderNumber(number: E164, tenantId: string) -> OrderedNumber
attachNumber(number: E164, tenantId: string) -> Attachment
releaseNumber(number: E164) -> Released
normalizeInboundWebhook(raw: CarrierWebhookPayload) -> NormalizedCallEvent
```

## Types (shape only; frozen shapes populated by contract-diff PR)

- `NumberSearch`: `{ rateCenter?, areaCode?, count }`
- `AvailableNumber`: `{ e164, rateCenter, monthlyCost }`
- `OrderedNumber`: `{ e164, orderId, tenantId }`
- `Attachment`: `{ e164, tenantId, callControlAppId }`
- `NormalizedCallEvent`: `{ eventType, from, to, tenantId, carrier: "telnyx"|"twilio", raw }`

## Contract rules

- **Tenant resolved from the dialed number** on every inbound webhook (REQ-0002).
- Webhook **signature verification** is mandatory before normalization.
- **10DLC registration state** is tracked per tenant before any tenant texting.
- Every implementation ships with **contract tests**; a drift from this interface fails
  the lane's own CI before it can break a neighbor.
- CI/preview/agent environments carry **test credentials only**. Live keys live in a
  separate account the crew cannot read.
