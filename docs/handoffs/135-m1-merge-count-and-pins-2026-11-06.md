# 135 — merge count correction and fresh pins

- Date: 2026-11-06
- Owner: Member 1
- Scope: correction record only. No code, gate or ref changed.
- T8.3 blocked. No merge to `main`, no tag, no live-success claim.

## 0. Fresh `ls-remote`

```
$ git ls-remote origin \
    refs/heads/canonical/m1-m5-integration \
    refs/heads/integration/live-bridge \
    refs/heads/integration/live-bridge-2026-11-03 \
    refs/heads/m1/t30-acceptance-ab-2026-11-05

d1ce352f60057ab3cd389c6af609c7b5ed3bcefd  canonical/m1-m5-integration
6d67140ee560ec66d5e606965d8193ae810405b1  integration/live-bridge
e2317772d638dbedbc64e6f049d1dcf4f1bc7699  integration/live-bridge-2026-11-03
e6689e47c0987afb8ec302d61050c6702f8c340f  m1/t30-acceptance-ab-2026-11-05
```

Canonical is **`d1ce352`** (the merge on top of `dc3bcd3`). `dc3bcd3` is its
first parent and remains a valid historical pin.

## 1. `6d67140` is docs-only; `41ff540` is the merge

```
6d67140  docs(m1): record the branch alignment and the withdrawn T30 swap
parent   41ff540
stat     MEMORY.md | 1 +
```

`6d67140` is **not** a merge commit. The merge is:

```
41ff540  Merge 3f21d31 into integration/live-bridge
parents  c217046 3f21d31
```

## 2. Corrected full-suite number

Measured on clean `git archive` trees, interpreter `role5-kit/.venv`,
`pytest -q -o addopts=""`:

| Tree | Result |
|---|---|
| `6d67140` | **513 passed / 9 skipped / 0 failed** (522 collected) |
| `41ff540` | **513 passed / 9 skipped / 0 failed** (522 collected) |

The merge message's **506 passed / 9 skipped** is not reproduced on either
tree. No tested commit/tree produced 506, so there is no exact tree+command to
attach to 506; the measured number is **513/9/0**, seven more passes. The merge
is green either way, and this correction changes no code or gate.

Canonical is a different tree: `d1ce352` measures **449 passed / 2 skipped**
with `--ignore=tests/e2e`, or **449 passed / 9 skipped** without it. Do not
apply the live-bridge 513 count to canonical.

## 3. Partial pass-through

Canonical `d1ce352` retains the M5 partial semantics:

- `aggregate_job_usage` keeps `job_id OR attempt_id`-via-`runs`;
- partial sums return `partial=True`, all-real returns `False`;
- `_ai_usage_for_job` passes the aggregate through unchanged;
- plan fallback returns `partial=False`.

## 4. Gates

CWE121 v2 hash and the 120 contract gate are unchanged. 124 remains
`inconclusive / required_check_not_run / symbolic`; V4 has no M4 replay marker.
T8.3 blocked.
