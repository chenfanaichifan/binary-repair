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
| M3+M5 | P3B v5 | DONE 2026-10-30, checker PASS 22/22 | `docs/handoffs/evidence/P3B/`, `dist/P3B-package-v5-2026-10-30.zip` `bfba4e51…29ce2` | `a312949cef45bbacc1324a66feb9f68fbdebe8bb55c6c278daebb87367f7dfd8` | M5 adapter/replay |
| M3+M5 | P3A authoritative version | DECIDED 2026-10-30: **v6**, checker PASS 26/26 (re-run by this agent) | `docs/handoffs/evidence/P3A/`, `dist/P3A-routea-2026-10-29-v6.zip` `192492ee…870c1` | `023b94fac2ecc3d6e991901092c2c7c980002e875e2fe5e283524118e3b22115` | none on producer side |
| M3+M5 | for-M4 / for-M5 bundles | v7 built 2026-10-30, carry P3A v6 + P3B v5 + P4 v3 | `dist/for-M5-2026-10-30-v7.zip` `fda47221…77a5`, `dist/for-M4-2026-10-30-v7.zip` `a408a1c4…6051` | per-zip SHA256SUMS inside | Lead personal check (M4 waived) |
| M3+M5 | T5.2 adapter + synthetic p2 | **CLEARED** 2026-10-30 20:20 — integration head `aab162a` fetched into a worktree; `pytest tests/integration/test_p2_acceptance.py` 5 passed, `test_attempt_writer.py` 6 passed | `.tmp/integration` (worktree, not committed) | — | none; no synthetic pass was needed |
| M3+M5 | T5.3 real p2 + Gate 4 record | **DONE** 2026-10-30 20:22 — two real jobs, both `p2_acceptance.py` exit 0 (job1 `inconclusive`, job2 `rejected`); observed values in the Gate 4 record | `docs/handoffs/evidence/P2-real/`, `docs/route-b/23-gate4-record.md`, `docs/handoffs/39-m3-v2-v5-p2-2026-10-30.md` | `fe41df8b9a49976b040a36072eadc2cda489fcbf4fb3109d8484b9e3765106a6` | Lead personal check; `gate4_pass` still absent |
| M3+M5 | V2 interface | **DONE** 2026-10-30 20:20, measured in guest — Route A 16/16 **passed**; Route B 15/16 **failed** (`extra_load_segments_within_contract`: 2 added PT_LOAD, contract allows 1) | `docs/handoffs/evidence/P2-real/v2-routea.json`, `v2-routeb.json`, `readelf/` | in `P2-real/SHA256SUMS` | M4/Lead to adjudicate the Route B reading against `authorized_edits[2]` |
| M3+M5 | V5 reproducibility | **DONE** 2026-10-30 20:20 — Route A fresh replay ×2 byte-identical; Route B record re-verified (executor not re-run, stated in payload) | `docs/handoffs/evidence/P2-real/v5-reproducibility.json` | in `P2-real/SHA256SUMS` | none |
| M4 | independent verification | WAIVED by Lead 2026-10-30 — not performed | — | — | Lead verifies personally |
| Lead | Gate 4 approval | NOT RUN | — | — | after real p2 exit 0 + Gate 4 record |
| M3+M5 | V4 symbolic verdict | **BLOCKED (unchanged)**: raw solver output not in this checkout. Now the *only* thing keeping Route A from 6/6 | — | — | obtain raw bounded-explore stdout; verdict stays `inconclusive`, self-verified label when written |
| M3+M5 | Gate 5A | BLOCKED (unchanged): jobwrap has no fixed-script mode | `dist/Gate5A-blocked-2026-10-29.zip` | — | fixed-script mode or written equivalent invocation; no PASS/FAIL until then |
| M3+M5 | Gate 3 local draft | ANNOTATED 2026-10-30: superseded by signed record `0b3b51e4…f2da`; Gate 3 stays closed | `docs/route-a/gate3-record.md` header | — | replace with signed record when Lead supplies it; never re-verify |

## Guest state after this window

- VM `D:\VMs\binrepair-u2404-x64-01` was booted to uid 11 (`gate4-harness`) at
  20:19 for the V2/V5 probes and is **still running** at the time of this note;
  the V2/V5 scripts and the three binaries are staged in `lab@…:~/v2/`.
- Re-run of the V2/V5 probes needs only that directory; no package rebuild.
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

- `git push origin member-3-route-a` **succeeded 2026-10-30 20:20**
  (`222f7e3..beea6c2`); the earlier `SEC_E_NO_CREDENTIALS` condition no longer
  holds. Remote commits now include the byte-exact evidence packages
  (`docs/handoffs/evidence/**` stored with `-text`; index bytes == working-tree
  bytes, verified on six files).
- Local tool files (`.opencode/`, `.probe-dir/`, `opencode.jsonc*`) remain
  untracked by choice; `dist/` and `worklogs/` stay out of git.
