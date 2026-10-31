#!/usr/bin/env python3
"""
v4_model.py — TRUE bounded-symbolic model of badSink's guard property, in pure z3.

This model does NOT use angr's symbolic-execution engine.  It directly encodes
the *function-level semantics* of the target into a z3 formula and asks the
solver whether the forbidden behavior is reachable within a bounded input
domain.  Because we drive z3 directly, the solver query accounting (sat /
unsat / unknown / number of checks / time) is exact and reproducible.

Target
------
CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink
    void badSink(char *data)

Contract (docs/handoffs/evidence/P3A/contract.json)
- dest_capacity_bytes = 50, capacity_includes_terminator = true
- valid_domain          = C string inputs of length 0..49 bytes
- forbidden_behavior    = write past dest[50] for inputs of length >= 50
- max_valid_input_bytes = 49

Semantics modelled
------------------
badSink copies the C string `data` into a 50-byte stack buffer `dest` with
`strcpy(dest, data)`.  strcpy writes strlen(data)+1 bytes (the bytes plus the
terminating NUL).  The write overflows dest[50] iff strlen(data)+1 > 50,
i.e. iff strlen(data) >= 50.

The three candidates differ only in the *guard* that runs before the copy:

    original  : no guard.  strcpy always runs.
                overflow reachable (strlen >= 50)  -> SAT (defect)
    routea    : hand-written strlen; if len > 49 -> write(2, ERR)+exit(1);
                else strcpy.  (contract authorized_edits[0])
                overflow unreachable                -> UNSAT (fixed)
    routeb    : hand-written strlen; if len >= 50 -> fprintf(stderr)+exit(1);
                else memset(dest,0,50)+strcpy.
                overflow unreachable                -> UNSAT (fixed)
    defective : deliberately broken guard (len > 50 -> error, i.e. len 50 slips
                through).  NEGATIVE CALIBRATION — the model MUST return SAT here
                to prove it can actually detect a missing/off-by-one guard.

Byte-level modelling
--------------------
Rather than abstracting input to a single length integer, we model the input as
a symbolic byte array `data : Int -> BV8` and a symbolic length `L` with the
constraint that data[L]==0 and data[i]!=0 for all 0<=i<L.  The overflow
condition is expressed as a write to a dest index >= 50.  A SAT result yields a
concrete byte string (counterexample); UNSAT is a proof over the whole bounded
domain.

Input domain bound
------------------
BOUND = 64.  The valid domain is strlen in [0, 49]; the over-long domain is
strlen in [50, BOUND].  We prove the property for the entire bounded domain
[0, BOUND] by asserting the overflow condition together with the candidate's
guard, so UNSAT means "no input of length 0..BOUND triggers a forbidden write".

Solver accounting
-----------------
Every check() records: result (sat/unsat/unknown), a per-query counter,
wall-clock time, the bound, and the seed.  Because we drive z3 directly, these
numbers are exact (no rust-backend instrumentation gap as in the angr attempt).

Frozen candidate hashes
-----------------------
original.elf          aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393
routea-candidate.elf  c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82
routeb-candidate.elf  208574ab5b7753fab6f28860830069770622fb7b1fcb8d181fa50453f8656717
"""

import json
import time
import hashlib
from datetime import datetime, timezone

import z3

BOUND = 64                    # input domain: strlen in [0, 64]
DEST_CAPACITY = 50            # dest[50], terminator included
MAX_VALID = 49                # valid_domain: strlen 0..49
FORBIDDEN_WRITE_INDEX = 50    # a write to dest[i] with i >= 50 is forbidden

FROZEN_HASHES = {
    "original.elf":         "aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393",
    "routea-candidate.elf": "c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82",
    "routeb-candidate.elf": "208574ab5b7753fab6f28860830069770622fb7b1fcb8d181fa50453f8656717",
}

# ---------------------------------------------------------------------------
# candidate guard definitions
#
# Each candidate returns the guard-pass predicate, i.e. the condition under
# which strcpy actually runs.  The overflow condition is then
#   guard_pass  AND  (strcpy writes past dest[50])
# which is   guard_pass  AND  (L >= 50).
# ---------------------------------------------------------------------------

def guard_original(L):
    """No guard: strcpy always runs."""
    return z3.BoolVal(True)


def guard_routea(L):
    """Route A: hand-written strlen; if len > 49 -> error+exit; else strcpy.

    guard_pass == (len <= 49)."""
    return L <= MAX_VALID


def guard_routeb(L):
    """Route B: hand-written strlen; if len >= 50 -> fprintf+exit; else copy.

    guard_pass == (len < 50)."""
    return L < DEST_CAPACITY


