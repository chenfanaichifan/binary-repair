#!/usr/bin/env python3
"""Offline evaluator for the BinaryRepair assistant's FAQ + state guidance.

Run from the workbench root:
    python tools/eval_assistant_faq.py

This checks retrieval, state resolution and action mapping without calling a
model or using an API key. Add --json to print machine-readable results.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.workbench_assistant import guidance_context  # noqa: E402


def run() -> tuple[int, list[dict]]:
    cases = json.loads((ROOT / "evals" / "assistant_faq_cases.json").read_text(encoding="utf-8"))
    results = []
    failures = 0
    for case in cases:
        guidance = guidance_context(case["message"], case.get("state"))
        answers = " ".join(item["answer"] for item in guidance["faq"])
        resolved = guidance["state"]
        expect = case.get("expect", {})
        problems = []
        expected_next = expect.get("next_action")
        if expected_next and resolved["next_action"] != expected_next:
            problems.append(f"next_action={resolved['next_action']} expected={expected_next}")
        expected_action = expect.get("action_type")
        actual_action = (resolved.get("action") or {}).get("type")
        if expected_action and actual_action != expected_action:
            problems.append(f"action={actual_action} expected={expected_action}")
        expected_advisory = expect.get("advisory")
        actual_advisory = (guidance.get("advisory") or {}).get("recommendation")
        if expected_advisory and actual_advisory != expected_advisory:
            problems.append(f"advisory={actual_advisory} expected={expected_advisory}")
        expected_schema = expect.get("packet_schema")
        actual_schema = (guidance.get("packet") or {}).get("schema")
        if expected_schema and actual_schema != expected_schema:
            problems.append(f"packet={actual_schema} expected={expected_schema}")
        if expect.get("readonly") and (guidance.get("packet") or {}).get("allowed_writes") is not False:
            problems.append("packet is not read-only")
        for needle in expect.get("answer_contains", []):
            if needle not in answers:
                problems.append(f"answer missing {needle!r}")
        if problems:
            failures += 1
        results.append({
            "id": case["id"],
            "ok": not problems,
            "stage": resolved["stage"],
            "next_action": resolved["next_action"],
            "action": actual_action,
            "advisory": actual_advisory,
            "problems": problems,
        })
    return failures, results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    failures, results = run()
    if args.json:
        print(json.dumps({"total": len(results), "failed": failures, "results": results}, ensure_ascii=False, indent=2))
    else:
        for item in results:
            mark = "PASS" if item["ok"] else "FAIL"
            print(f"{mark} {item['id']}  stage={item['stage']}  next={item['next_action']}")
            for problem in item["problems"]:
                print(f"      - {problem}")
        print(f"\n{len(results) - failures}/{len(results)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
