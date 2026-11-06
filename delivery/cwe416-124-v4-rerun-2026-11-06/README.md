# CWE416 124 rerun with the 128 product V4 evidence

This bundle carries record 128's `v4-symbolic.json` as the V4 artifact and
declares `gates.V4 = passed`. V2 is re-scored from `original.elf`/`candidate.elf`
by `route_bundle_ingest`; the source `v2-interface.json` is a measured
observation, not a verdict.

- original: `c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9`
- candidate: `46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0`
- V4 artifact: `v4-symbolic.json` (product schema, record 128)
- V2: scored by the product check from the binary pair; 5/5

## Actual rerun

All six required gates are `passed` on the Route B attempt:

```
V0 passed V1 passed V2 passed V3 passed V4 passed V5 passed
attempt outcome success_within_scope
obligations: all six passed
```

The run remains `screening` because the Route A attempt has no result bundle;
that is not a six-gate failure. This bundle does not claim a completed run,
T8.3 relief, or a live success.
