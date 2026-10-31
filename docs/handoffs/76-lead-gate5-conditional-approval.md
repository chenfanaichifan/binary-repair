# 76 — Lead/M4 conditional Gate 5 approval (maximum-release path)

**From:** Lead / M4 (same operator; role-separated, not human-independent)
**To:** M3, M5, M1, M4
**Date:** 2026-10-31 22:15 (Asia/Hong_Kong)
**Status:** **Gate 5 Route A: CONDITIONAL PASS for integration/MVP candidate**,
not a final acceptance signature. `51` remains unsigned until the 29-file evidence
package is re-hashed.

## 1. What is accepted now

- Successor design: separate fixed-argv `jobwrap-gate5`, old Gate 4 `jobwrap`
  `b232d60b…` untouched; no P4 re-sign.
- Successor binary SHA-256: `90af91ef6b238428d202f891e5829ed81733b76dd9e7f184acd91f4cd769ff20`.
- Pinned probe: `scripts/m4_gate5_probe.py`
  `f39a0302dd1aa42635da80fa4e9160d37a221f5ac383270add3eaedcffd146cb`.
- Pinned identities: candidate `c4a159…aa82`, original `aa428157…8393`.
- Producer run: **19 PASS / 0 FAIL / 0 NOT VERIFIED**; six cases 6/6.
- Isolation attestation: uid/gid 1003, CapEff 0, NoNewPrivs 1, Seccomp 2,
  default_route empty, separate netns, probe blob pinned.
- Fail-closed mismatch test: tampered probe rejected before execution.
- Checklist file `67a` SHA-256
  `316094B2A68AC2FB5765B3D83012833A8084890D75E100BD2A54018D90DF4B29`;
  29-line manifest hash
  `05438764a119ee979fa3ab175b8ec08250e392e112cd5203fbd52cdf77873ec8`
  (self-consistent; actual files not yet delivered here).

## 2. Decision (maximum release, quality barrier at final tag)

**Gate 5 Route A is conditionally PASS for integration/MVP candidate purposes.**
This removes Gate 5 from the *integration blocker* list, but it is not a claim
that M4 has independently re-hashed the 29 evidence files.

The quality barrier is moved to the **final MVP acceptance tag**:

1. M3/M5 must deliver `gate5-evidence.zip` (29 files + real `SHA256SUMS`), the
   successor source commit (`ac96e74`/successor branch), build recipe, and
   fail-closed raw log.
2. M4 performs one independent re-hash of the 29 files and fills record `51`
   R1–R8 with PASS/FAIL/NOT VERIFIED.
3. If all pass: Gate 5 Route A becomes **final PASS**, Lead signs, final tag may
   be considered.
4. If any mismatch: this conditional PASS is revoked; Gate 5 returns to BLOCKED.

Until step 2 completes: `51` stays unsigned; no final MVP tag; fixture NOT FROZEN.

## 3. Scope boundaries

- Gate 4 formal remains PASS (strict unchanged round-trip, F2 waiver); this record
  does not change Gate 4.
- Gate 5 Route B remains separate/NOT RUN; this record is Route A only.
- V4 model-level PASS remains scope-limited; no binary-level/whole-program claim.
- No merge/tag action is authorized by this record alone; M1 still controls main
  and final tag.

## 4. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead (conditional release) | Lead | 2026-10-31 | **CONDITIONAL PASS for integration; final Gate5 PASS pending 29-file re-hash**; same-person limitation |
| M4 verifier | M4 | 2026-10-31 | **CONDITIONAL**; record 51 unsigned until evidence package verified |
| M3/M5 evidence owner | M3/M5 | 2026-10-31 | pending archive + source commit + raw logs |
