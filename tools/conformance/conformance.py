#!/usr/bin/env python3
"""Conformance CLI v0 — 1145cx harness lane.

Compiles contract items into a verifier plan and records a drift ledger.
"Done" means verifier evidence passes, not that an agent says it finished:
the contract states intent, tests observe reality, agents close the gap.

v0 scope (Stage 0):
  - `plan`   : read contract, list requirements -> verifiers.
  - `verify` : run verifiers (v0 has none wired yet) and emit a drift ledger
               entry for every declared-but-unproven verifier.
  - `ledger` : print the current drift ledger.

Generated verifier packages are CI-produced; this file is the compiler, not
hand-edited test output.  Gate definitions here are owned by the harness lane
only — other lanes contribute fixtures, never edit this.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = REPO / "contract" / "platform.contract.v0.1.json"
LEDGER = REPO / "tests" / "drift-ledger.json"


def _load_contract() -> dict:
    if not CONTRACT.exists():
        sys.exit(f"contract not found: {CONTRACT}")
    return json.loads(CONTRACT.read_text())


def _verifiers(contract: dict) -> list[dict]:
    out = []
    for req in contract.get("requirements", []):
        for v in req.get("verifiers", []):
            out.append({"requirement": req["id"], "lane": req.get("lane"), "verifier": v})
    return out


def cmd_plan(_args) -> int:
    contract = _load_contract()
    vs = _verifiers(contract)
    print(f"contract {contract.get('contractVersion')} — "
          f"{len(contract.get('requirements', []))} requirements, {len(vs)} verifier refs")
    for v in vs:
        print(f"  [{v['lane']:>10}] {v['requirement']} -> {v['verifier']}")
    meta = contract.get("meta", {})
    print(f"\ntarget at full contract: {meta.get('targetRequirementCount')} reqs / "
          f"{meta.get('targetVerifierCount')} verifiers")
    return 0


def cmd_verify(_args) -> int:
    """v0: no verifiers are wired yet, so every one is UNPROVEN -> drift."""
    contract = _load_contract()
    vs = _verifiers(contract)
    entries = []
    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    for v in vs:
        entries.append({
            "ts": now,
            "requirement": v["requirement"],
            "lane": v["lane"],
            "verifier": v["verifier"],
            "status": "UNPROVEN",
            "detail": "v0: verifier not yet implemented by owning lane",
        })
    LEDGER.write_text(json.dumps({"generatedAt": now, "entries": entries}, indent=2) + "\n")
    proven = 0
    print(f"verified: {proven}/{len(vs)} proven; {len(vs)} drift entries written to "
          f"{LEDGER.relative_to(REPO)}")
    # v0 exits non-zero when anything is unproven, so CI shows red until lanes close the gap.
    return 0 if not entries else 1


def cmd_ledger(_args) -> int:
    if not LEDGER.exists():
        print("no drift ledger yet — run `conformance verify`")
        return 0
    data = json.loads(LEDGER.read_text())
    print(f"drift ledger — generated {data.get('generatedAt')}")
    for e in data.get("entries", []):
        print(f"  {e['status']:>8}  [{e['lane']}] {e['requirement']} {e['verifier']}: {e['detail']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="conformance", description="1145cx conformance CLI v0")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan", help="list requirements -> verifiers").set_defaults(fn=cmd_plan)
    sub.add_parser("verify", help="run verifiers, write drift ledger").set_defaults(fn=cmd_verify)
    sub.add_parser("ledger", help="print current drift ledger").set_defaults(fn=cmd_ledger)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
