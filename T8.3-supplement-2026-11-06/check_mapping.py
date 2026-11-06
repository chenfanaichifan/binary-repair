#!/usr/bin/env python3
"""Check that the V4 property, the harness, and the contract agree with each other.

    python3 check_mapping.py                       # run from this supplement
    python3 check_mapping.py --bundle ../T8.3-evidence-2026-11-06

This is the mechanical half of `property-mapping.md`: it compares fields rather
than trusting the prose. It exits 0 only when every check holds, 1 otherwise, so
a reader can rerun it instead of reading the argument.

What it cannot check is the part that needs judgement — whether "the pointer was
freed earlier on this path" is equivalent to "the output carries allocator
residue" for this binary. That argument is written down in the markdown, with its
assumptions named, so it can be argued with.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

GATES = ["behaviour", "identity", "interface", "reproducibility", "structure", "symbolic"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path,
                    default=Path(__file__).resolve().parent.parent
                    / "T8.3-evidence-2026-11-06")
    args = ap.parse_args(argv)

    contract_path = args.bundle / "fixture/contract.json"
    harness_path = args.bundle / "v4/harness-output.json"
    for p in (contract_path, harness_path):
        if not p.is_file():
            print(f"missing: {p}", file=sys.stderr)
            return 2

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    harness = json.loads(harness_path.read_text(encoding="utf-8"))

    checks: list[tuple[str, bool, str]] = []

    def check(ok: bool, name: str, detail: str) -> None:
        checks.append((name, ok, detail))

    # 1. the harness asks about the function the contract names
    check(harness["target_entry"] == contract["target_entry"],
          "target_entry matches", contract["target_entry"])

    # 2. no-input means no-input on both sides
    check(contract["input_mode"] == "none"
          and harness["input_domain"].startswith("none:"),
          "input_mode none on both sides",
          f"contract={contract['input_mode']!r}, harness={harness['input_domain'][:38]}…")

    # 3. the property is the pointer-flow one, and says so as a field
    text = harness["property_text"].lower()
    check(harness["property_kind"] == "pointer-flow"
          and "free()" in text and "printline()" in text,
          "property is pointer-flow",
          f"{harness['property_kind']}: {harness['property_text']}")

    # 4. every hook is a call the contract allows, and all allowed calls are hooked
    hooked = [h["symbol"] for h in harness["hooks"]]
    allowed = sorted(contract["allowed_calls"])
    check(sorted(hooked) == allowed, "hooks == allowed_calls", ", ".join(sorted(hooked)))

    # 5. the calibration actually distinguishes the two binaries
    cases = {c["id"]: c for c in harness["cases"]}
    good, bad = cases.get("known_good"), cases.get("known_bad")
    check(good is not None and good["observed"] == "holds"
          and good["solver"].get("unsat") == 1,
          "known_good holds with unsat", str(good and good["solver"]))
    check(bad is not None and bad["observed"] == "violated"
          and bad["solver"].get("sat") == 1,
          "known_bad violated with sat", str(bad and bad["solver"]))

    # 6. the model scope and the empty-disjunction disclosure travel with the data
    disclosed = any("empty" in n.lower() and "disjunction" in n.lower()
                    for n in harness["not_claimed"])
    check(harness["claimed_scope"] == "model" and disclosed,
          "scope model, empty disjunction disclosed",
          f"claimed_scope={harness['claimed_scope']}")

    # 7. the contract's forbidden behaviour is what the property asks about
    forbidden = contract["forbidden_behavior"].lower()
    check("free()" in forbidden and "stdout" in forbidden,
          "forbidden_behavior mentions the free() and the output",
          contract["forbidden_behavior"][:70] + "…")

    # 8. every obligation the contract requires has a gate name
    check(sorted(contract["required_obligations"]) == sorted(GATES),
          "required_obligations are the six gates",
          ", ".join(contract["required_obligations"]))

    width = max(len(n) for n, _, _ in checks)
    for name, ok, detail in checks:
        print(f"  [{'ok' if ok else 'FAIL'}] {name:<{width}}  {detail}")
    failed = [n for n, ok, _ in checks if not ok]
    print()
    print(f"{len(checks) - len(failed)}/{len(checks)} mapping checks passed")
    if failed:
        for name in failed:
            print(f"  failing: {name}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
