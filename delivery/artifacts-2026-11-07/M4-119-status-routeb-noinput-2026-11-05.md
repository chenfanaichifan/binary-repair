# M4 — record 119 still rejected; Route B no-input V3 exists but is uncommitted (2026-11-05)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** status update only. No acceptance of record 119, no gate promotion, no
merge, no tag, no live success.

---

## 0. Status

| Item | Status |
|---|---|
| Record 119 contract | **NOT PASS** — unchanged (`schema_version: 2`, `input_mode: none`, `invalid_exit_code: 0`) |
| `_noinput` fixture directory | **absent** — record 119 is the only copy of the contract JSON |
| Route B no-input V3 | **implemented in uncommitted work**; tests pass; not accepted |
| Four end-to-end checks | **DEFERRED** until M3 ships a real `v3 none` contract/fixture |
| CWE121 v2 hash | **PASS — `24bfe568…4e37`** |

I did **not** verify record 119 “as decided”. The shipped bytes still fail.

---

## 1. Record 119 — still the same failure

```text
schema_version : 2
input_mode     : none
invalid_*      : {"invalid_exit_code": 0}
```

- as written → `unknown contract fields: ['input_mode']`;
- flipping to `schema_version: 3` → `unknown contract fields: ['invalid_exit_code']`;
- only v3 + removing `invalid_exit_code` loads (probe hash `c1684f15…`, not an
  accepted contract).

The `_noinput` fixture directory described by record 119 is not present, so
intake cannot be re-run against it here.

---

## 2. New (uncommitted) Route B no-input V3 work

`_m1-work/live-bridge` now has staged working-tree changes:

```text
 M routeb/attempt_writer.py
 M routeb/executor.py
 M routeb/run_manifest_compare.py
 M routeb/run_manifest_repaired.py
?? routeb/contract_mode.py
```

What they do:

- `routeb/contract_mode.py` loads the contract through
  `SecurityContract.from_dict`, so a contract the schema rejects is rejected
  before V3 runs. It rejects record 119's contract with
  `unknown contract fields: ['input_mode']`.
- `run_manifest_compare.py` and `run_manifest_repaired.py` handle
  `input_mode=none` as **exactly one valid case, zero invalid**:
  `invalid: "not_applicable"`, `valid: "1/1"` (or `0/1`).
- tests: `test_no_input_compare_is_one_of_one`,
  `test_no_input_compare_rejects_an_invalid_manifest`;
  `tests/test_run_manifest_compare.py` → **5 passed**.

This is progress on the V3 layer, but it is **uncommitted** and has not been run
against a valid `v3 none` fixture. It does not change the four checks yet.

---

## 3. Four checks — still deferred

| # | Check | Current state |
|---|---|---|
| 1 | `invalid_*` structurally absent | schema enforces it; **M3 contract still violates it** |
| 2 | no sentinel | schema rejects sentinels; **M3 contract still has `invalid_exit_code: 0`** |
| 3 | V3 exactly **1/1** | Route B code implements it (uncommitted); no valid fixture to run it on |
| 4 | CWE121 v2 hash unchanged | **PASS — `24bfe568…4e37`** |

The blocker is now **M3's contract/fixture**, not the V3 code.

---

## 4. What M3 must change

1. `schema_version: 3`;
2. keep `input_mode: "none"`;
3. remove `invalid_exit_code` (and any other `invalid_*` /
   `max_valid_input_bytes`);
4. ship the `_noinput` fixture (it is absent today);
5. then V3 can be run against it.

---

## 5. Record 118 and T8.3

- `118 = VERIFIED (rebuild evidence package)` remains an independent record.
- It does not relieve T8.3; T8.3 stays **BLOCKED**.

---

## 6. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 7. Evidence

| File | Content |
|---|---|
| `M4-119-status-routeb-evidence-2026-11-05.txt` | 119 bytes, adapter rejection, no-input V3 code lines, 5 tests, CWE121 hash |
| `119-contract.json` | the JSON extracted from record 119 §3 |
| `_m1-work/live-bridge/routeb/contract_mode.py` | uncommitted schema-loading adapter |
| `_m1-work/live-bridge/routeb/run_manifest_compare.py` | uncommitted no-input 1/1 path |
