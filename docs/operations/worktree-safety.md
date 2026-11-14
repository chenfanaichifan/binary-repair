# Shared-worktree safety protocol (2026-11-14)

Status: adopted for phase 3 after **two external reset incidents** in this
project.  Applies to every human/agent editing
`binary-repair-gui` (and its sibling worktrees) at the same time.

This repository is edited concurrently by the Lead, multiple teammates and an
external operator/session.  The worktree has been externally reset twice:
uncommitted work is **not durable**, and a green local tree is not evidence
until the Lead has committed it.  The protocol below exists so a reset can only
lose a small, regenerable batch — never a milestone.

Related contracts: `.tmp/team/contract.md`,
`.tmp/team/coverage-plan-contract.md`, `.tmp/team/audit-contract.md`,
`.tmp/team/full-coverage-contract.md`.  Recovery helpers:
`.tmp/team/reproduce_backup.py`,
`artifacts/coverage-closure-2026-11-14/capture_acceptance.py`,
`scripts/audit_capability_coverage.py`.

## 1. Roles (who may write what)

- **Lead is the only git writer.**  The Lead runs `git add`, `commit`,
  `checkout`, `stash`, `reset`, `rebase`, `push` and the final
  `coverage-audit-2026-11-14` → `workbench-v3` fast-forward.
  Teammates must **never** run any state-changing git command; read-only
  inspection (`git status`, `git log`, `git diff`, `git show`, `git reflog`) is
  allowed.
- **Teammates** edit only the write scopes recorded on their shared task
  (`team_task_list`), keep batches small, run the tests they can run, and message
  the Lead as soon as the files are on disk so they can be committed.
- **External operator** may also write to the worktree at any time.  Treat every
  file outside your own write scope as someone else's live workspace: never
  revert, format, "clean up" or delete it.

## 2. Worktree/branch isolation

The checkout is a **linked worktree**: `binary-repair-gui/.git` is a file
pointing at `binary-repair/.git/worktrees/allhands`.  Other worktrees already
exist for other lanes/experiments (for example a `member-5` worktree and
`worktree-feature-final`), and that is the intended isolation mechanism.

- Risky, long-running or parallel work goes into its **own linked worktree and
  branch**, created by the Lead:
  `git worktree add ../binary-repair-<lane> -b <lane> coverage-audit-2026-11-14`.
- Never `git checkout`/`git switch` the shared worktree to another branch; it
  strands every other agent's uncommitted work.  Use `git -C <path>` (Lead) or a
  separate worktree instead.
- Keep each lane's write scopes disjoint (recorded in the shared task).  When two
  lanes must touch the same file (for example `.github/workflows/ci.yml`), the
  owner of the file is decided in the contract and the other lane requests
  changes by message.
- Do not merge/rebase yourself; the Lead integrates and pushes.

## 3. Commit and push cadence

Because a reset can arrive at any step, durability comes from **small commits**,
not from big verified batches:

1. Teammate finishes a small batch (roughly one concern: one script, one doc,
   one test file group) and runs the relevant checks.
2. Teammate messages the Lead with exact paths, the commands run and the honest
   result (including known mid-flight failures).
3. Lead commits that batch with a focused, scoped message
   (`feat(release-gate): ...`, `docs(operations): ...`, `test(coverage): ...`),
   pushes `coverage-audit-2026-11-14` and only then lets the next batch land.
4. After a green final run the Lead fast-forwards `workbench-v3`.
5. Unfinished work is announced explicitly ("not ready to commit"), so the Lead
   can choose to commit it on a scratch branch rather than lose it.

Commit messages reference the workstream/task (e.g. T5/task-16) so a reset can
be reconstructed from the contract plus `git log`/`git reflog`.

## 4. Stash safety

`git stash` is a trap in a shared worktree: the external operator or another
reset can drop/overwrite stashes, and a blind `stash pop` can clobber files that
another agent wrote in the meantime.  Rules:

- Do **not** use `git stash`/`stash pop`/`stash drop` in the shared worktree.
  This includes teammates hiding an untracked file "for a moment".
- To park work: copy/patch it outside the worktree or into a Lead-owned scratch
  path, or ask the Lead to commit it on a temporary branch.
  `git diff > <backup>.patch` (read-only) plus a file copy is the safe pattern.
- If the Lead must stash: one named stash per lane, never `--include-untracked`
  with other lanes' files, and never `stash pop` without checking
  `git stash show --include-untracked` first.
- Untracked evidence/artifacts are especially risky: regenerate them from the
  scripts (`capture_acceptance.py`, `audit_capability_coverage.py`,
  `reproduce_backup.py`) instead of relying on untracked copies.

## 5. The two reset incidents and the lessons

**Incident 1 (phase 2).**  The phase-2 contract records that the worktree had
already been externally reset once and that uncommitted work was at risk.  The
team moved to immediate Lead commits after each small batch and re-ran the audit
and tests on the integrated tree rather than on local dirt.

