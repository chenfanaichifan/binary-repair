"""Drive the real acceptance code with the 124 bundle's own gate-index.

No binary is executed, no symbolic engine is started, nothing is patched. The
point is to show what the pipeline *does* with a bundle whose V2 and V4 are
`not_run`, so the answer does not depend on anyone's reading of a record.

Run from the repository root.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from app.domain.acceptance import decide_attempt_outcome          # noqa: E402
from app.services.orchestration import GATES, build_obligations   # noqa: E402

BUNDLE = Path("docs/handoffs/evidence/cwe416-candidate-2026-11-05")


def verdict_for(results: dict, required: dict | None, candidate: str, contract: str):
    obligations = build_obligations(results, required=required)
    return (
        obligations,
        decide_attempt_outcome(
            obligations=obligations,
            candidate_sha256=candidate,
            expected_sha256=candidate,
            reviewed_scope_sha256=contract,
        ),
    )


def show(verdict) -> None:
    print(f"    outcome            : {verdict.outcome.value}")
    print(f"    reason             : {verdict.reason.value if verdict.reason else None}")
    print(f"    failing_obligation : {verdict.failing_obligation}")
    print(f"    detail             : {verdict.detail}")
    print(f"    is_success         : {verdict.is_success}")


def main() -> int:
    index = json.loads((BUNDLE / "gate-index.json").read_text(encoding="utf-8"))
    results = {g["gate"]: g["result"] for g in index["gates"]}
    candidate = index["candidate_sha256"]
    contract = index["contract"]["sha256"]

    print("$ python3 show_verdict.py    (repo root; no binary is executed)")
    print()
    print(f"  bundle           : {BUNDLE.as_posix()}")
    print(f"  gate-index says  : {results}")
    print(f"  candidate_sha256 : {candidate}")
    print(f"  contract sha256  : {contract}")
    print()
    print("  GATES as the service declares them (app/services/orchestration.py:24-31):")
    for gate, kind, required in GATES:
        print(f"    {gate}  kind={kind:<16} required={required}")
    print()
    print("  The worker calls evaluate_attempt without a `required` mapping")
    print("  (app/services/worker.py:305), so build_obligations() falls back to the")
    print("  third column above: every gate is required.")
    print()

    obligations, verdict = verdict_for(results, None, candidate, contract)
    print("  [A] as the bundle stands, contract untouched:")
    for o in obligations:
        print(f"      {o.kind:<16} required={str(o.required):<5} result={o.result.value}")
    show(verdict)
    print()

    print("  [B] COUNTERFACTUAL 1 — what if `interface` were not required?")
    print("      Not a result. Nothing may quote it. No file was edited.")
    obligations_b, verdict_b = verdict_for(results, {"V2": False}, candidate, contract)
    show(verdict_b)
    print()

    print("  [C] COUNTERFACTUAL 2 — neither `interface` nor `symbolic` required.")
    print("      Not a result, not a claim, and not achievable by evidence: it is a")
    print("      contract-owner edit to contract.json#required_obligations. Shown only")
    print("      to locate the two walls, i.e. to prove nothing else stands in the way.")
    _obligations_c, verdict_c = verdict_for(results, {"V2": False, "V4": False}, candidate, contract)
    show(verdict_c)
    print()

    print("  Reading:")
    print("    [A] fails on `interface`, before `symbolic` is even reached: V2 is")
    print("        `not_run` because Route B has no interface check")
    print("        (routeb/attempt_writer.py:228 — \"interface check not implemented")
    print("        in Route B executor\").")
    print("    [B] with `interface` no longer required, the attempt still fails — now on")
    print("        `symbolic`. So a hand-written V4 would move the failing obligation")
    print("        from `interface` to `symbolic`, not to success.")
    print("    [C] both disabled is the only combination that reads as success, and it")
    print("        is a contract-owner edit, not evidence. Quoting [C] as the outcome")
    print("        of this bundle would be a fabricated pass.")
    print()
    print("  Two walls, then, and neither is an evidence task. Note that [C] also says")
    print("  \"4 required obligations passed\": V0, V1, V3 and V5 are the four, which is")
    print("  exactly what this candidate does demonstrate.")
    print()
    print("  And: no code path reads v4-symbolic.json, v2-interface.json or")
    print("  gate-index.json (see 02-readers.txt). A V4 file, real or invented, has no")
    print("  route into a verdict at all.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
