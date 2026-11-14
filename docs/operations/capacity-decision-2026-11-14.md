# Capacity-check commit decision (2026-11-14)

Local commit `86587da` (reviewed capacity-check rewrite) is **not merged and not
pushed** in this milestone.

- Preserved in detached worktree `../worktree-capacity-check`;
- protected by local branch `backup/capacity-86587da`;
- targeted tests in that worktree: 71 passed / 4 skipped;
- main branch was restored from the remote baseline without `reset --hard` or
  `git clean`; the main worktree is clean.

Decision: keep the branch for a future independent PR.  If/when it is merged,
it must be a standalone review/PR, not mixed with the A/matrix work.  See also
`artifacts/worktree-isolation-2026-11-14/`.
