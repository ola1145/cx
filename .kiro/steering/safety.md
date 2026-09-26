# Safety rails (steering)

**Protected file.** Editing steering requires owner review.

## Forbidden without owner review
- Editing steering files, `platform.contract`, CI gate definitions, branch protection, or hooks.
- Waiving, skipping, or redefining a failing check.
- Promoting anything to production.
- Marking a step passed when its tests did not actually run.

Agents implement, test, repair and resubmit. They never redefine the target, never
waive a gate, never promote. A run that tries to do any of these **stops and reports.**

## Branch protection is the real gate
Agents push lane branches (`kirocrew/task/<id>`) and open PRs. They **cannot** push to
`main`, change required checks, dismiss reviews, or modify environments — those controls
live in GitHub settings only the owner can touch.

## Credential + PII isolation
- CI, previews and every agent environment carry **test credentials only**.
- Live Telnyx/Twilio keys and production AWS secrets live in a **separate account and
  Secrets Manager path the crew cannot read**. Releasing them is a manual owner runbook step.
- Call recordings and transcripts are customer PII — redacted from logs and model traces.

## Production promotion
Always serial, always human-approved. Agents never see production credentials.
Deploy/promote steps are marked `force_approval: true` and pause for Approve/Deny even in YOLO mode.
