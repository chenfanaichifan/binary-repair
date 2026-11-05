# 108 — CWE416 no-input intake/test adaptation (M5 option A)

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Branch: `m1/t30-acceptance-ab-2026-11-05`
- Scope: fixture intake and its tests. **No schema change**, no fixture byte
  change, no contract written. No merge to `main`, no tag, no live-success
  claim.
- M5 reference: `origin/member-5/complete-m5` @ `4c36898`
  (`feat(m5): add v3 no-input contract mode`). It was a read-only cross-check
  when this record was written; record 109 then integrated it by cherry-pick.
- **Update (record 109):** the matrix is now exact — argv/stdin 4+2, none 1+0;
  `tests/invalid.json` must be **absent** for none (an empty file is rejected);
  contract validation is delegated to `SecurityContract`, so schema findings are
  `contract_schema_invalid`. Current tests: 39 intake, 449 full (109 adds the end-to-end suite). Where the text
  below says "at least one" or allows an empty invalid file, record 109 wins.

The Lead selected **option A**: `input_mode: "none"` in the M5 v3 contract.
M1's part is the fixture intake and tests; the schema remains M5's.

---

## 0. Status at a glance

| Item | Status |
|---|---|
| No-input contract route | **A selected** (M5 v3) |
| `app/domain/contracts.py` | **M5 v3 integrated** by cherry-pick `4c36898` (`7c279a1`) — not a second schema |
| Fixture intake | **adapted** for `input_mode: "none"` |
| Intake tests | **39 passed** (`tests/test_fixture_intake.py`) |
| Full suite | **449 passed / 2 skipped / 0 failed** |
| CWE121 contract | **unchanged**: v2, default argv, 4+2 matrix, same hash |
| CWE416 fixture | **still incomplete**: no contract/build/ELF/tests; 7 `missing_file` |
| Sentinel `invalid_*` for CWE416 | **none added** |
| T8.3 | **BLOCKED** |
| main / tag / live success | **no / no / no** |

The schema is not merged into this branch. M1's intake accepts the M5 v3 shape,
but a v3 contract will not load on this branch until M5's schema lands. That is
the intended sequencing, not a hidden merge.

---

## 1. What changed

### 1.1 `tools/fixture_intake.py`

The checker now reads `contract.json#input_mode` as data:

| Shape | Behaviour |
|---|---|
| `schema_version: 2`, no `input_mode` | historical argv contract; CWE121 unchanged |
| `schema_version: 2` + `input_mode` | `contract_input_mode_not_allowed_v2` |
| `schema_version: 3`, `input_mode: "argv"` / `"stdin"` | input-bearing; 4 valid + 2 invalid; `trigger_case` required and must resolve |
| `schema_version: 3`, `input_mode: "none"` | no-input; the rules in §2 |
| any other schema version | `contract_schema_version_unknown` |
| unknown `input_mode` | `contract_input_mode_unknown` |

The required-file set is mode-aware: `tests/invalid.json` is **not required**
for `input_mode: "none"`. If it exists, it must contain zero cases. The 4-valid
minimum does not apply; the no-input minimum is 1.

The four rejection fields and `max_valid_input_bytes` are forbidden in the
no-input shape. M5's v3 treats `max_valid_input_bytes` as invalid-only, so
leaving it at `0` is still a sentinel value, not an omission.

### 1.2 `tests/test_fixture_intake.py`

The fixture builder gained `input_mode`, `include_invalid` and an optional
`trigger_case`. New tests cover:

- a complete no-input fixture passes;
- each of the four `invalid_*` fields is rejected when present;
- `max_valid_input_bytes` is rejected when present;
- an invalid case is rejected when present;
- a missing valid case is rejected;
- an empty `tests/invalid.json` (`"tests": []`) is accepted;
- a leftover `trigger_case` pointer is rejected;
- an unknown `input_mode` is rejected;
- a v2 contract carrying `input_mode` is rejected;
- v3 `argv`/`stdin` keep the 4+2 matrix;
- the v2 argv default still passes with the 4+2 matrix.

### 1.3 `docs/fixtures.md`

The required-layout section, the finding table and a new “No-input fixtures”
section record the same rules. The CWE416 current-state note says the fixture
still lacks a contract and that its `trigger_case: "invalid-first"` must be
removed when the v3 no-input contract is added.

---

## 2. The no-input rules, exactly

For `schema_version: 3`, `input_mode: "none"`:

1. **The four rejection fields must be absent**:
   `invalid_input_response`, `invalid_exit_code`, `invalid_stdout`,
   `invalid_stderr`. `max_valid_input_bytes` is absent as well (M5 v3 treats it
   as invalid-only). Any present field is
   `no_input_invalid_fields_present`; sentinel values are not an alternative.
