# 55 — M5 completed artifacts index (upload only)

This index records M5-produced artifacts. It is **not** a gate pass, not an M4
verifier row, and not a Lead approval.

## Evidence packages

| Path | SHA-256 | Status |
|---|---|---|
| `dist/m5-evidence/P3A-routea-2026-10-29-v4.zip` | `347e7d22…fa15` | P3A final; adapter/worker inconclusive |
| `dist/m5-evidence/P3B-package-v3-2026-10-29.zip` | `72d789c6…034b` | P3B v3 structural accept; partial/inconclusive |
| `dist/m5-evidence/P4-package-2026-10-29.zip` | `427dd71d…2dd4` | P4 observed only; incomplete; NOT RUN |
| `dist/m5-evidence/P3B-fixed-C-2026-10-29.zip` | `2f7691be…54b8` | source package; superseded by P3B v3 for runtime |
| `dist/m5-evidence/P3B-v3-worker-rerun-2026-10-29.log` | `f1c7c6dc…2a14` | P3B v3 observation only |

`dist/m5-evidence/SHA256SUMS` is the package-level manifest.

## M5 code/docs

```text
scripts/check_handoff.py
scripts/normalize_handoff.py
docs/handoffs/INTERFACE-v1.md
routeb/jobwrap_routeb.sh
routeb/jobwrap_gate5.sh
routeb/experiment/samples/fixed_badSink_existing_imports.c
tools/p2_acceptance.py
tests/integration/test_p2_acceptance.py
docs/handoffs/39..53, docs/route-b/23-gate4-record.md
```

## Status (unchanged)

```text
Gate 4: DRAFT / NOT RUN
Gate 5: BLOCKED (D3)
P3A v4: accepted partial / inconclusive
P3B v3: partial / inconclusive; v4 pending executor + adapter/worker
P4: observed only; incomplete
PR #10: no merge/tag
Fixture: NOT FROZEN
```
