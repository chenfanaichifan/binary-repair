# 112 — v3 schema on the common M1/M5 baseline; intake runs on the same branch

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Branch: `canonical/m1-m5-integration`
- Scope: integrate M5 `4c36898`'s v3 `SecurityContract` and make
  `tools/fixture_intake.py` run against it on this branch. No fixture contract
  was created. No merge to `main`, no tag, no live-success claim.

The common baseline is `canonical/m1-m5-integration`, not a second schema on the
M1 feature branch. The v3 schema is M5's file; the intake imports it.

---

## 0. Status

| Item | Status |
|---|---|
| v3 schema on baseline | **yes** — cherry-pick of `4c36898` as `708d957` |
| Second `contracts.py` | **none** — one `app/domain/contracts.py`, M5's implementation |
| `tools/fixture_intake.py` on this branch | **runs with v3** |
| CWE121 v2 hash | **`24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37`** (unchanged) |
| CWE121 matrix | **4 valid + 2 invalid**, unchanged |
| CWE416 contract | **absent** — no sentinel `invalid_*` written |
| T8.3 | **BLOCKED** |
| main / tag / live success | **no / no / no** |

---

## 1. Schema

`4c36898` (`feat(m5): add v3 no-input contract mode`) touched only
`app/domain/contracts.py` and `tests/test_contracts.py`. It was cherry-picked as
`708d957` onto the canonical baseline. The file is exactly M5's v3
implementation: `INPUT_MODES` includes `argv`, `stdin`, `none`; v3 `none`
requires no `invalid_*` and no `max_valid_input_bytes`.

CWE121 is a v2 contract with no `input_mode`; its hash is unchanged and it still
has the 4+2 matrix.

---

## 2. Intake on the same branch

`tools/fixture_intake.py` imports `SecurityContract` from that branch instead of
carrying a second schema. It enforces:

- argv/stdin: exactly **4 valid + 2 invalid**;
- none: exactly **1 valid + 0 invalid**;
- none must not ship `tests/invalid.json`, empty included;
- contract errors are `contract_schema_invalid`.

`tests/test_fixture_intake.py` covers the schema rejection of the four
`invalid_*` fields and `max_valid_input_bytes`, the empty-invalid-manifest
rejection, exact counts, and the v2 argv default.

---

## 3. Results

| Check | Result |
|---|---|
| `tests/test_fixture_intake.py` + `tests/test_contracts.py` on baseline | **74 passed** |
| Full baseline after v3 + intake | **430 passed / 2 skipped / 0 failed** (before record 113's acceptance tests; now 446) |
| M1 local checkpoint before this baseline merge (`1b08ae5`) | **425 passed / 2 skipped / 0 failed** |
| CWE121 intake | `OK (1 warning: reproduction_unverified)` |
| CWE416 intake | `FAILED (7 missing_file)` — contract still absent |

**425/2/0 is recorded as the M1 local checkpoint at `1b08ae5`**, not as the
post-baseline count. The post-baseline branch has 430 tests because it adds the
M5 v3 contract tests and the intake v3 tests. CI still needs **binutils** for
the `readelf`/`objdump` checks; the two local skips are
`ELF execution requires Linux`.

---

## 4. CWE416

`fixtures/public/CWE416_Use_After_Free__malloc_free_char_01/` still has only:

```
PROVENANCE.md
defect.json
src.c
```

No `contract.json`, no `tests/`, no sentinel `invalid_*`. When the no-input
contract is eventually created, `defect.json#trigger_case: "invalid-first"`
must be **deleted** in the same change; it must not be carried into the
no-input fixture. The intake already reports `no_input_trigger_case_present`
until it is gone.

## 5. Constraints

- T8.3 remains **blocked**.
- No merge to `main`, no tag, no live success.
- No fixture contract was created by this change.
