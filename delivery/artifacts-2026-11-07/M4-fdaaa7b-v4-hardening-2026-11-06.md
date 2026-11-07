# M4 — fdaaa7b V4 hardening verification (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** the five requested V4 rejection shapes at `fdaaa7b`. No code change,
no gate promotion, no merge, no tag.

---

## 0. Verdict

**All five requested shapes are rejected at `fdaaa7b`; a valid base is still
accepted.**

| # | Shape | Result |
|---|---|---|
| 1 | `cases=1` + `known_* = True` | **REJECTED** — `cases >= 2` required |
| 2 | `known_bad_rejected=True` + `failed=0` | **REJECTED** — `failed >= 1` required |
| 3 | `complete=True` + `unexplored` non-empty | **REJECTED** |
| 4 | `complete=True` + `unknown > 0` | **REJECTED** |
| 5 | `claimed_scope="binary-level proof"` | **REJECTED** — `Literal["model"]` |
| + | valid base (positive control) | **ACCEPTED** |
| — | 124 outcome | **`inconclusive` / `required_check_not_run` / `symbolic`** |

This closes the residual from the prior review, where `cases=1` with all
`known_*` true was still accepted in the working tree. At `fdaaa7b` the
hardening is **committed** and the counts are cross-checked.

---

## 1. Commit and tree state

```text
fdaaa7bd8141cf53893e772698c2221387404651
feat(m1): harden typed V4 calibration and accounting
git status --short: (empty)
```

Changed: `app/domain/v4.py` (+25), `tests/test_v4_evidence.py` (+71),
`tests/integration/test_v4_bundle_gate.py`, `tests/integration/test_worker.py`,
`docs/handoffs/125-…`.

---

## 2. What the committed validators do

`Calibration._counts`:

```python
if self.cases < 2:
    raise ValueError("calibration requires cases >= 2")
if self.passed + self.failed > self.cases:
    raise ValueError("calibration passed+failed exceeds cases")
if not (self.known_good and self.known_bad and self.known_bad_rejected):
    raise ValueError("calibration requires known_good, known_bad and known_bad_rejected")
if self.known_good and self.passed < 1:
    raise ValueError("known_good requires passed >= 1")
if self.known_bad_rejected and self.failed < 1:
    raise ValueError("known_bad_rejected requires failed >= 1")
```

`ExplorationAccounting._complete_has_no_unexplored` rejects
`complete=True` with non-empty `unexplored`.

`SolverAccounting._step_cap` rejects `steps >= max_steps`, and rejects
`complete=True` with `unknown != 0` or `timeouts != 0`.

`V4Evidence`:

```python
claimed_scope: Literal["model"]
...
if not any("binary-level" in item.lower() for item in self.not_claimed):
    raise ValueError("not_claimed must explicitly exclude binary-level proof")
```

---

## 3. Probe results at `fdaaa7b`

```text
valid base: ACCEPTED
cases=1, passed=1, failed=0 (no known_*): REJECTED — 3 validation errors
cases=1, passed=1, failed=0 + known_* true: REJECTED — 1 validation error
known_bad_rejected=True + failed=0 (cases=2): REJECTED — 1 validation error
complete=True + unexplored nonempty: REJECTED — 1 validation error
complete=True + unknown>0: REJECTED — 1 validation error
claimed_scope="binary-level proof": REJECTED — 1 validation error
not_claimed without binary-level: REJECTED — 1 validation error
```

The valid base uses `cases=4, passed=3, failed=1, known_good/known_bad/
known_bad_rejected=true`, `unexplored=[]`, `unknown=0`, `steps=10 < max_steps=100`,
`claimed_scope="model"`, and `not_claimed=["binary-level proof"]` — accepted, so
the hardening is not a blanket rejection.

---

## 4. Tests

```text
tests/test_v4_evidence.py
tests/test_orchestration_required.py
tests/integration/test_v4_bundle_gate.py
tests/integration/test_cwe416_124_ingest.py
→ 34 passed
```

The required lock from `f57a051` still holds; V2/V4 cannot be made optional.

---

## 5. 124 — unchanged

```text
V2 passed 5/5; V4 not_run; all required
outcome = inconclusive
reason  = required_check_not_run
failing = symbolic
```

The V4 hardening changes **what would be accepted if V4 passed**; it does not
change 124, whose V4 is `not_run`. 124 stays at this conclusion until a
legitimate V4 exists.

---

## 6. Record 118 and T8.3

`118 = VERIFIED (rebuild evidence package)` remains independent: it does not
promote V0–V5, does not produce a candidate, and does not relieve T8.3.
T8.3 stays **BLOCKED**.

---

## 7. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 8. Evidence

| File | Content |
|---|---|
| `M4-fdaaa7b-v4-evidence-2026-11-06.txt` | commit identity, clean status, validator lines, probe output, 34 tests, 124 outcome |
| `probe_v4_hardening.py` | the eight-shape probe |
| `_m4-verify/fdaaa7b/` | clean archive of the commit used for all runs |
