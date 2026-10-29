# BinaryRepair

**AI-assisted binary vulnerability repair with deterministic acceptance.**

BinaryRepair is a course project for repairing one known vulnerability in a Linux
x86-64 ELF without rebuilding from source. Two independent routes produce candidate
bytes; one shared acceptance engine decides whether the final executable is
`success_within_scope`. A model's claim is never evidence: only checks on the final
bytes count.

> **Status [2026-10-29, branch `integration/consolidation-2026-10-29`]: integrated demo state; no repair verified.**
> This tree is the consolidated candidate for `main`: it carries the controller, the
> member-2 controller-backed GUI (`app/backend.py` adapter in `mock` / `http` /
> `local` modes), the acceptance engine, the AI boundary, SQLite v1 + 002/003,
> Route A/B tooling, the public CWE-121 fixture, the member-4 acceptance unit suite,
> and the governance documents (`AGENTS.md`, `MEMORY.md`, `agent_docs/`,
> `docs_BinaryRepair/`).
>
> No binary has been repaired and verified end to end. Guest execution, real
> Route A/B candidate builds, V1-V5 real checks, V4 symbolic analysis and V5 replay
> are all **not_run**. Do not present demo or synthetic data as repair evidence.
>
> Gate 3 (Route A) is recorded as **approved on 2026-10-22** in
> `docs_BinaryRepair/handoffs/33-gate3-approved.md`. That record was **not
> re-measured** in this consolidation, and it does not cover the fixture freeze,
> Gate 4/5/6 or MVP acceptance. Gate 4 remains **NOT RUN**.

## What is in this tree

| Slice | Location | State |
|---|---|---|
| FastAPI + Jinja GUI (setup / comparison / evidence) | `app/main.py`, `app/backend.py`, `app/templates/`, `app/static/` | three screens; mock/http/local data adapter; demo mode labelled |
| Job controller: create / get / approve / start / cancel / retry | `app/services/jobs.py` | identity + state tests pass |
| HTTP controller API + canonical routes | `app/controller_api.py` | `/api/jobs/{id}/runs`, `/api/attempts/{id}/evidence`; `/start` aliases |
| Acceptance engine and V0–V5 decision rules | `app/domain/acceptance.py`, `outcomes.py` | unit tests |
| Security contract v2 + canonical manifest hash | `app/domain/contracts.py`, `manifests.py` | schema_version=2, shared suite |
| AI candidate boundary + DeepSeek provider | `app/domain/candidates.py`, `app/services/provider.py`, `binaryrepair_ai/`, `schemas/` | typed failures, fake transport |
| SQLite v1 baseline + 002/003 | `app/db/schema.sql`, `app/db/migrations/` | jobs+artifacts baseline; AI tables; verdict columns |
| Route B kit | `routeb/`, `docs/route-b/` | feasibility scripts and notes |
| Public candidate fixture | `fixtures/public/CWE121_src_char_declare_cpy_51b/` | NOT FROZEN; gates 3–5 in progress |
| Member-4 acceptance unit suite | `tests/unit/test_acceptance.py` | 29 tests, **29 passed** on this Windows host (measured 2026-10-29) |
| Controller evidence endpoints | `app/controller_api.py` | serve **persisted** obligation rows with `evidence: persisted` / `not_persisted`; no static `V0 passed` placeholder |
| Governance and instruction docs | `AGENTS.md`, `MEMORY.md`, `REVIEW-CHECKLIST.md`, `agent_docs/` | consolidation copies; `agent/` kept as the frozen archive |
| Product/design documents and handoffs | `docs_BinaryRepair/` | 41 files carried over from the member-4 branch |
| Analysis and runtime evidence | `docs/analysis/` | root-cause analysis, runtime verification, controller fixes, M2 merge report, independent verification |

### Not yet done

- Gate 3 (Route A): recorded as **approved on 2026-10-22**
  (`docs_BinaryRepair/handoffs/33-gate3-approved.md`, summarised in `MEMORY.md`).
  The record was **not re-measured** in this consolidation and its scope is Gate 3
  only; it does not freeze the fixture or accept the MVP.
- Gate 4 (Route B formal): **NOT RUN (guest access + gate4-harness)**. The
  supplementary GitHub Actions run (6/6 unchanged round trip) is recorded in
  `docs/route-b/09-gate4-evidence.md`; it is not the formal run.
- Contract revision: `24bfe568…4e37` is the recorded reviewed scope. This tree does
  not re-verify the Gate 3 signature chain.
- Real repair execution. The controller queues runs and stores evidence; it does
  not execute uploaded binaries on the host.
