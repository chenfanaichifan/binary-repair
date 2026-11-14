# Autonomous repair audit (2026-11-16)

Unified static audit entry (`scripts/autonomous_repair_audit.py`). It
orchestrates the committed checks as subprocesses and aggregates their
status. It does not run dynamic/Lima suites and does not claim a repair
capability or a verified disposition.

- mode: `full`
- ok: `True`
- exit code: `0` (0 pass, 1 failed check, 2 required not_run)

## Checks

| id | status | required | detail |
|---|---|---|---|
| `universe-methodology` | passed | True | exit 0 (no JSON report parsed) |
| `autonomous-reflection` | passed | True | exit 0 (no JSON report parsed) |
| `coverage-gate-static` | passed | True | exit 0; report ok=True |
| `acceptance-model-audit` | passed | True | exit 0 (no JSON report parsed) |
| `capability-gap-discovery` | passed | True | exit 0; report ok=True |
| `meta-audit` | passed | True | exit 0; report ok=True |
| `provider-coverage` | passed | True | exit 0; report ok=True |

## Not run

- none

## Limitations

- not_run checks are not evidence: a missing script/input never counts as a pass
- this orchestration is static only; it does not run dynamic/Lima suites
- the audit never promotes capability or claims verified repair

