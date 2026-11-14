# Acceptance-model audit matrix (2026-11-16)

Deterministic matrix for the A01-A08 acceptance dimensions and the
AM01-AM20 mismatch model (`app/services/acceptance_models.py`).

- cases: **43** (positive 4, negative 39)
- AM classes covered by a negative case: 20/20 (AM01, AM02, AM03, AM04, AM05, AM06, AM07, AM08, AM09, AM10, AM11, AM12, AM13, AM14, AM15, AM16, AM17, AM18, AM19, AM20)
- recall: **1.0**, precision: **1.0**, ok: **True**

## Cases

| case | purpose | expected | detected | decision | ok |
|---|---|---|---|---|---|
| negative-am01-target-sha | target SHA spoof is rejected | AM01 | AM01 | rejected | yes |
| negative-am02-tree-sha | tree SHA spoof is rejected | AM02 | AM02 | rejected | yes |
| negative-am03-format | container format spoof is rejected | AM03 | AM03 | rejected | yes |
| negative-am04-arch | arch spoof is rejected | AM04 | AM04 | rejected | yes |
| negative-am05-scope-overclaim | module experience cannot claim a function task | AM05 | AM05 | rejected | yes |
| negative-am06-static-dynamic | missing dynamic evidence mode is rejected | AM06 | AM06 | rejected | yes |
| negative-am07-whole-program | single-function evidence cannot claim whole program | AM07 | AM07 | rejected | yes |
| negative-am08-evidence-hash | tampered evidence hash is rejected | AM08 | AM08 | rejected | yes |
| negative-am09-served-only | served-model-only identity cannot verify requested | AM09 | AM09 | rejected | yes |
| negative-am10-unknown-identity | unknown model identity is rejected | AM10 | AM10 | rejected | yes |
| negative-am11-mismatched-identity | mismatched model identity is rejected | AM11 | AM11 | rejected | yes |
| negative-am12-invalid-alias | undeclared model alias is rejected | AM12 | AM12 | rejected | yes |
| negative-am13-method-missing | required method without evidence is rejected | AM13 | AM13 | rejected | yes |
| negative-am14-environment | environment spoof is rejected | AM14 | AM14 | rejected | yes |
| negative-am15-only-positive | only-positive evidence cannot satisfy regression | AM15 | AM15 | rejected | yes |
| negative-am16-statistics | insufficient repeats are rejected | AM16 | AM16 | rejected | yes |
| negative-am17-tool-version | tool version drift is rejected | AM17 | AM17 | rejected | yes |
| negative-am18-independence | self-review independence violation is rejected | AM18 | AM18 | rejected | yes |
| negative-am19-extra-claim | claims beyond the task contract are rejected | AM19 | AM19 | rejected | yes |
| negative-am20-evidence-incomplete | incomplete evidence record is rejected | AM20 | AM20 | rejected | yes |
| positive-declared-alias | a declared model alias is verified | - | - | verified | yes |
| positive-exact-identity | complete exact-identity acceptance verifies | - | - | verified | yes |
| positive-static-only | static-only task with static evidence verifies | - | - | verified | yes |
| positive-whole-program | whole-program task with whole-program evidence verifies | - | - | verified | yes |
| variant-am01-target-sha-other | any target SHA deviation is rejected | AM01 | AM01 | rejected | yes |
| variant-am02-tree-sha-other | any tree SHA deviation is rejected | AM02 | AM02 | rejected | yes |
| variant-am03-format-macho | Mach-O acceptance cannot verify an ELF task | AM03 | AM03 | rejected | yes |
| variant-am04-abi | ABI spoof is rejected with the arch class | AM04 | AM04 | rejected | yes |
| variant-am05-vulnerability-scope | whole-program evidence cannot claim a vulnerability task | AM05 | AM05 | rejected | yes |
| variant-am07-claim-scope | whole-program claim without whole-program evidence | AM07, AM19 | AM07, AM19 | rejected | yes |
| variant-am08-evidence-hash-2 | second evidence hash tamper is rejected | AM08 | AM08 | rejected | yes |
| variant-am09-served-different | served-only different model cannot verify requested | AM09 | AM09 | rejected | yes |
| variant-am10-no-identity | missing identity record is unknown | AM10 | AM10 | rejected | yes |
| variant-am11-exact-but-served | exact status with a different served model is rejected | AM11 | AM11 | rejected | yes |
| variant-am12-alias-requested | alias for a different requested model is invalid | AM12 | AM12 | rejected | yes |
| variant-am13-static-method-missing | missing static method evidence is rejected | AM13 | AM13 | rejected | yes |
| variant-am14-runtime-tier | runtime tier claim mismatch is rejected | AM14 | AM14 | rejected | yes |
| variant-am15-positive-only-flag | only_positive acceptance is rejected | AM15 | AM15 | rejected | yes |
| variant-am16-repeats-bar | higher repeat bar is rejected when evidence is thin | AM16 | AM16 | rejected | yes |
| variant-am17-acceptance-version | acceptance-level tool version drift is rejected | AM17 | AM17 | rejected | yes |
| variant-am18-shared-source | shared-source independence violation is rejected | AM18 | AM18 | rejected | yes |
| variant-am19-claim-scope | claim scope overclaim is rejected | AM19 | AM19 | rejected | yes |
| variant-am20-extra-ref | task evidence reference without acceptance evidence | AM20 | AM20 | rejected | yes |

## Reproduce

```
python scripts/audit_acceptance_models.py --write
python scripts/audit_acceptance_models.py --check
python scripts/audit_acceptance_models.py --json
```

`--check` recomputes the matrix and report from the committed `cases.json`, compares them byte-for-byte (canonical JSON) and verifies `SHA256SUMS`; any tampering or a missed/extra mismatch exits non-zero.
