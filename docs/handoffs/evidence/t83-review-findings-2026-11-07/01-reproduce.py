#!/usr/bin/env python3
"""Show whether the deterministic planner distinguishes CWE-121 from CWE-416.

Run from the repository root:

    python docs/handoffs/evidence/t83-review-findings-2026-11-07/01-reproduce.py

Two modes:

  (default)        report what the planner returns for the two contexts and say
                   whether the plans are the same. Exit 0 either way: it is a
                   measurement, not an assertion.
  --expect-distinct
                   exit 0 only if the two plans differ in substance. This is the
                   mode to put in a test suite once the planner is fixed; until
                   then it fails, which is the point.

Why the entry point is `app.services.assistant.generate_plan` and not
`app.domain.assistant.deterministic_plan`: the service layer is what the GUI and
the controller call, it is the one that builds a context from a job, and it is
the path a reviewer would use. Calling the domain function directly would let a
gap in the wiring hide behind a correct-looking function.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from app.services.assistant import generate_plan  # noqa: E402

CASES = [
    (
        "CWE-121",
        "CWE-121 stack-based buffer overflow: a fixed-size stack buffer is filled "
        "from a command-line argument and copied on with strcpy.",
        {"class": "CWE-121", "mechanism": "bounds-check", "input_mode": "argv",
         "bug_site": "stack", "fixture": "CWE121_src_char_declare_cpy_51b"},
    ),
    (
        "CWE-416",
        "CWE-416 use after free: a heap block is released and then read on the "
        "same path, so stdout carries allocator residue.",
        {"class": "CWE-416", "mechanism": "lifetime", "input_mode": "none",
         "bug_site": "heap", "fixture": "CWE416_Use_After_Free__malloc_free_char_01_noinput"},
    ),
]


def normalise(plan) -> dict:
    """The plan without the one field that is random by design."""
    data = plan.model_dump(mode="json")
    data.pop("plan_id", None)
    return data


def question_rows(plan) -> list[tuple[str, str, str, str | None]]:
    rows = []
    for step in plan.steps:
        for q in step.questions:
            rows.append((step.id, q.key, q.input, q.default))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect-distinct", action="store_true")
    args = ap.parse_args()

    plans = []
    for name, description, context in CASES:
        plan = generate_plan(description, context=context)
        plans.append((name, plan, context))

    print("=" * 78)
    print("the deterministic planner, called through generate_plan()")
    print("=" * 78)
    print()

    for name, plan, context in plans:
        print(f"--- {name} ---")
        print(f"  context passed in : {json.dumps(context, sort_keys=True)}")
        print(f"  mode              : {plan.mode}")
        print(f"  steps             : {len(plan.steps)}")
        for step in plan.steps:
            print(f"    {step.id:<12} kind={step.kind:<9} title={step.title!r}")
            for q in step.questions:
                print(f"      question {q.key!r}: input={q.input} "
                      f"required={q.required} ascii={q.ascii} default={q.default!r}")
        print()

    a, b = plans[0][1], plans[1][1]
    na, nb = normalise(a), normalise(b)

    print("=" * 78)
    print("do the two plans differ, once the random plan_id is removed?")
    print("=" * 78)
    identical = na == nb
    print(f"  identical: {identical}")
    print()

    rows_a, rows_b = question_rows(a), question_rows(b)
    print("  question by question:")
    print(f"    {'step':<12} {'key':<14} {'input':<9} default")
    print("    " + "-" * 68)
    for (sa, ka, ia, da), (sb, kb, ib, db) in zip(rows_a, rows_b):
        same = (sa, ka, ia, da) == (sb, kb, ib, db)
        print(f"    {ka:<12} {ka:<14} {ia:<9} {da!r}"
              f"{'' if same else '   <-- differs'}")
    print()

    if identical:
        print("  Reading: the planner returns one plan regardless of the defect class.")
        print("  The context argument is accepted and then not read — see")
        print("  app/domain/assistant.py:84, the only line in that module that")
        print("  mentions `context`, and it is the parameter list.")
        print()
        print("  Consequence for T8.3: these plans cannot carry the class contrast the")
        print("  task asks for. Two saved plans taken from this planner would be the")
        print("  same document with different ids, and calling that evidence would be")
        print("  presenting an id as a difference.")
    else:
        print("  Reading: the plans differ. Check that the difference is substantive")
        print("  (repair strategy and verification obligations), not a title.")

    print()
    print("=" * 78)
    print("what a class-specific plan would have to say")
    print("=" * 78)
    print("""
  CWE-121 (stack overflow, argv)
    identify   the destination capacity and the terminator rule
    propose    a length guard before the copy
    test       valid inputs, a boundary-length input, an oversized input
    invalid    applicable: the oversized input is the trigger case

  CWE-416 (use after free, no input)
    identify   the allocation, the release, and the read after the release
    propose    a lifetime repair (reorder, or keep cleanup and stop the later read)
    test       the no-input output, plus the pointer-flow property
    invalid    not_applicable: the entry takes no input, so there is no invalid
               input column to fill. This is the "N/A" the review asks for.

  Both still go through V0-V5 unchanged. A different plan is not a different
  acceptance standard.
""")

    if args.expect_distinct:
        if identical:
            print("RESULT: FAIL — the plans are identical, so the class contrast is absent.")
            return 1
        print("RESULT: PASS — the plans differ.")
        return 0

    print("RESULT: measured, not asserted. identical=%s" % identical)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
