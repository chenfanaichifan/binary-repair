# Review 9–12 — canonical reconstruction

Date: 2026-11-07  
Status: canonical reconstruction; original pasted list is not present in any surviving workspace/WeChat file.

## Provenance

The only surviving references are:

```text
docs/development/handoffs/97-m1-review-closeout-2026-11-05.md:117
docs/development/handoffs/91-m5-completion-2026-11-05.md:38
```

Record 91 states:

```text
9/10 missing incomplete_test_set/timeout_observed;
11 is error/tool_failed, not reject/evidence_hash_mismatch;
12 lacks scope/bounded.
```

Record 97 names the sections as `M4 items 9-12`.

## Reconstructed item text

### 9 — incomplete_test_set

An execution request whose test set is empty or missing required manifests must
not be accepted as a valid/pass case. It must return a machine-readable
`incomplete_test_set` reason.

### 10 — timeout_observed

A case that times out must be recorded as `timeout_observed`, not as a pass and
not as an opaque `error`. The timeout must remain visible to the caller.

### 11 — evidence_hash_mismatch

When evidence bytes do not match their recorded SHA-256, the request must be
rejected with a machine-readable `evidence_hash_mismatch` reason. It must not be
collapsed into `error/tool_failed`.

### 12 — scope/bounded

Responses/UI must carry scope and bounded fields. Missing fields mean `unknown`.
`exceeded: true` means "超出边界" and must never be displayed as pass.

## Current coverage

```text
9  tools/mcp_tool_adapters.py -> incomplete_test_set
10 tools/mcp_tool_adapters.py -> timeout_observed
11 tools/mcp_tool_adapters.py -> evidence_hash_mismatch
12 app/controller_api.py attempts fields + M2 UI pending
```

Tests:

```text
tests/test_mcp_tool_adapters.py
  test_run_case_incomplete_set_is_machine_reason
  test_run_case_timeout_has_machine_reason
  test_apply_candidate_maps_ingest_hash_error
tests/integration/test_contract_gaps.py
```

## Limitations

```text
This is a reconstruction, not a recovered original document.
It must not be described as verbatim source.
M4 can review the semantics and tests, but the provenance remains reconstructed.
```
