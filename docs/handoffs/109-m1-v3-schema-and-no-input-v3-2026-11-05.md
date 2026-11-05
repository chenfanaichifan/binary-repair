# 109 — M5 v3 schema integrated; exact V3 matrices; no-input V3 is 1/1

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Branch: `m1/t30-acceptance-ab-2026-11-05`
- Common baseline: `canonical/m1-m5-integration` @ `1430e1e` (v3 schema
  `708d957` + intake). M1 merged it; `app/domain/contracts.py` diff vs the
  baseline is 0.
- Scope: schema integration, fixture-intake matrix, and the V3 no-input
  acceptance path. **No fixture byte change, no CWE416 contract.** No merge to
  `main`, no tag, no live-success claim.

M5's v3 schema is now **in this branch** by cherry-pick, not by a second copy.
The CWE416 contract is still absent; the intake and the V3 runner are ready for
it, but no sentinel `invalid_*` field is written.

---

## 0. Status at a glance

| Item | Status |
|---|---|
| M5 v3 schema | **integrated on the common baseline** — `708d957` (canonical `1430e1e`); M1 merged it |
| Second schema copy | **none** — one `app/domain/contracts.py`; diff vs canonical baseline is 0 |
| CWE121 v2 hash | **`24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37`** (unchanged) |
| no-input v3 hash | `98ba686723ec85a7631e156dc240315d1cf4736fde0f1adc9c709d52ef3a33a7` |
| Intake argv/stdin | exactly **4 valid + 2 invalid** |
| Intake none | exactly **1 valid + 0 invalid**; `tests/invalid.json` must be absent |
| V3 none | **1/1**, `invalid: not_applicable` |
| CWE416 contract | **still absent**; no sentinel fields |
| 118 evidence | readable; waiting for M4's five-gate verification; no self-upgrade |
| T8.3 | **BLOCKED** |
| main / tag / live success | **no / no / no** |

---

## 1. Schema integration: one implementation

`4c36898` (`feat(m5): add v3 no-input contract mode`) touched exactly:

```
app/domain/contracts.py
tests/test_contracts.py
```

It was first cherry-picked on the M1 feature branch (`7c279a1`) and then
integrated on the common baseline `canonical/m1-m5-integration` as `708d957`
(commit `1430e1e`). M1 merged that baseline. There is now **one**
`app/domain/contracts.py`; `git diff canonical/m1-m5-integration HEAD` for it is
empty. `fixture_intake.py` imports that class instead of carrying its own field
rules.

CWE121 is a v2 contract with no `input_mode`. Its hash is unchanged:

```
24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37
```

The v3 no-input body hashes to:

```
98ba686723ec85a7631e156dc240315d1cf4736fde0f1adc9c709d52ef3a33a7
```

That is the same body the M5 branch loads. The schema rejects the four
`invalid_*` fields and `max_valid_input_bytes` in `input_mode: "none"`; the
intake reports the rejection as `contract_schema_invalid`, not with a duplicate
set of mode rules.

---

## 2. Fixture intake: exact matrices

`tools/fixture_intake.py` now checks the matrix, not a minimum:

| Mode | Valid | Invalid | Invalid manifest |
|---|---|---|---|
| `argv` / `stdin` (v2 or v3) | exactly 4 | exactly 2 | required |
| `none` (v3) | exactly 1 | exactly 0 | **must be absent** |

- Extra cases are `too_many_valid` / `too_many_invalid`; short matrices remain
  `too_few_valid` / `too_few_invalid`.
- `input_mode: "none"` is not required to ship `tests/invalid.json`, and an
  empty file is **not** a substitute: `no_input_invalid_manifest_present`.
- A no-input fixture with 0 or 2 valid cases is
  `no_input_valid_case_count_mismatch`.
- The full contract body is validated by `SecurityContract.from_dict`; a
  rejected body is `contract_schema_invalid`.

`docs/fixtures.md` and the checker docstring record the same rules.

The intake tests are **39 passed**. They include the four rejection fields,
`max_valid_input_bytes`, an empty invalid manifest, 0/2 valid cases, 0/2/3/5
case matrices, v3 argv/stdin, the v2 default, and the unknown-mode case.

---

## 3. Acceptance V3: 1/1 no-input, invalid N/A

### 3.1 Repaired runner

`routeb/run_manifest_repaired.py` accepts `--input-mode` or `--contract`. For
`none` it:

- refuses any `tests/invalid.json`, including an empty one;
- requires exactly one valid case;
- invokes the binary with no argument and no stdin;
- compares exit code, stdout and stderr with the frozen expectation;
- writes `input_mode: "none"`, `invalid: "not_applicable"`,
  `passed`/`total` = 1/1 (or 0/1), and `repaired_pass`.

The historical argv/stdin path is unchanged: it runs the program argument and
optional stdin and keeps `invalid: "measured"`.

