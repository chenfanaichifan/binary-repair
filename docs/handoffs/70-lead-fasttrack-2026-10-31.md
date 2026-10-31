# Lead fast-track approval policy (2026-10-31)

**Reason:** the Lead and M4 are the same operator; repeating independent-verification
loops and treating every environment-only gap as a blocker was slowing delivery.
This policy removes *non-substantive* blockers while keeping gate claims honest.

## Default approvals (no further back-and-forth)

| Change type | Default decision |
|---|---|
| Bug fix / integration change with changed-area tests passing | **APPROVE merge**; full-suite environment gaps are recorded, not blocking |
| Docs-only / record cleanup | **APPROVE** if no gate/claim is changed |
| Evidence package with valid `SHA256SUMS` + checker PASS | **ACCEPT** as observed evidence; no re-review loop |
| Same-operator M4/Lead verification | **APPROVE with disclosure**, not an independent claim |
| Environment-only failure (missing binutils/capstone/elftools, e2e timeout) | **Not a blocker**; record `not_run`/environment reason |

## Still requires evidence (cannot be auto-approved)

These are not "process pedantry"; writing them without evidence would fabricate a result:

- `V4 proven` / `success_within_scope`
- `Gate 5 PASS`
- A final MVP acceptance tag claiming full acceptance

They may remain `not_run`/`BLOCKED`; the delivery can still be approved as an
integration/partial result. Do not relabel `not_run` as `passed`.

## Immediate decisions

1. **`1406f11` is APPROVED for merge into `main`.** Changed-area tests pass
   (29 acceptance, 6 orchestration, 11 writer+p2); no gate/V4 change; the reported
   full-suite gap is environment-only and is recorded as not locally reproduced.
   No tag is created by this approval.
2. **P0-1 full-suite environment gap is non-blocking for integration.** Keep the
   `verifiable subset` wording; do not claim full-suite PASS.
3. **M2 e2e timeout is non-blocking**; record as `not_run`/environment.
4. **V4 and Gate 5 remain honest gaps** until raw evidence exists; final MVP
   acceptance must list them, but they do not block merging integration work.

## Merge/tag discipline retained

- Only M1 writes `main`/tags; this approval authorizes merging `1406f11`, not a
  final MVP tag.
- A final acceptance tag still needs the remaining gate claims or an explicit
  acceptance report that records them as open.
- No test/oracle weakening is authorized by this policy.
