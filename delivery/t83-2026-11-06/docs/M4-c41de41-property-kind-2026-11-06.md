# M4 — c41de41 explicit property_kind verification (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** the four `property_kind` checks at `c41de41`. No gate promotion, no
merge, no tag.

---

## 0. Verdict

**All four requested behaviours hold at `c41de41`.**

| # | Check | Result |
|---|---|---|
| 1 | missing `property_kind` | **REJECTED** — `v4_harness output cannot be converted: 'property_kind'` |
| 2 | `pointer-flow` + empty ranges | **ACCEPTED** — `kind=pointer-flow, ranges=None` |
| 3 | `memory-range` + empty ranges | **REJECTED** |
| 4 | text containing “pointer” no longer affects classification | **PASS** — text says pointer + `memory-range` → **REJECTED**; text omits pointer + `pointer-flow` → **ACCEPTED** |
| — | 124 outcome | **`inconclusive` / `required_check_not_run` / `symbolic`** |

---

## 1. Commit

```text
c41de418d72168b963f0ecdb294bfef0de3149cf
fix(m1): require explicit property_kind from the V4 harness
git status --short: (empty)
```

Changed: `app/domain/v4.py` (−4/+2 lines around the mapping),
`tests/fixtures/v4_harness_output.json` (+`property_kind`),
`tests/test_v4_harness_adapter.py` (+8), docs.

---

## 2. What changed

The text heuristic is gone:

```text
(no text-based property_kind inference)
```

The converter now reads the harness field directly:

```python
"property_kind": data["property_kind"],
...
"property_kind": data["property_kind"],   # preserved in source, too
```

and the model keeps:

```python
property_kind: Literal["pointer-flow", "memory-range"]
if self.property_kind != "pointer-flow" and not self.forbidden_ranges:
    raise ValueError("only pointer-flow may leave forbidden_ranges empty; "
                     "memory-range needs at least one range")
```

A missing `property_kind` raises `V4EvidenceError` in `from_v4_harness`; it is
not defaulted and not inferred.

---

## 3. Probe results

```text
missing property_kind: REJECTED - v4_harness output cannot be converted: 'property_kind'
pointer-flow + empty ranges: ACCEPTED (kind=pointer-flow, ranges=None)
memory-range + empty ranges: REJECTED - 1 validation error for V4Evidence
text says pointer + memory-range + empty: REJECTED - 1 validation error for V4Evidence
text omits pointer + pointer-flow + empty: ACCEPTED (kind=pointer-flow, ranges=None)
```

The last two lines are the proof that classification now follows the **field**,
not the text.

---

## 4. Tests

```text
tests/test_v4_harness_adapter.py
tests/test_v4_evidence.py
tests/integration/test_cwe416_124_ingest.py
tests/integration/test_v4_bundle_gate.py
→ 42 passed
```

The three residual fixes from `e24a569` remain in force: memory-range empty
rejected, disclosure forced, all known-bad required.

---

## 5. Producer file consequence

The workspace `v4-evidence.json` still **lacks** `property_kind`, so the
committed converter now rejects it (that is check #1). M3 must add
`property_kind` to the harness output; the committed test fixture already has
`"property_kind": "pointer-flow"`.

The adapter five checks remain valid for a harness output that carries the
field; they cannot be re-run on the old producer file until M3 updates it.

---

## 6. 124 — unchanged

```text
V0 passed, V1 passed, V2 not_run, V3 passed, V4 not_run, V5 passed
outcome = inconclusive
reason  = required_check_not_run
failing = symbolic
```

The `property_kind` change is a schema tightening, not a gate result; 124's V4
is still `not_run`.

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
| `M4-c41de41-property-kind-evidence-2026-11-06.txt` | commit, clean status, explicit-field lines, four probes, 42 tests, 124 outcome |
| `probe_v4_property_kind.py` | the four-check probe |
| `_m4-verify/c41de41/` | clean archive of the commit used for all runs |
