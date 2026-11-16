# Default branch switch runbook (2026-11-17)

Status: P0-3. Owner: M4 (runbook only; **execution requires the repo owner**).
Audit performed 2026-11-17 against the live remote; no git write operation was
performed by M4.

## 1. Current facts (measured)

| Item | Value |
|---|---|
| GitHub repository | `chenfanaichifan/binary-repair` (origin: `git@github.com:chenfanaichifan/binary-repair.git`) |
| Remote default branch (symref) | `ref: refs/heads/main HEAD` -> `8869b07b2c4e8d306d39f4ee71f6feadf8e14f17` (stale) |
| Delivery branch | `final/consolidated-2026-11-16` = `ae89f888028131699fa2b9d5f5f764ba3b4a3842` (also verified via `git ls-remote origin`; the tip may advance until the integration freeze - always re-read it in verification) |
| Remote refs | 192 total = 91 heads + 89 tag refs |
| Local checkout | `binary-repair-gui` on `final/consolidated-2026-11-16`, clean worktree |
| Tooling for API-side switch | `gh` CLI: **absent**; `GH_TOKEN`/`GITHUB_TOKEN`: **unset**; SSH key works for fetch |

Conclusion: the default branch is still the old `main` (2026-11-12 history).
Visitors and clones land on stale code. Switching requires GitHub repository
admin rights (Settings) or an admin token; neither is available in this
workspace, so this item is **blocked_by=owner:github_default_branch**.

## 2. Owner operation steps (GitHub UI)

1. Open `https://github.com/chenfanaichifan/binary-repair/settings/branches`
   (must be signed in as the repository owner/admin).
2. Under "Default branch", choose the pencil/switch control and select
   `final/consolidated-2026-11-16`.
3. Confirm the change (GitHub asks for confirmation because it affects clones,
   PRs and links). Do **not** delete `main`; keep it as historical branch.
4. Optional hardening (same Settings page): add a branch protection rule for
   the new default branch (require PR + status checks) if the project will keep
   accepting changes. Do not block the owner from emergency pushes yet.
5. Optional: in Settings -> General, set the repository description/topics to
   match the delivery branch so visitors understand where the deliverable is.

Rationale for keeping `main`: the old branch is referenced by historical
releases/course material; deleting it is not required and would only add risk.

## 3. Verification commands (run after the owner switch)

From a machine with network access (read-only commands; safe for M4/Lead):
```
cd binary-repair-gui

# 1) default branch symref must point at the delivery branch
git ls-remote --symref origin HEAD
# expected:
#   ref: refs/heads/final/consolidated-2026-11-16	HEAD
#   <frozen delivery tip at switch time>	HEAD

# 2) delivery branch still present and identical
git ls-remote origin refs/heads/final/consolidated-2026-11-16
git rev-parse origin/final/consolidated-2026-11-16

# 3) ref counts unchanged apart from the default-branch marker
git ls-remote origin | wc -l            # expect 192
git ls-remote --heads origin | wc -l    # expect 91
git ls-remote --tags origin | wc -l     # expect 89

# 4) fresh-clone smoke test in a throwaway directory
git clone --depth 1 git@github.com:chenfanaichifan/binary-repair.git /tmp/binrepair-default-check
git -C /tmp/binrepair-default-check log --oneline -1   # expect 503b226 ...
git -C /tmp/binrepair-default-check branch --show-current  # expect final/consolidated-2026-11-16
rm -rf /tmp/binrepair-default-check
```
Record for the handoff report: command outputs (symref line, ref counts, clone
HEAD) and the timestamp of the switch.

## 4. Risks and rollback

| Risk | Impact | Mitigation |
|---|---|---|
| Owner switches while a teammate pushes to `main` | confusing default-branch state | freeze pushes during the switch (integration is Lead-only) |
| Old links/PRs assume `main` | historical links may resolve to the old branch or new default | keep `main`; document the switch in README/CONSOLIDATION (Lead owns text) |
| Branch rename/delete by mistake | default branch cannot be deleted but a rename breaks refs | do not rename; only change the default pointer |
| CI tied to `main` push events | workflows may stop running on the default branch | check `.github/workflows` triggers after switch (Lead/CI owner) |
| No admin access during handoff window | blocked state persists | owner must perform it before handoff sign-off |

Rollback (no data loss): open the same Settings page and select `main` as the
default branch again. No refs/objects change, so rollback is immediate and safe.

## 5. What M4 can and cannot do

- Can: provide the exact steps, the verification commands and evidence
  requirements; re-run section 3 after the owner reports completion.
- Cannot: perform the switch (no `gh`, no admin token, and git write operations
  are out of scope for members).
- Status: **blocked_by=owner:github_default_branch**. Verification evidence in
  section 1 was collected read-only; post-switch verification is pending.
- Lead decision (2026-11-16): the owner executes the switch; M4's deliverable is
  this runbook (steps + verification + rollback). Re-run section 3 after the
  owner reports completion and paste the symref/clone output into the handoff
  report.
