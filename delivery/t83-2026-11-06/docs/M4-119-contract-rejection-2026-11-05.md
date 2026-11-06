# M4 — record 119 contract REJECTED; not verified “as decided” (2026-11-05)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** contract rejection only. No acceptance of record 119, no gate
promotion, no merge, no tag, no live success.

---

## 0. Verdict

**Record 119's contract does NOT pass. It is not a `v3 none` contract.**

| Check | Result |
|---|---|
| contract as written | **REJECTED** — `schema_version: 2` + `input_mode` |
| flip to `schema_version: 3` only | **REJECTED** — leftover `invalid_exit_code: 0` |
| v3 + remove `invalid_exit_code` | loads (probe only; not the shipped file) |
| intake re-run | **not possible** — the `_noinput` fixture directory is absent |
| CWE121 v2 hash | **PASS — `24bfe568…4e37`** |

I did **not** accept the record's “written as decided” framing. The bytes say
otherwise.

---

## 1. What record 119 actually ships

Record 119 describes a fixture at
`fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/`, but that
directory **does not exist** in the tree. The only contract bytes available are
the JSON embedded in record 119 §3:

```text
schema_version : 2
input_mode     : none
invalid_*      : {"invalid_exit_code": 0}
```

So the shipped document is a **v2 contract carrying a v3 field**, plus one
leftover rejection field with a sentinel value. It is neither a valid v2 contract
nor a valid v3 `none` contract.

---

## 2. Measured against the v3 schema

```text
119 as written (v2 + input_mode)
  -> ValueError: unknown contract fields: ['input_mode']

schema_version = 3 only
  -> ValueError: unknown contract fields: ['invalid_exit_code']

schema_version = 3 and invalid_exit_code removed
  -> LOADED hash=c1684f15bb1c67cb9b3d6752e4023ca670a432ceb92342f6d10d040ee17b4f7c
     rejections: all None
```

The third line is a **probe of what would be required**, not an accepted
contract and not a reviewed hash. It shows the two edits that are still missing.

Note the failure mode of line 2: for `input_mode=none`, `from_dict` uses the
mode-specific required-key set, so any `invalid_*`/`max_valid_input_bytes` key is
`unknown` — structural absence is enforced. The constructor path would reject the
same value as a sentinel. Either way, `invalid_exit_code: 0` cannot survive.

---

## 3. Intake — cannot be independently reproduced

- The `_noinput` fixture directory is absent, so `fixture_intake.py --check`
  cannot be run against it here.
- Record 119 reports its own intake findings (`missing_file src.c`,
  `missing_file tests/invalid.json`, then `too_few_valid`, `too_few_invalid`,
  `defect_trigger_unknown`). M4 did not reproduce them because the directory
  does not exist in this workspace.

---

## 4. What M3 must change

1. `schema_version: 3`.
2. keep `input_mode: "none"`.
3. remove `invalid_exit_code` (and every other `invalid_*` /
   `max_valid_input_bytes`).
4. then re-run intake; then V3.

Until then the contract is **not v3 none**, regardless of the record's title.

---

## 5. Four checks deferred until M3 rewrites it as v3 none

| # | Check | Expected evidence |
|---|---|---|
| 1 | `invalid_*` structurally absent | `to_dict()` and `from_dict()` both exclude them |
| 2 | no sentinel | any non-null rejection value is rejected, not just ignored |
| 3 | V3 exactly **1/1** no-input | one execution, zero invalid cases |
| 4 | CWE121 v2 hash unchanged | `24bfe568…4e37` |

---

## 6. Record 118 and T8.3

- `118 = VERIFIED (rebuild evidence package)` is an **independent** record.
- It does not relieve T8.3: one sample, one defect class, no second-public-sample
  obligation satisfied.
- T8.3 remains **BLOCKED**.

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
| `M4-119-contract-rejection-evidence-2026-11-05.txt` | extraction, three schema probes, CWE121 hash |
| `119-contract.json` | the JSON extracted from record 119 §3 (probe input) |
| `119-m3-cwe416-noinput-contract-2026-11-05.md` | the record under review |
