# M4 — V4 attributes, negative-control design, and harness output (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** V4 data-model attributes and negative-control design, then the harness
output. No code change, no gate promotion, no merge, no tag.

---

## 0. Verdict

| Item | Result |
|---|---|
| V4 is **model-level**, not binary-level | **CONFIRMED** — `scope: Literal["model"]`; `scopes.py` maps symbolic → model |
| 124 `claimed_scope` | **safe** — `null`; `not_claimed` explicitly excludes binary-level proof |
| `claimed_scope` as a model field | **not constrained** — free string; a future pass could overclaim |
| Negative-control design | **not structurally enforced** — `Calibration` allows zero negative cases; `complete=True` can coexist with `unexplored`/`unknown`/`timeouts` |
| V4 harness output | **none exists** — 124 has only the `not_run` stub; the P4 manifest is a gate-4 harness, not V4 |
| 124 outcome | **`inconclusive` / `required_check_not_run` / `symbolic`** — unchanged |

So: the **scope** is correctly model-level; the **claim text** and **negative
control** are the two places where the typed model can still be over-read. The
124 artifact itself does not overclaim, because it is `not_run` with
`claimed_scope: null`.

---

## 1. V4 attributes — what the typed model enforces

`app/domain/v4.py` (`V4Evidence`):

| Attribute | Enforcement |
|---|---|
| `schema_version=1`, `gate="V4"`, `kind="symbolic"` | literals |
| `scope: Literal["model"]` | **cannot be binary-level** |
| `state: Literal["passed"]`, `ran: Literal[True]` | only a passed claim is representable |
| `candidate_sha256`, `original_sha256` | 64-hex; optional binding check against the attempt |
| `tool_versions` | non-empty dict; no empty names/values |
| `preconditions`, `memory_predicates` | non-empty lists |
| `forbidden_ranges` | non-empty; `start < end`, `reason` non-empty |
| `hooks` | non-empty |
| `exploration_accounting` | `states_explored`, `states_pruned`, `max_depth`, `complete`, `unexplored` |
| `solver_accounting` | `engine`, `version`, `queries ≥ 1`, `sat`, `unsat`, `unknown`, `timeouts`, `complete` |
| `calibration` | `suite`, `cases ≥ 1`, `passed`, `failed`, `complete`; `passed + failed ≤ cases` |
| `replay` | `command`, `runs ≥ 2`, `identical`, `evidence_sha256` |
| `claimed_scope` | **free string, `min_length=1`** |
| `not_claimed` | non-empty list |

The `model_validator` rejects incomplete exploration/solver/calibration, a
non-identical replay, empty tool versions, and hash mismatches. That is a real
improvement over a hash-only pass.

---

## 2. Negative-control design — the gap

The design intent (record 62 §3) is “the original violation is found, and a
deliberately defective candidate is rejected”. The typed model only records
aggregate calibration counters:

```python
class Calibration:
    suite: str
    cases: int          # >= 1
    passed: int         # >= 0
    failed: int         # >= 0
    complete: bool
    # validator: passed + failed <= cases
```

Consequences:

1. **No negative case is required.** `cases=1, passed=1, failed=0,
   complete=True` validates. Nothing forces a known-bad candidate to be
   rejected.
2. **`complete` is producer-declared.** `ExplorationAccounting.complete=True`
   with `unexplored=["…"]` still validates; the validator never checks that
   `unexplored == []`.
3. **Solver unknowns are not disqualifying.** `SolverAccounting.complete=True`
   with `unknown > 0` or `timeouts > 0` still validates, although record 62 says
   unknown/timeout stay inconclusive.

So the **negative-control and “complete” claims are not structurally enforced**.
They are honest-producer fields. A V4 `passed` could be built on a calibration
with no negative case and on exploration that lists unexplored states.

**Recommendation:** require at least one known-bad/negative case and one
known-good case (or explicit `negative_cases`/`positive_cases`), and make
`complete` imply `unexplored == []`, `unknown == 0`, `timeouts == 0` — or reject
the inconsistency. Until then, treat these fields as claims, not proofs.

---

## 3. `claimed_scope` — the overclaim gap

```python
scope: Literal["model"] = "model"       # protected
claimed_scope: str = Field(min_length=1)  # free text
```

The **scope field** and the obligation row are model-level and cannot become
binary-level (`scope_for_kind("symbolic") == "model"`). But `claimed_scope` is a
free string: a passed artifact could say `"binary-level proof"` and still
validate. `not_claimed` is also free; there is no requirement to include
“binary-level proof” or “machine code”.

**124 is safe:** its stub has `claimed_scope: null` and `not_claimed` explicitly
lists `"binary-level proof of the repair"` and `"memory-safety for any path
other than the single no-input observation"`. Since `state: not_run`, the typed
validator is not even invoked.

**Recommendation:** constrain `claimed_scope` to a model-level enum (or reject
substrings like “binary”, “machine code”, “proof of the binary”), and require
`not_claimed` to include the binary-level exclusion. The current artifact is
fine; the model is not.

---

## 4. Harness output — there is none for V4

| Artifact | What it is | V4 relevance |
|---|---|---|
| 124 `v4-symbolic.json` | `state: not_run`, `ran: false`, `claimed_scope: null` | **the only V4 artifact; not a run** |
| `_m3-run/docs/handoffs/evidence/P4/harness-manifest.json` | gate-4 round-trip harness (jobwrap, gate4.conf, original/roundtrip) | **no V4 entry; not a V4 harness** |
| 126 decision | explicitly rejects hand-running a V4 harness as evidence | no V4 output authorized |

Record 126 is explicit: the writer hardcodes `"V4": "not_run"`, no code assigns
V4 from an artifact, and a hand-run harness has no bundle field to land in. So a
V4 harness output **does not exist** in 124, and a hand-run result would not be
admissible even if it were perfect. `P4` must not be repurposed as V4.

V4 therefore stays `not_run`; the absence of harness output is consistent with
the data model, not an omission to paper over.

---

## 5. 124 — unchanged

```text
V2 passed 5/5; V4 not_run; all required
outcome = inconclusive
reason  = required_check_not_run
failing = symbolic
```

124 stays at this conclusion until a **legitimate** V4 exists: a committed
Route B payload, a producer that derives V4 from a real run, a writer that reads
it, and complete accounting — then M4 replay on the same candidate. None of that
is present.

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
| `M4-v4-attributes-evidence-2026-11-06.txt` | V4 fields, calibration/exploration/solver shapes, 124 stub, P4 manifest check, 124 outcome |
| `_m4-verify/67b3458/app/domain/v4.py` | the typed model under review |
| `_m3-run/docs/handoffs/evidence/P4/harness-manifest.json` | the gate-4 harness, not V4 |
