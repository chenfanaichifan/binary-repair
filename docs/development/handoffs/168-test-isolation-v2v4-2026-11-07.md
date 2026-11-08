# 168 — Writer test isolation fix after M4 review

Date: 2026-11-07  
Owner: M1/M5

M4 found that `tests/test_attempt_writer_gates.py` ran the writer directly on
`artifacts/cwe416-124-v4-rerun-2026-11-06`, rewriting
`v2-interface-scored.json` and then breaking the bundle SHA256SUMS.

## Fix

```text
_run() now copytree()s the source bundle into tmp_path and runs the writer
against the copy. Delivery bundles are never modified by tests.
```

## Verification

```text
tests/test_attempt_writer_gates.py
tests/integration/test_cwe416_124_v4_rerun.py
tests/integration/test_cwe416_124_ingest.py
tests/integration/test_v4_bundle_gate.py
tests/integration/test_p2_acceptance.py
-> 14 passed

artifacts/cwe416-124-v4-rerun-2026-11-06/SHA256SUMS -> all OK after tests
pytest -q -> exit 0
```

## Status

```text
T8.3: pending M4 revalidation after clean combined run
P1: Route B success; overall inconclusive (Route A identity-only)
```

No tag, merge or live-success claim.
