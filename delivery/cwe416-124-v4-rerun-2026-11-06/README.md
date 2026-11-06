# CWE416 124 rerun with the 128 product V4 evidence

This bundle carries record 128's `v4-symbolic.json` as the V4 artifact and
declares `gates.V4 = passed`. V2 is re-scored from `original.elf`/`candidate.elf`
by `route_bundle_ingest`; the source `v2-interface.json` is a measured
observation, not a verdict.

- original: `c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9`
- candidate: `46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0`
- V4 artifact: `v4-symbolic.json` (product schema, record 128)
- V2: scored by the product check from the binary pair; 5/5

## Actual rerun: provisional

The bundle declares V4 passed, but the product refuses it without M4's
independent replay marker:

```
V0 passed V1 passed V2 passed V3 passed V4 not_run V5 passed
attempt outcome inconclusive / required_check_not_run / symbolic
obligations: symbolic not_run
```

This is producer/ingest provisional, not `success_within_scope`. The run also
remains `screening` because Route A has no result bundle. No completed-run,
T8.3 relief, or live-success claim.
