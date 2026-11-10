# BinaryRepair v1.2.1-rc1 candidate handoff (refreshed 2026-11-09)

```text
public base   94393403319a10acc00552a7ae62836699036518 (v1.2.0)
source branch release/v1.2.1
source head   99d15507a93aeecae511370ac3a2264f68c87782
candidate     67476c8010e68080c99b422f26f83f98fc0ad2bb
tag           v1.2.1-rc1 -> 67476c8 (annotated)
```

This handoff is refreshed from `release/v1.2.1@99d1550`, not `78ac8d2`.
It contains the final 222/228 alignment and the F2 key-cleanup/hold resolution.

## Verification

```text
recorded at source head 99d1550:
  737 collected / 735 passed / 2 Linux-only skipped / 0 failed
  browser e2e: 12 passed

refresh environment (this handoff):
  pytest --ignore=tests/e2e: 728 collected, exit 0, 0 failed
  browser e2e: NOT RUN (ModuleNotFoundError; current env lacks the browser deps)
  old e2e-99d/0d579 logs are retained for the source record

Linux real-key UI: PASS
Windows DPAPI (fake key): PASS
real provider smoke: ok (deepseek-flash, 38/5/43)
```

Real-key status:

```text
Windows real-key UI: PASS on cross-head 8f0908a (Lead accepted for rc1)
0d5791a real-key replay: NOT RUN
real key cleared: true
key file absent: true
key status: configured=false
log key count: 0
```

## Contents

```text
README.md
SHA256SUMS
docs/handoffs/216... / 218... / 220... / 221... / 222... / 226... / 228... / 229...
logs/full-0d579.txt, full-99d.txt, full-f2.txt
logs/e2e-0d579.txt, e2e-99d.txt
logs/m5.txt
```

## Limitations

- This is `v1.2.1-rc1`, a prerelease candidate, not a stable public release.
- Windows real-key UI was not re-run on `0d5791a`; the accepted evidence is the
  cross-head `8f0908a` PASS.
- Do not move public `main` from `9439340`.
- Do not move `v1.2.0` tag `82f3209d鈥?-> 9439340`.
- Do not create `v1.2.1` stable.

M4 owns public push/prerelease creation after verifying the bundle, tag target and
SHA256SUMS.


