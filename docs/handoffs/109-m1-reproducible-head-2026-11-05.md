# M1: reproducible head, and the `8c77fcd` investigation closed

- Date: 2026-11-05
- Owner: M1 (host backend)
- Status: decision recorded; branch heads set; T8.3 stays blocked

## Decision

| Role | Commit | Meaning |
|---|---|---|
| Reproducible base anchor | `ddd3869` | `chore: ignore worklogs, .tmp and .dsh-acl-recovery` |
| Current head | `4997443` | `ddd3869` + the six commits listed below |

`integration/live-bridge` and `integration/live-bridge-2026-11-03` both point at
`4997443`. `ddd3869` is the named anchor that M4/M5 reproduce from; the head is
that anchor plus the commits that carry the retained work.

Why the head is not `ddd3869` itself: `ddd3869` ships the **narrow**
`aggregate_job_usage` (any NULL token row collapses the whole answer to `None`).
The wide version, which sums the real rows and reports `partial`, landed later in
`de48d6a`. Setting the head to `ddd3869` would have deleted the wide semantics
that this same instruction requires be kept. Both cannot be true at once, so the
anchor and the head are recorded separately.

## The six commits above the anchor

```
de48d6a feat(usage): report a partial sum instead of discarding it
9d59e72 Revert "feat(fixtures): complete the CWE121 baseline and pin CWE416"
c9316d3 feat(intake): require a distinct bug site for the second class
965b868 feat(intake): land the bug-site check and complete the task-30 fixture
03e3b11 feat(fixtures): scaffold the CWE-122 second class from SARD 112
4997443 fix(fixtures): store the SARD case as bytes, not as text
```

`9d59e72` is a deliberate revert: the CWE-121 sample was reconstructed from its
own ELF and never rebuilt, so it cannot claim upstream provenance. It is back to
`contract.json` + `original.elf` + two cases and is **not verified**. That gap is
recorded, not backfilled.

## Retained items, verified at the head

| Item | Evidence |
|---|---|
| M5 `c50ca04` | ancestor of `ddd3869` |
| M5 `017ca87` | ancestor of `ddd3869` |
| M5 `af01baf` | ancestor of `ddd3869` |
| Wide `aggregate_job_usage` | `de48d6a`; returns `{input_tokens, output_tokens, partial}` |
| Migrations `005`/`006` (M1) | present since `ddd3869` |
| Migrations `007`/`008` (M5) | present since `ddd3869`; `007` is an empty placeholder |
| `schema_migrations` `[1..8]` | `tests/test_db_v2.py:53` and `:86` assert `[1, 2, 3, 4, 5, 6, 7, 8]` |

## `8c77fcd` is closed

Conclusion: **`8c77fcd` does not belong to this repository. It is replaced by
`ddd3869` as the reproducible anchor.**

The record behind that conclusion, unchanged from handoff 104:

| Probe | Result |
|---|---|
| `git cat-file -t 8c77fcd` | `fatal: Not a valid object name` |
| `for-each-ref` over every local and remote ref | no match |
| reflog and unreachable-object scan | no match |
| all 163 `origin` refs, including `refs/pull/*` | no match |
| `git remote -v` | a single remote, so there is no second origin to fetch from |

No object with that prefix exists anywhere in this clone, so nothing in this
repository can be built on it. It also appears as the prerequisite of M3's
`member-3-t62-host-safe.bundle`, which is why that bundle cannot be unpacked here
(handoff 105). That is a property of the bundle, not of this branch.

## Instructions for M4 and M5

- Stop referencing `8c77fcd`. It is not a commit in this repository.
- Reproduce from `ddd3869` (anchor) and consume `4997443` (head) on
  `integration/live-bridge`.
- If a bundle or a note still demands `8c77fcd` as a prerequisite, treat it as
  unavailable and request a full `git bundle create <name>.bundle <branch>` or a
  direct push instead of a delta pack.

## Boundary

- T8.3 remains **blocked**. The CWE-122 fixture still reports
  `missing_file original.elf` and `missing_file tests/SHA256SUMS`, and will until
  M3 returns the Linux build (handoff 108).
- No merge to `main`. No tag. No live-success claim anywhere in this change.
