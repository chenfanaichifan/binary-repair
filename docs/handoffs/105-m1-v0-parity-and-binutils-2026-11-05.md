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