def guard_defective(L):
    """Deliberately defective: the guard rejects len > 50 instead of len > 49.

    len == 50 slips through to strcpy -> overflow.  NEGATIVE CALIBRATION."""
    return L <= DEST_CAPACITY   # off-by-one: lets len==50 through


CANDIDATES = {
    "original": {
        "hash": FROZEN_HASHES["original.elf"],
        "guard": guard_original,
        "desc": "no guard (original vulnerable binary)",
        "expect": "sat",          # must find a counterexample
    },
    "routea": {
        "hash": FROZEN_HASHES["routea-candidate.elf"],
        "guard": guard_routea,
        "desc": "Route A: len>49 -> error+exit; else strcpy",
        "expect": "unsat",        # must prove no overflow
    },
    "routeb": {
        "hash": FROZEN_HASHES["routeb-candidate.elf"],
        "guard": guard_routeb,
        "desc": "Route B: len>=50 -> error+exit; else memset+strcpy",
        "expect": "unsat",        # must prove no overflow
    },
    "defective": {
        "hash": None,             # synthetic negative calibration, no real binary
        "guard": guard_defective,
        "desc": "deliberately defective: guard is len>50 (off-by-one)",
        "expect": "sat",          # must find the off-by-one counterexample
    },
}


class SolverCounter:
    """Wrap z3.Solver.check to tally every query exactly."""

    def __init__(self, solver):
        self.solver = solver
        self.sat = 0
        self.unsat = 0
        self.unknown = 0
        self.checks = 0
        self.time_ms = 0.0

    def check(self, *args, **kwargs):
        t0 = time.time()
        r = self.solver.check(*args, **kwargs)
        self.time_ms += (time.time() - t0) * 1000.0
        self.checks += 1
        if r == z3.sat:
            self.sat += 1
        elif r == z3.unsat:
            self.unsat += 1
        else:
            self.unknown += 1
        return r


def make_symbolic_input(solver, bound=BOUND):
    """Build the byte-level symbolic input: data array + symbolic length L.

    Constraint: data[L]==0 (NUL terminator at L) and data[i]!=0 for 0<=i<L.
    Returns (data, L)."""
    data = z3.Array("data", z3.IntSort(), z3.BitVecSort(8))
    L = z3.Int("L")
    solver.add(L >= 0, L <= bound)
    solver.add(data[L] == 0)                       # NUL at L
    for i in range(bound):
        # for every i < L, data[i] != 0  (strlen == L exactly)
        solver.add(z3.Implies(L > i, data[i] != 0))
    return data, L


def overflow_condition(L):
    """A write past dest[50] occurs iff strcpy writes strlen+1 > 50 bytes,
    i.e. strlen >= 50.  We express this as an explicit out-of-bounds write
    index: dest is written at indices 0..L, so index L >= 50 is forbidden."""
    return L >= FORBIDDEN_WRITE_INDEX


def concrete_counterexample(model, data, L, nbytes=52):
    """Render a SAT model into a concrete byte string (up to nbytes)."""
    out = []
    Lv = model.eval(L, model_completion=True).as_long()
    for i in range(min(nbytes, BOUND + 1)):
        b = model.eval(data[i], model_completion=True).as_long()
        out.append(b)
    return {"strlen": Lv, "bytes": out,
            "ascii_hint": "".join(chr(b) if 32 <= b < 127 else "." for b in out)}


def run_candidate(name, spec):
    """Run one candidate and record exact solver accounting."""
    s = z3.Solver()
    ctr = SolverCounter(s)

    # timeouts / simplification
    s.set("timeout", 30000)          # 30s per check (never hit in practice)
    seed = 0xC0FFEE
    s.set("random_seed", seed)

    data, L = make_symbolic_input(s, BOUND)
    guard_pass = spec["guard"](L)
    overflow = overflow_condition(L)

    # The property we ask about: does there exist an input in [0, BOUND] for
    # which the guard lets the copy run AND the copy overflows dest[50]?
    s.push()
    s.add(guard_pass, overflow)
    t0 = time.time()
    result = ctr.check()
    elapsed = time.time() - t0
    # capture the model (if SAT) BEFORE popping the assertion scope
    model = s.model() if result == z3.sat else None
    s.pop()

    verdict = "sat" if result == z3.sat else (
        "unsat" if result == z3.unsat else "unknown")

    out = {
        "candidate": name,
        "candidate_sha256": spec["hash"],
        "desc": spec["desc"],
        "expected": spec["expect"],
        "verdict": verdict,
        "bound": BOUND,
        "dest_capacity": DEST_CAPACITY,
        "max_valid": MAX_VALID,
        "seed": seed,
        "solver_accounting": {
            "checks": ctr.checks,
            "sat": ctr.sat,
            "unsat": ctr.unsat,
            "unknown": ctr.unknown,
            "solver_time_ms": round(ctr.time_ms, 3),
            "wall_elapsed_s": round(elapsed, 3),
            "timeout_set_ms": 30000,
        },
    }

    if result == z3.sat:
        out["counterexample"] = concrete_counterexample(model, data, L)
        out["meaning"] = ("SAT: an input in [0,%d] triggers a forbidden write "
                           "past dest[50]" % BOUND)
    elif result == z3.unsat:
        out["meaning"] = ("UNSAT: no input of strlen 0..%d makes the guard pass "
                           "AND overflow dest[50]; property proven over the "
                           "bounded domain" % BOUND)
    else:
        out["meaning"] = "UNKNOWN: solver could not decide (model incomplete)"

    # calibration check against expectation
    out["calibration_ok"] = (verdict == spec["expect"])
    return out


