# 52 — Lead ruling: P3A v5 ratified, Gate 5 invocation blocked, M5 hard deadline 2026-10-30 10:00

**From:** Lead (decision owner)
**To:** M3 (executor), M5 (Gate 4 DRI / tooling), cc M1, M4
**Date:** 2026-10-29 18:15 (Asia/Hong_Kong)
**Status:** decision record. **No Gate 4/5 approval, no fixture freeze, no PASS claimed.** Gate 3
stays closed/approved; Gate 4 `NOT RUN`; Gate 5 `pending/unsigned`; Gate 6 partial; fixture
`NOT FROZEN`.
**Basis:** M3's completion relay (P3A v5, Gate 5 suite, P4/P3B blockers); `docs/handoffs/34`,
`35`, `41`, `47`, `50`, `51`; `docs/route-b/23-gate4-record.md` (DRAFT/NOT RUN).

> **Amendment 2026-10-29 18:30:** M5 reports D1–D4 delivered on `origin/main` (handoff 44:
> T5.1 ratified; gate4 kit `499f510c…`/runner `515c4d60…`, routeb wrapper `70b50f92…`, gate5
> wrapper `859ac8fe…`) — pending independent hash verification. The hard deadline in §4 now
> covers verification/merge, not authoring; the Gate 4/5/P3B/identity status is in
> `docs/handoffs/53` and `BOARD.md`.

> **Provenance note:** M3's message reached the Lead as a chat relay with abbreviated hashes
> (`f5b56359…`, `005be610…`, `8b5594cf…`). Full 64-hex values must be read from the delivered
> package's `handoff.json`/`SHA256SUMS`, never from prose. Nothing in this ruling verifies
> content that the Lead cannot access.

## 1. M3's completion information (recorded as reported, not yet independently verified)

| Item | Reported by M3 | Lead treatment |
|---|---|---|
| P3A | **v5** `f5b56359…`; checker PASS (25 artifacts / 26 sums); `SHA256SUMS` hash `005be610…`; candidate/evidence unchanged; v4 void | **ratified as the canonical P3A version** — see §2; content still needs M4/M5 package verification |
| Gate 5 Route A | suite `8b5594cf…`; M4 fixed-script launch mode **unsupported by jobwrap** | **blocked** — see §3; no direct run, no PASS/FAIL |
| T3.1 P4 | **NOT RUN**, waiting on M5 gate4-harness + v6 kit | stays `NOT RUN`; Gate 4 record stays DRAFT |
| T3.3 P3B | old run **V3 FAIL**; fixed C `c9609f32…` waiting for guest rerun | `NOT VERIFIED`; no Gate 4 row may use the old run |
| Gate 4 / Gate 5 | both **unsigned** | unchanged |

## 2. Decision on P3A v5 — RATIFIED as version/format, not as gate evidence

1. **P3A v5 is the canonical P3A version. P3A v4 is void.** M3 does not need to reproduce the
   Lead's unavailable P3A-v1 draft; rebuilding under `docs/handoffs/INTERFACE-v1.md` is an
   acceptable basis. The Lead will not demand byte-identical draft adoption.
2. Ratification is **conditional and not a pass**. It becomes usable only when:
   - the P3A package (artifacts + `SHA256SUMS`) is delivered to a path M4/M5 can read (repo
     evidence store or an approved transfer), with the full 64-hex identifiers in its
     `handoff.json`/`SHA256SUMS` (not prose);
   - `check_handoff.py <P3A> --expect-from M3 --expect-to M5` PASS is reproduced by M5 and by M4;
   - M4 independently re-hashes every artifact, confirms the candidate hash from bytes, and
     confirms the "candidate/evidence unchanged" claim against v4;
   - the package is not edited after delivery (republish as a new version if changed).
3. If those conditions fail, the package is **rejected/blocked**; v5 does not become Gate 4/5
   evidence and no row may cite it.
4. The reported `f5b56359…` is treated as the package/version identifier until the package is
   read; the **candidate hash must be declared and verified from bytes** — no inference from a
   truncated chat hash.

## 3. Decision on the Gate 5 Route A invocation — do not run direct

M3 is right that running `scripts/m4_gate5_probe.py` directly (outside the fixed-argv jobwrap)
would violate W5/isolation. **Direct execution is forbidden. No PASS/FAIL may be written from an
unisolated run.**

