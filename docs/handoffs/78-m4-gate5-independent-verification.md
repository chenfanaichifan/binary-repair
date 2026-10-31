# 78 — M4 independent verification of full Gate 5 Route A evidence (`gate5-evidence.zip`)

**From:** M4 (independent verifier; same operator as Lead — role-separated, not human-independent)
**To:** Lead, M3/VMer, M5
**Date:** 2026-10-31 22:40 (Asia/Hong_Kong)
**Source:** `gate5-evidence.zip` (the full package, not the earlier v1 subset)
**Outer SHA-256:** `371CDACD15ABE3E0DB629440640AB4320DD3D3D72C8E323C33ED57A1C8DCBE8C`
(387,563 B; read-only; no binary executed)
**Verdict:** **Gate 5 Route A: PASS** for this evidence package, independently re-hashed and
checked. **Gate 5 Route B: NOT RUN** — no Route B Gate 5 raw evidence exists to verify.
This record confirms, but does not replace, the signed record `51`/`77`.

## 1. Package and manifest — PASS

- Outer SHA-256 matches the final-approval value `371cdacd…be8c`.
- Root `SHA256SUMS`: **43/43**, 0 mismatch; manifest SHA-256
  `a193a749bceb17e854effa041bc315507e86a3e5288a0e7743c55cc2d578d845`.
- `evidence/SHA256SUMS`: **29/29**, 0 mismatch; SHA-256
  `05438764a119ee979fa3ab175b8ec08250e392e112cd5203fbd52cdf77873ec8`.

## 2. R1–R8 independent re-hash and review

| ID | Verdict | Independent observation |
|---|---|---|
| R1 | **PASS** | candidate `c4a159…aa82`; original `aa428157…8393`; probe `f39a0302…d146cb`; successor binary `90af91ef…ff20`; source `jobwrap_gate5.c` `09900e3a…7340` |
| R2 | **PASS** | GDB: `0x401000–0x402000` mapped `r-xp`; probe-summary R2 |
| R3 | **PASS** | cave file = memory = candidate slice `0x4018e9..0x401fff`, 1,815 B, SHA `1926ce1f…6b1d` |
| R4 | **PASS** | GDB markers SITE `0x401304` → CAVE `0x4018e9` → AFTER `0x401309` → RET `0x401317` |
| R5 | **PASS** | six raw cases: raw rc/stdout/stderr hashes match `six-cases.json`; valid rc0, invalid rc1, 6/6 |
| R6 | **PASS** | fixed invocation `jobwrap-gate5 probe m4-gate5 -- /srv/gate5-build /var/tmp/gate5-work`; execv `/usr/bin/python3 .../m4_gate5_probe.py ...`; uid/gid 1003, CapEff 0, NoNewPrivs 1, Seccomp 2, no default route, netns; fail-closed tampered-probe exit 1 with mismatch log |
| R7 | **PASS** | candidate before = after `c4a159…aa82` |
| R8 | **PASS** | root 43/43 + evidence 29/29; manifests hash-bound |

Build provenance: source bytes, `build-recipe.md`, and GCC 13.3.0 guest environment are in the
package. **Limitation:** the named git commit `ac96e74` is still not fetchable from this
workspace; source bytes are hash-bound in the zip, but reproducibility from a commit is not
independently demonstrated. This is recorded, not hidden; it does not invalidate the Route A
probe rows, but it is a provenance limitation.

## 3. Route B Gate 5 — no evidence

The package is **Route A only**. Record `51`/`77` explicitly say Gate 5 Route B is **NOT RUN**;
there is no Route B Gate 5 raw evidence to re-hash. I cannot mark Route B PASS/FAIL; it remains
**NOT VERIFIED / NOT RUN**.

## 4. V4

The current V4 status is **model-level PASS (bounded 64)** as previously recorded. Binary-level
V4 (candidate-binary symbolic execution) was **not run** and is not part of this Gate 5
verification. If binary-level V4 is required, it is a separate guest/angr task; do not infer it
from this Gate 5 evidence.

## 5. M4 verifier row

| Role | Verdict | Limitation |
|---|---|---|
| M4 verifier — Gate 5 Route A | **PASS**, R1–R8 independently verified | M4 verifier = Lead same operator; role-separated, not independent two-person signature. Source commit `ac96e74` unavailable; source bytes/build recipe hash-bound in zip. |

No new final MVP tag, no fixture freeze, no Gate 5 Route B claim.

## 6. Status

| Item | Status |
|---|---|
| Gate 5 Route A | **PASS** (evidence `371cda…be8c`; R1–R8) |
| Gate 5 Route B | **NOT RUN** (no evidence) |
| Gate 4 | PASS (strict scope; unchanged) |
| V4 | model-level PASS (bounded 64); binary-level not run |
| Fixture | **NOT FROZEN** |
| Final MVP tag | **NOT CREATED** / MVP NOT COMPLETE |
