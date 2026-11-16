# Handoff readiness checklist (2026-11-17)

Status: P1-2. Owner: M4. 20 items with PASS / PARTIAL / FAIL / NOT_RUN and the
evidence command for each. "PASS" means the item was verified from this
workspace; items that need the user/owner or a live GitHub token are marked
explicitly and never counted as complete.

Audit baseline: repository `binary-repair-gui` on
`final/consolidated-2026-11-16` at HEAD `ae89f88` (Lead's ASCII-docs
relocation); remote `origin` = `git@github.com:chenfanaichifan/binary-repair.git`.

## Checklist

| # | Item | Status | Evidence (command -> result) |
|---|---|---|---|
| 1 | Repository present, correct branch | PASS | `git rev-parse --abbrev-ref HEAD` -> final/consolidated-2026-11-16; worktree contains M1/M2/M3 in-progress changes only, M4 additions are separate files |
| 2 | Remote delivery branch visible | PASS | `git ls-remote origin refs/heads/final/consolidated-2026-11-16` -> ae89f888028131699fa2b9d5f5f764ba3b4a3842 |
| 3 | Python venv usable | PASS | `.venv/bin/python --version` -> Python 3.11.8 |
| 4 | Environment self-check passes | PASS | `tools/handoff/check-env.sh` -> exit 0, "== RESULT: ENV OK" (includes secret scan of docs + review) |
| 5 | Four member task files present (workspace + repo) | PASS | workspace M1-M4 task files present; repo copies delivery/zh/handoff/M1-task.md ... M4-task.md; check-env validates both sets |
| 6 | Tool area complete | PASS | tools/handoff: check-env, run-scope-tests, member-report, scan-secrets (hardened), offsite-backup (enhanced); plus binary-repair-gui/scripts/security/verify-offsite-backup.sh added by M4 |
| 7 | Local full backup present and restorable | PASS | mirror 117M / 203 refs (113 heads, 79 tags), git fsck --full clean; bundle 127M, bundle verify = complete history; restore drill ALL PASS (docs/operations/backup-2026-11-17.md) |
| 8 | Offsite backup copy | FAIL (blocked) | not_run - blocked_by=user:offsite_path. Drill at /tmp/binrepair-offsite-drill PASS but a /tmp copy is not offsite; commands ready in backup-2026-11-17.md section 5 |
| 9 | Key rotation inventory + secret scans | PARTIAL | Inventory/runbook + scans delivered (docs/operations/security-key-rotation-2026-11-17.md): repo docs/scripts/app/review scan = 0 candidates; whole repo = 12 synthetic test fixtures only; materials = synthetic fixtures only. Actual rotation of the four credential slots + local GUI key store is blocked_by=owner |
| 10 | Default branch points at delivery branch | FAIL (blocked) | `git ls-remote --symref origin HEAD` -> ref: refs/heads/main HEAD / 8869b07 (stale). No gh CLI, GH_TOKEN/GITHUB_TOKEN unset -> blocked_by=owner:github_default_branch; runbook + verification + rollback in docs/operations/default-branch-2026-11-17.md |
| 11 | Report wording consistency review | PARTIAL | Review delivered (docs/operations/report-consistency-2026-11-17.md): master report 3/6 wording PASS in all 9 requested sections; benchmark numbers consistent; open findings R1-R4/G1/N1-N2 handed to Lead (no master-report/claims edits by M4) |
| 12 | claims / LIMITATIONS mutual consistency | PARTIAL | Numbers consistent (2/24, hidden 0/8, false_verified 0, P16-R3 7/10, nightly not_run). Open: LIMITATIONS section 17 still says non-loop 0/6 without as-of date (lines 214/499); claims has no explicit final_release_sha/final_release_ci fields; claims latest_verified_ci.branch points at deleted workbench-v3 |
| 13 | Training/handoff materials contain no real keys | PASS (partial coverage) | tools/handoff/scan-secrets.sh over handoff materials + WeChat-Share + repo top-level docs -> 13 candidates, all synthetic test fixtures quoted from tests; no real credential. Caveat: handoff/archive (~1.5 GB local archive) not exhaustively text-scanned (not_run); it is local-only and must not be published |
| 14 | Hidden corpus not leaked | PASS | benchmark/phase8c/hidden-commitment.json publishes only opaque per-sample ids + binary digests (8 samples) plus aggregate counts; claims hidden_available=false, material_committed=false; hidden material retained by owner. Isolation operational (0700), not cryptographic - same-UID/root caveat documented |
| 15 | CI status for the delivered tree | PARTIAL (recorded evidence only) | Recorded: gated code SHA f1ba37e CI 43744573286 success + Ubuntu 43744573230; final release SHA 4a7b235 CI 43748886046 / Ubuntu 43748886289; self-hosted nightly not_run. No fresh GitHub API query (no token); current HEAD ae89f88 has no recorded CI run |
| 16 | Release gate evidence intact | PASS | artifacts/release-gate-2026-11-16-phase8c/gate.json: ok=true, exit_code=0, release_sha=4a7b235..., 13/13 required checks passed, frozen_matches_release=true; honest not_run list (github_actions, international_provider_matrix, self_hosted_nightly_lima_capture) |
| 17 | Branch/tag cleanup state | PASS | git ls-remote origin -> 192 refs; heads 91, tag refs 89; session-related residual refs (workbench-v3/phase8/universal/ai-binary/coverage-audit/release-2026-11-1x/autonomy/handoff-v4) -> 0 |
| 18 | Rollback plan documented and drill-proven | PASS | Ref restore from mirror/bundle drill PASS (workbench-v3=4a7b235, final branch=4322a51 snapshot, fsck clean); procedures in backup-2026-11-17.md section 6 + consolidation record; remote ref restore itself is a Lead-only git write and was not executed |
| 19 | Member permissions / boundary controls | NOT_RUN | Design verified in workspace (shared fs, disjoint write scopes, no member git writes, M4 tool logs confined to .tmp/handoff/m4); actual GitHub collaborator permissions need owner/admin token -> blocked_by=owner:repo_permissions_check |
| 20 | First sync meeting time recorded | NOT_RUN | Lead decision; no calendar/session record available in this workspace |

