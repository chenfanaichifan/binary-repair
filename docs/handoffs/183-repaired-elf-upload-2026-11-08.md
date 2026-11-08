# 183 — Repaired ELF upload/download entry

Date: 2026-11-08

Teacher-facing requirement: upload the final repaired ELF to the GUI and get a
direct download entry.

## Implemented

```text
POST /api/jobs/{job_id}/deliverables
  multipart file
  ELF magic required
  max 64 MiB
  sha256 registered
  role = operator_deliverable
  never executed
  never creates an obligation or changes a verdict

GET /api/jobs/{job_id}/artifacts
  exposes operator_deliverable and candidate artifacts

GET /api/jobs/{job_id}/artifacts/{artifact_id}/download
  verified bytes, attachment
```

GUI:

```text
/agent downloads panel
  file input: agent-deliverable-input
  button: agent-deliverable-upload
  status: agent-deliverable-status
  artifact links: 产物：<name>（<role>）
```

## Safety boundary

The uploaded bytes are stored and downloadable only. The host does not execute
them, and they are not acceptance evidence. V0–V5 still decide the verdict.

## Test

```text
tests/integration/test_deliverable_upload.py
  registered + downloadable
  non-ELF rejected
  no run/verdict created
tests/test_agent_console.py::test_deliverable_upload_controls_exist
-> pass
```

## Limitation

A browser cannot execute an ELF; the entry is a download/open-with dialog, not a
remote execution feature.