- GUI-to-controller `http` mode exists after the member-2 merge and is exercised by
  `tools/p0_acceptance.py` (17/17 on the merge candidate). `tools/p2_acceptance.py`
  exits `2 BLOCKED` until a real result bundle reaches the worker; that is the
  honest current state.
- VM broker, symbolic (V4), and final V5 reproducibility evidence.

## Repository layout

```text
app/                 GUI + controller + domain + SQLite layer
  backend.py         GUI data-source adapter (mock / http / local)
  status.py          derived verdict labels for rendering (never decides outcomes)
  visuals.py         synthetic code-view payload for the comparison screen
  domain/            acceptance engine, contracts, manifests, candidate boundary
  services/          jobs, orchestration, DeepSeek provider, worker
  db/                connection, migrate, schema.sql, migrations/002-003
  templates/, static/ three screens, local CSS, polling and code-view JS
binaryrepair_ai/     provider implementation (internal; import app.* instead)
schemas/             candidate/context JSON Schema + examples
routeb/              Route B fixture, Ghidra export, Patcherex2 probes
fixtures/public/     candidate ELF + frozen test manifests + SHA256SUMS
tests/               unit + integration + fixture contract + browser e2e tests
tools/               controller launcher helpers and P0/P2 acceptance scripts
docs/route-b/        Route B design, DB v2, gate 6 notes
docs/screenshots/    GUI screenshots (mock mode; labelled synthetic data)
docs/analysis/       root-cause analysis, runtime verification, controller fixes, M2 merge report, independent verification
docs_BinaryRepair/   PRD, technical design, research, verification design, dated handoffs
agent_docs/          instruction documents referenced by AGENTS.md
agent/               frozen per-document archive (read-only; not a development area)
```

`agent/` is the frozen per-document archive kept from the integration cleanup.
Historical branch snapshots remain in git history; the pre-cleanup tree is tagged
`archive/2026-10-22/pre-cleanup`.

## Quick start (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# GUI on http://127.0.0.1:8123 (prints a one-time ?token=... URL)
.\start.ps1
```

Controller service (separate process, loopback only):

```powershell
.\start-controller.ps1      # canonical app.controller_api:app on 127.0.0.1:8000
```

GUI in http-adapter mode (same controller, real job store):

```powershell
$env:BINARYREPAIR_BACKEND = "http"
$env:BINARYREPAIR_API_BASE = "http://127.0.0.1:8000"
.\start.ps1
```

### GUI slice and data-source adapter (Member 2, merged 2026-10-29)

The three screens (`app/main.py` + Jinja templates) render whatever one adapter
(`app/backend.py`) reports; the GUI never decides an outcome. `app/status.py`
derives the displayed overall label from the controller's route outcomes: success
only when both routes report `success_within_scope`, and `not_run` is rendered
verbatim.

| `BINARYREPAIR_BACKEND` | Adapter | Data shown |
|---|---|---|
| `mock` (default) | `MockBackend` | synthetic demo data, `demo: true`, yellow banner shown |
| `local` | `LocalBackend` | real job store (`app/services/jobs.py`, SQLite); execution not implemented, start hidden |
| `http` | `HttpBackend` | a controller over HTTP (canonical `app.controller_api.py`); `demo` comes from its snapshot |

The launcher keeps a stable local session token in `var/session.token`, prints a
one-time `?token=...` URL, and the GUI converts it to an
`HttpOnly; SameSite=Strict` cookie. Every non-static request needs the session;
POST forms also carry a CSRF token derived from it.

Acceptance helpers:

- `python tools/p0_acceptance.py` — live GUI + controller journey: session
  bootstrap, controller health, real job creation, `demo: false`, no demo banner,
  contract edit, approval, start, cancel, and "cancelled is not success". Needs
  both servers running.
- `python tools/p2_acceptance.py` — verdict pipeline gate; drives (or verifies
  with `--job-id`) a `finished` run and checks the run verdict, both route
  outcomes, and the V0-V5 obligation set. It exits `2 BLOCKED` while no result
  bundle reaches the worker, which is the honest current state.
- `python -m pytest -q tests/e2e` — headless Microsoft Edge + DevTools protocol
  journeys; skips with a clear message when Edge is not installed.

Screenshots of the mock-mode journey are in `docs/screenshots/`.

### Ubuntu (target runtime)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8123
```

## Tests

```bash
pytest -q
```

Expected on a clean checkout: all non-runtime tests pass; V3 runtime tests skip
unless `BINARYREPAIR_CANDIDATE_ELF` (or the original ELF) is available. A skip is
not a pass. The fixture manifests are hashed as raw bytes; `.gitattributes` pins
them to LF/exact bytes so checkout line endings cannot change the reviewed hash.

