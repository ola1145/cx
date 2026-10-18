# 1145cx Onboarding

Owner onboarding for 1145cx: WhatsApp · Telegram · Web · Voice. Step Functions spine + AgentCore/LangGraph agent. 10 parallel workstreams building to AWS CDK v2 Python.

## Prerequisites
- Python 3.12, Node 20, uv (`pip install uv`), AWS CDK CLI (via npm)
- AWS profile `1145ai` configured (`aws configure --profile 1145ai`)
- AWS account 298713973957 (1145ai), region us-east-1

## Quick start

```bash
make setup       # uv sync + npm ci
make schemas     # generate JSON Schema from contracts
make test        # unit + contract tests (no AWS creds needed)
make synth       # CDK synth for sandbox (no creds needed)
make validate    # synth all 3 environments
make diff        # cdk diff against sandbox (needs AWS creds)
```

## Project layout

| Folder | Owns |
|---|---|
| `contracts/` | C1–C13 Pydantic models + JSON Schema + fixtures |
| `lib/` | Shared lib: DDB codec, safe HTTP, secrets, logging |
| `mocks/` | In-memory fakes for every contract |
| `ws1-channels/` | Webhooks, ingest, inbox, media, delivery, voice worker |
| `ws2-spine/` | Step Functions spine, agent (AgentCore/LangGraph) |
| `ws3-identity/` | Cognito, phone verify, sign-in links |
| `ws4-billing/` | Stripe Checkout, webhooks, billing fields |
| `ws5-legal/` | Consent ledger, greeting rule, opt-outs |
| `ws6-research/` | Safe fetcher, scouts, profiler |
| `ws7-numbers/` | Telnyx number search, order, assign, test call |
| `ws8-tenant/` | Provisioning, tenant config, dashboard seed |
| `ws9-data/` | DataStack — ALL DynamoDB tables + S3 |
| `ws10-ops/` | Alarms, sweeper, admin viewer, EventBridge |
| `infra/` | CDK app wiring every ws stack |

## Architecture rules (all code must follow these)
1. One writer per session — only the spine writes slots
2. The agent only talks — validators decide what is saved
3. No message is lost — inbox first, every turn reads queued items
4. Nothing bought/called for an unverified owner
5. Every failure ends in a named state
6. Scraped text never reaches the agent prompt
7. One codec for stored numbers — always use `cx_lib.ddb`

## Secrets layout (AWS Secrets Manager)
Secrets are in Secrets Manager under `cx/{env}/telnyx`, `cx/{env}/telegram`, `cx/{env}/livekit`, `cx/{env}/stripe`, `cx/{env}/google`, `cx/{env}/signin`. Never in the repo. Tests use `SECRETS_BACKEND=env`.

## Gates
- **G0** Contracts frozen, mocks pass, lib codec merged, CDK skeleton deploys
- **G1** All workstream unit + contract tests green
- **G2** Integration pairs pass in sandbox (paid switches off)
- **G3** E2E + security suites pass in staging; alarms drilled
