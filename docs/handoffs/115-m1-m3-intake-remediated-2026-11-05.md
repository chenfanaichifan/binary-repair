# 115 — M3 intake remediated: `1b08ae5` base, v2+input_mode still rejected

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Branch: `canonical/m1-m5-integration`
- Scope: record the M3 intake update. No CWE416 contract, no gate promotion.
  No merge to `main`, no tag, no live-success claim.

---

## 0. Gate result after remediation

| Gate | Result |
|---|---|
| M3 uses `1b08ae5` intake | **PASS** — `52ffecd` merges `1b08ae5` as an ancestor; the old tool is gone |
| no-input contract only v3 | **PASS** — M3's v2+`input_mode` body is still rejected |
| acceptance/V3 1/1 | **PASS** — canonical/M1, one valid / zero invalid, `invalid=not_applicable` |
| CWE416 upgraded | **NO** — no valid v3 contract, no candidate, no gate |
| CWE121 v2 4+2 / hash | **PASS** — `24bfe568…4e37` |
| T8.3 | **BLOCKED** |
| main / tag / live success | **no / no / no** |

---

## 1. M3 now uses the `1b08ae5` intake

M3 head: `origin/m3/cwe122-fixture-build` @ `52ffecd`.

| Ref | Intake |
|---|---|
| M3 `52ffecd` | `1192d8fde75c0e0763c491451756cd55578ef125` |
| old M3 `6ce16ac` | `573d39aedf87943012392c3a05f1d2228b21e3fa` (removed) |
| `1b08ae5` | `e5cf99fbbdc422711e33b1459030c72ff6e90157` |

`git merge-base --is-ancestor 1b08ae5 52ffecd` is **true**. The merged tool is
`1b08ae5`'s `input_mode`/v3 no-input logic **plus** M3's `bug_site` check, so
M3's existing classification tests keep working. The old blob is no longer in
M3's tree.

M3 full suite after the merge: **419 passed / 2 skipped / 0 failed**.

## 2. v2 + input_mode is rejected

M3's `CWE416_..._01_noinput/contract.json` is still:

```
schema_version: 2
input_mode: none
invalid_exit_code: 0
```

Running the merged intake with the fixture's missing `src.c` filled in (a
temp copy only) reports:

```
error contract_input_mode_not_allowed_v2 contract.json#input_mode
      v2 is the historical argv contract; input_mode starts at v3
```

That is the required rejection. A v2 body may not carry `input_mode`; only a
v3 `none` body can be a no-input contract. M3's contract is therefore **not** a
valid no-input contract and is not adopted.

The real fixture still lacks `src.c` (it ships `original.c`), so the intake also
reports the source-name blocker; that is a fixture-naming issue, not a reason to
accept the v2 contract.

## 3. Acceptance/V3 remains 1/1

The common baseline's V3 no-input path is unchanged: exactly one valid case,
zero invalid, `invalid=not_applicable`, `passed=1`, `total=1`, `valid="1/1"`.
The real execution record is at
`docs/handoffs/evidence/V3-no-input-2026-11-05/` (exit 0, stdout
`4e4f5f494e5055545f4f4b0a`, empty stderr). It is a synthetic host-native demo,
not CWE416 and not an ELF.

## 4. CWE416, CWE121, T8.3

- CWE416 is **not upgraded**: no valid v3 contract, no candidate, no V3/V4/V5
  promotion. `defect.json#trigger_case` must be deleted when a valid v3
  no-input contract is created.
- CWE121 remains the v2 argv contract, hash
  `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37`, 4+2.
- T8.3 remains **blocked**; no main merge, no tag, no live success.

## 5. Checks

```
M3 52ffecd full suite                 419 passed / 2 skipped / 0 failed
M3 v2+input_mode intake               contract_input_mode_not_allowed_v2
canonical 48e32ce full suite          446 passed / 2 skipped / 0 failed
M1 5d0245c full suite                 449 passed / 2 skipped / 0 failed
M1 local checkpoint 1b08ae5           425 passed / 2 skipped / 0 failed
```

CI still needs **binutils**; the two local skips are
`ELF execution requires Linux`.
