# Phase-8D additive gap registry

- generated_at: `2026-11-17T00:00:00Z` (fixed; no wall clock)
- historical registry: `artifacts/gap-registry-2026-11-16/gaps.json` (sha `9283c140bb4a60619b37e4259362c8d0a85f81c80994e3e7f21edc6c4bf7ef9c`, 64 records, **not rewritten**)
- records: 8 (AUDIT-8D-01..08)
- phase-8D dimensions covered: D02, D09, D10
- capability promotion: **false**; no auto-promotion
- gaps.json sha256: `7767b785666ff92994c4bf84746bcb0592653c39abc4eb27fa563b77b71a0c15`

| audit | category | severity | reproduction | status | gap | experiment |
|---|---|---|---|---|---|---|
| `AUDIT-8D-01` | hidden_evidence_gap | high | reproduced | open | `GAP-8D-AUDIT-01` | EXP-8D-HIDDEN-STAGE-ATTRIBUTION |
| `AUDIT-8D-02` | verifier_root_cause_gap | high | reproduced | open | `GAP-8D-AUDIT-02` | EXP-8D-HEAP-MALLOC-ABI-ROOT-CAUSE |
| `AUDIT-8D-03` | discovery_gap | high | reproduced | open | `GAP-8D-AUDIT-03` | EXP-8D-DISCOVERY-ADAPTERS |
| `AUDIT-8D-04` | acceptance_gap | high | reproduced | open | `GAP-8D-AUDIT-04` | EXP-8D-FALSE-REJECT-SUITE |
| `AUDIT-8D-05` | acceptance_gap | high | reproduced | open | `GAP-8D-AUDIT-05` | EXP-8D-ACCEPTANCE-MUTATION |
| `AUDIT-8D-06` | reflection_gap | high | reproduced | open | `GAP-8D-AUDIT-06` | EXP-8D-REFLECTION-EXECUTION |
| `AUDIT-8D-07` | governance_gap | critical | reproduced | open | `GAP-8D-AUDIT-07` | EXP-8D-PROMOTION-GATE |
| `AUDIT-8D-08` | isolation_gap | critical | reproduced | open | `GAP-8D-AUDIT-08` | EXP-8D-HIDDEN-ISOLATION-AUDIT |

## Historical lineage

- `AUDIT-8D-01`: `GAP-FAIL-META-GATE-MISMATCH-GATE-SCENARIO-EXECUTION`, `GAP-KNOW-4E20E505D6BE`
- `AUDIT-8D-02`: `GAP-FAIL-META-GATE-MISMATCH-GATE-REWRITE`, `GAP-KNOW-2449225E53BC`, `GAP-KNOW-0046331D4CF9`
- `AUDIT-8D-03`: `GAP-KNOW-8CFA10A33EE8`, `GAP-KNOW-E9D869738D70`
- `AUDIT-8D-04`: `GAP-FAIL-META-GATE-MISMATCH-SAFE-DEFAULT`, `GAP-FAIL-META-GATE-MISMATCH-GATE-PROFILE-ENFORCEMENT`
- `AUDIT-8D-05`: `GAP-FAIL-META-GATE-MISMATCH-GATE-SATISFIABILITY`
- `AUDIT-8D-06`: `GAP-KNOW-E9D869738D70`
- `AUDIT-8D-07`: `GAP-FAIL-META-GATE-MISMATCH-GATE-PROFILE-ENFORCEMENT`, `GAP-FAIL-META-GATE-MISMATCH-GATE-PROFILE-CHECKS`
- `AUDIT-8D-08`: `GAP-CLAIM-RG-EXTERNAL-POC-DOC-MACHO-X86-64`, `GAP-FAIL-META-GATE-MISMATCH-GATE-POC-UNAVAILABLE`

## Limitations

- these are audit findings, not repair capability claims
- reproduction_status=reproduced means the evidence was inspected/replayed, not that the gap is fixed
- no record may be promoted by this builder; only the separate promotion gate can evaluate a capability state
- the historical Phase-7 registry bytes must remain unchanged; lineage is by reference only
- hidden evidence remains aggregate-only; no hidden sample ids/paths/content are included
