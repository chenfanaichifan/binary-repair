# 53 — Lead record: P3B provenance hold, Gate 4 JOIN-1 conditions, and the M4=Lead identity limitation

**From:** Lead (decision/record owner)
**To:** M1, M3, M4, M5, M2
**Date:** 2026-10-29 18:30 (Asia/Hong_Kong)
**Status:** **RECORD ONLY — no gate approval, no pass, no fixture freeze.** Gate 3 stays
closed/approved; Gate 4 `NOT RUN`; Gate 5 `pending/unsigned`; Gate 6 partial; fixture
`NOT FROZEN`.

## 1. P3B provenance hold — no `pass` may be written until it is fixed

M5's review `docs/handoffs/39-m5-to-m3-P3B-v2.md` (on `origin/main`) already records the
package verdict. The measured facts are:

| Item | Observed |
|---|---|
| Package | `P3B-package-2026-10-29.zip`, SHA-256 `f46a3c8ac3c5cfbea646ea5b08e2fb03ce12ec535fcb6fd1d966ecdcf182f639` |
| Checker | PASS (15 files / 15 sums, `9fec168f…`) — necessary, not sufficient |
| Candidate | `63fcafa6ed01d2db7d5d8a1af460af994e65da853c0c250b05c3eb761f616d01` |
| Replacement C | `a2e4ff8f5071c20328f977153775c8dc7d8bf8a9f867278a5de2d48b81ccc90e` |
| `manifest-repaired.json` | 6/6, `repaired_pass=true` (runtime only) |
| Provenance binding | **broken**: `jobwrap-routeb.json` says `c_source_sha256=c9609f32…`, `exit_code=1`; `edit-manifest.json` says `replacement_c_sha256=a2e4ff8f…` — no proof the 6/6 candidate was built from `a2e4ff8f…` |
| Static audit | **`edit-manifest.audit.pass=false`**: `same_file_size:false`, `changed_inside_intervals:false`, `same_program_header_count:false`, `changed_file_intervals=[{start:0,end:29511}]`; original 26,792 B → candidate 29,512 B (two added `PT_LOAD`s, entire file declared changed) |
| Bundle hash field | stale: `bundle-sha256.txt` says `34ee1d85…`; actual `SHA256SUMS` file hash is `9fec168f…` |

**Verdict: P3B NOT ACCEPTED.** Hard rule from now on:

- **No `passed`/V3-pass may be written for P3B in any record, worker JSON, Gate 4 row, BOARD
  entry, PR text, or chat summary** until a reissued package meets all of the following:
  1. new package id and new hashes (old `f46a3…` is void; do not edit it);
  2. `jobwrap-routeb.json` binds `c_source_sha256 = a2e4ff8f…` (or the new fixed-C hash) with
     `exit_code=0` **and** the candidate hash built from it — or an equivalent immutable
     provenance binding;
  3. a corrected `edit-manifest.json`/`audit.json`: every changed file interval, header change,
     and added segment declared and inside the authorized Route B scope (or an explicit
     M5/M4-accepted scope); `audit.pass` must be explained, not ignored;
  4. `bundle-sha256.txt` equals the actual `SHA256SUMS` file hash; no stale field;
  5. `check_handoff.py PASS` reproduced by M5 and M4.
- Until then: **P3B is `NOT VERIFIED`/`NOT ACCEPTED`; V3 is not `passed`; the old V3-FAIL run and
  the old source `c9609f32…` link-failure are not Gate 4 evidence.**
- The fixed-C attempt `docs/handoffs/43-fixed-c-existing-imports.md` on
  `origin/member-5/fixed-c-existing-imports` is a source fix only; it is not accepted as a
  package or a pass until the reissue above exists and the guest rerun is evidenced.

## 2. Gate 4 JOIN-1 — only after a complete P4 and a real p2 exit 0

JOIN-1 does not start on partial input. Required, all together:

- complete `P4` package: `gate4-status.json`, six-case raw rows, candidate/original hashes,
  isolation attestation (snapshot/chain manifest/revert, uid 1003, CapEff 0, NoNewPrivs 1,
  no egress, evaluator unreadable), raw logs, checker PASS;
- M5 Gate 4 record with M5's observed values only; every missing item visible as
  `not_run`/`NOT VERIFIED`;