**Required (M5 owns):** provide one of the following by the hard deadline:

- **preferred:** a fixed-argv `jobwrap` probe mode, e.g.
  `jobwrap probe m4-gate5 -- <repo-root> <work-dir>` that `execv`s exactly
  `python3 <repo-root>/scripts/m4_gate5_probe.py <repo-root> <work-dir>` after creating the
  no-egress netns and dropping to uid 1003 — no shell string, no caller-supplied command; or
- a documented **existing** fixed-argv invocation of the same jobwrap version that does exactly
  this, with the exact syntax, the jobwrap SHA-256, and the isolation attestation it emits.

M3/VMer must not substitute `sudo -u 1003`, a direct shell, or an ad-hoc wrapper for this. If no
fixed invocation exists by the deadline, M3/VMer publishes a **blocked package** naming M5 as the
unblocker; M4 records Gate 5 Route A as `NOT VERIFIED` (record `51` stays unsigned), and Gate 5
stays `pending`.

## 4. M5 hard deadline — 2026-10-30 10:00 (Asia/Hong_Kong)

The following M5 deliverables are a **hard cutoff**. The Lead will not approve Gate 4/5 or
freeze the fixture while any is missing:

| # | M5 deliverable | Unblocks |
|---|---|---|
| D1 | `gate4-harness` + `v6` kit (pinned hashes, invocation doc) | T3.1 P4 / Gate 4 formal run |
| D2 | `jobwrap` Route B invocation (fixed argv, no shell) | T3.3 P3B rerun |
| D3 | Gate 5 fixed-script launch mode (or documented fixed-argv equivalent, §3) | Gate 5 Route A probe |
| D4 | `INTERFACE-v1.md` + checker state reconciled (already on the final branch; M5 confirms it is current) | P3A v5/P4 package acceptance |

**If D1-D4 are not delivered at 2026-10-30 10:00:** M3/VMer publish blocked packages for
P4/P3B/Gate-5 probe with the exact missing item and "M5" as the unblocker; the Lead marks the M5
rows `OVERDUE`/`blocked`; Gate 4 stays `NOT RUN`, Gate 5 stays `pending`, M4's Gate 5 record stays
`NOT VERIFIED`, and **no approval/freeze happens**. This deadline supersedes the earlier
12:00/18:00 delivery times for these specific items.

## 5. Status (unchanged by this ruling)

| Gate/artifact | Status |
|---|---|
| Gate 3 Route A | CLOSED / APPROVED `0b3b51e4…`; do not reopen |
| Gate 4 Route B formal | `NOT RUN`; record `docs/route-b/23-gate4-record.md` is DRAFT with P4/P3B/checker/real-p2 missing and M4/Lead rows blank |
| Gate 5 placement | `pending`; Route A probe blocked on §3; Route B half M5 pending; record `51` unsigned/`NOT VERIFIED` |
| Gate 6 | partial; V4 `not_run` |
| Fixture | **NOT FROZEN** (`docs/handoffs/48`); no freeze decision is made or implied here |
| P3A v5 | ratified version, pending package verification (§2) |

## 6. Next actions by owner

- **M5 (hard deadline 2026-10-30 10:00):** D1-D4; publish the fixed Gate 5 invocation (or the
  documented equivalent) with exact hashes and jobwrap version.
- **M3/VMer:** after D1-D4, run P4 and the Gate 5 probe; if missed, publish blocked packages with
  exact missing items and unblocker; do not run the Gate 5 probe direct.
- **M4:** keep record `51` unsigned; when the P3A v5 package and Gate 5 raw output arrive, verify
  independently and fill only `PASS`/`FAIL`/`NOT VERIFIED`; JOIN-1 stays waiting for P4 + signed
  M5 record + real p2.
- **Lead:** hold the hard deadline; no approval/freeze until the evidence exists.

## 7. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead (ruling/deadline) | Lead | 2026-10-29 | P3A v5 ratified (conditional); Gate 5 direct-run forbidden; M5 hard deadline 2026-10-30 10:00; no approval/freeze |
| M5 (ack + delivery) | M5 | — | pending D1-D4 |
| M3/VMer (ack + execution/blocked) | M3 | — | pending D1-D4 |
