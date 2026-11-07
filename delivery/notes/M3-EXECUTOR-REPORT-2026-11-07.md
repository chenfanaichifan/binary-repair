# M3 executor report — 2026-11-07

Source: M3 chat report, archived by M5. This is a status note, not the executor
code or evidence package.

## Reported by M3

```text
new: workers/executor/run_job.py
new: workers/executor/run_job.sh
new: workers/executor/self_test.py
new: workers/executor/README.md
new: tests/test_guest_executor.py
record: 151-m3-guest-executor-account-isolation-2026-11-07.md
evidence: t62-guest-executor-2026-11-07/
self_test: 9/9
pytest: 9 passed
account guard: euid 1003 only
```

## Still missing / not claimed

```text
executor code is not in this repository checkout
jobwrap has no executor mode
isolation.json: jobwrap=not_attested, no_new_privs=0, normal netns
T6.2 formal conformance: NOT RUN
repair account still exists
T8.3 marker unchanged
```

M3 must push the actual executor code, tests, record 151 and evidence directory.
