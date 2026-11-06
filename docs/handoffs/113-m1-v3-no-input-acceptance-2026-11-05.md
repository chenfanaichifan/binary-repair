# 113 — V3 no-input acceptance: 1/1, invalid N/A, and real byte evidence

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Branch: `canonical/m1-m5-integration`
- Scope: V3 no-input acceptance on the common baseline. No CWE416 contract, no
  fixture contract created. No merge to `main`, no tag, no live-success claim.

---

## 0. Status

| Item | Status |
|---|---|
| v3 schema on this baseline | `708d957` (M5 `4c36898`) |
| Intake on the same baseline | `1430e1e` |
| V3 no-input | **1 valid, 0 invalid, `invalid=not_applicable`, `1/1`** |
| 0 invalid recorded as 2/2 or 0/0 | **rejected** |
| CWE121 v2 | 4+2 and argv V3 semantics unchanged; hash `24bfe568…4e37` |
| CWE416 contract | **absent**; no sentinel `invalid_*` |
| T8.3 | **BLOCKED** |
| main / tag / live success | **no / no / no** |

---

## 1. The V3 rule

For `input_mode: "none"`:

- the manifest has exactly **one** valid case (`valid.json`);
- there is **no** `tests/invalid.json`; an empty file is not a substitute;
- the binary is invoked with no argv and no stdin;
- the V3 record is `passed=1`, `total=1`, `valid="1/1"`,
  `invalid="not_applicable"`.

A shape with 0 valid or 2+ valid cases, or any invalid manifest, is rejected
before a V3 record is written. It is never reshaped into `2/2`, `0/0`, or a
six-case matrix.

`app/domain/acceptance.py` is unchanged: V3 remains one required behaviour
obligation. The no-input distinction lives in the V3 evidence.

## 2. Where it lives

- `routeb/run_manifest_repaired.py` — one valid case, no args/stdin, byte compare;
- `routeb/run_manifest_compare.py` — one valid case, no invalid file;
- `routeb/contract_mode.py` — every contract goes through `SecurityContract`;
- `routeb/executor.py` — `--contract` / `--input-mode` pass-through;
- `routeb/attempt_writer.py` — runtime detail includes `1/1` and
  `invalid not applicable`.

The argv/stdin path keeps the historical 4+2 matrix and remains unchanged.

## 3. Real evidence

`docs/handoffs/evidence/V3-no-input-2026-11-05/` records one actual execution:

- one valid case, no argv, no stdin;
- exit code **0**;
- stdout bytes `4e4f5f494e5055545f4f4b0a` (`NO_INPUT_OK\n`);
- stderr bytes empty;
- `passed=1`, `total=1`, `valid="1/1"`, `invalid="not_applicable"`.

`manifest-repaired.json` carries the `got` record; `run.log` is the runner
summary; `SHA256SUMS` binds every file. The candidate is a host-native Python
demo, not an ELF and not CWE416. It proves the acceptance runner's byte capture
and 1/1 shape; it is not a CWE416 gate.

## 4. CWE121

CWE121's v2 contract has no `input_mode`. Its hash is unchanged and its matrix is
still exactly 4 valid + 2 invalid. Its V3 semantics (argv, six cases) are not
touched by the no-input branch.

## 5. CWE416 and T8.3

No CWE416 `contract.json` exists; the fixture still has only `PROVENANCE.md`,
`defect.json` and `src.c`. No sentinel `invalid_*` is written. When the no-input
contract is created, `defect.json#trigger_case: "invalid-first"` must be
**deleted in the same change**.

T8.3 remains blocked. No merge to `main`, no tag, no live success.

## 6. Checks

```
tests/test_run_manifest_repaired.py   5 passed
tests/test_run_manifest_compare.py    5 passed
tests/test_v3_no_input_e2e.py         9 passed
full baseline                        446 passed / 2 skipped / 0 failed
```

The two skips are `ELF execution requires Linux`; CI still needs **binutils**
for the `readelf`/`objdump` checks. The M1 local checkpoint before the baseline
merge remains **425/2/0** at `1b08ae5`.
