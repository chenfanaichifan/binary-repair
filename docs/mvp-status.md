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

## MVP run completed (2026-10-22)

Real Route A attempt + Route B static attempt were integrated into one job:

- job `f81300cbfad64c72b15988cede6fba2c`, run
  `d99bc20f8d1d423b8c7e61abb12e4917`
- Route A: real gate3-harness-v2 attempt JSON (V0/V1/V3 passed, V2/V4/V5
  not_run); the two evidence files were registered as controller artifacts so
  passed obligations carry an `evidence_artifact_id`.
- Route B: static executor bundle (V0/V1 passed, V2/V3/V4/V5 not_run).
- Worker: both attempts terminal → `evaluate_run` → job `finished`.
- Run verdict: **`inconclusive`**, reason `required_check_not_run`, failing
  obligation `interface`; both routes `inconclusive`. This is the accepted MVP
  outcome (honest, not a success claim).
- `tools/p2_acceptance.py --job-id …` → **P2 ACCEPTANCE PASSED**
  (`phase=finished`, verdict/obligations consistent).
- GUI renders the run verdict, per-route verdicts and V0–V5 obligations; no
  success label.
- Screenshot: `docs/screenshots/09-mvp-finished.png`.

Caveats: M4 verifier and M5 formal-bundle replay are still pending; this is
**not** a signed Gate 3/Gate 4 decision. Route B remains static.

## Remaining after MVP completion

| Item | Owner | Status |
|---|---|---|
| Independent M4/M5 verification of the real Gate 3 evidence | M4/M5 | pending (out of M2 scope) |
| Merge `member2-backend-adapter` into `main` | Lead | pending (branch-only rule) |
| Optional final proposal/screenshot pass | M2 | available |


## M2 verification pass (2026-10-29, ahead of 10-30/10-31 schedule)

### Source-language cleanup (10-30 12:00 item)

- Scanned the M2 slice (`app/`, `tools/`, `tests/`): 10 Python files actually
  contained Chinese comments/docstrings; all were rewritten in English.
- Result: **0 CJK comments/docstrings** remain; UI Chinese string literals are
  unchanged. `python -m compileall app tools tests` passes.
- Behaviour guard: 26 selected tests passed (`test_language_policy`,
  `test_status_honesty`, `test_verdict_view`, `test_backend_contract`,
  `test_security`); full unit suite 57 passed / 3 skipped.

### Browser e2e on Edge (10-30 18:00 item)

- This machine actually has Edge
  (`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`), so the runs
  were real, not recorded as environment `not_run`.
- First run: 6 passed / 1 failed due to a `codeview.js` load/click race; fixed
  with a `codeviewReady` marker and an explicit wait.
- After the fix: **7/7 passed twice** (35.2 s and 32.2 s).

### Real http-mode walkthrough (10-31 item)

- Controller tag `controller-worker-executor-2026-10-22` on :8000, GUI http mode
  on :8123, real job store (`demo:false`).
- `tools/p0_acceptance.py` → **17/17 PASS**.
- `tools/p2_acceptance.py --timeout 5` → **exit 2, BLOCKED**
  (`phase='queued'`, no result bundle/executor). This is the expected honest
  result without an external executor; it is not recorded as a pass.
- Screenshots refreshed: `00-landing.png`, `01-setup.png`,
  `02-comparison.png`, `03-evidence.png`.

### `tools/controller_service.py` keep/delete recommendation

**Keep, but mark as dev/test-only; do not use it as the production controller.**

Reasons:

- It is still used by `tests/test_controller_service.py` and the e2e
  `controller_server`/`http_server` fixtures; deleting it breaks 7 e2e journeys.
- It is an honest fallback bridge (`demo:false`, real SQLite store, start
  returns 409 because execution is not implemented), useful for offline GUI
  development when the real controller is unavailable.
- Production uses Member 1's `app.controller_api:app` via
  `start-controller.ps1`; the bridge must not be presented as that service.

Delete only after the e2e fixtures are repointed at the real controller and the
offline fallback is no longer needed.

