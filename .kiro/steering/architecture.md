# Architecture (steering)

**Protected file.** Editing steering requires owner review (propose via PR; only the owner merges).

## Frozen decisions
- REST control plane stays; **no GraphQL** (19 Sep).
- **Telnyx** is the default carrier; **Twilio** is failover behind one carrier interface.
  **Amazon Connect** stays out of the DID path.
- Backend and non-UI only. PWA dashboard and admin console are a later, separate lane.

## Five contract-first seams (decouple every lane)
1. `contract/platform.contract.v0.1.json`
2. `openapi/control-plane.v0.1.yaml`
3. `contract/interfaces/carrier.interface.md`
4. `contract/interfaces/voice-session.interface.md`
5. `tools/conformance` generated verifier package

A lane codes against the seam, never against another lane's internals.

## Ownership map (Rule 1: lanes never edit each other's directories)
| Lane | Owns |
|------|------|
| Infra / CDK | `infra/` |
| API + lifecycle | `services/api`, `services/onboarding` |
| Telephony | `services/telephony` |
| Voice | `services/voice` |
| AgentCore | `services/agentcore` |
| Harness + CI | `tests/`, `contract/` tooling, `.github/workflows` |
