# 45 — P4 CLI B and native evidence

P4 uses wrapper `b232d60b…` and the no-argument form:

```bash
jobwrap gate4
```

runner/repo/work come from root-owned `gate4.conf`; no `--` arguments. The old
`jobwrap gate4 -- ...` form is withdrawn.

The runner emits `manifest-compare.json` only. Any `case-01..06.json` is derived:

```json
{"derived_from":"manifest-compare.json","runner_native":false}
```

Only `manifest-compare.json` is native. Missing native case raw is recorded as a
missing item; do not write `gate4_pass`.

Gate 5 remains a separate fixed-script mode (A); P4 adds no second entry point.