2. **The invalid case count must be 0**: `tests/invalid.json` may be absent, or
   present with `"tests": []`. Any invalid case is
   `no_input_invalid_cases_present`.
3. **At least one valid case must exist**: zero valid cases is
   `no_input_valid_case_missing`.
4. **`defect.json#trigger_case` must be absent or null**: there is no invalid
   case to point at. A leftover pointer is
   `no_input_trigger_case_present`.

The checker does not duplicate the full `SecurityContract` validation. It
checks layout and these semantics; the schema loader remains the authority on
the rest.

---

## 3. Cross-check against M5's v3 schema

M5's branch was read in a separate worktree; it was not merged or copied into
this branch.

| Check | Result |
|---|---|
| M5 head | `4c36898` |
| no-input v3 contract loads | yes; hash `98ba686723ec85a7631e156dc240315d1cf4736fde0f1adc9c709d52ef3a33a7` |
| `invalid_input_response` present | rejected: unknown field |
| `invalid_exit_code` present | rejected: unknown field |
| `invalid_stdout` present | rejected: unknown field |
| `invalid_stderr` present | rejected: unknown field |
| `max_valid_input_bytes` present | rejected: unknown field |
| CWE121 v2 contract loads | yes; hash `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37` — same as this branch |

This is why the intake rejects the five fields: they are not merely “not
required” by M5's v3, they are unknown fields that make the contract
unloadable. Rejecting them in intake catches the mistake before a candidate is
built.

CWE121's v2 contract is byte-identical and its hash is unchanged. The default
argv path is still the 4+2 matrix.

---

## 4. CWE416 fixture state

The real fixture is still:

```
fixtures/public/CWE416_Use_After_Free__malloc_free_char_01/
  PROVENANCE.md
  defect.json
  src.c
```

No `contract.json`, `build.json`, `build.sh`, `original.elf` or `tests/`. Intake
still reports 7 `missing_file` findings and stops; that is the true state.

Two consequences, stated so they are not mistaken for new work:

- **No sentinel fields were added.** The fixture has no contract, so there is
  nothing to fill with `invalid_*` placeholders.
- **`defect.json` still has `"trigger_case": "invalid-first"`.** It is a
  CWE121-shaped leftover. When a v3 `input_mode: "none"` contract is added, the
  intake will report `no_input_trigger_case_present` until the pointer is
  removed. The fixture was not edited here: the contract does not exist yet, and
  removing the pointer without the mode would make the default argv check fail
  for the opposite reason.

The fixture remains blocked on M5's schema landing, a contract, a build, an ELF,
and tests. T8.3 is not relieved by any of this.

---

## 5. Canonical / live-bridge version closure

This record does not merge anything. The fork status is unchanged:

- `canonical/m1-m5-integration` (`1938c31`) still carries the corrected CWE416
  provenance and the V0 content-binding comment.
- `integration/live-bridge-2026-11-03` (`bcb7a30` at the remote head used for
  this work) carries the later M5 merges and the record-105 work.
- The T30 canonical artifact path remains
  `docs/handoffs/evidence/T30/build/original.elf` at `c274893`; the `c274893`
  binding is in `delivery/t30-rebuild-2026-11-05/PROVENANCE.md`.
- M5's v3 schema is on `member-5/complete-m5`; it is a separate branch and is not
  merged here. The eventual reconciliation is a merge decision, not an intake
  detail.

No main merge, no tag, no live-success claim.

---

## 6. Checks run

```
pytest tests/test_fixture_intake.py -o addopts=""      36 passed
pytest --ignore=tests/e2e -o addopts=""                425 passed / 2 skipped / 0 failed
fixture_intake.py --check CWE121_...                   OK (1 warning: reproduction_unverified)
fixture_intake.py --check CWE416_...                   FAILED (7 missing_file)
```

The two skips are `ELF execution requires Linux`; a skip is not a pass.

The M5 cross-check was a separate worktree at `origin/member-5/complete-m5`; its
output is quoted in §3, not merged into the test suite.

---

## 7. Not claimed

- **Not** a schema change. `app/domain/contracts.py` on this branch is still v2;
  M5's v3 is not merged.
- **Not** a CWE416 contract, candidate, or V0–V5 result. The fixture is still
  incomplete.
- **Not** a T8.3 fixture or T8.3 credit.
- **Not** an M4 verification of 118. The 118 evidence is delivered; M4 may
  verify on its own record.
- **Not** a merge, tag, or live success.

## 8. Open items

1. **M5:** land the v3 schema on the integration line; M1's intake already
   accepts the shape.
2. **M1/fixture owner:** when the CWE416 build exists, add the v3 no-input
   contract, one valid case, no invalid file, and remove
   `defect.json#trigger_case`.
3. **Lead:** any canonical/live-bridge merge remains a separate decision; no
   merge is performed here.