### 3.2 Compare runner

`routeb/run_manifest_compare.py` has the same no-input shape: one valid case,
no invalid file, no argument; `same_count`/`total` = 1/1 and
`invalid: "not_applicable"`. The argv/stdin comparison is unchanged.

### 3.3 Executor and runtime detail

`routeb/executor.py` accepts `--contract` (or `--input-mode`) and passes the
mode to both runners. The runtime record carries `input_mode` and
`invalid`; `routeb/attempt_writer.py` reports `1/1` and
`invalid not applicable` in the V3 detail.

`app/domain/acceptance.py` is unchanged: V3 is still one required behaviour
obligation. The no-input distinction lives in the V3 evidence (1/1, invalid
N/A), not in a second acceptance engine.

### 3.4 Full-chain contract validation

Route B does not read `input_mode` from a raw JSON body at the acceptance edge.
`routeb/contract_mode.py` loads the body through M5's `SecurityContract`; the
repaired runner, the compare runner, the executor and
`routeb/attempt_writer._verify_contract` all use it. A no-input contract with a
sentinel field therefore fails before any case is run, not only at intake.

### 3.5 Tests

- `tests/test_run_manifest_repaired.py`: 5 passed (1/1, invalid manifest
  rejected, two valid cases rejected, argv still runs, runtime detail).
- `tests/test_run_manifest_compare.py`: 5 passed, including the no-input 1/1 and
  empty-invalid-manifest rejection.
- `tests/test_v3_no_input_e2e.py`: 9 passed. A real executable with a valid
  no-input contract returns `1/1` and `invalid: not_applicable`; each of the
  four `invalid_*` fields and `max_valid_input_bytes` makes the CLI return 2
  before writing an artefact; the executor rejects a sentinel contract before
  creating a bundle; `_verify_contract` rejects the same body.
- Full suite on M1: **449 passed / 2 skipped / 0 failed**.
- Common baseline full suite: **430 passed / 2 skipped / 0 failed**.
- M1 local checkpoint before the baseline merge (`1b08ae5`): **425 passed / 2 skipped / 0 failed**.

**425/2/0 is the recorded M1 local checkpoint at `1b08ae5`**; the post-baseline
branch has 449 tests because it adds the v3 and V3 no-input tests. CI still
needs **binutils** for the `readelf`/`objdump` checks. The two local skips are
`ELF execution requires Linux`; a skip is not a pass.

---

## 4. CWE416 contract and fixture

No `contract.json` was created. The real fixture still has only:

```
PROVENANCE.md
defect.json
src.c
```

Intake reports 7 `missing_file` findings. The `defect.json` still carries
`"trigger_case": "invalid-first"`. When the v3 no-input contract is created,
that pointer must be **deleted in the same change**; it must not be carried into
the no-input fixture. The intake reports `no_input_trigger_case_present` until
it is gone. No sentinel `invalid_*` field was written anywhere.

The schema now in this branch means a v3 no-input contract can load here. The
fixture still needs the build, ELF, contract and tests before it can pass
intake; T8.3 is not relieved by any of this.

---

## 5. 118 evidence and M4

The 118 evidence is delivered at
`delivery/t30-rebuild-2026-11-05/` (record 107): 11 files, top-level zip hash
`968fb8d9…0fcbd5`, directory 10/10, guest 5/5. It is readable by M4/M5.

M1 does **not** upgrade it. T30 remains `PASS WITH LIMITATIONS` on the M1 side
until M4 completes its five-gate verification and writes its own record. No
V0–V5 promotion is made here.

---

## 6. Fork and constraints

- The canonical/live-bridge fork is still recorded, not merged. The M5 schema
  came in as a cherry-pick of `4c36898`, not a branch merge.
- T30 canonical path remains
  `docs/handoffs/evidence/T30/build/original.elf` at `c274893`; the binding is
  in `delivery/t30-rebuild-2026-11-05/PROVENANCE.md`.
- T8.3 remains **blocked**.
- No merge to `main`, no tag, no live-success claim.
- No fixture byte changed; no CWE416 contract written.

---

## 7. Not claimed

- **Not** a second schema; the M5 implementation is the only one.
- **Not** a CWE416 contract or candidate; the fixture is still incomplete.
- **Not** a V3 gate pass on a candidate; only the runner/intake path is ready.
- **Not** an M4 verification of 118; M4 owns that record.
- **Not** a T8.3 credit, merge, tag, or live success.

## 8. Open items

1. **M4:** complete the five-gate verification of 118 and record the result.
2. **M1/fixture owner:** add the v3 no-input contract, one valid case, no
   invalid file, and remove `defect.json#trigger_case` when the CWE416 build
   exists.
3. **M5:** keep the v3 schema as the authority; any further schema change is
   M5's commit, not an intake edit.
