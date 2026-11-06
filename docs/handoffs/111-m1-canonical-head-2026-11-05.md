# M1: canonical head, the `8735f75` push history, and the branch fork

- Date: 2026-11-05
- Owner: M1 (host backend)
- Boundary: T8.3 stays blocked; no merge to `main`, no tag, no live-success claim

## Canonical head

```
branch   canonical/m1-m5-integration
remote   origin -> https://github.com/chenfanaichifan/binary-repair.git
ref      refs/heads/canonical/m1-m5-integration
sha      1938c311672282ebd1fee3634fec9aad57760769   (short 1938c31)
```

Read back from `git ls-remote origin` after the push. This is the only remote in
the clone (`git remote -v` lists `origin` and nothing else).

## Was `8735f75` ever pushed?

Yes — to the **same** remote and the **same** ref, and it was then overwritten.

The remote-tracking reflog is the record (`git reflog show
refs/remotes/origin/canonical/m1-m5-integration`):

```
1938c31  @{0}: update by push     <- current
8735f75  @{1}: update by push     <- was on the remote
ce36d6f  @{2}: update by push
db497fa  @{3}: update by push
33fc145  @{4}: update by push
```

The sequence: `ce36d6f -> 8735f75` was a fast-forward on 2026-11-05, and the
subsequent `8735f75 -> 1938c31` was a `--force-with-lease` update made when the
requested baseline turned out to be the 406/3/0 commit (see below).

Consequences today:

| Question | Answer |
|---|---|
| Is `8735f75` on any remote ref now? | No. `git ls-remote origin \| grep 8735f75` is empty. |
| Was it pushed to a different remote? | No. There is one remote, `origin`. |
| Was it pushed to a different branch or tag? | No. Only `refs/heads/canonical/m1-m5-integration`. |
| Where does it live now? | Local `backup/canonical-8735f75` only, unpushed. |

So the earlier note "pushed `ce36d6f..8735f75`" was accurate at the time, but it
is not the current remote state; the current remote state is `1938c31`.

## `33fc145` vs `1938c31`

Not alternatives; one line:

```
33fc145  db: keep M1 005/006 and M5 007/008, chain is [1..8]
   |
   |  8 commits, including 017ca87 "reject V0 without candidate hash match"
   v
1938c31  = canonical head
```

`33fc145` is an ancestor of `1938c31`. Keeping one means keeping `1938c31`;
`33fc145` is a history point.

`8735f75` is a **descendant** of `1938c31` (it adds the wide-usage test and
measures 407/3/0). It was the head for one round, then the requested 406/3/0
baseline put the head back on `1938c31`. It is retained on a local backup ref,
not as the canonical head.

## Branch topology: canonical and integration are two lines

They share an ancestor and then diverge. They are **not** the same line, and one
is not a superset of the other in ancestry.

```
                        fba137e  feat(fixtures): complete the CWE121 baseline and pin CWE416
                       /       \
       (canonical)    /         \    (integration)
         ba65aed     /           \   9d59e72  Revert "feat(fixtures): complete the CWE121 baseline
       1938c31  <-- /             \            and pin CWE416"
                                  \
                                   ... -> bcb7a30  (both integration branches)
```

Facts, all verified:

| Item | Value |
|---|---|
| merge-base(`integration/live-bridge`, `canonical/m1-m5-integration`) | `fba137e` |
| `integration/live-bridge` | `bcb7a30` |
| `integration/live-bridge-2026-11-03` | `bcb7a30` (identical tip) |
| `canonical/m1-m5-integration` | `1938c31` |
| CWE-122 fixture present at `bcb7a30` | yes |
| CWE-122 fixture present at `1938c31` | **no** |

### What `9d59e72` reverts

`9d59e72` is a revert of `fba137e` on the integration side. It removes the
reconstructed CWE-121 artefacts that `fba137e` had added:

```
.gitattributes                                             5 -
docs/fixtures.md                                          74 +-
docs/handoffs/103-m1-fixtures-baseline-2026-11-05.md     101 -
fixtures/public/CWE121_src_char_declare_cpy_51b/build.json 73 -
  .../build.sh 46 -   .../defect.json 7 -   .../harness.c 37 -
  .../src.c 48 -      tests/SHA256SUMS 11 +-
  CWE416 .../PROVENANCE.md 44 -
```

Why it was reverted: the CWE-121 sample was reconstructed from its own ELF and
never rebuilt from source, so it cannot claim upstream provenance. On the
integration side the fixture is therefore back to `contract.json` +
`original.elf` + two cases, with **no** `build.json` claim at all.

### Where CWE-122 lives

The CWE-122 fixture (`fixtures/public/CWE122_c_CWE129_fgets_01/`, SARD 112
`c_CWE129_fgets_01`) exists **only** on the integration line. It is not on
canonical, and canonical must not be described as containing it. T8.3 is blocked
on that fixture, so the block applies to the integration line, not to
`1938c31`.

## Checked at `1938c31`

| Requirement | Evidence |
|---|---|
| migrations 005/006 + 007/008 | `app/db/migrations/` lists 002..008 |
| `007` empty placeholder | zero non-comment statements |
| `schema_migrations` `[1..8]` | `tests/test_db_v2.py` asserts `[1, 2, 3, 4, 5, 6, 7, 8]` |
| V0 binds by candidate hash, no `ids[0]` | no `ids[0]` in the file; raises `IngestError` when nothing matches |
| CWE121 unverified | `build.json` -> `"status": "unverified"` |
| CWE416 has no hand-made ELF | tree holds `PROVENANCE.md`, `defect.json`, `src.c` only |

Note the asymmetry: canonical reaches CWE121 `unverified` through an explicit
`build.json`; integration reaches the same state by having no `build.json` at
all (reverted). Both are "not verified"; neither claims a rebuild.

## Test numbers, measured here

| Commit | Result |
|---|---|
| `1938c31` (canonical) | 406 passed / 3 skipped / 0 failed |
| `8735f75` (backup ref) | 407 passed / 3 skipped / 0 failed |

`pytest --ignore=tests/e2e`, Windows, the repo's own venv. The `+1` is the
wide-usage test. **Local results only**: `tests/test_routeb_executor.py` needs
GNU `readelf`/`objdump` from an external toolchain directory not in the repo, so
CI must install binutils itself.

## Boundary

- T8.3 remains **blocked**: the CWE-122 fixture reports `missing_file
  original.elf` and `missing_file tests/SHA256SUMS`.
- No merge to `main`, no tag.
- The remote SHA records where the branch points. It does not claim the pipeline
  ran end to end, and no live-success statement is made.
