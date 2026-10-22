# Controller integration (P0 checklist for Member 2)

The GUI never invents job state. It reads a controller through one adapter
interface and renders whatever the controller reports.

## Ready-to-run helpers

- `.\start-controller.ps1` — creates/updates a fixed worktree of `origin/main`
  at `..\binaryrepair-controller` and serves `app.controller_api:app` on
  `127.0.0.1:8000`, with `BINARYREPAIR_DATA_DIR=var\controller`.
- `tools\p0_acceptance.py` — one command checks session bootstrap, controller
  health, real job creation, `demo:false`, no demo banner, contract edit,
  approval, start → `queued`, cancel → `已取消`, and that cancel is not labelled
  success. Exit code is non-zero on failure.

```powershell
.\start-controller.ps1          # terminal 1
.\start.ps1                     # terminal 2 (http mode points at :8000)
.\.venv\Scripts\python.exe tools\p0_acceptance.py
```

## Data-source modes

| `BINARYREPAIR_BACKEND` | Adapter | What it proves |
|---|---|---|
| `mock` (default) | `MockBackend` | UI/contract behaviour only; `demo: true`, execution never real |
| `local` | `LocalBackend` | Real Member 1 controller store (`app/services/jobs.py`, SQLite); `demo: false`, execution not implemented yet |
| `http` | `HttpBackend` | GUI talks to a controller over HTTP; `demo` comes from the controller snapshot |

Switching to the real HTTP controller:

```powershell
$env:BINARYREPAIR_BACKEND = "http"
$env:BINARYREPAIR_API_BASE = "http://127.0.0.1:8000"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
```

`GET /healthz` reports `backend` and `demo` (`null` for `http` until a job is
fetched, because only the controller knows whether its data is synthetic).

## Endpoints the GUI consumes

```
POST /api/jobs                        multipart: binary, defect, valid_tests, environment, valid_domain,
                                      forbidden, invalid_outcome, assumptions
GET  /api/jobs/{id}                   snapshot: id, phase, routes{A,B}, contract, original_sha256, demo
POST /api/jobs/{id}/start             requires an approved current contract
POST /api/jobs/{id}/cancel            cancel
POST /api/jobs/{id}/contract          form: expected_revision, contract fields; 409 on stale revision
POST /api/jobs/{id}/approve           form: expected_sha256, reviewer_label; 409 on stale hash
GET  /api/jobs/{id}/obligations       {"A": [...], "B": [...]}
GET  /api/jobs/{id}/artifacts         {"A": [...], "B": [...]}
GET  /api/jobs/{id}/visuals           code-view payload (synthetic demo data today)
```

Snapshot requirements:

- `contract.revision`, `contract.sha256`, `contract.approved` (plus the four
  contract fields) — used for 409 conflict behaviour and the approval badge.
- `routes.A` and `routes.B`, each with `phase`, `outcome` (`null` while running),
  `stages[]`, `tests{passed,total}`, `verification`, `compatibility`,
  `changed_regions[]`, `elapsed_s`, `manual_interventions`, `ai_usage`.
- `demo: false` once the controller runs real jobs; the GUI banner disappears
  automatically and `/api/jobs/{id}` stops being labelled as a fixture.
- All data strings are English ASCII; the GUI scans snapshot/obligations/artifacts
  and rejects non-ASCII payloads with `502` instead of rendering them.

## Final controller (Member 1, worker commit)

Member 1's controller + run worker live at `origin/main` commit `ad1a1f8`
(`feat(worker): consume queued runs and persist verdicts and obligations`).
The tag `controller-api-2026-10-22` (`1826505`) predates the worker, so the
launcher currently pins `ad1a1f8`; ask Member 1 for an updated tag that includes
the worker.

```powershell
.\start-controller.ps1   # worktree at ad1a1f8, serves app.controller_api on :8000
```

Run the worker once (from the controller worktree):

```powershell
python -m app.services.worker --data-dir <project>\var\controller --once
```

Worker behaviour (verified live):

