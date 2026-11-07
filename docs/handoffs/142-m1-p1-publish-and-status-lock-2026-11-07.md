# 142 — P1 publication, V2 value, and status lock

- Date: 2026-11-07
- Owner: Member 1
- Canonical remains **`3a107ab`**; M5 `a63f80d` read-only.
- No main merge, tag or live-success claim.

## 1. P1 published

```
delivery/m1-real-p1-2026-11-07.zip
sha256 9bd3e9e9be2ca0d0dc91128882f716e1e8fc825b3c22f7fdad8a6fe5a41058c5

job      3cde2df6164d4b8fbf9c8b75b93b4a37
run      8d7a422830794a68bd50709716c62109
route A  046ea49a23ab4ff59e98d6247ca4c726
route B  119f3ffa22c54e6e84e0c313e1055012
```

Package contains `route-a-input.json`, `ids.json`, `worker.txt`, `p2.txt`,
`snapshot.json`, README and `SHA256SUMS`. The global `delivery/SHA256SUMS` and
`delivery/MANIFEST.md` now reference it. The stale 124 MANIFEST row was corrected
to "provisional, V4 not_run, no success".

## 2. V2 actual value

P1 **Route A and Route B both V2 = `not_run`**. The P1 archive has no V2
artifact. P1 p2 verdict is `inconclusive / required_check_not_run / identity`
(Route A V0 not_run).

The 5/5 static interface result belongs to **124 only**; it must not be copied
onto P1.

## 3. T8.3 status lock

Canonical status: **T8.3 BLOCKED**.

- 118 is **VERIFIED (rebuild evidence package)**, independent of T8.3.
- A T8.3 `COMPLETE` label is not adopted; it is retracted/ignored because the
  second defect-class and V5 evidence are absent.
- COMPLETE and BLOCKED must not coexist in any M1 record.

## 4. Route A / V5

- Route A is identity-only: candidate artifact registered, all six gates
  `not_run`; it is not an execution pass and not a copy of Route B.
- P1 V5 is `not_run`; the second guest replay is requested at
  `delivery/p1-v5-replay-request-2026-11-07/`. No V5 evidence is invented.

## 5. Checks

```
M1 full --ignore=e2e   505 passed / 2 skipped / 0 failed
```

CWE121/120 gates unchanged. T8.3 blocked; no main merge, tag or live success.