## Summary

- PASS: items 1-7, 13 (partial coverage but no hit), 14, 16, 17, 18 = 12 rows
- PARTIAL: items 9, 11, 12, 15 = 4 rows
- FAIL (blocked by user/owner): items 8, 10 = 2 rows; item 19 is NOT_RUN but
  owner-blocked; item 9's rotation half is owner-blocked
- NOT_RUN: items 19, 20 = 2 rows
- Owner/user actions required before handoff sign-off: items 8, 9 (rotation),
  10, 19, and part of 15 (fresh CI on frozen HEAD)

## Recommended pre-handoff actions (ordered)

1. Owner/user: provide an offsite destination path; run
   tools/handoff/offsite-backup.sh <path> then
   binary-repair-gui/scripts/security/verify-offsite-backup.sh <path>.
2. Lead: after integration freeze, refresh mirror+bundle under new dated names,
   re-run the offsite copy + verification, and confirm the frozen delivery tip is
   in the restored objects (backup doc section 4 has the exact commands).
3. Owner: rotate the four credential slots + replace the GUI key store; update
   the key inventory document with the completion timestamp (never values).
4. Owner: switch the GitHub default branch (runbook section 2), then re-run
   runbook section 3 and paste symref/clone evidence into the handoff report.
5. Lead: apply/close report-consistency findings R1-R4; decide whether to add
   claims final-release CI fields.
6. Lead: run the release-gate suite once on the frozen final tree (or state
   clearly that added docs do not change code and rely on the recorded 4a7b235
   gate) and record CI for the frozen HEAD.
7. Lead: record the permission check (row 19) and the first sync meeting (row 20).

## Reproduction

From the workspace root:
    tools/handoff/check-env.sh
    tools/handoff/run-scope-tests.sh m4
    binary-repair-gui/scripts/security/verify-offsite-backup.sh <offsite-dir-or-drill>
    cd binary-repair-gui && .venv/bin/python scripts/check_markdown_language.py --json --allowlist docs/operations/markdown-language-allowlist.json