### Measured test state on this Windows host (2026-10-29)

These are the only verified test numbers; they come from `docs/analysis/RUNTIME-VERIFICATION.md`
and `docs/analysis/CONTROLLER-FIXES.md`. The environment is Windows 11 with Python
3.14.6; `capstone` and `pyelftools` are not installed.

```powershell
python -m pytest tests/unit/test_acceptance.py   # -> 29 passed
python -m pytest tests/                          # -> stops at collection: 5 modules uncollectable
                                                 #    (capstone x3, pyelftools x2), 0 tests run
```

With `--continue-on-collection-errors` and the measurement helper
(`scripts/pytest_rt_report.py`) the merged tree yields **236 collected, 227
passed, 2 skipped, 7 environment errors, 5 uncollectable modules**. The 7 errors
are the browser e2e journeys (`tests/e2e/`): the sandbox cannot start headless
Edge/DevTools, so those journeys are `not_run`. The two skips are guest-dependent
V3 tests. The five uncollectable modules (`test_routea_cave`,
`test_routea_manifest`, `test_routea_worker`, `test_routeb_attempt_writer`,
`test_routeb_executor`; 13 test functions) need `capstone` / `pyelftools` and are
`not_run`, never passed.

Without the helper, this Windows sandbox makes pytest's own temporary directory
unreadable after the first `tmp_path` fixture; dozens of tests then error at
fixture setup and pytest crashes in its session-finish hook before printing a
complete summary. Those are **environment errors, not test failures** (no
assertion is reached), and they are reported as such. Use the helper or a POSIX
host for a clean summary.

GUI and adapter suites live next to the controller suites:
`tests/test_smoke.py` (three screens + local session gate),
`tests/test_language_policy.py` (English API/exports, Chinese UI),
`tests/test_backend_contract.py` (HTTP adapter mapping + stub shape),
`tests/test_local_backend.py` (real job store, honest `not_run`),
`tests/test_status_honesty.py`, `tests/test_verdict_view.py`,
`tests/test_contract_revision.py`, `tests/test_security.py`,
`tests/test_visuals.py`, `tests/test_dryrun_view.py`,
`tests/test_routea_adapter.py`, and the browser journeys under `tests/e2e/`
(Edge + DevTools protocol; skipped when Edge is absent).
Route A/B ELF suites need `capstone`/`pyelftools`; where those packages are not
installed the affected tests are uncollectable, which is `not_run`, not `passed`.

### Historical issues now closed or recorded

- **DB v2 `contracts.body_json`**: v2 stores canonical SecurityContract text in
  `body_json`; the old 001 schema is retired. Free-text contract fields need no
  schema change; a new revision changes `contracts.sha256` /
  `reviewed_scope_sha256`.
- **V3 manifest line endings**: the fixture JSON is pinned as exact bytes; a fresh
  checkout keeps `valid.json` `17b2ee39…`, `invalid.json` `d493f370…`, manifest-set
  `a564f039…`. Older Windows checkouts that produced `7f984a…` are recorded as a
  line-ending artifact, not an oracle change.

## Documentation

- [Route B overview](docs/route-b/README.md)
- [Root integration map](docs/route-b/04-root-integration.md)
- [DB v2 decisions](docs/route-b/05-db-v2-spec.md)
- [Gate 6 evidence notes](docs/route-b/06-gate6-evidence.md)
- [Candidate handoff / gate status](docs/route-b/03-feasibility-checklist.md)
- [Controller integration and P0 checklist](docs/controller-integration.md)
- [GUI integration plan](docs/integration-plan.md)
- [GUI screenshots (mock mode)](docs/screenshots/)

## Ground rules

- The host never executes uploaded or repaired binaries. Execution belongs to a
  disposable VM with no network, no credentials, and a snapshot reset.
- A patch is accepted only by `app/domain/acceptance.py`; the GUI and controller
  never invent a second success rule.
- `not_run` / `unknown` / `timed_out` are not `passed`. `skip` is not `pass`.
- Conclusions say "this PoC no longer triggers", never "the program is unexploitable".
- Do not modify `original.elf`, its manifest, provenance, oracle, or harness to make
  a gate pass.
- Keep changes small and tested; do not commit `var/`, `.env`, or model keys.

## Branch policy

`main` is the only integration target. Feature work goes through a short-lived
branch and a PR. Stale or merged branches should be deleted after their tip is
tagged under `archive/<date>/<name>`; `main` should stay free of full branch-tree
copies.
