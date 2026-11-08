# 179 — M2 all inputs handoff (P1/P2/Review)

Date: 2026-11-07

## P1 final — consume, do not re-run

```text
job       9247357c54714546a7ff84891f7766f8
run       54a088e418d94a75b10d08bd893a5581
route A   516d69ac6a5e44eca23ec9bca914dc5d
route B   90aa7abe41cd4dd2b7d9211a44d247db
created   2026-11-07T15:36:50+00:00
phase     finished
verdict   success_within_scope
```

Raw API JSON:

```text
artifacts/p1-real-window-2026-11-07/api/attempts.json
artifacts/p1-real-window-2026-11-07/api/route-a-evidence.json
artifacts/p1-real-window-2026-11-07/api/route-b-evidence.json
```

Snapshot / p2:

```text
artifacts/p1-real-window-2026-11-07/controller/snapshot.json
artifacts/p1-real-window-2026-11-07/p2/p2-result.txt
artifacts/p1-real-window-2026-11-07/p2/P2-ACCEPTANCE.txt
```

p2 command:

```text
python tools/p2_acceptance.py --job-id 9247357c54714546a7ff84891f7766f8 --base-url http://127.0.0.1:<port>
exit 0
synthetic false
```

Identity:

```text
original  c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9
Route A candidate 2a96b1083f23a0885ef6152dee39c48648d496a7a026e37ccfb31382c412970e
Route B candidate 46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0
contract 8a2b408c9b1463ca8cb14692d11f1580f80816a74e81cc13310852f3700e3c3b
```

## M3 executor identity / credentials

```text
wrapper: /usr/local/sbin/jobwrap-executor (setuid root:lab)
executor uid: 1003 runner; no sudo; no SSH keys
attestation: /run/binrepair/executor/attest-<pid>.json root-owned 0444
no credentials are injected into M2
```

Records:

```text
docs/development/handoffs/152-m3-t62-executor-conformance-2026-11-07.md
workers/executor/README.md
artifacts/p1-real-window-2026-11-07/host/attest-1882.txt
```

VMer record 88 original is **not present** in this repo or surviving workspace.
Closest reset evidence:

```text
artifacts/p1-real-window-2026-11-07/host/reset.txt
artifacts/p1-real-window-2026-11-07/v5-replay-2026-11-07/NOTES.md
```

If M2 requires record 88, it must be marked `NOT AVAILABLE`; P1 already has a
completed reset record and must not be restarted for M2.

## Evidence binding

```text
2d74659 fix(m1): score Route A V2 from route_a/candidate.elf
1dccf08 feat(m1): integrate P1 Route A V4 and fix worker gate evaluation
0e6ace8 cherry-pick of 1dccf08
```

## M5 analysis / comparison

Typed analysis evidence:

```text
app/domain/analysis.py
  schema_version 1
  candidate_sha256
  expected_effects[]
  assumptions[]
  uncertainties[]
```

Comparison is currently an artifact role, not a typed JSON schema:

```text
role: behavior_comparison
```

M2 must use `GET /api/jobs/{id}/comparison`; it returns:

```json
{"job_id":"...","status":"not_provided|available","detail":"...","comparison":null,"artifacts":[]}
```

When an artifact exists, `status=available` and `comparison` is the parsed JSON;
when absent, render `not_provided`, never pass and never guess field names.

Attempts now expose `started_at`, `finished_at`, `candidate_sha256`,
`route_label`, `timeline_status`, `duration_ms`, `exit_code` (null = unknown).

## Review 9–12

```text
docs/development/reviews/review-9-12-canonical-2026-11-07.md
docs/development/reviews/review-9-12-m4-verification-2026-11-07.md
docs/development/reviews/review-9-12-m4-verdict-2026-11-07.json
```

Original text is not recoverable; M4 verdict: 9/10/11 PASS against canonical
reconstruction, 12 NOT VERIFIED until M2 UI/scope display exists.

## M2 immediate work

```text
T7.6: consume P1 final job; display success_within_scope
      use attempts/evidence JSON above
      analysis/comparison absent -> unavailable
T8.4: badge/script v1 already done; keep
Review 12: implement scope/bounded display; then M4 re-verifies
```
