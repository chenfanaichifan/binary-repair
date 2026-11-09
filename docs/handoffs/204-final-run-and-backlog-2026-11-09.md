# 204 — final run and remaining backlog

Date: 2026-11-09  
Source head: `6eb169`

## Run

```text
old clean clone: 729 collected / 727 passed / 2 Linux-only skipped / 0 failed
browser e2e: 12 passed
M2 subset: pass
M3 self_test: 9/9
P2: exit 0 / success_within_scope
public v1.1.3: 367d29b, full pass
```

## Closed

```text
r4 18/18 + 132
v1.1.3 public main/tag/release
v1.1.2 retained/superseded
v1.1.1/v1.1.0/v1.0.0 unchanged
old main 472aa94 unchanged
```

## Remaining tasks

M4:
- add signed `release/V1.1.3-RELEASE-RECEIPT.md` to source delivery
- do not change public tag/main

M1:
- add M4 receipt to handoff package when received
- keep source code head `30dc006`

M2:
- v1.2.0 optional: non-http upload hide, 64 MiB hint, merge two 196 docs
- work only on m2-h/new branch; do not touch final tag

P1/Review owner:
- 12 fresh browser replays in v1.2.0 batch

Lead:
- hold v1.1.3 freeze
- decide v1.2.0 scope/date

M3/VMer:
- no new task; evidence frozen; record 88 NOT AVAILABLE
```
