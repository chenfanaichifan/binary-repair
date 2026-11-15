# Acceptance-model audit matrix (2026-11-16)

Deterministic matrix for the A01-A08 acceptance dimensions and the
AM01-AM24 mismatch model (`app/services/acceptance_models.py`).

- cases: **62** (positive 13, negative 49)
- AM classes covered by a negative case: 28/28 (AM01, AM02, AM03, AM04, AM05, AM06, AM07, AM08, AM09, AM10, AM11, AM12, AM13, AM14, AM15, AM16, AM17, AM18, AM19, AM20, AM21, AM22, AM23, AM24, AM25, AM26, AM27, AM28)
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
| negative-am21-repair-scope-escape | whole-image repair scope exceeds a target_scoped task | AM21 | AM21 | rejected | yes |
| negative-am22-semantic-scope-partial | partial semantic coverage is rejected | AM22 | AM22 | rejected | yes |
| negative-am23-oracle-self-report | generator self-report cannot satisfy the oracle requirement | AM23 | AM23 | rejected | yes |
| negative-am24-benchmark-version-mismatch | stale benchmark version/sample set is rejected | AM24 | AM24 | rejected | yes |
| negative-am25-layout-missing | a patch plan without candidate layout evidence is rejected | AM25 | AM25 | rejected | yes |
| negative-am25-operation-mismatch | a plan operation missing from the candidate layout is rejected | AM25 | AM25 | rejected | yes |
| negative-am26-associated-out-of-range | an associated change outside the authorized range is rejected | AM26 | AM26 | rejected | yes |
| negative-am26-unauthorized-associated | an associated change without authorization is rejected | AM26 | AM26 | rejected | yes |
| negative-am27-abi-missing | executable modification without derivable ABI evidence is rejected | AM27 | AM27 | rejected | yes |
| negative-am28-oracle-metadata | incomplete / not executed oracle metadata is rejected | AM28 | AM28 | rejected | yes |
| positive-abi-derived | derivable ABI evidence satisfies the ABI requirement | - | - | verified | yes |
| positive-associated-authorized | an authorized associated rodata change verifies | - | - | verified | yes |
| positive-benchmark-version | matching benchmark version and sample-set commitment verifies | - | - | verified | yes |
| positive-declared-alias | a declared model alias is verified | - | - | verified | yes |
| positive-exact-identity | complete exact-identity acceptance verifies | - | - | verified | yes |
| positive-independent-oracle | an independent external oracle satisfies the oracle requirement | - | - | verified | yes |
| positive-oracle-metadata | complete executed-oracle metadata verifies | - | - | verified | yes |
| positive-patch-plan-replay | a declared patch plan replays into the candidate layout | - | - | verified | yes |
| positive-repair-scope-no-range | target-scoped repair without a VA range verifies | - | - | verified | yes |
| positive-repair-scope-target | target-scoped repair actions inside the declared range verify | - | - | verified | yes |
| positive-semantic-scope-complete | full semantic-scope coverage verifies | - | - | verified | yes |
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
