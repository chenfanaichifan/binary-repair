# 236 — M2 public v1.2.1-rc1 verification

Date: 2026-11-10

## Public identity

```text
repo          leesirleesirlee-star/Binary_Repair
tag           v1.2.1-rc1
tag object    f5346978b46622c6c582e13d7cf6330f72e638f3
peeled commit d7d20f4ff2f920b5cfec5e81e3c4377529a9885a
branch        v1.2.1-rc1
prerelease    true
release       https://github.com/leesirleesirlee-star/Binary_Repair/releases/tag/v1.2.1-rc1
public main   94393403319a10acc00552a7ae62836699036518 (v1.2.0)
v1.1.3        367d29b (frozen)
```

## Verification on the public tag

```text
741 collected / 739 passed / 2 Linux-only skipped / 0 failed
browser e2e 12 passed
artifacts sums 201/201
```

## UI/security observations

```text
comparison three-state: inherited from v1.2.0
upload gate: HTTP visible / file hidden / 65 MiB rejected
key panel: password, no prefill, no key echo
Windows real-key UI: PASS cross-head 8f0908a (Lead accepted)
0d/99d real-key replay: NOT RUN
key cleared: true
```

This is a prerelease record; no stable claim.
