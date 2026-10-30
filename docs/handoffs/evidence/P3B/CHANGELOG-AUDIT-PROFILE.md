# CHANGELOG — audit-profile (2026-10-29)

Added `--audit-profile {route_a,route_b}` to `routeb/executor.py`.

- `route_a`: original behaviour. `same_file_size` must be true; no relaxation.
- `route_b`: `same_file_size` is still recorded truthfully as `false` when the
  candidate changes size. A new check `size_change_recorded` passes only when the
  size really changed and `changed_file_intervals` reaches the last common byte.
  `pass` = every check except `same_file_size`, plus `size_change_recorded`.

## Why the default is route_b here

This executor is only invoked by `jobwrap routeb`; the Route A path (gate3 /
Route A acceptance) does not call it. The default was set to `route_b` because
the wrapper at this snapshot has no way to forward `--audit-profile`.

## Constraint for the future

If Route A ever reuses this executor, the default is not acceptable: the wrapper
must pass `--audit-profile route_a` explicitly (or the default must be restored).
Route A auditing is not relaxed by this change.

Executor hash with this change: 87fee2b7f28eee7b4e29422940cc93fc68f5a49e45e722e715b1622ef9301d91


## Correction (2026-10-29, v4)

`87fee2b7…` is the PREVIOUS build. The executor that actually ran is
`4f07217583c00c3a02ceaa8294eb330270a0ba7ba9ec03ce3aa4fbcfa831b05d`, shipped as
`executor/routeb_executor.py`. Evidence: `audit.json` reports
`audit_profile=route_b_recompile` and `changed_inside_intervals=true`, neither of
which `87fee2b7` can emit; and `87fee2b7` could not have returned exit_code 0.
