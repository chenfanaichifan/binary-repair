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

```text
V2 not_run
V4 not_run
V5 passed (independent replay)
no route A controller result
p2 acceptance: M1 exit 0, verdict inconclusive
repair success: no
```

T8.3 is independent and remains complete (V4 marker/124).
