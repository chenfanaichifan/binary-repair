# 169 — task-33: Route A input_mode=none without tests/invalid.json

Date: 2026-11-07  
Owner: M1/M5

## Change

```text
workers/executor/run_job.py
  route_a + input_mode=none: invalid.json may be absent
  non-empty invalid.json -> package_invalid (sentinel rejected)
  argv/stdin: invalid.json still required

workers/route_a/worker.py
  manifest_set_hash(tests_dir, input_mode)
  none: only valid.json is hashed; invalid_sha256=null
  non-empty invalid.json -> SystemExit

workers/route_a/result_bundle.py
  none: invalid.json is not required, not hashed, not in evidence
  identity.invalid_sha256=null
  argv/stdin: invalid.json remains required
```

## Tests

```text
tests/test_routea_noinput_package.py
  no-input package without invalid -> accepted
  non-empty sentinel -> rejected
  argv package without invalid -> rejected
  worker none manifest -> only valid
  result-bundle none -> no invalid hash/evidence
5 passed

pytest --ignore=tests/e2e -> exit 0
```

## P1 package

```text
delivery/p1-routea-package-2026-11-07/
  verified route_a none
  candidate 2a96b1083f23a0885ef6152dee39c48648d496a7a026e37ccfb31382c412970e
```

This package is ready for a real guest Route A run. It does not by itself
produce Route A V2/V3/V5 evidence.

## Status

```text
task-33: FIXED
P1 Route B: success
P1 Route A: package ready, guest execution pending
T8.3: pending M4 revalidation
```
