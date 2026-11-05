# V0 parity pinned; binutils present; suite fully green

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Branch head: `fba137e`
- Suite: `408 passed / 3 skipped / 0 failed`

Test pointer remains `docs/handoffs/99-m1-v0-parity-2026-11-05.md`.

## The requested merge point changed

The task named `f11a165` as the integration merge point. This branch was reset
there, then a second M1 session moved it back to `fba137e`
(`feat(fixtures): complete the CWE121 baseline and pin CWE416`, parent
`eedb4b6`). The operator then chose to keep `fba137e` rather than fight the
reset, so:

- the branch head is `fba137e`, not `f11a165`
- migrations are `005/006` (M1) plus `007/008` (M5), `schema_migrations` `[1..8]`
- `f11a165`'s `[1..6]` no longer describes this branch

`f11a165` remains an ancestor, so its V0 parity work is included.

## V0 stays inside the V0 gate

`tools/route_bundle_ingest.py` binds the candidate only inside
`if gate == "V0":`, picking the artifact whose digest equals
`candidate_sha256`. No other gate reuses that rule; V1/V2 still resolve their
evidence by relative path. When no V0 artifact matches, ingestion raises instead
of binding the first file.

## result-bundle listing is checked twice, separately tested

`_sums_names(bundle)` plus `handoff.json#files` must both list
`result-bundle.json`; either omission rejects the bundle.

The two tests were previously entangled — the "handoff missing" case also
removed it from `SHA256SUMS`, so a single failure could not tell which check
fired. They are now isolated:

| Test | handoff.json#files | SHA256SUMS |
|---|---|---|
| `test_legacy_result_bundle_missing_from_handoff_is_rejected` | omits it | lists it |
| `test_legacy_result_bundle_in_handoff_but_not_sums_is_rejected` | lists it | omits it |

## binutils: the permanent failure is gone

`tests/test_routeb_executor.py::test_static_routeb_bundle` asserted
`file_count >= 8` and failed with `7` on every branch, because
`routeb/executor.py` writes five independent views through `readelf` and
`objdump`, and this host had neither.

Installed into `D:\brtmp\toolchain` (no system change):

```
w64devkit 2.11.0            -> objdump.exe (GNU binutils 2.47)
MSYS2 binutils 2.47-4       -> readelf.exe + objdump.exe
gettext-runtime, libiconv, zlib, zstd  -> libintl-8, libiconv-2,
                                          libasprintf, libcharset, zlib1, libzstd
```

Working directory: `D:\brtmp\toolchain\msys-binutils\bin`. Prepend it to `Path`
for the test run. `readelf --version` and `objdump --version` both report
GNU Binutils 2.47.20260726.

This is a host toolchain, not a repository dependency: the repo still expects
`readelf` and `objdump` on `PATH`, and a machine without them still produces
`7` and fails that test. CI needs the same binaries.

## Session note

A second M1 session was writing this branch concurrently; a reset performed here
was undone by it. The operator has since asked it to stop. One of its uncommitted
tests (`test_ai_usage_sources.py`, aggregation counting) is included here rather
than left loose, so it is not lost by the next reset.

## Constraints held

- T8.3 stays blocked; nothing here claims it complete.
- No merge to `main`, no tag, no live-success claim.

## M5 af01baf: the weaker aggregate was rejected

M5 pushed `af01baf feat(m5): aggregate ai_usage across job`, merged here as
`c0c0580`. Its `aggregate_job_usage` filters `model_calls` by `job_id` alone.
Route calls never carry a `job_id` — they carry `attempt_id` — so every route
token would have been invisible to the aggregate.

This branch already had the wider query:

    WHERE job_id = ? OR attempt_id IN (
      SELECT a.id FROM attempts a JOIN runs r ON r.id = a.run_id
      WHERE r.job_id = ?)

`OR` cannot double count: SQL selects a row at most once, so a row carrying
both bindings still contributes once.

**The merge produced two definitions**, ours near the top and M5's at the end of
`model_calls.py`. Python binds the later one, so without attention the module
would have silently returned to the narrow behaviour while M5's own test still
passed (it only exercises job-bound rows). The trailing copy was deleted; the
file now defines `aggregate_job_usage` once.

Two tests cover what the hand-off asked to verify:

| Test | Asserts |
|---|---|
| `test_aggregate_counts_job_and_attempt_bindings_once` | 2+3 (job) + 4+5 (attempt) + 1+1 (both) = 7/9, not 14/18 |
| `test_aggregate_ignores_another_jobs_attempts` | another job's attempt rows do not leak in |

## Suite difference is PATH, not code

This record says `0 failed`; a run in the app's own shell still reports
`test_static_routeb_bundle` failing with `assert 7 >= 8`. `readelf` and
`objdump` are not on that shell's PATH, and `routeb/executor.py` counts the
files they produce. Same tree, different environment.
