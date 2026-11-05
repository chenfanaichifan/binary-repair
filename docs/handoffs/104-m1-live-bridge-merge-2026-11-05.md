# integration/live-bridge branch created; M5 017ca87 merged

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Branch: `integration/live-bridge-2026-11-03`
- Merge commit: `1429e59` (parents `ce36d6f`, `017ca87`)
- Suite: `402 passed / 3 skipped / 1 failed` (missing `readelf`)

## The requested base did not exist

The task named `8c77fcd` as the base and `integration/live-bridge-2026-11-03`
as the target. Neither existed:

| Check | Result |
|---|---|
| `git cat-file -t 8c77fcd` | not a valid object |
| `rev-list --all` for `8c77fcd*` | no match |
| `fsck --unreachable --no-reflogs` | no match |
| `reflog --all` | no match |
| all 163 refs on `origin`, incl. `refs/pull/*` | no match |
| local + remote branch list | no `live-bridge` branch |
| `.git/config` | one remote, `github.com/chenfanaichifan/binary-repair` |

There is no second remote and no deleted-remote ref log, so "the old origin"
does not exist in this clone. The base was therefore taken as `ce36d6f`, the
current `canonical/m1-m5-integration` head, on the operator's decision.

`ce36d6f` already contains `c50ca04`, so merging the named M5 commit alone would
have been a no-op. M5's only new commit is `017ca87 fix(m5): reject V0 without
candidate hash match`.

## Conflict resolution

Both sides had independently implemented the same V0 rule — M1 in `0c3708a`,
M5 in `017ca87`: if no gate artifact hashes to `candidate_sha256`, reject
instead of binding the first listed file.

- `tools/route_bundle_ingest.py`: kept M1's implementation and message
  (`gate V0 evidence does not contain the declared candidate ...`), because
  record 101 and its test assert on it; added a comment naming `017ca87`.
- `tests/integration/test_route_bundle_ingest.py`: kept M1's `_bundle` helper
  (it writes the real digest with a comment explaining why a placeholder is
  unsafe) and aligned M5's new test to the behaviour rather than its wording.

No semantic divergence remained.

## Migrations

Both numberings are kept, unchanged by this merge:

```
005_assistant_messages        M1, body applied
006_obligation_scope          M1
007_assistant_messages        M5 slot, empty placeholder
008_assistant_plan_superseded M5 columns
```

`schema_migrations` is `[1, 2, 3, 4, 5, 6, 7, 8]`, verified by building a fresh
database on this branch.

## Checks run

```
pytest --ignore=tests/e2e
-> 402 passed, 3 skipped, 1 failed

tests/integration/test_route_bundle_ingest.py
tests/integration/test_assistant_plan_endpoint.py
tests/integration/test_assistant_endpoint.py
tests/integration/test_ai_usage_sources.py
-> 35 passed
```

The single failure is `test_routeb_executor.py::test_static_routeb_bundle`
(`assert 7 >= 8`): `routeb/executor.py` counts files produced with `readelf` and
`objdump`, and this host has neither. Pre-existing on every branch, unrelated to
the merge.

## Constraints held

- T8.3 stays blocked; nothing here claims it complete.
- No merge to `main`.
- No tag.
- Branch pushed so M4/M5 can reproduce: `origin/integration/live-bridge-2026-11-03`
  = `1429e59`, 0 ahead / 0 behind.
