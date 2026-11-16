# Phase-8D gap governance: audit registry, hidden isolation and promotion gate

Status: additive Phase-8D evidence only.  This document does not claim a new
repair capability, hidden generalisation, or capability promotion.

## 1. Additive audit gap registry

`app/services/phase8d_gap_registry.py` and
`scripts/build_phase8d_gap_registry.py` add eight records
`AUDIT-8D-01..08` under `GAP-8D-AUDIT-01..08`:

| audit | finding | category | reproduction |
|---|---|---|---|
| AUDIT-8D-01 | hidden runtime zero candidates lack stage attribution | hidden_evidence_gap | reproduced |
| AUDIT-8D-02 | heap-malloc independent ABI rejection has no root-cause classification | verifier_root_cause_gap | reproduced |
| AUDIT-8D-03 | 4/7 discovery mechanisms are not_run | discovery_gap | reproduced |
| AUDIT-8D-04 | acceptance has no systematic False Reject coverage | acceptance_gap | reproduced |
| AUDIT-8D-05 | acceptance has no rule-mutation suite | acceptance_gap | reproduced |
| AUDIT-8D-06 | reflection has plans but no execution/results | reflection_gap | reproduced |
| AUDIT-8D-07 | no capability promotion state machine/approval gate | governance_gap | reproduced |
| AUDIT-8D-08 | hidden isolation is operational, not cryptographic | isolation_gap | reproduced |

Every record carries a category, evidence refs, reproduction status, severity,
confidence, dependencies, lineage (`derived_from` historical gap ids),
capability-dimension refs (D01-D20), a concrete proposed experiment, and an
explicit status.  The committed Phase-7 gap registry is read-only: the builder
records its SHA-256 and fails if the historical bytes change or if a lineage
parent is absent.  The historical artifact is never rewritten.

The registry covers the Phase-8D dimensions D02 (CPU architectures), D09
(data-flow analysis) and D10 (control-flow analysis), plus related dimensions
(D03, D13, D14, D19, D20).  This is a review surface, not a capability claim.

## 2. Hidden isolation audit

`scripts/audit_hidden_isolation.py` performs a read-only audit of the private
Phase-8C hidden corpus:

- private root is a real directory owned by the current user with exact mode
  `0700`;
- the public commitment and private manifest agree on the commitment digest,
  public-manifest digest and 8/6/2 counts;
- all material paths are relative/non-traversing and material bytes match the
  opaque binary digests;
- the hidden aggregate has the same 8 executed samples, 0 verified, 0
  false-verified and contains no per-sample ids/paths/material fields;
- opaque hidden ids/digests do not appear in tracked public files outside the
  canonical commitment.

The audit fails closed on missing root, wrong permissions, symlink root,
commitment/tamper inconsistency, aggregate shape/leakage, or public leakage.
It records reads/writes and **does not publish the private root path, hidden
ids, paths or content**.  It explicitly reports:

> operational isolation = true; cryptographic isolation = **false**

Same-UID/root readers can inspect the private root; this limitation is not
mitigated by a 0700 mode or an opaque commitment.

## 3. Promotion gate

`app/services/promotion_gate.py` and `scripts/evaluate_promotion.py` implement a
conservative state machine:

```
discovered -> analysis_only -> candidate_generated
          -> independently_verified -> generalized -> promoted
```

Rules enforced:

- only the next legal state is allowed; skipping levels is denied;
- prior-state evidence must be complete (`prior_state_evidence_complete`,
  `prior_evidence_refs`); a supplied state history must never skip;
- each target has required evidence: analysis, candidate/patch-plan/integrity,
  independent verifier + executed oracle + bounded regression, public + hidden +
  holdout generalization and hidden commitment/aggregate digests, and
  independent human approval for promotion;
- `false_verified` and `false_verified_internal` must be exactly 0;
- `not_run`, `blocked`, `unavailable` evidence never passes;
- auto-promotion is forbidden;
- promotion requires an independent approver id/role/reference/date and no
  unresolved blockers.

`artifacts/phase8d-promotion-2026-11-17/` evaluates actual Phase-8C evidence:
the public fixture cannot generalize (hidden has 0 verified), heap-malloc cannot
be independently verified (independent ABI rejection and internal withdrawal),
hidden analysis-only cannot produce a candidate (0 candidates), and promotion
without generalization/approval is denied.  No capability is promoted.

## 4. Evidence artifacts

- `artifacts/phase8d-gap-registry-2026-11-17/{gaps.json,README.md,SHA256SUMS}`
- `artifacts/phase8d-hidden-isolation-2026-11-17/{isolation.json,README.md,SHA256SUMS}`
- `artifacts/phase8d-promotion-2026-11-17/{promotion.json,README.md,SHA256SUMS}`

Each artifact has a fixed `generated_at` (`2026-11-17T00:00:00Z`) and an
independent `--check` that rebuilds deterministically in memory.

## 5. Boundaries and limitations

- This is not a new vulnerability-repair capability and does not promote any
  capability.
- The hidden benchmark remains 8 samples with 0 candidates/0 verified; a
  promotion gate denial is not hidden coverage.
- The promotion gate evaluates evidence; it does not produce or validate a new
  patch, and a synthetic allowed test transition is policy-test data only.
- The isolation audit cannot prevent same-UID/root reads and does not make the
  private corpus cryptographically secret.
- Phase-8D open-world discovery adapters, full false-reject/acceptance mutation
  suites and reflection execution remain proposed experiments, not delivered
  capabilities.
