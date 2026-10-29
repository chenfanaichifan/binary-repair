# 41 — Team assignment, as of 2026-10-29 17:00

**From:** Lead
**Status:** current allocation for all five members. Supersedes the owner list in `docs_BinaryRepair/handoffs/14-next-actions-by-owner.md` where that list predates the consolidation (Gate 3 is closed; the member-2 GUI slice is merged; the acceptance suite is on the integration branch).
**Integration state:** branch `integration/consolidation-2026-10-29`, HEAD `2c0e3c4`, clean tree. `origin/main` is still `4107836` — **the integration branch is the work to be merged, not a second main.**
**Honest gate state:** Gate 3 closed/approved; **Gate 4 NOT RUN**; Gate 5 runtime pending; Gate 6 partial (V4 pending); fixture **NOT FROZEN**; real pipeline `tools/p2_acceptance.py` **BLOCKED (exit 2)**. No repaired binary has been verified.

## 0. One-page picture

| Person | Role now | Current deliverable | Deadline |
|---|---|---|---|
| **M1** | main owner / release | open PR of the integration branch, merge after approval, keep `main` runnable and current | 2026-10-30 PR, 2026-10-31 merge |
| **M2** | GUI owner | language-policy cleanup, desktop e2e, live `http` GUI walkthrough, GUI docs | 2026-10-31 |
| **M3** | Gate 4 executor / evidence producer | T3.0–T3.3 packages `P4`, `P3A`, `P3B` (see BOARD) | 2026-10-30 18:00 |
| **M4** | independent verifier / Gate 5–6 | verify Gate 4 record (JOIN-1), Route A runtime plan, V4 calibration | 2026-10-31 18:00 |
| **M5** | Gate 4 DRI / interface + adapter | T5.1–T5.3: interface v1, adapter + synthetic p2, real p2 + Gate 4 record | 2026-10-30/31 |
| **Lead** | decision + approval | approve rows, resolve blocking, fixture-freeze decision after gates 3–5 | continuous |

No one is allowed to work from the stale `member-4-verification` tree anymore. All new work branches from `integration/consolidation-2026-10-29` HEAD (or `main` after the merge).

## 1. M1 — main owner / release

**Goal:** `main` becomes the single integrated, runnable tree.

1. **Now → 2026-10-30 12:00:** push `integration/consolidation-2026-10-29` and open a PR against `main` with the measured summary from `README.md` (238 collected / 229 passed / 2 skipped / 7 environment errors / 5 uncollectable; demo exit 0; P0 17/17; p2 exit 2 BLOCKED). Request Lead approval; do not merge before it.
2. **Before merge:** re-run the suite on the branch tip (with `scripts/pytest_rt_report.py` or on Ubuntu) and paste the observed line into the PR. Confirm the DB v2 and V3 line-ending issues are closed (they pass on this tree; record the evidence, do not re-open the oracle).
3. **2026-10-31:** after M4's independent verification and Lead approval, merge with a merge commit, tag `mvp-integration-2026-10-31`, and update `main` README status with **measured** facts only.
4. **Branch hygiene:** tag stale branch tips under `archive/2026-10-31/<branch>` before deleting them; keep `agent/` as the frozen archive; no new branch-tree copies in `main`.
5. **Do not:** merge other members' unverified slices directly, push secrets, or mark any gate as passed without its evidence.

## 2. M2 — GUI owner

**Goal:** the merged GUI is clean, honest, and demonstrable on a real desktop.

1. **2026-10-30 12:00 — language cleanup (41 files carry Chinese comments/docstrings from the M2 slice):** translate comments and docstrings to English starting with `app/backend.py`, `app/main.py`, `app/demo.py`, `app/status.py`, `app/visuals.py`, `tools/*.py`, and test docstrings. **Chinese UI text stays** (allowed by the language policy); change no behaviour. DoD: `tests/test_language_policy.py`, `tests/test_status_honesty.py`, `tests/test_verdict_view.py`, `tests/test_backend_contract.py`, `tests/test_security.py` pass; no Chinese in code comments.
2. **2026-10-30 18:00 — desktop e2e:** run `python -m pytest -q tests/e2e` (Edge + DevTools) on a desktop where Edge is available; record pass/fail per journey. In this sandbox those 7 journeys are environment errors — do not report them as passes. Fix real failures; otherwise record `not_run` with the reason.
3. **2026-10-31 — live GUI `http` walkthrough:** run `start-controller.ps1` + `start.ps1` with `BINARYREPAIR_BACKEND=http`, execute `tools/p0_acceptance.py` (expect 17/17) and `tools/p2_acceptance.py` (expect 2 BLOCKED until M5 closes the pipeline). Refresh `docs/screenshots/` with labelled mock-mode images only, and update `docs/controller-integration.md`.
4. **Decision:** recommend keep-vs-remove for the `tools/controller_service.py` legacy bridge; write the reason in the GUI doc.
5. **Do not:** decide outcomes in templates/route handlers, touch `app/domain/acceptance.py`, or edit controller/worker code.

## 3. M3 — Gate 4 executor / evidence producer (BOARD T3.0–T3.3)

**Goal:** real guest packages `P4`, `P3A`, `P3B` that pass the checker.

