# 200 — all-member rerun for v1.1.3

Date: 2026-11-09

## Old delivery clean clone

```text
729 collected / 727 passed / 2 Linux-only skipped / 0 failed
browser e2e: 12 passed
```

## Public v1.1.3 local

```text
commit 367d29bf1906b86db9d5a67cf612effe3b653ef0
tag v1.1.3
729 collected / 727 passed / 2 Linux-only skipped / 0 failed
artifacts sums 201/201
```

## Members

```text
M2 subset: pass (run-m2-tests.sh)
M3 self_test: 9/9
P2: exit 0, success_within_scope
```

## Public release state

```text
v1.1.2 is public and broken (13 test failures).
v1.1.3 is local and prepared; public push needs M4 permission.
```

## Remaining

```text
M4: push v1.1.3 main/tag/release after v1.1.2.
```