- consumes queued runs and moves phases to `screening` / `analyzing`;
- does **not** execute binaries itself: it needs one result bundle per attempt at
  `<data-dir>/jobs/<job>/runs/<run>/attempts/<attempt>.json` (schema in the
  worker docstring) or an external executor command in
  `BINARYREPAIR_ATTEMPT_CMD`;
- without a bundle it prints `has no result bundle yet` and waits — the run stays
  at `screening` (no fake verdict);
- with bundles it persists V0–V5 obligations and calls
  `orchestration.evaluate_attempt` / `evaluate_run`.

Remaining gaps confirmed live:

- No result-bundle producer / executor yet (Route A worker and `jobwrap routea`
  are still to be implemented by M3 + VMer); this is what blocks `finished`.
- `app/controller_api.py` did not change in `ad1a1f8`: its snapshot routes are
  still placeholders and `/obligations` still returns static placeholders, so
  even after a bundle is consumed the API needs to read attempts/obligations
  (controller TODO, Member 1).
- Same idempotency key with a different contract should return `409`; the
  canonical check is still to be added.

`tools/p2_acceptance.py --worker-command "<python> -m app.services.worker --data-dir <abs> --once"`
runs the worker once after start; today it exits `2 BLOCKED` with
`phase='screening'` because no result bundle exists.
- Verdict write-back is library-only today (`orchestration.evaluate_attempt` /
  `evaluate_run` write `outcome/reason/failing_obligation/detail` and
  `verdict.json` / `run-verdict.json`), but the controller API is not wired and
  obligations have no write path, so a real run cannot produce a verdict yet.
  `tools/p2_acceptance.py` is ready for when this lands (it exits `2 BLOCKED`
  until the pipeline reaches `finished` with real obligations).

Verified P0 run: GUI `http` mode → create job → contract edit → approve →
start `202` → snapshot `demo:false`, `phase=queued`, routes `queued`; GUI shows
`排队中` and never claims success. `start` really goes through persisted
approval; the missing part is execution, not the GUI/controller contract.

## Bridge service (fallback)

If the `main` checkout is unavailable, this branch also ships a bridge backed by
the real Member 1 job store:

```powershell
$env:BINARYREPAIR_CONTROLLER_DATA = "var/controller"
.\.venv\Scripts\python.exe -m uvicorn tools.controller_service:app --host 127.0.0.1 --port 8000
```

It persists jobs with `app/services/jobs.py` and reports `demo: false`, but its
`start` returns `409` because execution is not implemented there. Use the final
controller above for P0 acceptance.

Switching the GUI (no page changes required):

```powershell
$env:BINARYREPAIR_BACKEND = "http"
$env:BINARYREPAIR_API_BASE = "http://127.0.0.1:8000"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
```

## P0 acceptance checklist

1. `POST /jobs` with a real sample creates a job in the controller store
   (SQLite row + `var/jobs/<id>/`), not in GUI memory.
2. The comparison page polls `GET /api/jobs/{id}` every 2 seconds and updates
   phase/stage/outcome from the controller response.
3. The snapshot reports `demo: false` and the yellow demo banner is gone.
4. `start` returns `409` until the current contract revision is approved; stale
   revision/hash also returns `409` (never a silent overwrite).
5. `cancel` is visible as `已取消`, not as success.

Current status: P0 passes against Member 1's final controller (job creation,
persistence, polling, approval, start → `queued`, `demo: false`, no demo
banner). Execution itself is still pending in the worker pipeline: the snapshot
keeps placeholder routes/stages at `queued`, obligations report `not_run`, and
the visualizations/artifacts stay empty until workers write them. This is the
honest "queued, not verified" state.

## P1 honesty rules enforced in tests

- Overall result is derived from both routes (`app/status.py` + `poll.js`):
  success only when **both** outcomes are `success_within_scope`.
- `finished` is a phase, not a verdict; unfinished/running shows `—`.
- `cancelled` shows `已取消`; `error` shows `失败（执行错误）`.
- `not_run` never counts as passed; evidence tables render `not_run` verbatim.
- Contract approval is bound to `revision + sha256`; edits clear approval.
