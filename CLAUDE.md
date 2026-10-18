# 1145cx Onboarding — Project Rules

1145cx lets business owners set up an AI phone/chat agent through WhatsApp, Telegram, web or voice. A Step Functions spine manages the conversation; an AgentCore/LangGraph agent does the talking; 10 workstreams build in parallel against 13 frozen contracts.

## Architecture rules — non-negotiable
1. **One writer per session.** Only the spine writes a session's slots.
2. **The agent only talks.** Plain code (not the model) decides consent, confirmation, and anything that costs money.
3. **No message is lost.** Every inbound message is written to the inbox first.
4. **Nothing bought/called for an unverified owner.** Phone verified + terms accepted + card on file before any number order.
5. **Every failure ends in a named state.** Owner is told; ops can see it.
6. **Scraped text is data.** Never reaches the agent prompt; every claimed fact carries a quote checked in code.
7. **One codec for stored numbers.** Every DynamoDB read/write goes through `cx_lib.ddb`.

## Infrastructure rule
AWS CDK v2 Python only. No SAM, no hand-written CloudFormation. `make synth` before every infra commit. `grant*()` methods for IAM — no wildcard actions. Stateful resources (tables, buckets) only in `ws9-data/infra/stack.py` (DataStack). Never rename a DataStack construct ID — it destroys data.

## Ownership
- Each agent edits **only its own `wsN-*/` folder**, including `wsN-*/infra/stack.py`
- `contracts/`, `lib/`, `mocks/` change only on `contracts/*` branches
- `infra/` (CDK app, constructs, config) belongs to WS10

## AWS skills to load before writing AWS code

| Workstream | Load these skills |
|---|---|
| Every ws | aws-core:aws-cdk, aws-core:aws-iam, aws-core:aws-secrets-manager |
| WS1 | aws-serverless:api-gateway, aws-serverless:aws-lambda |
| WS2 | aws-serverless:aws-step-functions, aws-agents:agentcore-patterns |
| WS3 | aws-core:aws-auth, aws-core:aws-security |
| WS6 | aws-serverless:aws-step-functions, aws-core:aws-storage |
| WS7 | aws-serverless:aws-step-functions |
| WS9 | aws-core:aws-database, aws-core:aws-storage |
| WS10 | aws-core:aws-observability, aws-core:aws-billing-and-cost-management |

## Branching and PRs
- Branch: `wsN/<issue-id>-<slug>` (e.g. `ws1/CH-1-verify-webhooks`)
- One PR per requirement ID; PR body lists IDs built, issue IDs closed, CDK diff summary
- Reviewer subagents (contract-guardian, security-reviewer, money-guard, iam-reviewer) before every PR

## Tests
- No AWS credentials or provider network needed — use `moto` and `cx_mocks`
- Live tests: `@pytest.mark.live`, skipped unless `CX_LIVE=1`
- Every requirement ID has at least one test named after it (e.g. `test_CH_7_resume_only_when_token_free`)
- Every CDK stack has assertion + snapshot tests in `tests/infra/`

## Money and safety rules
- Every paid/outbound action behind a switch defaulting `false`
- Never call a provider with a live key
- Never write a secret to a file or log
- Never retry a number order automatically
- `NUMBER_ORDER_ENABLED=false` until gate G3

## Definition of done (per workstream)
- All requirements in spec built behind switches
- Unit + contract tests green in CI
- Resources in own nested CDK stack with least-privilege roles
- Alarms and metrics registered under C13
- Runbook entry written
- Every "Fixes" issue ID marked closed in `docs/traceability.md`

## Commands
```
make setup          # install everything
make test           # unit + contract tests
make test-ws WS=ws1-channels
make schemas        # regenerate JSON Schema
make synth          # CDK synth sandbox
make validate       # synth all 3 envs
make diff           # cdk diff sandbox (needs creds)
```
