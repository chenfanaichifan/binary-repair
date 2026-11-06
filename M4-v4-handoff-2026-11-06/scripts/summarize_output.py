#!/usr/bin/env python3
"""Print the one-screen summary of a harness output file.

    python3 summarize_output.py /path/to/harness-output.json

Used while assembling the environment evidence; not part of the harness. The
last three lines are derived from the case list rather than read from the file,
because harness-output.json records per-case measurements and leaves the
calibration verdict to M1's adapter. The line is labelled `derived` so nobody
mistakes it for a field.
"""

import json
import sys
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else "harness-output.json")
data = json.loads(path.read_text(encoding="utf-8"))

for case in data["cases"]:
    solver = case["solver"]
    calls = " ".join(f"{k}={v}" for k, v in sorted(solver.items()))
    print(
        "  {id:<10} {expected:<9} -> {observed:<9} {calls:<34} steps={steps}/{max_steps}".format(
            calls=calls,
            **{k: case[k] for k in ("id", "expected", "observed", "steps", "max_steps")},
        )
    )

print(
    "  complete={complete} unexplored={unexplored} unknown={unknown} "
    "timeouts={timeouts}".format(**data)
)
print("  solver totals: {calls}".format(
    calls=" ".join(f"{k}={v}" for k, v in sorted(data["solver"].items()))
))
print(
    "  claimed_scope={claimed_scope} replay runs={runs} identical={identical}".format(
        claimed_scope=data["claimed_scope"],
        runs=data["replay"]["runs"],
        identical=data["replay"]["identical"],
    )
)

by_kind = {case["kind"]: case for case in data["cases"]}
good = by_kind.get("known_good")
bad = by_kind.get("known_bad")
print(
    "  derived: known_good_holds={} known_bad_rejected={}".format(
        good is not None and good["observed"] == good["expected"] == "holds",
        bad is not None and bad["observed"] == bad["expected"] == "violated",
    )
)
