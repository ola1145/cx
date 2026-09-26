# Stage 0 — Serial Spine: Requirements

Stage 0 is **serial** and must merge first. Nothing parallelizes until it does — every
other lane imports these seams.

## Deliverables (all in one serial spine PR)
1. Repo skeleton and directory tree (one directory per lane, per the ownership map).
2. `contract/platform.contract.v0.1.json` committed (the only shared target).
3. `openapi/control-plane.v0.1.yaml` — OpenAPI skeleton for the REST control plane.
4. `contract/interfaces/carrier.interface.md` — the carrier seam.
5. `contract/interfaces/voice-session.interface.md` — the VoiceSession seam.
6. `tools/conformance/conformance.py` — conformance CLI v0 (plan / verify / ledger).
7. `.github/workflows/lane-ci.yml` — CI skeleton (fast lane).
8. `.kiro/steering/{architecture,safety,testing,lanes}.md` — steering.
9. `.kiro/hooks/*.json` — PostFileSave + Stop hooks.
10. `.kiro/specs/lane-*/` — one spec per lane (requirements/design/tasks stubs).

## Acceptance
- `python3 tools/conformance/conformance.py plan` lists requirements -> verifiers.
- `python3 tools/conformance/conformance.py verify` writes a drift ledger.
- CI skeleton runs conformance + secret-scan + lane-scope-guard jobs.
- Steering and contract are marked protected.

## Owner-only follow-ups (agents cannot do these)
- Create the GitHub repo/remote and push `main`.
- Set branch protection, required checks, merge queue, environment approvals.
- Provide the real 110-requirement / 206-verifier contract via a contract-diff PR.
- Set AWS Budgets alerts and Telnyx spend alerts.
