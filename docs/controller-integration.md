# Controller integration (P0 checklist for Member 2)

The GUI never invents job state. It reads a controller through one adapter
interface and renders whatever the controller reports.

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

## P0 acceptance checklist

1. `POST /jobs` with a real sample creates a job in the controller store
   (SQLite row + `var/jobs/<id>/`), not in GUI memory.
2. The comparison page polls `GET /api/jobs/{id}` every 2 seconds and updates
   phase/stage/outcome from the controller response.
3. The snapshot reports `demo: false` and the yellow demo banner is gone.
4. `start` returns `409` until the current contract revision is approved; stale
   revision/hash also returns `409` (never a silent overwrite).
5. `cancel` is visible as `已取消`, not as success.

Current status: `local` mode already passes 1, 2, 4, 5 against Member 1's real
store. `http` mode is adapter-complete and covered by contract tests, but Member 1
has not exposed the HTTP API yet, so the demo server currently points at
`tools/stub_backend.py` (`demo: true`). Wire `BINARYREPAIR_API_BASE` to the real
service to complete P0.

## P1 honesty rules enforced in tests

- Overall result is derived from both routes (`app/status.py` + `poll.js`):
  success only when **both** outcomes are `success_within_scope`.
- `finished` is a phase, not a verdict; unfinished/running shows `—`.
- `cancelled` shows `已取消`; `error` shows `失败（执行错误）`.
- `not_run` never counts as passed; evidence tables render `not_run` verbatim.
- Contract approval is bound to `revision + sha256`; edits clear approval.
