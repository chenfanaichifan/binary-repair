# Phase-8D promotion gate evaluation

- generated_at: `2026-11-17T00:00:00Z` (fixed)
- decisions: 4 (allowed 0, denied 4)
- capability_promotion: **false**; promoted_count=0
- public verified: 2; hidden verified: 0
- published false_verified: 0; internal withdrawn: 1

| record | transition | decision | first violations |
|---|---|---|---|
| `phase8c-stack-strcpy-x86_64` | independently_verified -> generalized | denied | generalization.hidden_verified: hidden verification is required; generalization.hidden_verified_count: at least one independently verified hidden sample is required; generalization.holdout_verified: holdout verification is required |
| `phase8c-stack-strcpy-x86_64` | independently_verified -> promoted | denied | illegal transition independently_verified->promoted; legal next is 'generalized'; generalization.hidden_verified: hidden verification is required; generalization.hidden_verified_count: at least one independently verified hidden sample is required |
| `phase8c-heap-malloc` | candidate_generated -> independently_verified | denied | verification.false_verified_internal=1 must be 0; verification.decision: independent verifier must decide verified |
| `phase8c-hidden-runtime` | analysis_only -> candidate_generated | denied | candidate.candidate_sha256: candidate sha256 is required; candidate.patch_plan_sha256: patch plan sha256 is required; candidate.integrity_evidence_refs: candidate integrity evidence is required |

## Policy

The gate permits only the next legal state and requires prior-state evidence, independently executed verification, hidden/holdout evidence, bounded regression, false_verified=0, and independent human approval at promotion. It has no auto-promotion path and never treats not_run as pass.

## Limitations

- no capability was promoted; all Phase-8C transitions above are denied
- the public fixture's verification is not hidden or holdout generalization evidence
- heap-malloc's independent ABI rejection is preserved; its deterministic claim is withdrawn
- hidden has 0 candidates and 0 independently verified samples; hidden generalisation is not established
- a promotion decision would also require independent human approval and a complete generalized evidence bundle
- not_run/blocked evidence is never treated as a pass