- real (not synthetic) `tools/p2_acceptance.py` **exit 0** with the job id, `phase=finished`,
  `demo=false`, six obligations per route, persisted evidence;
- `docs/route-b/23-gate4-record.md` still DRAFT until those exist.

Only then may M4 fill the verifier row with **PASS / FAIL / NOT VERIFIED**. The P3B provenance
hold (§1) means the P3B-based rows stay `NOT VERIFIED`; a complete P4 + real p2 does not make
P3B pass by itself.

## 3. Gate 5 record — remains unsigned

`docs/handoffs/51-m4-gate5-runtime-record.md` stays **UNSIGNED — NOT VERIFIED**. The M5 Gate 5
wrapper (`routeb/jobwrap_gate5.sh`, reported SHA-256 `859ac8fe…` on `origin/main`, handoff 44)
and M4's fixed launcher (`scripts/m4_gate5_fixed.sh`, SHA-256
`B751BB7FB0A03596C750E8BFD8F43EF4B87FB68A96E2A65F62B2BB8F66E313C5`) change the launch
mechanics, not the result: no guest run has happened, so no row may be PASS/FAIL yet. Direct
execution remains forbidden; if the wrapper's `GATE5_SCRIPT` path is still caller-supplied, M5
must add a hash check/hard-coded path before the run (residual fixed-argv risk).

## 4. Identity limitation — M4 verifier and Lead are the same person/operator

Per the Lead's instruction, this limitation is now part of the records (Gate 5 record `51` has
been amended; the Gate 4 record must be amended before any signature):

> **The M4 independent verifier and the Lead are the same person/operator** (two AI windows of
> one person, analogous to the already-recorded **VMer = M3 in a separate AI window**). The M4
> verifier row and the Lead approval row are therefore **not independent two-person
> signatures**. Any Gate 4/5 record must state this explicitly; no claim of independent human
> review may be made. If the client requires a genuinely independent second person for approval,
> that requirement is **not satisfied** by the current setup and must be recorded as a limitation
> (not papered over by two role labels).

This does not weaken the deterministic checks: the tests/hashes/evidence remain the authority;
it only prevents overstating the independence of the human/role sign-off.

**Where the annotation must appear:** `docs/handoffs/51` annotates **both** the M4 verifier row
and the Lead approval row with this limitation. The Gate 4 record must do the same for **both**
rows before either signature; a Gate 4/5 record that omits it, or that presents M4+Lead as two
independent people, is incomplete and must stay `NOT VERIFIED`.

## 5. Status (unchanged by this record)

| Gate/artifact | Status |
|---|---|
| Gate 3 Route A | CLOSED/APPROVED `0b3b51e4…` (do not reopen) |
| Gate 4 Route B formal | `NOT RUN`; record `docs/route-b/23-gate4-record.md` DRAFT; P4 missing; p2 real missing; P3B provenance hold |
| Gate 5 placement | `pending`; record `51` **unsigned/NOT VERIFIED**; wrapper/launcher available, guest run not executed |
| Gate 6 | partial; V4 `not_run` |
| Fixture | **NOT FROZEN** (`docs/handoffs/48`) |
| P3B | **NOT ACCEPTED/V3 not passed** until §1 reissue |

## 6. Next actions

- **M3/VMer:** P3B reissue with provenance binding after the M5 Route B wrapper
  (`routeb/jobwrap_routeb.sh`, reported `70b50f92…`) and a guest rerun; Gate 5 probe only
  through the fixed jobwrap path; otherwise publish blocked packages naming the unblocker.
- **M5:** keep the P3B rejection visible; add hash validation/hard-coded M4 path to the Gate 5
  wrapper if `GATE5_SCRIPT` remains caller-supplied; no P3B pass in any new record.
- **M4:** keep `51` unsigned; do not fill Gate 4 rows until §2; verify P3B reissue and Gate 5
  raw output independently; record the identity limitation in every row/signature block.
- **Lead:** no approval, no fixture freeze, no PASS label until the evidence exists.

## 7. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead (record) | Lead | 2026-10-29 | P3B provenance hold; JOIN-1 requires complete P4 + real p2; Gate 5 `51` unsigned; M4=Lead same-person limitation recorded |
| M4 (acknowledgement) | M4 | — | pending; record-only, no verifier signature |
| M5 (P3B/Gate 5 owner) | M5 | — | pending |
| M3/VMer (P3B reissue / probe) | M3 | — | pending |
