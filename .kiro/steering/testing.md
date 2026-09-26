# Testing (steering)

**Protected file.** Editing steering requires owner review.

## "Done" is verifier evidence, not agent say-so
The contract states intent; tests observe reality; agents close the gap. A step is done
only when its verifier evidence passes.

## Quality ratchet (floors only move UP)
- Coverage floor
- Mutation-score minimum
- Share of the contract's 206 verifiers passing

Lowering any floor is a **protected-file change requiring owner review.**

## Conformance + drift
- The conformance CLI (`tools/conformance/conformance.py`) compiles contract items into
  verifiers and records a **drift ledger** on every `verify`.
- A failed conformance check auto-files a repair task on the owning lane.
- Each seam ships with contract tests; a lane that drifts fails its OWN CI before it
  can break a neighbor.

## Test-credential-only rule
CI, previews and agent environments use test credentials only. Telnyx integration tests
run single-concurrency against one shared test Call Control app and a small number pool.

## Nightly full e2e (staging, before any promotion)
Sub-10-minute onboarding drill ending in a real demo call; a scored voice session; a
copilot confirm-before-mutate check; a blocked-unapproved-mutation test.
