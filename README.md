# 1145cx — Crew Parallel Backend

Backend and non-UI only. Six lanes build the platform backend in parallel under Kiro Crew;
each lane runs in its own git worktree and branch. The checked-in
`contract/platform.contract.v0.1.json` is the only shared target.

## Stage 0 — serial spine (this commit)
One lane goes first: repo skeleton, the contract, the OpenAPI skeleton, the carrier and
VoiceSession interfaces, the conformance CLI v0, and the CI skeleton. **Nothing
parallelizes until Stage 0 merges** — every other lane imports these seams.

## Two rules that make parallelism safe
1. Lanes never edit each other's directories. A lane PR touching another lane's files is
   rejected in review.
2. Contract files are protected (`platform.contract`, OpenAPI, carrier + VoiceSession
   interfaces, steering). Touching them needs explicit owner review.

## Layout
```
contract/    platform.contract.v0.1.json + interfaces/ (protected seams)
openapi/     control-plane.v0.1.yaml (protected seam)
infra/       Lane 1 — CDK
services/    Lane 2 (api, onboarding), Lane 3 (telephony), Lane 4 (voice), Lane 5 (agentcore)
tests/       Lane 6 — harness + gates
tools/       conformance CLI (harness)
.github/     CI workflows (harness)
.kiro/       steering, hooks, per-lane specs
```

## Conformance CLI v0
```
python3 tools/conformance/conformance.py plan     # requirements -> verifiers
python3 tools/conformance/conformance.py verify   # writes tests/drift-ledger.json
python3 tools/conformance/conformance.py ledger    # print drift ledger
```

## Owner-only (agents cannot do these)
- Create the GitHub repo/remote; push `main`.
- Set branch protection, required checks, merge queue, environment approvals.
- Provide the real 110-requirement / 206-verifier contract via a contract-diff PR.
- Set AWS Budgets + Telnyx spend alerts. Hold production promotion approvals.
