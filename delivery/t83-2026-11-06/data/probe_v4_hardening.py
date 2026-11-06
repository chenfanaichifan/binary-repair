import copy
import sys

from app.domain.v4 import validate_v4_evidence

HARDENED = sys.argv[1] == "hardened"


def base(known=True):
    cal = {
        "suite": "known-safe/known-bad",
        "cases": 4,
        "passed": 3,
        "failed": 1,
        "complete": True,
    }
    if known:
        cal.update(known_good=True, known_bad=True, known_bad_rejected=True)
    return {
        "schema_version": 1,
        "gate": "V4",
        "kind": "symbolic",
        "scope": "model",
        "state": "passed",
        "ran": True,
        "candidate_sha256": "b" * 64,
        "original_sha256": "c" * 64,
        "tool_versions": {"angr": "10.0.4.post1", "z3": "5.1.0"},
        "preconditions": ["no ASLR"],
        "memory_predicates": ["data points to a freed chunk"],
        "forbidden_ranges": [{"start": 0, "end": 64, "reason": "freed object"}],
        "hooks": ["after free", "before read"],
        "exploration_accounting": {
            "states_explored": 12,
            "states_pruned": 3,
            "resource_pruned": 1,
            "max_depth": 8,
            "complete": True,
            "unexplored": [],
        },
        "solver_accounting": {
            "engine": "z3",
            "version": "5.1.0",
            "queries": 12,
            "sat": 1,
            "unsat": 11,
            "unknown": 0,
            "eval": 0,
            "timeouts": 0,
            "steps": 10,
            "max_steps": 100,
            "complete": True,
        },
        "calibration": cal,
        "replay": {
            "command": "angr replay",
            "runs": 2,
            "identical": True,
            "evidence_sha256": "a" * 64,
        },
        "claimed_scope": "model",
        "not_claimed": ["binary-level proof"],
    }


def check(label, data):
    try:
        validate_v4_evidence(data)
        print(f"{label}: ACCEPTED")
    except Exception as exc:  # noqa: BLE001
        first = str(exc).splitlines()[0]
        print(f"{label}: REJECTED — {first}")


print(f"== {'hardened (working tree)' if HARDENED else 'committed fa41102'} ==")
check("valid base", base(known=HARDENED))

d = base(known=HARDENED)
d["calibration"] = {"suite": "s", "cases": 1, "passed": 1, "failed": 0, "complete": True}
check("cases=1, passed=1, failed=0 (no known_*)", d)

if HARDENED:
    d = base()
    d["calibration"] = {
        "suite": "s",
        "cases": 1,
        "passed": 1,
        "failed": 0,
        "known_good": True,
        "known_bad": True,
        "known_bad_rejected": True,
        "complete": True,
    }
    check("cases=1, passed=1, failed=0 + known_* true", d)

    d = base()
    d["calibration"] = {
        "suite": "s",
        "cases": 2,
        "passed": 2,
        "failed": 0,
        "known_good": True,
        "known_bad": True,
        "known_bad_rejected": True,
        "complete": True,
    }
    check("known_bad_rejected=True + failed=0 (cases=2)", d)

d = base(known=HARDENED)
d["exploration_accounting"]["unexplored"] = ["state-7"]
check("complete=True + unexplored nonempty", d)

d = base(known=HARDENED)
d["solver_accounting"]["unknown"] = 1
check("complete=True + unknown>0", d)

d = base(known=HARDENED)
d["claimed_scope"] = "binary-level proof"
check('claimed_scope="binary-level proof"', d)

d = base(known=HARDENED)
d["not_claimed"] = ["something else"]
check("not_claimed without binary-level", d)
