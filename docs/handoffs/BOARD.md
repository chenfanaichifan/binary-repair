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
| M3+M5 | P3B v6 | **DONE 2026-10-31** — Route B candidate fix (reuse R-X PT_LOAD tail, 0 new segments); candidate 208574ab (was 63fcafa6); **fixed 16:11** per M5 consume feedback: bundle-record.md corrected, V2 raw evidence (`v2-routeb-fixed.json` + readelf) added, SHA256SUMS consistent (zip==disk==git). checker PASS 25/25; zip `dist/P3B-package-v6-2026-10-31.zip` `b5ddbb48…03a4` | `docs/handoffs/evidence/P3B/`, `executor/probe_patcherex2.py` | SHA256SUMS `5370f2bb…82db` | M5 adapter/replay with new candidate |
| M3+M5 | P3A v7 | v6 (26 files, checker PASS 26/26) was the 10-29 authoritative job; **v7 2026-10-31 16:11** = v6 + V2/V5 supplements (`v2-routea-supplement.json`, `v5-routea-supplement.json`, readelf), checker PASS 29/29; zip `dist/P3A-routea-2026-10-31-v7.zip` `0d013a28…b2cf` | `docs/handoffs/evidence/P3A/` | SHA256SUMS `45367710…a23f` | M5 adapter reads supplement files for Route A V2/V5; V4 evidence in P2-real/v4 (see v11) |
| M3+M5 | for-M4 / for-M5 bundles | **v12 built 2026-10-31 17:18** — v11 + V4 raw replay package (`v4/REPLAY-README.md` + accounting scripts/logs) per Lead Standard B; carry P2-real + P3A v7 + P3B v6 (fixed) + P4 v3 | `dist/for-M5-2026-10-31-v12.zip` `84d2827f…905b`, `dist/for-M4-2026-10-31-v12.zip` `ab2f8f4b…2ce0` | per-zip SHA256SUMS inside | Lead personal check (M4 waived) |
| M3+M5 | T5.2 adapter + synthetic p2 | **CLEARED** 2026-10-30 20:20 — integration head `aab162a` fetched into a worktree; `pytest tests/integration/test_p2_acceptance.py` 5 passed, `test_attempt_writer.py` 6 passed | `.tmp/integration` (worktree, not committed) | — | none; no synthetic pass was needed |
| M3+M5 | T5.3 real p2 + Gate 4 record | **DONE** 2026-10-30 20:22 — two real jobs, both `p2_acceptance.py` exit 0 (job1 `inconclusive`, job2 `rejected`); observed values in the Gate 4 record | `docs/handoffs/evidence/P2-real/`, `docs/route-b/23-gate4-record.md`, `docs/handoffs/39-m3-v2-v5-p2-2026-10-30.md` | `a3c3fdf429dcfcf2ed1615c4e8114d4e5c8d784ea933afdb95c9056c1c8cec74` | Lead personal check; `gate4_pass` still absent |
| M3+M5 | V2 interface | **FIXED** 2026-10-31 — Route A 16/16 passed (unchanged); Route B was 15/16 failed on 63fcafa6 (2 added PT_LOAD), now **fixed** on 208574ab (reuse R-X PT_LOAD tail, 0 added segments) → 16/16 passed. Raw V2 output now in each package: P3B `v2-routeb-fixed.json`, P3A `v2-routea-supplement.json` | `docs/handoffs/evidence/P2-real/v2-routea.json`, `v2-routeb.json`, `v2-routeb-fixed.json`; also copied into P3A/P3B packages | in `P2-real`/`P3A`/`P3B` SHA256SUMS | Lead to confirm Route B V2 now passes; V4 still not_run |
| M3+M5 | V5 reproducibility | **DONE** 2026-10-30 20:20 — Route A fresh replay ×2 byte-identical; Route B record re-verified. P3A v7 now carries `v5-routea-supplement.json`; P3B v6 `reproducibility.json` shows 208574ab byte-identical ×2 | `docs/handoffs/evidence/P2-real/v5-reproducibility.json`, `P3A/v5-routea-supplement.json`, `P3B/reproducibility.json` | in respective SHA256SUMS | none |
| M3+M5 | PR #10 suite status | **MEASURED** 2026-10-30 20:35 at head `aab162a` — `--ignore=tests/e2e`: 257 tests, 254 passed, 1 failed, 2 skipped; `tests/e2e` did not complete (exit 124 after 90 s) | `docs/handoffs/evidence/P2-real/suite/` | in `P2-real/SHA256SUMS` | M1: the one failure is `test_routeb_executor.py::test_static_routeb_bundle` (`assert 7 >= 8`) and passes 2/2 in the guest — a binutils-availability assertion, not a regression; M2: the browser journey stays unverified on this host |
| M4 | independent verification | WAIVED by Lead 2026-10-30 — not performed | — | — | Lead verifies personally |
| Lead | Gate 4 approval | **PASS 2026-10-31 (strict unchanged round-trip scope)** — Lead ruling 75: Gate 4 approved as PASS under strict unchanged round-trip scope; record hash `abed788e…499a`. M3+M5 need NOT re-run p2/controller or take any further Gate 4 action. V4 stays model-level (65), never binary-level/whole-program. Gate 5 still BLOCKED (record 51 unsigned); fixture NOT FROZEN; no final MVP tag. | `docs/route-b/23-gate4-record.md`, `docs/handoffs/75-lead-gate4-pass-strict-roundtrip-2026-10-31.md` | `abed788e…499a` | Gate 5 successor verification by M4; record 51 signing |
| M3+M5 | V4 model verdict | **PASS (model-level, bound 64)** — Lead ruling 65 (2026-10-31). V4 is a **bounded function-level model obligation**, satisfied by `v4/v4_model.py` → `v4/v4-result.json` (pure z3): real symbolic input (`data[L]==0`, `data[i]!=0` for `i<L`), explicit domain (valid 0..49, bound 64), exact solver accounting (1 check per candidate), calibration (original SAT / routea UNSAT / routeb UNSAT / defective off-by-one SAT), hash-consistent (`aa428157…`/`c4a159…`/`208574ab…`). **Scope/limitations** (binding): function-level guard model (guard threshold written from disassembly, not re-derived); NOT symbolic execution of the candidate binary; NOT whole-program/binary-level equivalence; bounded strlen [0,64]; strcpy/printLine/fprintf are semantic hooks; binary-level proof is a separate obligation. Gate 4 now PASS via strict round-trip scope (Lead 75, `abed788e…499a`); Gate 5 still BLOCKED; fixture NOT FROZEN. | `docs/handoffs/evidence/P2-real/v4/v4-result.json`, `docs/handoffs/65-lead-v4-final-verdict-2026-10-31.md` | in `P2-real/SHA256SUMS` | none — no further V4 harness/replay; Gate 5 remain open |
| M3+M5 | Gate 5A | **SUCCESSOR BUILT + PROBE RUN (2026-10-31); record 51 still UNSIGNED** — the old jobwrap lacked a `gate5` mode, so per Lead ruling 52 §3 (which allows a fixed-argv probe mode) M5 built an independent `jobwrap-gate5` successor (source `route-a/jobwrap-gate5/jobwrap_gate5.c`, git `80c90e7`, approved by handoff 66). Built inside the guest (`gcc -static -O2`), binary SHA-256 `90af91ef…ff20`, does NOT overwrite old `jobwrap b232d60b` / does NOT re-sign P4. Fixed argv `probe m4-gate5 -- <repo> <work>` execs absolute `/usr/bin/python3 <repo>/scripts/m4_gate5_probe.py`, compile-time pins probe blob `f39a0302…d146cb` (fail-closed, negative test passed). Real probe run: **19 PASS / 0 FAIL / 0 NOT VERIFIED**, isolation attested (uid 1003, CapEff=0, NoNewPrivs=1, seccomp, no default route in isolated netns). This is an execution witness only — record `51` stays UNSIGNED until M4 independently re-hashes and signs. | `docs/handoffs/73-lead-gate5-successor-corrections-2026-10-31.md`, `docs/handoffs/67-gate5-successor-execution-witness-2026-10-31.md`, `route-a/jobwrap-gate5/` | successor `90af91ef…ff20`, probe `f39a0302…d146cb` | M4 must independently verify and sign record `51`; Gate 5 stays pending/unsigned; fixture NOT FROZEN |
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
  16:38: `P2-real-2026-10-31.zip` (`a9db726a…b71a`),
  `P3A-routea-2026-10-31-v7.zip` (`0d013a28…b2cf`),
  `P3B-package-v6-2026-10-31.zip` (`b5ddbb48…03a4`),
  `P4-package-v3-2026-10-30.zip`, bundled as
  `for-M5-2026-10-31-v11.zip` (`e1e5af8c…f0f2`) /
  `for-M4-2026-10-31-v11.zip` (`a17e254c…a641`). Each zip carries its own
  `MESSAGE.md` README + `SHA256SUMS`; SHA256SUMS are packed verbatim so
  zip-internal == disk == git. v11 carries the P2-real package (which v10
  omitted), so the V4 bounded-symbolic self-verified evidence (`P2-real/v4/`)
  actually ships; the P3A/P3B zip hashes changed vs v9 only because their
  `handoff.json` notes now reference V4 instead of `not_run`.
- Local tool files (`.opencode/`, `.probe-dir/`, `opencode.jsonc*`) remain
  untracked by choice; `dist/` and `worklogs/` stay out of git.
