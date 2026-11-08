# 165 — M5 Review 9–12 triage: machine-readable reasons

Date: 2026-11-07  
Owner: M5  
Status: M5-side triage complete; scope/bounded remains a UI presentation item.

## Findings

```text
9  incomplete_test_set   -> run_case reason when the runner refuses an empty/missing manifest
10 timeout_observed      -> run_case reason when the outer timeout fires; never a pass
11 evidence_hash_mismatch -> apply_candidate reason when ingest reports hash/mismatch
12 scope/bounded          -> no M5 contract change; UI must render unknown / exceeded
```

## Implementation

`tools/mcp_tool_adapters.py`:

```text
run_case:
  timeout -> status=timeout, reason=timeout_observed
  empty/incomplete manifest -> status=incomplete_test_set, reason=incomplete_test_set
  other invalid -> invalid_request

apply_candidate:
  IngestError containing hash/mismatch/does not match -> evidence_hash_mismatch
  other IngestError -> bundle_invalid
```

## Tests

```text
tests/test_mcp_tool_adapters.py:
  test_run_case_timeout_has_machine_reason
  test_run_case_incomplete_set_is_machine_reason
  test_apply_candidate_maps_ingest_hash_error

8 adapter tests pass
pytest --ignore=tests/e2e -> exit 0
```

## Non-claims

```text
No gate promotion.
No T8.3 change.
No verified_by.
No usage change.
```

Item 12 (scope/bounded) is presentation, not adapter logic; M2 renders:
missing -> unknown, exceeded:true -> "超出边界", never pass.
