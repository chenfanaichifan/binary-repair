# 50 — P3B v3 accepted into adapter (partial, not a gate pass)

**Package:** `P3B-package-v3-2026-10-29.zip`
**SHA-256:** `72d789c665fa2e7796b092b3c351a488472a68269549a5e709168dcf1020034b`
**checker:** PASS (18 files / 18 sums, `8bec86e0…`)

```text
candidate: 63fcafa6ed01d2db7d5d8a1af460af994e65da853c0c250b05c3eb761f616d01
c-source:  a2e4ff8f5071c20328f977153775c8dc7d8bf8a9f867278a5de2d48b81ccc90e
jobwrap:   exit_code=0, uid=1003, CapEff=0, NNP=1, netns=empty
audit:     route_b_recompile, pass=true, size_change_recorded=true
V3:        6/6, repaired_pass=true
```

Adapter/worker rerun (log `/tmp/p3b-v3-worker.log`):

```text
V0 passed; V1 passed; V2 not_run; V3 passed; V4 not_run; V5 passed
outcome: inconclusive
reason: required_check_not_run
failing_obligation: interface
```

P3B v3 is accepted as partial Route B evidence. It is **not** a Gate 4 pass;
V2/V4 remain not_run. Old `f46a3c8a…` is superseded.
