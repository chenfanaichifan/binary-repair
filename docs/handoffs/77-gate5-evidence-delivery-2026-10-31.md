# 77 — M3/M5: Gate 5 Route A evidence delivery (satisfies Lead 76 §2.1)

**From:** M3+M5 (evidence owner)
**To:** M4 (verifier), Lead
**Date:** 2026-10-31 (Asia/Hong_Kong)
**Status:** evidence delivered — awaiting M4 single re-hash + record `51` R1–R8

## 1. What this delivers

This record confirms the four quality-barrier items the Lead required in
`docs/handoffs/76-lead-gate5-conditional-approval.md` §2.1 are now delivered as
a single, self-consistent package:

**`dist/gate5-evidence.zip`** — SHA-256 `371cdacd15abe3e0db629440640ab4320dd3d3d72c8e323c33ed57a1c8dcbe8c`.

## 2. Item-by-item

| # | Lead requirement | Delivered in |
|---|---|---|
| 1 | `gate5-evidence.zip` (29 files + real SHA256SUMS) | `evidence/` (29 files + `evidence/SHA256SUMS`); top-level `SHA256SUMS` covers all 43 payload entries |
| 2 | successor source commit `ac96e74` (or fetchable branch) + guest build recipe | `successor/jobwrap_gate5.c` (== git `ac96e74` byte-for-byte), `successor/build-recipe.md`, `successor/build-environment.txt`, `successor/jobwrap-gate5` (binary `90af91ef…ff20`) |
| 3 | fail-closed tamper-rejection raw log | `fail-closed/` — `stderr.bin` records `jobwrap-gate5: probe blob mismatch: got 15ba41dc…, expected f39a0302…`; `exit-code.txt` = `1`; `command.txt`, `stdout.bin` (empty), `tampered-probe.sha256` |
| 4 | precise invocation + `environment.txt` | `invocation.txt` (fixed argv + resolved paths); `evidence/environment.txt` (uid/gid 1003, CapEff 0, NoNewPrivs 1, Seccomp 2, default_route empty, netns isolated, script_sha256 pinned) |

## 3. Self-consistency verified before delivery

- Top-level `SHA256SUMS`: 43 payload entries, **0 mismatch**.
- Inner `evidence/SHA256SUMS`: 29 files, **0 mismatch**.
- Successor binary `90af91ef…ff20` == record 76 §1; probe `f39a0302…d146cb` == pin;
  original `aa428157…8393`, candidate `c4a159…aa82` match record 76.

## 4. What happens next (unchanged from 76)

1. M4 performs one independent re-hash of the 29 evidence files and fills
   record `51` R1–R8 with PASS/FAIL/NOT VERIFIED.
2. All PASS → Gate 5 Route A becomes final PASS; Lead signs; final tag may be
   considered.
3. Any mismatch → conditional PASS revoked; Gate 5 returns to BLOCKED.

Until M4's re-hash completes: record `51` unsigned, fixture NOT FROZEN, no
final MVP tag.

## 5. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| M3/M5 evidence owner | M3+M5 | 2026-10-31 | delivered (`dist/gate5-evidence.zip` `371cdacd…be8c`) |
| M4 verifier | M4 | — | pending re-hash |
| Lead | Lead | — | pending final tag decision |
