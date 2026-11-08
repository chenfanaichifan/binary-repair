# Delivery index — canonical paths

Date: 2026-11-08  
Status: P1 success_within_scope; P2 PASS; T8.3 COMPLETE.

## Canonical — current

### P1 final (authoritative)

```text
delivery/p1-real-window-2026-11-07/
  controller/snapshot.json
  controller/ids.json
  api/attempts.json
  api/route-a-evidence.json
  api/route-b-evidence.json
  p2/p2-result.txt
  p2/P2-ACCEPTANCE.txt
  bundle/a1.routeb/
  v5-replay-2026-11-07/       16/16 HOST-SHA256SUMS
```

Job: `9247357c54714546a7ff84891f7766f8`  
Verdict: `success_within_scope`.

### Route A V4 / inputs

```text
delivery/p1-routea-v4-symbolic-2026-11-07/
delivery/p1-routea-real-v4-2026-11-07/
delivery/p1-routea-v4-input-2026-11-07/
delivery/p1-routea-package-2026-11-07/
delivery/v4-harness-2026-11-07/
```

### T8.3 / 124

```text
delivery/cwe416-124-v4-rerun-2026-11-06/
delivery/m4/v4-2026-11-07/
delivery/m4-revalidation-ebc92a8/
docs/handoffs/170-t83-fresh-tree-closure-2026-11-07.md
docs/handoffs/171-m4-t83-confirmation-2026-11-07.md
```

### Repaired ELF upload

```text
POST /api/jobs/{job_id}/deliverables
role: operator_deliverable
never executed; never acceptance evidence
UI: /agent -> 下载面板 -> 上传修复文件
```

### M2 / M4 / Review

```text
delivery/m2-handoff-2026-11-08.zip
docs/reviews/review-9-12-canonical-2026-11-07.md
docs/reviews/review-9-12-m4-verification-2026-11-07.md
docs/reviews/review-9-12-m4-verdict-2026-11-07.json
docs/reviews/review-12-m4-verification-2026-11-08.md
docs/handoffs/180-review12-pass-2026-11-08.md
```

### M5 / contracts

```text
tools/mcp_tool_adapters.py
tools/route_bundle_ingest.py
app/services/assistant_llm.py
tests/test_mcp_tool_adapters.py
tests/test_assistant_llm.py
docs/handoffs/179-m2-all-inputs-handoff-2026-11-07.md
```

### Distribution snapshot

```text
delivery/upload-2026-11-07/      zips + SHA256SUMS + MANIFEST
delivery/p1-v5-logs-2026-11-07.zip
delivery/p1-routea-package-2026-11-07.zip
delivery/v4-harness-2026-11-07.zip
```

## Historical — kept for audit, not current

```text
delivery/artifacts-2026-11-07/            old member artifact dump
delivery/cwe416-124-candidate-2026-11-05/ superseded by v4 rerun
delivery/m5-m4verify-2026-11-06/          earlier M5 handoff
delivery/t30-rebuild-2026-11-05/          earlier T30 rebuild
delivery/m2/ delivery/m3/ delivery/notes/ historical member notes
```

These are retained because records/handoffs cite them. Do not delete without
checking `docs/handoffs/` references; prefer keeping the audit trail.

## Redundancy rules

```text
canonical P1 = delivery/p1-real-window-2026-11-07/
canonical 124 = delivery/cwe416-124-v4-rerun-2026-11-06/
canonical V5 = v5-replay-2026-11-07/ (16/16)
canonical Route A V4 = delivery/p1-routea-v4-symbolic-2026-11-07/
old candidate package = cwe416-124-candidate-2026-11-05 (do not use for current gates)
upload-2026-11-07 = distribution snapshot, not a second source of truth
```

## Not stored

```text
private keys
guest credentials
regenerated V5 logs (the four original logs are tracked)
```
