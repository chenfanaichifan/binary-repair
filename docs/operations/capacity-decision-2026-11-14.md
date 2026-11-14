# Capacity-check integration decision (2026-11-14)

Status: **superseded later the same day by the full-coverage milestone**.

The original decision kept local commit `86587da` (reviewed capacity-check
rewrite) isolated in worktree `../worktree-capacity-check` and branch
`backup/capacity-86587da`, not merged and not pushed, to keep it separate from
the path-A/benchmark work.

During the capability-gap audit the same class was re-identified as one instance
of the general problem the milestone addresses: a *repair-capability gap* whose
evidence model (PoC differential, in-place rewrite) cannot be expressed by the
legacy stack gate. Keeping a working engine outside the product would have left
that gap open, so the reviewed implementation was re-integrated under an
explicit, declared evidence model:

- engine: `app/services/repair/capacity.py`;
- matrix: sink class `capacity_check_mismatch`, strategy `capacity` on
  `elf/x86_64/64/little` only;
- gate: profile `native_poc_rewrite` in
  `app/services/binary_pipeline.py`/`app/services/unified_verification.py`,
  with `patch.capacity` and `patch.rewrite` re-deriving every rewrite action
  from the original and candidate bytes and the supplied PoC/regression
  manifest as the only runtime evidence;
- discovery: explicit `strategy="capacity"` or the fail-closed automatic
  fallback when the legacy immediate engine finds nothing;
- fail-closed behaviour: no manifest, no runner or a non-passing differential
  keeps the outcome `not_verified`/inconclusive with no candidate download.

Acceptance evidence in this milestone: `fixtures/elf/vuln-capacity-confusion-x86_64.elf`
(sha256 `72fb53cb...`) repairs to `93e27f2f...` and passes all 21 required gate
checks through the review API with the real manifest executed in the Lima guest;
the synthetic sibling-check fixture also repairs to `5b6501b0...`. The branch
`backup/capacity-86587da` remains as historical evidence of the isolation step;
the integrated version is on `coverage-audit-2026-11-14`.