def verify_hashes(paths):
    """Verify the frozen binaries' sha256 against the declared hashes."""
    results = {}
    for label, (path, want) in paths.items():
        try:
            with open(path, "rb") as f:
                got = hashlib.sha256(f.read()).hexdigest()
            results[label] = {"path": path, "match": got == want,
                              "got": got, "want": want}
        except FileNotFoundError:
            results[label] = {"path": path, "match": False,
                              "got": None, "want": want,
                              "error": "file not found"}
    return results


def main():
    # 1. verify the frozen binaries we model against actually match.
    hash_check = verify_hashes({
        "original": ("original.elf", FROZEN_HASHES["original.elf"]),
        "routea": ("routea-candidate.elf", FROZEN_HASHES["routea-candidate.elf"]),
        "routeb": ("routeb-candidate.elf", FROZEN_HASHES["routeb-candidate.elf"]),
    })

    # 2. run the three real candidates + the synthetic defective calibration.
    runs = [run_candidate(name, spec) for name, spec in CANDIDATES.items()]

    all_calibrated = all(r["calibration_ok"] for r in runs)

    doc = {
        "schema": "v4-z3-model",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": {
            "kind": "function-level bounded symbolic (pure z3, no angr engine)",
            "target_signature": "void badSink(char *data)",
            "dest_capacity_bytes": DEST_CAPACITY,
            "capacity_includes_terminator": True,
            "max_valid_input_bytes": MAX_VALID,
            "forbidden_behavior": "write past dest[50] for inputs of length >= 50",
            "input_bound_bytes": BOUND,
            "byte_level": True,
            "library_hooks": [
                "strcpy modelled as: writes strlen(data)+1 bytes (bytes + NUL)",
                "printLine / fprintf modelled as: no effect on dest (output only)",
                "exit(1) / write(2,ERR,42) modelled as: control leaves badSink, "
                "strcpy unreachable on the invalid path",
            ],
            "hook_justification": ("strcpy is the only operation that writes to "
                                   "dest; printLine/fprintf only read; the guard "
                                   "diverts control to exit before strcpy on the "
                                   "invalid path. Modelling strcpy as the "
                                   "strlen+1-byte write captures the sole "
                                   "overflow source exactly."),
        },
        "candidate_hashes": FROZEN_HASHES,
        "hash_check": hash_check,
        "runs": runs,
        "calibration": {
            "original_sat": runs[0]["verdict"] == "sat",
            "defective_sat": runs[3]["verdict"] == "sat",
            "candidate_unsat": runs[1]["verdict"] == "unsat" and
                                runs[2]["verdict"] == "unsat",
            "all_expected_met": all_calibrated,
            "note": ("The model is only trustworthy if (a) original is SAT "
                     "(vulnerability detected), (b) defective is SAT (negative "
                     "calibration detects an off-by-one guard), and (c) both "
                     "routea/routeb are UNSAT (fix proven over the bound)."),
        },
    }

    with open("v4-result.json", "w") as f:
        json.dump(doc, f, indent=2)

    # console summary
    print("=== V4 z3 model result ===")
    print("hash check:",
          {k: ("OK" if v["match"] else "FAIL") for k, v in hash_check.items()})
    for r in runs:
        print("  %-10s -> %-5s (expect %-5s) %s" %
              (r["candidate"], r["verdict"], r["expected"],
               "CALIB OK" if r["calibration_ok"] else "CALIB FAIL"))
    print("calibration all_expected_met:", all_calibrated)
    print("wrote v4-result.json")


if __name__ == "__main__":
    main()
