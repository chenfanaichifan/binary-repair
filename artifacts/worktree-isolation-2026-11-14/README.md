# Isolating the unpushed capacity-check commit (2026-11-14)

The local feature branch had advanced to `86587da` (capacity-check rewrite),
which was **not** on the remote and not authored by this workstream.  It was
isolated without merging or rewriting history:

```bash
git worktree add --detach ../worktree-capacity-check 86587da
git branch backup/capacity-86587da 86587da
git stash push -- CHANGELOG.md docs/acceptance/LIMITATIONS.md \
  docs/acceptance/ai-binary-repair-2026-11-13.md docs/status/claims.json \
  scripts/verify_evidence.py
git switch -C feature/ai-binary-repair origin/workbench-v3
git stash pop
```

The main workspace is now based on the remote `fd205dc` line (plus this
workstream's docs/commits).  The capacity worktree remains at `86587da` and its
targeted tests passed:

```
tests/test_capacity_repair.py
tests/test_binary_pipeline_capacity.py
tests/test_poc_runner.py
tests/test_guest_runner.py
=> 71 passed / 4 skipped
```

No `reset --hard` or `git clean` was used.  The capacity work is **not merged or
pushed**; merge/PR/discard is a user decision.

Remote at time of record: `feature/ai-binary-repair` / `workbench-v3`;
`main` unchanged.
