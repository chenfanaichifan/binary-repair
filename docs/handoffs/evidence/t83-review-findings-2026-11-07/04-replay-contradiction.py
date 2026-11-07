#!/usr/bin/env python3
"""Does the V4 adapter believe a claim of replay identity that its digests deny?

The review reported that supplying two different replay digests together with
``identical: true`` was accepted. This script checks that against the code rather
than against a summary of it, and separates the two halves of the path:

  half 1  the producer (M3's v4_harness.py). Its ``identical`` is a read-only
          property computed from the digests, so it cannot emit the contradiction.
          Checked by reading the source: a property has no setter.
  half 2  the adapter (M1's app/domain/v4.py from_v4_harness). It reads
          ``replay["identical"]`` when present and only derives the value when the
          key is missing. Fed a contradictory input, it accepts it.

Run with the M1 worktree on sys.path:

    git worktree add --detach .tmp/wt-m1c c41de41
    cd .tmp/wt-m1c && python ../../docs/handoffs/evidence/t83-review-findings-2026-11-07/04-replay-contradiction.py

Exit 0 always: it reports what the code does. The point is the output, not a
pass/fail, because the fix belongs to whoever owns that file.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HARNESS = ROOT / "docs/handoffs/evidence/cwe416-v4-2026-11-06/v4_harness.py"


def check_producer() -> None:
    print("=" * 78)
    print("half 1 — can the producer emit identical=true with differing digests?")
    print("=" * 78)
    print()
    source = HARNESS.read_text(encoding="utf-8")
    tree = ast.parse(source)

    replay_cls = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Replay":
            replay_cls = node
            break
    if replay_cls is None:
        print("  Replay class not found — this check is stale, investigate.")
        return

    fields = []
    properties = []
    for item in replay_cls.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            fields.append(item.target.id)
        if isinstance(item, ast.FunctionDef):
            decos = [ast.unparse(d) for d in item.decorator_list]
            if "property" in decos:
                properties.append((item.name, decos))

    print(f"  dataclass fields : {fields}")
    print(f"  properties       : {[p for p, _ in properties]}")
    print()

    identical = dict(properties).get("identical")
    if identical and "property" in identical:
        print("  identical is a @property: computed from digests, never stored.")
        print("  There is no setter, so no caller can set it to True. The value the")
        print("  producer writes into JSON is therefore derived, not asserted.")
    else:
        print("  identical is NOT a property — the producer could be handed a value.")
    print()

    body = [n for n in ast.walk(replay_cls) if isinstance(n, ast.FunctionDef)
            and n.name == "identical"]
    if body:
        print("  source:")
        snippet = ast.get_source_segment(source, body[0])
        for line in (snippet or "").splitlines():
            print(f"    {line}")
    print()


def check_adapter() -> None:
    print("=" * 78)
    print("half 2 — does the adapter accept identical=true with differing digests?")
    print("=" * 78)
    print()

    sys.path.insert(0, ".")
    try:
        from app.domain.v4 import from_v4_harness
    except Exception as exc:  # pragma: no cover - depends on the worktree
        print(f"  cannot import app.domain.v4 ({exc}); run from the M1 worktree.")
        return

    real = json.loads(
        (ROOT / "T8.3-evidence-2026-11-06/v4/harness-output.json").read_text(encoding="utf-8")
    )
    print(f"  baseline (the shipped harness output):")
    print(f"    replay.digests   : {real['replay']['digests']}")
    print(f"    replay.identical : {real['replay']['identical']}")
    print()

    tampered = json.loads(json.dumps(real))
    tampered["replay"]["digests"] = ["a" * 64, "b" * 64]
    tampered["replay"]["identical"] = True

    print("  tampered input:")
    print(f"    replay.digests   : {tampered['replay']['digests']}")
    print(f"    replay.identical : {tampered['replay']['identical']}   <- the lie")
    print()

    try:
        evidence = from_v4_harness(tampered)
    except Exception as exc:
        print(f"  rejected: {type(exc).__name__}: {exc}")
        print()
        print("  RESULT: the contradiction was refused. Nothing further to report.")
        return

    print("  ACCEPTED. The adapter produced evidence with:")
    print(f"    replay.runs      : {evidence.replay.runs}")
    print(f"    replay.identical : {evidence.replay.identical}")
    print(f"    replay.evidence_sha256: {evidence.replay.evidence_sha256}")
    print()
    print("  So the adapter trusts the producer's claim of identity instead of")
    print("  deriving it. app/domain/v4.py:287-289:")
    print()
    print('      identical = bool(')
    print('          replay.get("identical", runs >= 2 and len(set(digests)) == 1)')
    print('      )')
    print()
    print("  The default argument is only evaluated when the key is absent, so a")
    print("  present-but-false claim wins over the digests.")
    print()
    print("  What this is and is not:")
    print("    is      a converter that can carry a claim its own data denies")
    print("    is not  a gate bypass on its own: the adapter adds no verified_by, so")
    print("            a bundle built from this still reads V4 not_run (record 126)")
    print()
    print("  Minimal fix, in the file that owns it:")
    print()
    print("      derived = runs >= 2 and len(set(digests)) == 1")
    print("      declared = replay.get(\"identical\", derived)")
    print("      if bool(declared) != derived:")
    print("          raise V4EvidenceError(")
    print("              f\"replay.identical={declared} contradicts digests={digests}\")")
    print("      identical = derived")
    print()
    print("  Deriving and rejecting a contradiction beats defaulting: a producer")
    print("  that says true is then either redundant or wrong, never trusted.")


def main() -> int:
    check_producer()
    check_adapter()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
