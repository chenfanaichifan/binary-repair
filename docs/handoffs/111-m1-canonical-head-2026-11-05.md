# M1: one canonical head, and the 33fc145 / 1938c31 relation

- Date: 2026-11-05
- Owner: M1 (host backend)
- Boundary: T8.3 stays blocked; no merge to `main`, no tag, no live-success claim

## Canonical head

```
branch   canonical/m1-m5-integration
remote   origin/canonical/m1-m5-integration
sha      8735f75643712b07915f74bdff3f92c3277c1c6f   (short 8735f75)
pushed   2026-11-05, ce36d6f..8735f75 (fast-forward, no force)
```

This SHA was read back from `git ls-remote origin` after the push, not predicted
before it.

## The relation between the two candidates

They are not two alternatives. They are three points on one line:

```
33fc145  db: keep M1 005/006 and M5 007/008, chain is [1..8]
   |
   |  8 commits, including 017ca87 "reject V0 without candidate hash match"
   v
1938c31  docs(fixtures): name the mirror by its full URL
   |
   |  1 commit: 8735f75 "keep the attempt join and report partial aggregates"
   v
8735f75  = canonical head
```

- `33fc145` is an **ancestor** of `1938c31` (`merge-base --is-ancestor` = 0;
  `rev-list --count 33fc145...1938c31` = 0 / 8).
- `1938c31` is an **ancestor** of `8735f75` (0 / 1).
- So "keep one of 33fc145 and 1938c31" resolves to **1938c31**: it is the
  strictly newer point and contains everything 33fc145 has.

`33fc145` is demoted to a history point. It is not the canonical head and no
document should present it as one.

## Why the branch sits on 8735f75 rather than on 1938c31

`1938c31` still ships the **narrow** `aggregate_job_usage`: a single NULL token
row collapses the whole answer to `None`, and attempt-bound rows are not joined.
`8735f75` is its only direct child and fixes exactly that, keeping the attempt
join and reporting partial sums — the behaviour this project already asked for.
Stopping at `1938c31` would therefore have dropped a requirement that predates
this instruction, so the branch stops one commit later.

`1938c31` remains the answer to "which of the two old candidate SHAs is the
final wording"; `8735f75` is the answer to "which commit the branch points at".

## Checked at 8735f75

| Requirement | Evidence |
|---|---|
| migrations 005/006 + 007/008 present | `app/db/migrations/` lists 002..008 |
| `007` still an empty placeholder | the file has zero non-comment statements |
| `schema_migrations` `[1..8]` | `tests/test_db_v2.py` asserts `[1, 2, 3, 4, 5, 6, 7, 8]` |
| V0 binds by candidate hash, no `ids[0]` fallback | V0 branch computes `matches` from `candidate_sha256` and raises `IngestError` when empty; there is no `ids[0]` in the file |
| CWE121 stays unverified | `build.json` says `"status": "unverified"` |
| CWE416 has no hand-made ELF | the directory holds `PROVENANCE.md`, `defect.json`, `src.c` only — no `original.elf` |
| wide `aggregate_job_usage` | `8735f75` keeps the attempt join and returns `partial` |

## Test numbers, measured here, on this machine

| Commit | Result | Notes |
|---|---|---|
| `1938c31` | 406 passed / 3 skipped / 0 failed | the commit the "406/3/0" figure refers to |
| `8735f75` | 407 passed / 3 skipped / 0 failed | one extra test, the wide-usage case |

Both runs used `pytest --ignore=tests/e2e`, on Windows, against the repo's own
venv. The `+1` is not flakiness: `8735f75` adds a test for the partial aggregate.

These are **local results only**. `tests/test_routeb_executor.py` needs GNU
`readelf` and `objdump` on `PATH`; CI must install binutils itself and must not
assume this host's toolchain.

## Note on the integration branch

`integration/live-bridge` and `integration/live-bridge-2026-11-03` sit on a
different line: they branch from `fba137e`, revert it in `9d59e72`, and carry the
CWE-122 fixture and the `partial` helper work. They are a superset in intent but
not in ancestry, so they are not ancestors of `8735f75` and must not be used as
one.

## Boundary

- T8.3 remains **blocked**: the CWE-122 fixture still reports
  `missing_file original.elf` and `missing_file tests/SHA256SUMS`.
- No merge to `main`, no tag.
- The pushed SHA is a fact about the remote. It does not mean the pipeline was
  exercised end to end, and no document here claims live success.
