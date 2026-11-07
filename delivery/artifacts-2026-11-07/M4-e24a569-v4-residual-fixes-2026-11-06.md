# M4 — e24a569 V4 residual fixes verified (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** the three residual fixes at `e24a569`. Supersedes the earlier
working-tree preview. No gate promotion, no merge, no tag.

---

## 0. Verdict

**All three residual fixes are committed and verified; the adapter five checks
remain valid.**

| # | Residual | Result |
|---|---|---|
| 1 | `forbidden_ranges` no longer silently empty | **PASS** — `memory-range` + empty → **REJECTED**; `pointer-flow` + empty → accepted **explicitly** |
| 2 | empty-disjunction forced disclosure | **PASS** — removing the sentence → converter **re-adds** it |
| 3 | all known-bad rejected | **PASS** — one known-bad `observed="holds"` → **REJECTED** |
| + | adapter five checks | **still valid** — conversion, calibration, accounting, replay, `not_claimed` |
| — | 124 outcome | **`inconclusive` / `required_check_not_run` / `symbolic`** |

---

## 1. Commit

```text
e24a569c64b2d4bbe2654e018a152c11946a9626
feat(m1): require property_kind for empty V4 ranges and force disclosure
git status --short: (empty)
```

Changed: `app/domain/v4.py` (+106/−40), `tests/test_v4_evidence.py`,
`tests/test_v4_harness_adapter.py`, `test_v4_bundle_gate.py`,
`test_worker.py`, docs.

---

## 2. The three fixes

### 2.1 `forbidden_ranges` — explicit, not silent

```python
forbidden_ranges: list[ForbiddenRange] | None = None
property_kind: Literal["pointer-flow", "memory-range"]
...
if self.property_kind != "pointer-flow" and not self.forbidden_ranges:
    raise ValueError("only pointer-flow may leave forbidden_ranges empty; "
                     "memory-range needs at least one range")
```

Probe:

```text
converted property_kind: pointer-flow   forbidden_ranges: None
memory-range + empty ranges: REJECTED
pointer-flow + empty ranges: ACCEPTED (explicit allowance)
```

Empty is allowed **only** when `property_kind == "pointer-flow"`; a memory-range
claim without ranges is rejected.

### 2.2 Empty-disjunction — forced disclosure

```python
def _with_empty_disjunction_disclosure(not_claimed, *, cases, candidate_sha256):
    if any("empty-disjunction" in item.lower() or "empty disjunction" in item.lower()
           for item in not_claimed):
        return not_claimed
    candidate = next(case for case in cases
                     if case.get("kind") == "known_good"
                     and case.get("binary_sha256") == candidate_sha256)
    if int(candidate["solver"]["unsat"]) > 0 and int(candidate["witness"]["free_calls"]) == 0:
        return not_claimed + [EMPTY_DISJUNCTION_DISCLOSURE]
    return not_claimed
```

Probe: removing the sentence from the producer's `not_claimed` → **re-added**.
The converted file still has the sentence at index 5.

### 2.3 All known-bad rejected

```python
known_bad_rejected = bool(known_bad_cases) and all(
    c.get("observed") == "violated" for c in known_bad_cases
)
```

Probe: adding a second known-bad case with `observed="holds"` → **REJECTED**;
`known_bad_rejected` false → `Calibration` fails. One rejected known-bad is no
longer enough when another is accepted.

---

## 3. Adapter five checks — still valid

```text
claimed_scope: model
calibration: cases=2 passed=1 failed=1 known_good/known_bad/known_bad_rejected=True
exploration: initial=2 deadended=2 errored/unconstrained/deferred/active=0
             complete=True unexplored=[]
solver: engine=angr version=10.0.4.post1 queries=4 sat=1 unsat=1
        unknown=0 eval=2 timeouts=0 steps=25 max_steps=128 complete=True
replay: command=v4_harness.py runs=2 identical=True
        evidence_sha256=cb2137a2…
forbidden_ranges: None (pointer-flow)
empty-disjunction in not_claimed: True
binary-level exclusion: True
revalidate: passed
```

---

## 4. Tests

```text
tests/test_v4_evidence.py
tests/test_v4_harness_adapter.py
tests/integration/test_cwe416_124_ingest.py
tests/integration/test_v4_bundle_gate.py
→ 41 passed
```

---

## 5. Residual heuristic (not one of the three)

`property_kind` is inferred as `"pointer-flow" if "pointer" in property_text else
"memory-range"`. A pointer-flow property whose text omits “pointer” would require
ranges (conservative), while a memory-range text mentioning “pointer” could be
classified `pointer-flow` and allow empty ranges. If this matters, make
`property_kind` an explicit harness output field rather than a text heuristic.

This does not affect the three requested checks; it is the next tightening if V4
is to be relied on beyond this artifact.

---

## 6. 124 — unchanged

```text
V0 passed, V1 passed, V2 not_run, V3 passed, V4 not_run, V5 passed
outcome = inconclusive
reason  = required_check_not_run
failing = symbolic
```

The fixes change what a **V4 pass** would accept; they do not change 124, whose
V4 is `not_run`. The producer file still does not upgrade the gate.

---

## 7. Record 118 and T8.3

`118 = VERIFIED (rebuild evidence package)` remains independent: it does not
promote V0–V5, does not produce a candidate, and does not relieve T8.3.
T8.3 stays **BLOCKED**.

---

## 8. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 9. Evidence

| File | Content |
|---|---|
| `M4-e24a569-v4-residual-evidence-2026-11-06.txt` | commit, clean status, validator lines, adapter five checks, three residual probes, 41 tests, 124 outcome |
| `probe_v4_adapter.py` | adapter five-check probe |
| `probe_v4_residuals.py` | the three-residual probe |
| `_m4-verify/e24a569/` | clean archive of the commit used for all runs |
