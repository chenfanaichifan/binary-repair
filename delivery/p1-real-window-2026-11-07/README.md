# P1 real guest window — 2026-11-07

Source ZIP: `M3-P1-real-guest-window-2026-11-07.zip`
SHA256: `6d2ef8f3378582a88b8701402a707a0a2161c24fd192b0e8f61507cf27a329d0`

This is a real guest Route B repair run through `jobwrap-executor` (uid 1003,
no-egress netns, CapEff=0, NoNewPrivs=1, seccomp=2). It is not synthetic.

## Result

```text
wrapper exit: 0
bundle SHA256: dbc032fb5a1a846b9a23ec3e379442b8f97ba431b61f00aa9794f75d87973b2f
V0 passed
V1 passed
V2 not_run
V3 passed (1/1)
V4 not_run
V5 not_run
```

## Host ingest

Using `tools.route_bundle_ingest.ingest` on a real controller job/run/attempt:

```text
imported: yes
V0/V1/V3 artifacts registered
V2/V4/V5 not_run
attempt: inconclusive / required_check_not_run / symbolic
```

M3's `host_importer` projection failed on a V0 artifact binding; that projection
is not the production `route_bundle_ingest` path. The production ingest was
re-run here and succeeded.

## V5

The 2026-11-07 independent guest replay (`V5-replay.json`, pass=true, original and
candidate byte-identical twice) is integrated as the bundle's V5 gate.

```text
v5-replay.json: pass=true, runs=2, matches P1 candidate 46d16e99…
```

## P2 / P1 closure

Local controller rerun (2026-11-07):

```text
job        a6565abf6eef472ba4775436973806b2
run        3c30b19801aa47eabfb728953c1e2562
phase      finished
verdict    inconclusive / required_check_not_run / identity
route A    6 required, inconclusive (identity-only)
route B    6 required + optional repaired_behaviour, success_within_scope
V2         passed (host check_interface 5/5)
V4         passed (M4 marker)
V5         passed (independent replay)
p2         exit 0, synthetic=false
```

Evidence: `controller/snapshot.json`, `p2/p2-result.txt`.
This is a finished two-route job, not a repair success.


T8.3 is independent and remains complete (V4 marker/124).