- **Today:** confirm guest access and snapshot (T3.0). If the guest is unreachable, publish a **blocked package** by 2026-10-30 12:00 with the exact error and who can unblock — do not wait for M5.
- **2026-10-30 18:00:** `P4` (Gate 4 formal run), `P3A` (Route A real executor bundle), `P3B` (Route B runtime bundle). Each package: `handoff.json` + `SHA256SUMS` + logs, validated by `python scripts/check_handoff.py <pkg> --expect-from M3 --expect-to M5` → `PASS`.
- **Each package:** update the BOARD row and write `docs/handoffs/38-m3-to-m5-<id>.md` (10-line envelope). No logs in chat.
- **Never:** execute on the host, edit `app/`/`tests/`, reopen Gate 3, or claim a `passed` without the command that produced it.

## 4. M4 — independent verifier / Gate 5–6

**Goal:** independent rows, not producer work.

1. **Now:** read `docs/analysis/VERIFICATION.md` and the `BOARD.md`; prepare your own Gate 4 verification checklist (independent of M5's claims). Do not accept M5's hashes without recomputing them.
2. **2026-10-31 12:00–18:00 (JOIN-1):** when M5's record and real p2 run exist, verify them independently: package hashes, candidate/original hashes, six-case rows, isolation attestation, record wording, `p2` exit 0 on real data. Fill your verifier row with PASS / FAIL / NOT VERIFIED and the exact commands.
3. **Gate 5 (Route A runtime):** plan the runtime placement proof with M3's guest session after `P4`; run it and record PASS / NOT VERIFIED. Static design is already recorded; runtime is still `not_run`.
4. **Gate 6 / V4:** once the guest is available, run the bounded symbolic calibration; report `inconclusive` unless it completes. Gate 6 stays partial until then.
5. **Do not:** produce Gate 4 evidence, sign your own test, or accept a package that fails `check_handoff.py`.

## 5. M5 — Gate 4 DRI / interface + adapter (BOARD T5.1–T5.3)

**Goal:** the gate closes only when you sign it, and you cannot wait for M3 to start.

- **2026-10-30 12:00 — T5.1:** publish `docs/handoffs/INTERFACE-v1.md` (bundle schema, package schema linking `scripts/check_handoff.py`, naming, hash rules, adapter commands, version-bump rule). Self-test the checker.
- **2026-10-30 18:00 — T5.2:** adapter `A → worker JSON`; synthetic package → worker → `tools/p2_acceptance.py` exit 0, labelled `synthetic: true`. DoD: `tests/integration/test_attempt_writer.py` → 4 passed.
- **2026-10-31 12:00 — T5.3:** consume M3's `P4`/`P3A`/`P3B`; run `check_handoff.py` first; recompute hashes; real p2 exit 0; fill the Gate 4 record with observed values only. If a package is invalid, reply `docs/handoffs/39-m5-to-m3-<id>.md` with exact missing/mismatched items.
- **Do not:** accept an artifact without the checker, edit M3's package, weaken tests/acceptance, or fill M4/Lead rows.

## 6. Lead — decisions only

1. Approve/reject M5's Gate 4 record after M4's row; keep the record hash pinned.
2. Approve the integration PR after M4 verification; decide branch cleanup with M1.
3. Fixture-freeze decision **only after gates 3–5**; it stays `NOT FROZEN` until then.
4. Escalate on the BOARD rule: 24h no update → `OVERDUE`, 48h → narrow scope/reassign.
5. Keep this document and `BOARD.md` truthful; no gate status changes without evidence.

## 7. Cross-cutting rules (everyone)

- **Repo is the message bus.** Chat notifies; the artifact + hash is the message. Use the 10-line envelope from `docs/handoffs/35-ai-handoff-protocol.md`; M3/M5 use role cards `36`/`37`.
- **One DRI per gate** (Gate 4 = M5), **one ball at a time**, 24h escalation.
- **No host execution** of uploaded/repaired binaries or model-generated C. All execution in the guest under the broker.
- **Missing is not passing.** `not_run` / `NOT VERIFIED` / `skip` never become `passed`.
- **No new branch-tree archive copies; no reopening closed gates** (Gate 3 is closed). Small PRs only.
- **Measured numbers only.** Any number quoted in a PR or status page must come with the command that produced it.

## 8. This week

| Date | M1 | M2 | M3 | M4 | M5 |
|---|---|---|---|---|---|
| 10-29 (rest of day) | push + open PR; suite evidence | start language cleanup | T3.0 access check | prep verification checklist | T5.1 interface v1 |
| 10-30 12:00 | PR ready | cleanup batch 1 done | T3.0 delivered/blocked | checklist ready | interface v1 frozen |
| 10-30 18:00 | review PR comments | desktop e2e run | P4/P3A/P3B packages | review packages (read-only) | adapter + synthetic p2 exit 0 |
| 10-31 12:00 | merge prep | http walkthrough | fix rejected packages | independent Gate 4 verification | real p2 exit 0 + record draft |
| 10-31 18:00 | merge + tag after approval | docs/screenshots update | standby for fixes | verifier row signed | Gate 4 record signed |
| 11-01 | main hygiene | GUI follow-ups | — | Gate 5 runtime plan | — |
