# M3 bundle is a delta pack; the branch was reset and restored

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Branch: `integration/live-bridge-2026-11-03` @ `fba137e`
- Suite: `405 passed / 3 skipped / 1 failed` (missing `readelf`)

## The M3 bundle cannot be used

`member-3-t62-host-safe.bundle` (95 KB) carries one ref,
`refs/heads/member-3/t62-host-safe` = `96a0a20`, and one prerequisite:

```
8c77fcdb7813e4d3dec24a8f2eb0f40a9f5dbdb3
```

That prerequisite is exactly the base this branch could not find, which
confirms M3 built T6.2 on top of it. The pack is a **delta bundle**: it holds
only what `96a0a20` adds on top of `8c77fcd`, not the base object.

| Attempt | Result |
|---|---|
| `git bundle verify` | `Repository lacks these prerequisite commits: 8c77fcd...` |
| `git fetch <bundle>` | same |
| `git unpack-objects -r` into an empty repo | `fatal: bad pack file` |

So the file yields no objects at all, and M3's own T6.2 changes remain unreadable
here. A full bundle (`git bundle create <name>.bundle member-3/t62-host-safe`
with no `--not`) or a direct push of the branch is required. `8c77fcd` itself is
still absent from this clone and from all 163 origin refs.

## The branch was reset, then restored

Mid-session, `integration/live-bridge-2026-11-03` was moved to `f11a165` — a
commit roughly forty behind — leaving a tree with only migrations 002–006 and a
`[1..6]` chain. No commit objects were lost; `reflog` retained the whole
sequence.

Restored with `reset --hard fba137e` and verified:

```
versions: [1, 2, 3, 4, 5, 6, 7, 8]
migrations: 002 003 004 005_assistant_messages 006_obligation_scope
            007_assistant_messages 008_assistant_plan_superseded
```

The numbering decides as instructed: M1 keeps 005/006, M5 keeps 007/008, and
007 stays an empty placeholder because its body is byte-identical to 005 and the
`ALTER TABLE` statements are not idempotent.

Pushed back: `eedb4b6..fba137e`, 0 ahead / 0 behind.

## Discarded working-tree edit

One uncommitted edit to `tests/integration/test_route_bundle_ingest.py` was
based on the `f11a165` text and changed
`test_legacy_result_bundle_must_be_in_sums` to also list `result-bundle.json` in
`SHA256SUMS`, so that a rejection could only come from the handoff check.
`fba137e` already has that case as
`test_legacy_result_bundle_in_handoff_but_not_sums_is_rejected`, so the edit was
redundant and was dropped. A backup was kept at
`D:\brtmp\tbi_worktree_backup.py` during the operation.

## Constraints held

T8.3 blocked, no merge to `main`, no tag.

## Note for whoever writes next

Two sessions have been editing this clone's single working tree at the same
time; that is what produced the reset-to-`f11a165`, the temporary `[1..7]`
migrations, and the earlier duplicate commits. Branch work should happen in
separate worktrees (`D:/brtmp/m1-close` already exists for one of them).
