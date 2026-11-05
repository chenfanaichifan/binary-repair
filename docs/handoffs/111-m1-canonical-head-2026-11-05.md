# M1: one canonical head, and the 33fc145 / 1938c31 relation

- Date: 2026-11-05
- Owner: M1 (host backend)
- Boundary: T8.3 stays blocked; no merge to `main`, no tag, no live-success claim

## Canonical head

```
branch   canonical/m1-m5-integration
remote   origin/canonical/m1-m5-integration
sha      1938c311672282ebd1fee3634fec9aad57760769   (short 1938c31)
push     2026-11-05, forced update 8735f75 -> 1938c31 (force-with-lease)
```

The SHA was read back from `git ls-remote origin` after the push. No document
before the push claimed M4/M5 could reproduce from it.

This supersedes the earlier draft of this handoff, which had stopped the branch
at `8735f75`. The 406/3/0 figure below belongs to `1938c31`; `8735f75` measures
407/3/0 because it adds the wide-usage test. The requested baseline is
`1938c31`, so the branch now points there.

`8735f75` is not lost: it remains reachable from the local
`backup/canonical-8735f75` ref and from the detached worktree that was using the
branch. It is simply not the canonical head.

## The relation between the two candidates

They are not alternatives. They are two points on one line:

```
33fc145  db: keep M1 005/006 and M5 007/008, chain is [1..8]
   |
   |  8 commits, including 017ca87 "reject V0 without candidate hash match"
   v
1938c31  docs(fixtures): name the mirror by its full URL   = canonical head
```

- `33fc145` is an **ancestor** of `1938c31`
  (`merge-base --is-ancestor` = 0; `rev-list --count 33fc145...1938c31` = 0 / 8).
- So "keep one of 33fc145 and 1938c31" resolves to **1938c31**: it is strictly
  newer, and it carries the V0 tightening that `33fc145` predates.

`33fc145` is demoted to a history point. No document should present it as the
canonical head.

## Checked at 1938c31

| Requirement | Evidence |
|---|---|
| migrations 005/006 + 007/008 present | `app/db/migrations/` lists 002..008 |
| `007` still an empty placeholder | zero non-comment statements in the file |
| `schema_migrations` `[1..8]` | `tests/test_db_v2.py` asserts `[1, 2, 3, 4, 5, 6, 7, 8]` |
| V0 binds by candidate hash, no `ids[0]` fallback | the file has no `ids[0]`; V0 raises `IngestError` when no candidate matches |
| CWE121 stays unverified | `build.json` -> `"status": "unverified"`, reason recorded inline |
| CWE416 has no hand-made ELF | tree holds only `PROVENANCE.md`, `defect.json`, `src.c` |

## Test numbers, measured on this machine

| Commit | Result |
|---|---|
| `1938c31` (canonical) | **406 passed / 3 skipped / 0 failed** |
| `8735f75` (backup ref) | 407 passed / 3 skipped / 0 failed |

Both runs: `pytest --ignore=tests/e2e`, Windows, the repo's own venv. The `+1`
on `8735f75` is its wide-usage test, not flakiness.

These are **local results only**. `tests/test_routeb_executor.py` needs GNU
`readelf` and `objdump`; on this host they come from an external toolchain
directory that is not in the repo. CI must install binutils itself.

## Note on the integration branch

`integration/live-bridge` and `integration/live-bridge-2026-11-03` branch from
`fba137e` and revert it in `9d59e72`. They carry the CWE-122 fixture and the
`partial` helper work, but they are **not** ancestors of `1938c31` and must not
be treated as the same line.

## Boundary

- T8.3 remains **blocked**: the CWE-122 fixture still reports
  `missing_file original.elf` and `missing_file tests/SHA256SUMS`.
- No merge to `main`, no tag.
- The pushed SHA records where the branch points. It does not claim the pipeline
  ran end to end, and no live-success statement is made here.
