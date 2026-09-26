# Lanes (steering)

**Protected file.** Editing steering requires owner review.

## Two rules that make parallelism safe
1. **Lanes never edit each other's directories.** A lane PR touching another lane's files
   is rejected in review, no exceptions. Collisions become impossible by construction.
2. **Contract files are protected**: `platform.contract`, the OpenAPI spec, the carrier and
   VoiceSession interfaces, and steering. Any lane PR touching them needs explicit owner
   review. The contract evolves by decision, never by drift.

## Serial by necessity, parallel by default
Contract, OpenAPI and interfaces land in **Stage 0 (serial)**. Nothing parallelizes until
Stage 0 merges. All six lanes then run concurrently, each in its own worktree/branch.
Production promotion is always serial and always human-approved.

## The six lanes
- **Infra / CDK** — `infra/`: multi-stack app, IAM, AWS Config drift rules, budgets, env config.
- **API + lifecycle** — `services/api` + `services/onboarding`: REST endpoints, Cognito tenant
  auth, Step Functions onboarding.
- **Telephony** — `services/telephony`: Telnyx instant DID, fleet webhook, Twilio failover
  behind one carrier interface.
- **Voice** — `services/voice`: Nova 2 Sonic behind the VoiceSession interface + model eval harness.
- **AgentCore brain** — `services/agentcore`: per-tenant agent, owner copilot tools, ontology writes.
- **Harness + CI** — `tests/`, `contract/` tooling, `.github/workflows`: gates, conformance CLI,
  drift ledger, e2e.

## Isolation mechanics
Every task run gets `git worktree add` plus its own branch `kirocrew/task/<id>`; the owner's
checkout is untouched. Up to 3 concurrent task runs, executed in parallel batches of 3.
