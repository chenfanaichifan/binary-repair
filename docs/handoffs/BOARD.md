# BOARD — handoff status

Owners: M3+M5 merged agent (producer + consumer/record, one agent), Lead (approval).
Rule: publish first, notify second. Missing is not passing. No logs in chat.
Verification mode for all rows below: **self-verified (single agent)** — M4
independent verification waived by the Lead on 2026-10-30; the M4 verifier row
is never signed by this agent; Lead approval rows stay blank.

## Rows

| Owner | Item | Status | Artifact | SHA256SUMS hash | Next action |
|---|---|---|---|---|---|
| M3+M5 | T3.0 guest access | DONE 2026-10-30 19:30 (late vs 12:00) | `docs/handoffs/38-m3-to-m5-2026-10-30.md` §A | — | none; uid 13 identity recorded, then scripted revert to uid 11 |
| M3+M5 | P3B executor question | DONE 2026-10-30 19:30 — in-guest `4f072175…b05d` MATCH | `docs/handoffs/evidence/P3B/executor-confirmation.json` | `a312949cef45bbacc1324a66feb9f68fbdebe8bb55c6c278daebb87367f7dfd8` | M5 adapter/replay once `app/`+`tools/` arrive |
| M3+M5 | P4 v3 (guest-boot evidence) | DONE 2026-10-30 20:00 (late vs 18:00), checker PASS 26/26 | `docs/handoffs/evidence/P4/`, `dist/P4-package-v3-2026-10-30.zip` `a8f335a3…6cae` | `e4b81b34df9b2707542fe2158f9f76ce5760a675e6494d82df85994f669e6c5e` | Gate 4 record input; acceptance still NOT RUN |
| M3+M5 | P3B v5 | DONE 2026-10-30, checker PASS 22/22 | `docs/handoffs/evidence/P3B/`, `dist/P3B-package-v5-2026-10-30.zip` `bfba4e51…29ce2` | `a312949cef45bbacc1324a66feb9f68fbdebe8bb55c6c278daebb87367f7dfd8` | superseded by v6 below |
| M3+M5 | P3B v6 | **DONE 2026-10-31** — Route B candidate fix (reuse R-X PT_LOAD tail, 0 new segments); candidate 208574ab (was 63fcafa6); **fixed 16:11** per M5 consume feedback: bundle-record.md corrected, V2 raw evidence (`v2-routeb-fixed.json` + readelf) added, SHA256SUMS consistent (zip==disk==git). checker PASS 25/25; zip `dist/P3B-package-v6-2026-10-31.zip` `1fe4326c…8e63` | `docs/handoffs/evidence/P3B/`, `executor/probe_patcherex2.py` | SHA256SUMS `df58f968…91ba` | M5 adapter/replay with new candidate |
| M3+M5 | P3A v7 | v6 (26 files, checker PASS 26/26) was the 10-29 authoritative job; **v7 2026-10-31 16:11** = v6 + V2/V5 supplements (`v2-routea-supplement.json`, `v5-routea-supplement.json`, readelf), checker PASS 29/29; zip `dist/P3A-routea-2026-10-31-v7.zip` `d8c6bdaa…5eedd` | `docs/handoffs/evidence/P3A/` | SHA256SUMS `2580c232…5ec0` | M5 adapter reads supplement files for Route A V2/V5; V4 not_run |
| M3+M5 | for-M4 / for-M5 bundles | **v11 built 2026-10-31 16:38** — v10 + P2-real package (fixes v10's omission: V4 evidence `P2-real/v4/` now actually ships); carry P2-real + P3A v7 + P3B v6 (fixed) + P4 v3 | `dist/for-M5-2026-10-31-v11.zip` `e1e5af8c…f0f2`, `dist/for-M4-2026-10-31-v11.zip` `a17e254c…a641` | per-zip SHA256SUMS inside | Lead personal check (M4 waived) |
| M3+M5 | T5.2 adapter + synthetic p2 | **CLEARED** 2026-10-30 20:20 — integration head `aab162a` fetched into a worktree; `pytest tests/integration/test_p2_acceptance.py` 5 passed, `test_attempt_writer.py` 6 passed | `.tmp/integration` (worktree, not committed) | — | none; no synthetic pass was needed |
| M3+M5 | T5.3 real p2 + Gate 4 record | **DONE** 2026-10-30 20:22 — two real jobs, both `p2_acceptance.py` exit 0 (job1 `inconclusive`, job2 `rejected`); observed values in the Gate 4 record | `docs/handoffs/evidence/P2-real/`, `docs/route-b/23-gate4-record.md`, `docs/handoffs/39-m3-v2-v5-p2-2026-10-30.md` | `a3c3fdf429dcfcf2ed1615c4e8114d4e5c8d784ea933afdb95c9056c1c8cec74` | Lead personal check; `gate4_pass` still absent |
| M3+M5 | V2 interface | **FIXED** 2026-10-31 — Route A 16/16 passed (unchanged); Route B was 15/16 failed on 63fcafa6 (2 added PT_LOAD), now **fixed** on 208574ab (reuse R-X PT_LOAD tail, 0 added segments) → 16/16 passed. Raw V2 output now in each package: P3B `v2-routeb-fixed.json`, P3A `v2-routea-supplement.json` | `docs/handoffs/evidence/P2-real/v2-routea.json`, `v2-routeb.json`, `v2-routeb-fixed.json`; also copied into P3A/P3B packages | in `P2-real`/`P3A`/`P3B` SHA256SUMS | Lead to confirm Route B V2 now passes; V4 still not_run |
| M3+M5 | V5 reproducibility | **DONE** 2026-10-30 20:20 — Route A fresh replay ×2 byte-identical; Route B record re-verified. P3A v7 now carries `v5-routea-supplement.json`; P3B v6 `reproducibility.json` shows 208574ab byte-identical ×2 | `docs/handoffs/evidence/P2-real/v5-reproducibility.json`, `P3A/v5-routea-supplement.json`, `P3B/reproducibility.json` | in respective SHA256SUMS | none |
| M3+M5 | PR #10 suite status | **MEASURED** 2026-10-30 20:35 at head `aab162a` — `--ignore=tests/e2e`: 257 tests, 254 passed, 1 failed, 2 skipped; `tests/e2e` did not complete (exit 124 after 90 s) | `docs/handoffs/evidence/P2-real/suite/` | in `P2-real/SHA256SUMS` | M1: the one failure is `test_routeb_executor.py::test_static_routeb_bundle` (`assert 7 >= 8`) and passes 2/2 in the guest — a binutils-availability assertion, not a regression; M2: the browser journey stays unverified on this host |
| M4 | independent verification | WAIVED by Lead 2026-10-30 — not performed | — | — | Lead verifies personally |
| Lead | Gate 4 approval | **APPROVED 2026-10-31 (strict unchanged round-trip scope only)** — `gate4_pass=true` limited to that scope; overall MVP NOT APPROVED; M4 waived, proxy approval (not independent review) | `docs/route-b/23-gate4-record.md` | — | Route B V2 fix, Gate 5 jobwrap, V4 solver output still open |
| M3+M5 | V4 symbolic verdict | **MEASURED 2026-10-31 16:16** — bounded symbolic run in guest (angr 10.0.4): original/free → `counterexample` (model catches defect); original/valid, routea (c4a159), routeb (208574ab) → `proven`/`no_counterexample`. Self-verified single-agent, not independent. Evidence in `docs/handoffs/evidence/P2-real/v4/` (v4-evidence.json + v4_symbolic.py + v4_run_all.py) | `docs/handoffs/evidence/P2-real/v4/` | in `P2-real/SHA256SUMS` | still not driven through a fresh real p2; V4 evidence does not itself close V2-V4 as *independently* verified |
| M3+M5 | Gate 5A | **BLOCKED, confirmed at byte level 2026-10-30**: the exported `jobwrap` (22120 bytes, uid 11) carries `usage: jobwrap gate3 original\|patched <case-id\|all> \| jobwrap probe \| jobwrap gate4` — no `gate5` mode, so `jobwrap gate5` hits `unsupported mode`. `routeb/jobwrap_gate5.sh` does exist at integration head with fixed argv, but it has no `GATE5_SCRIPT` hash pinning, which D3 also required | `dist/Gate5A-blocked-2026-10-29.zip` | — | need a `jobwrap` build with a `gate5` mode **and** a `GATE5_SCRIPT_SHA256` check; no PASS/FAIL until then |
| M3+M5 | Gate 3 local draft | ANNOTATED 2026-10-30: superseded by signed record `0b3b51e4…f2da`; Gate 3 stays closed | `docs/route-a/gate3-record.md` header | — | replace with signed record when Lead supplies it; never re-verify |

## Guest state after this window

- VM `D:\VMs\binrepair-u2404-x64-01` was booted to uid 11 (`gate4-harness`) at
  20:19 for the V2/V5 probes and **powered off cleanly at 20:40**; no
  `vmware-vmx`, no `.lck`, `.vmsd snapshot.current = "11"`.
- The probes staged `~/v2/` (three binaries, `v2_interface.py`,
  `v5_reproducibility.py`, `regen_c4a159.py`, replay outputs) and `~/suite/`
  (routeb test cross-check) live **only in the current disk state**. A revert to
  uid 11 discards them; every script and JSON they produced is already in
  `docs/handoffs/evidence/P2-real/`, so nothing is lost that matters.
- Snapshots uid 12 (`routeb-harness-wip`) and uid 13 (`routeb-harness`) are
  untouched; revert to uid 13 to resume Route B execution work.
- Chain manifest (uid 4..11 + `.vmsd`, hashed powered off):
  `docs/handoffs/evidence/P4/chain-manifest.json`.

## Honest deadline note

The 2026-10-30 12:00 and 18:00 milestones were missed (this window started
16:45; packages completed 19:30–20:10). All timestamps in the packages are the
actual observed times. Nothing was backdated and no gate was marked passed to
compensate.

## Delivery state

- `git push origin member-3-route-a` **succeeded 2026-10-31** (Route B V2 fix,
  `e0993e6..4b2fe4b`); remote == local (`0` ahead). Remote commits include the
  byte-exact evidence packages (`docs/handoffs/evidence/**` stored with `-text`;
  index bytes == working-tree bytes, verified on six files).
- Delivery zips are in `dist/` (not in git). Authoritative set as of 2026-10-31
  16:30: `P3A-routea-2026-10-31-v7.zip` (`0d013a28…b2cf`),
  `P3B-package-v6-2026-10-31.zip` (`b5ddbb48…03a4`),
  `P4-package-v3-2026-10-30.zip`, bundled as
  `for-M5-2026-10-31-v10.zip` (`aeb0c739…bcca`) /
  `for-M4-2026-10-31-v10.zip` (`517c8974…7d7c2`). Each zip carries its own
  `MESSAGE.md` README + `SHA256SUMS`; SHA256SUMS are packed verbatim so
  zip-internal == disk == git. v10 adds the V4 bounded-symbolic self-verified
  evidence (`P2-real/v4/`); the P3A/P3B zip hashes changed vs v9 only because
  their `handoff.json` notes now reference V4 instead of `not_run`.
- Local tool files (`.opencode/`, `.probe-dir/`, `opencode.jsonc*`) remain
  untracked by choice; `dist/` and `worklogs/` stay out of git.
