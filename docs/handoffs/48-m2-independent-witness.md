# 48 — M2 independent witness (P3A v4 / P3B fixed / P4 / Gate 5)

**From:** M2 (GUI)
**To:** Lead, M3/VMer, M5, M4
**Date:** 2026-10-29
**Status:** witness in progress; **no gate signed**. Deadline 2026-10-31 12:00.

## Independence statement

M2 unpacked its own copies from the transfer directory and recomputed every
hash. M2 did **not** accept producer `observed` claims, did **not** run guest
code, did **not** edit any fixture/artifact, and does **not** sign Gate 3/4/5.
The checker result is the evidence; `PASS` here would still be only a handoff
witness, never a gate approval.

## Packages actually present

| Expected package | Present? | Result |
|---|---|---|
| P3A v4 | **NO** | Only `P3A-routea-2026-10-29-v3.zip`, `P3A-routea-2026-10-29.zip`, `P3A-routea-real-2026-10-29.zip` were available. No v4 package. |
| P3B (fixed) | **partial** | `P3B-fixed-C-2026-10-29.zip` contains `fixed_badSink.c`, README, RUNBOOK, SHA256SUMS only. No handoff/bundle/candidate. |
| P4 | **NO evidence** | `M3-P4-P3B-execution-kit-2026-10-29.zip` is an execution kit (checker/templates/RUNBOOK), not a P4 evidence package. |
| Gate 5 blocked/follow-up | **NO package** | Only the plan `docs/handoffs/43-m4-gate5-gate6-plan.md`; no blocked/follow-up package was delivered. |

## Commands and observations

Checker (same script for producers and consumers):

```powershell
python scripts/check_handoff.py <package> --expect-from M3 --expect-to M5
```

Observed:

- `P3A-routea-2026-10-29-v3`: **FAIL, 36 errors** (error count from checker
  summary). The producer handoff uses a private schema (`schema_version`, `id`,
  `files`, `package_id`) instead of interface v1: missing `task`, `deadline`,
  `requested_action`, `commands`, `expected`, `observed`, `artifacts`,
  `interface_version`, `status`. `SHA256SUMS` also omits `handoff.json`.
- `P3A-routea-2026-10-29`: **FAIL, 38 errors** (same class of interface-v1
  mismatch).
- `P3A-routea-real-2026-10-29`: **FAIL, missing `handoff.json`** (only
  `handoff.md`; checker cannot pass).
- `P3B-fixed-C-2026-10-29`: **FAIL, missing `handoff.json`**; no package.
- `p3b-2026-10-29`: missing `handoff.json`; checker cannot pass.
- `M3-P4-P3B-execution-kit-2026-10-29`: no package/handoff; checker not
  applicable.

Hash verification (`sha256sum -c SHA256SUMS`, PortableGit sha256sum):

| Package | Exit | Observation |
|---|---|---|
| P3A v3 | 0 | 25 listed files OK; `handoff.json` is not covered. |
| P3A plain | 0 | 27 listed files OK. |
| P3A real | 0 | 23 listed files OK. |
| P3B fixed C | 0 | 3 files OK; only source, no candidate. |
| P4/P3B kit | 0 | 5 kit files OK; kit is not evidence. |
| p3b static | **1 as shipped** | Last SHA256SUMS line has CRLF; `sha256sum` reads the CR as part of the filename. After LF normalization: **exit 0, 15 files OK**. |
| P3A/P3B candidate bytes | — | P3A `route_a/candidate.elf` = `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` (26,792 B); `original.elf` = `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` (26,792 B). P3B static `candidate.elf` = `decdcdb821bfe4c41a070b0a23a2f6497f46a92f439cb02a1e4139a82cde954b` (not the fixed-C build). |

Additional observations:

- `P3A-routea-real` handoff.md says gate3 source `gate3-bundle-v3-2026-10-22.zip`
  and V0/V1/V3 passed, V2/V4/V5 not_run; M4 verifier / M5 replay are pending.
  This is producer provenance, not witness evidence.
- `p3b` package has `bundle-sha256.txt = 4730000e…` while the `SHA256SUMS` file
  hash is `6046cfeb…`; README already warns not to reuse the old value. This
  witness records the discrepancy but does not call it a pass.
- P3B fixed-C cannot be witnessed as a fixed candidate: there is no compiled
  candidate, runtime manifest, or handoff package.
- P4 evidence does not exist; Gate 4 remains **NOT RUN**.
- Gate 5 blocked/follow-up package does not exist; Gate 5 remains pending.

## Witness verdict

**BLOCKED / NOT VERIFIED.** No package reached interface-v1 checker PASS; P3A v4,
a real fixed-P3B package, P4 evidence, and the Gate 5 package are missing. M2
signs no gate pass and changes no gate status. Gate 3/4/5 statuses remain as
recorded by their owners.

## Re-check trigger

Re-run this witness when M3/VMer/M5 publish:

1. P3A **v4** with interface-v1 `handoff.json`, complete `artifacts`,
   `commands/expected/observed`, and checker PASS;
2. P3B fixed package with candidate/edit-manifest/manifest-compare and checker
   PASS;
3. P4 evidence package (not the kit) with checker PASS;
4. Gate 5 blocked/follow-up package with checker PASS.

Commands are unchanged; only the package paths need updating.
