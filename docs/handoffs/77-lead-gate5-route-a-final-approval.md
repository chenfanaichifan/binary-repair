# 77 — Gate 5 Route A final approval after evidence re-hash

**From:** Lead / M4 (same operator; role-separated, not human-independent)
**To:** M3, M5, M1, M4
**Date:** 2026-10-31 22:30 (Asia/Hong_Kong)
**Re:** `gate5-evidence.zip` delivered by M3
**Status:** **Gate 5 Route A: PASS** (final Route A approval). Gate 5 Route B remains
**NOT RUN**. No final MVP tag, no fixture freeze.

## 1. Evidence package verified

| Item | Value |
|---|---|
| `gate5-evidence.zip` | 387,563 B, SHA-256 `371cdacd15abe3e0db629440640ab4320dd3d3d72c8e323c33ed57a1c8dcbe8c` |
| root `SHA256SUMS` | 43/43 valid, SHA-256 `a193a749…d845` |
| `evidence/SHA256SUMS` | 29/29 valid, SHA-256 `05438764…ec8` |
| successor `jobwrap-gate5` | `90af91ef…ff20` |
| probe `m4_gate5_probe.py` | `f39a0302…d146cb` |
| candidate / original | `c4a159…aa82` / `aa428157…8393` |
| six cases | 6/6, raw rc/stdout/stderr present |
| isolation | uid/gid 1003, CapEff 0, NoNewPrivs 1, Seccomp 2, `default_route=''`, netns `net:[4026532222]` |
| fail-closed | tampered probe: exit 1, hash mismatch message |
| build provenance | source `jobwrap_gate5.c` `09900e3a…7340`, guest build recipe + GCC 13.3.0 environment |

R1–R8 in record `51` are all PASS. The old Gate 4 `jobwrap b232d60b…` and P4 chain
were not touched.

## 2. Decision

1. **Gate 5 Route A: PASS.** `51` is signed by M4 and approved by Lead, with the
   same-person limitation recorded. Conditional approval `76` is converted to final
   Route A approval.
2. **Gate 5 Route B: NOT RUN** — separate record, no pass written.
3. **Fixture: NOT FROZEN.** Final MVP tag: **NOT CREATED**.
4. **MVP: NOT COMPLETE** while Route B is not run; Gate 4 is PASS (strict
   round-trip scope) and Gate 5 Route A is PASS.

## 3. Limitation

The named source commit `ac96e74` was not fetchable from this workspace; the
successor source bytes, build recipe and build environment are present in the
verified zip and hash-bound in the manifest. Reproducibility from source should be
recorded when the source commit is available.

## 4. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| M4 verifier | M4 | 2026-10-31 | **PASS — Gate 5 Route A**; R1–R8 verified from raw files |
| Lead approval | Lead | 2026-10-31 | **APPROVED — Gate 5 Route A PASS**; same-person limitation |
| Gate 5 Route B | M5 | — | **NOT RUN**; no pass |