**Incident 2 (between phase 2 and phase 3).**  A second external reset/revert
discarded in-flight edits again.  The response added: separate worktrees for
parallel lanes, reconstructable evidence (`reproduce_backup.py` regenerates the
marcx acceptance bundle; `capture_acceptance.py` regenerates the real-guest
capture), SHA256SUMS-checked artifacts, and this protocol.  The phase-3
contracts encode it as a rule ("external operator may still act on this
worktree; never run state-changing git").

Lessons (all encoded above):

1. Uncommitted files are **not** durable; commit/push cadence is the only
   protection.
2. Evidence must be **regenerable by command**, not hand-edited: a reset can
   delete it, but it can also be rebuilt and its digests re-verified.
3. **Isolation** (separate worktree/branch) beats in-place stashing.
4. A clean `git status` you did not create is a warning sign, not good news.
5. Never "helpfully" clean the shared tree; other agents' uncommitted files look
   like garbage to a `git clean`/checkout.

## 6. Detect a reset / external change

Run these read-only checks when files seem to move on their own, tests suddenly
fail, or a file you wrote is missing:

```bash
git status -sb                 # uncommitted/untracked state vs expected batch
git log --oneline -5           # did HEAD move?
git reflog -15                 # any reset/rebase/checkout entries?
git worktree list              # am I even in the worktree I think?
git diff --stat                # is my change still there?
git rev-parse HEAD origin/coverage-audit-2026-11-14   # in sync?
```

Signals: your edit is gone, `HEAD` changed without your action, `git status`
went from dirty to clean, files from another lane appear/disappear, or reflog
shows a reset/rebase you did not request.  If you see any of these: **stop
editing**, do not try to recover with state-changing git, message the Lead with
the observed facts (paths, `git status -sb`, recent reflog lines).

## 7. Restore runbook (Lead-led; teammates assist)

The goal is to restore from committed history or regenerate, not to guess which
copy of a file is newest.

1. **Freeze.**  All teammates stop writing; the Lead captures the observed
   state (`git status -sb`, `git log --oneline -10`, `git reflog -25`,
   `git worktree list`) and lists the paths that are missing.
2. **Find a source of truth** (in order):
   - the last commit on `origin/coverage-audit-2026-11-14` (Lead fetches/pulls),
   - the Lead's backup/patch copies under `.tmp/team/` (contracts, notes,
     backup scripts),
   - a sibling worktree or scratch branch holding the lane,
   - artifact/evidence directories carrying `SHA256SUMS`,
   - teammate editor local history as the last resort.
3. **Restore by regeneration first.**  Re-run the scripts instead of
   re-typing outputs:
   - `.venv/bin/python artifacts/coverage-closure-2026-11-14/capture_acceptance.py`
     (writes the committed real-guest capture; needs the Lima guest; Lead
     approves before committing);
   - `.venv/bin/python scripts/audit_capability_coverage.py` (re-measures the
     gap report/matrix);
   - `.venv/bin/python .tmp/team/reproduce_backup.py` (marcx capacity-check
     acceptance bundle + `SHA256SUMS`);
   - re-run the build/generator scripts for fixtures instead of trusting copied
     binaries (e.g. `fixtures/hard-cases/gen_capacity_archives.py`).
4. **Re-apply lost edits** from patch files/chat summaries in small batches, with
   the Lead committing each batch as soon as it is on disk.
5. **Re-run the verification matrix below**, then re-check artifact digests
   (`SHA256SUMS`) and claims/docs consistency before any release claim.

### Post-restore verification matrix

```bash
# fast, always runnable
.venv/bin/python scripts/release_gate.py --pr
.venv/bin/python scripts/verify_coverage_gate.py --static-only
.venv/bin/python scripts/verify_ci_evidence.py
.venv/bin/python -m pytest -q tests/test_release_gate.py \
    tests/test_coverage_gate.py tests/test_capability_audit.py \
    tests/test_acceptance_invariants.py tests/test_meta_audit.py \
    tests/test_ci_evidence.py

# workstream suites touched by the restored lane (examples)
.venv/bin/python -m pytest -q tests/test_capacity_repair.py \
    tests/test_binary_pipeline_capacity.py tests/test_repair_heap.py \
    tests/test_gate_profiles.py tests/test_target_scope.py \
    tests/test_legacy_manifest_gate.py tests/test_runtime_capabilities.py \
    tests/test_binary_review_api.py

# Lima/guest-capable host only (real acceptance path)
.venv/bin/python scripts/verify_coverage_gate.py --local
.venv/bin/python artifacts/coverage-closure-2026-11-14/capture_acceptance.py
.venv/bin/python scripts/release_gate.py --release

# browser-capable host (Chrome/CDP) when UI was touched
.venv/bin/python -m pytest -q tests/e2e

# full suite (release bar)
.venv/bin/python -m pytest -q
```

Only after all of these pass (and the Lead has re-run the audit so the static
census reflects the restored tree) may the restored state be pushed/released.

## 8. Local-only state (never committed)

Some state is intentionally not in git and cannot be restored by git: the
operator API key (`var/assistant.key`, never print or copy it into logs), session
tokens (`var/session.token`), the virtualenv (`.venv`), Lima instance
`binaryrepair` and its guest staging dir (`~/.br-guest-stage`), browser
profiles, and local caches.  After a reset/worktree switch, recreate them from
`.env.example`/`start-gui.sh`/docs rather than checking them into the tree.
Artifacts under `artifacts/` are committed evidence and must be regenerated by
their scripts, not hand-edited.

## 9. New-agent checklist

1. Read the phase contract and your task's write scopes; never edit outside them.
2. Confirm the current `git status -sb` / `HEAD` with the Lead before starting.
3. Work in small batches; test; message the Lead with paths/results immediately.
4. Never run state-changing git; never stash/clean/format other lanes' files.
5. If anything looks externally modified, stop and report instead of recovering
   on your own.
6. Leave the worktree dirty only for a batch that has just been reported.
