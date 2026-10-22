# MVP status and acceptance (2026-10-22)

## Accepted definition

MVP = the honest end-to-end demo:

1. Upload a real sample through the GUI; the job is created in the controller
   store (`demo:false`).
2. Contract review/edit/approval works; stale revision/hash return 409.
3. Start enqueues a run; the worker consumes per-attempt result bundles.
4. Both routes reach a terminal attempt verdict; `evaluate_run` writes the run
   verdict and job phase `finished`.
5. The GUI renders the controller verdict and V0–V5 obligations; it never
   computes or fabricates an outcome.
6. Evidence/export and security (session/CSRF) remain functional.

**Accepted outcome: `inconclusive`.** The current evidence only supports V0 and
V3 (with formal-run); V1 is unknown/incomplete, V2/V4/V5 are not run. MVP is a
complete, honest pipeline, **not** a claim that the vulnerability is fixed.
`success_within_scope` is explicitly out of scope for this MVP; it requires
formal Gate 4 + V4/V5 (M3/VMer/M4).

## Completed

- GUI: landing, two-step setup, comparison, evidence, dry-run interface view.
- Controller integration: `http` mode against tag
  `controller-worker-executor-2026-10-22` (`4107836`), demo:false, real jobs.
- Contract revision/approval/409, session token + CSRF + Origin.
- Worker + attempt_writer verified with a **real Route B static attempt**:
  job `11bab8b1…`, route B `inconclusive`, `required_check_not_run`,
  `failing_obligation=interface`; obligations persisted and rendered.
- M4 honesty sign-off: six outcomes, three-way consistency fixtures
  (snapshot/file/DB/GUI), lossless `unsupported→not_run` mapping.
- Tests: 57 unit passed / 3 skipped; 7 browser e2e passed.

## Remaining for MVP completion

| Item | Owner | Status |
|---|---|---|
| Provide the real `gate3-bundle-2026-10-22.zip` on this machine (path `D:\BinRepair\...` is not accessible here) | M3/VMer | blocked |
| Map the real Route A evidence to `routea-attempt-input.json` | M2 | schema ready (`docs/interfaces/route-a-attempt-input.md`) |
| Write Route A attempt, run worker, reach `finished` | M2 | waiting on the bundle |
| P2 acceptance: verdict + obligations consistent across snapshot/file/DB/GUI | M2 | script ready; waiting on the run |
| Final screenshots / demo script / docs update | M2 | after P2 |

Expected real verdict with the current evidence: `inconclusive`
(V0 passed, V3 passed, V1 unknown, V2/V4/V5 not_run) — this satisfies the
accepted MVP definition, never `success_within_scope`.

## How to unblock (one action)

Copy the evidence bundle to:

```
C:\Users\linyz\Desktop\项目文件的系统\binaryrepair-mvp\var\gate3-bundle-2026-10-22.zip
```

or attach/send the file. M2 will verify SHA-256
`0ef655464459dd0597f8259b3784ee15389884c9a75b26afa1299af7f54bf8d5`, map it and
finish the MVP run.
