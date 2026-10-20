# BinaryRepair

**AI-driven automated binary vulnerability repair and correctness verification 鈥?MVP.**

BinaryRepair repairs one known vulnerability in a Linux x86-64 ELF **without original source code**, using two independent AI-assisted routes, and decides the result with one shared **deterministic acceptance engine**. A patch is never accepted because a model says it is fixed: it counts only when every required check passes on the final executable bytes.

- **Target defect:** one public stack-buffer-overflow case (CWE-121), Linux x86-64 ELF.
- **Route A 鈥?direct instruction repair:** candidate machine-instruction changes applied to a copy of the binary.
- **Route B 鈥?recovered C repair:** recover C-like code for a local region, repair it, compile it, reintegrate it into a copy.
- **Same input for both routes:** one original ELF, one reviewed security contract, one frozen test set.
- **Verification first:** structural, compatibility, behavioural, and bounded symbolic checks on the actual final patched executables.

> **Status: MVP in progress; `main` is currently the per-branch archive.** The runnable slices live under
> `agent/<member>/`; the root `app/` tree was removed in the 2026-10-20 cleanup. The GUI skeleton and the
> AI candidate layer run from their folders. The job controller is not on `main` yet; the identity suite
> skips. The public fixture, the two real repair routes, and the VM broker are not implemented yet. No
> binary has been repaired or verified. Do not present demo data as repair evidence.

---

## Current status (2026-10-20)

| Slice | Where on `main` | State | Tests |
|---|---|---|---|
| GUI 鈥?setup / comparison / evidence screens | `agent/member2-gui`, `agent/member2-backend-adapter` | demo data, banner-labelled | 6 + 5 (language policy, smoke) plus adapter contract tests |
| AI candidate schema + provider failure typing | `agent/member-5-deepseek-schema` | complete slice | 18 + 15 + 11 + 11 + 8 + 3 |
| Acceptance engine (outcomes, decision rules) | `agent/member-4-verification` | complete slice; integration depends on the candidate/job slices | 29 unit |
| Job controller, SQLite schema | `agent/member-1-interface-reply` (identity tests only) | not on `main` yet; the identity suite skips | 鈥?|
| Route A analysis kit | `agent/member-3-route-a` | docs and scripts | 鈥?|
| Route B feasibility kit | `agent/member-5-deepseek-schema` | provider, schema, kit | 鈥?|
| Public fixture + test manifest | not delivered | 鈥?| 鈥?|
| Disposable Ubuntu VM + broker | not built | 鈥?| 鈥?|

`main` itself has no root test runner. Each subfolder is a full branch tree; run its suite from that
folder. A skip is not a pass.

---

## Architecture

Two trust boundaries. The trusted host never executes an uploaded or repaired binary.

```
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?         鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹?Trusted host                       鈹?         鈹?Disposable Ubuntu x86-64 VM        鈹?
鈹?                                   鈹?         鈹?(untrusted work)                   鈹?
鈹? Browser GUI (FastAPI + Jinja2)    鈹傗梽鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈻衡攤  Ghidra / Capstone / LIEF          鈹?
鈹? SQLite + immutable artifacts      鈹? broker  鈹? LLVM/Clang / binutils / angr      鈹?
鈹? Review approval + acceptance      鈹? typed   鈹?                                   鈹?
鈹? DeepSeek provider adapter         鈹? tasks   鈹? no network, no credentials,       鈹?
鈹?                                   鈹?         鈹? snapshot reset between runs       鈹?
鈹? never runs uploaded binaries      鈹?         鈹? runs analysis, patching, checks   鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?         鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
```

- **Host:** serves the GUI, records approvals, schedules jobs, calls the provider, imports artifacts, computes acceptance.
- **Guest:** performs parsing, compilation, execution, and symbolic analysis for a fixed list of operations. Guest output is untrusted data.
- **Browser:** may be on the host; the execution environment may differ from the browser host.

---

## Quick start (Windows)

The GUI slice is a complete branch tree under `agent/member2-gui/`.

```powershell
cd agent\member2-gui
.\start.ps1          # PowerShell one-command start
```

```bat
cd agent\member2-gui
run.bat              :: double-click also works
```

Or manually:

```powershell
cd agent\member2-gui
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
```

Open <http://127.0.0.1:8123>. The service binds to loopback only.

If `.venv` does not exist:

```powershell
cd agent\member2-gui
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

For the mock/http data adapter (the backend-adapter slice):

```powershell
cd agent\member2-backend-adapter
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
```

### Quick start (Ubuntu) 鈥?planned

The target platform is Ubuntu 24.04 with Python 3.12. From `agent/member2-gui/`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8123
```

---

## What the demo shows

The GUI runs entirely on **labelled demo data**; a banner says so on every screen.

1. **Setup / review** 鈥?pick a file (demo hashes it), enter a defect description, view and edit the security contract.
2. **Progress / comparison** 鈥?both routes side by side; stages advance on demo data; Route A shows *rejected* (valid-input regression failure) and Route B shows *inconclusive* (symbolic budget exhausted) on purpose, to demonstrate that unfinished or failed work is never displayed as success.
3. **Evidence / export** 鈥?V0鈥揤5 obligations, scope, artifact hashes, diagnostic-candidate labels, and an export JSON that carries `demo: true` and "export is not production approval".

The real controller replaces the demo data; the banner disappears only when real evidence exists.

---

## Language policy

- **UI may use Chinese** (titles, buttons, status badges, explanations).
- **Uploaded data, API payloads, and exports are English ASCII** 鈥?defect description, reproduction input, environment, contract fields, obligations, outcome reasons, changed regions, artifact roles, export JSON.
- Server-side non-ASCII form content returns `422`; the browser also blocks it.
- Uploaded filenames are converted to ASCII-safe names.
- Guarded by `tests/test_language_policy.py` in the GUI slice.

---

## Repository layout

`main` currently contains only the `agent/` archive and this README:

```text
agent/
  README.md                       index of the per-branch archive
  member2-gui/                    three-screen GUI, demo data, start.ps1 / run.bat
  member2-backend-adapter/        mock/http data adapter, stub controller, contract tests
  member-3-route-a/route-a/       Route A analysis docs and scripts
  member-4-verification/          acceptance engine, verification design, handoffs
  member-5-deepseek-schema/       candidate schema, DeepSeek provider, SQLite, Route B kit
  member-1-interface-reply/       identity tests and 搂4.1 reply (job controller not on main yet)
```

Each folder is a full branch tree with its own layout, tests, and README where applicable. Work in the
folder that owns the slice (or on a feature branch); do not edit another slice's folder in place.

The target end-to-end structure 鈥?once the slices are integrated into one runnable tree 鈥?is:

```text
app/
  main.py, api/            FastAPI entry, typed routes, local-session checks
  templates/, static/      three screens, local CSS, status polling
  domain/                  contracts, candidate schema, phases/outcomes, acceptance rules
  services/                job controller, provider adapter, artifact/export
  db/, migrations/         parameterized SQLite and schema migrations
workers/
  analysis/                headless Ghidra and ELF metadata
  route_a/, route_b/       route adapters and the Route B round-trip gate
  verification/            structural, concrete, symbolic checks
  broker/                  narrow VM task protocol
tests/
  unit/ integration/ e2e/ evals/
fixtures/public/           public binary inputs and provenance (no evaluator source)
docs_BinaryRepair/         PRD, technical design, research, verification design, handoffs
var/                       runtime artifacts (gitignored)
requirements.txt
```

---

## Tests

Run each suite from its own folder:

```bash
cd agent/member2-gui
python -m pytest -q

cd ../member-4-verification
python -m pytest tests/unit -q

cd ../member-1-interface-reply
python -m pytest tests/integration/test_identity_state.py -q
```

- GUI slice: 6 + 5 tests (smoke and language policy), plus adapter contract tests.
- Acceptance slice: 29 unit tests; the AI-boundary and identity integration suites need the candidate
  and job slices in the same tree, so they skip in the isolated folder.
- Job-controller slice: the identity suite skips until `app.services.jobs` is added; a skip is not a pass.
- The AI-boundary suite never calls the real provider, needs no API key, and spends no money.
- No uploaded or repaired binary is executed on the host.

---

## Team and branches

| Member | Responsibility | Branch |
|---|---|---|
| 1 | Job controller, security contract, SQLite, API, proposal | `member-1-*` |
| 2 | Three-screen GUI, data adapter, language policy | `member2-*` |
| 3 | Public fixture, isolated Ubuntu VM, Route A analysis | `member-3-route-a` |
| 4 | Acceptance engine, verification design, test infrastructure | `member-4-verification` |
| 5 | AI candidate schema, DeepSeek provider, Route B feasibility | `member-5-deepseek-schema` |

Conventions: `main` is the integration branch; work happens on `member-<N>-<scope>` branches and merges
through pull requests; commit messages start with the branch tag (for example
`[member-4-verification] feat: ...`).

---

## Documentation

- [`agent/member-4-verification/docs_BinaryRepair/verification-design.md`](agent/member-4-verification/docs_BinaryRepair/verification-design.md) 鈥?acceptance semantics, decision precedence, interface contracts, coverage matrix.
- [`agent/member-4-verification/docs_BinaryRepair/handoffs/`](agent/member-4-verification/docs_BinaryRepair/handoffs/) 鈥?interface confirmations sent between slices.
- [`agent/member-4-verification/AGENTS.md`](agent/member-4-verification/AGENTS.md) 鈥?project instructions for coding agents (constraints, gotchas, safety rules).
- [`agent/member-4-verification/MEMORY.md`](agent/member-4-verification/MEMORY.md) 鈥?current state, decisions, known issues.
- [`agent/member2-gui/docs/member2-notes.md`](agent/member2-gui/docs/member2-notes.md) 鈥?GUI role notes.
- [`agent/member-5-deepseek-schema/docs/route-b/README.md`](agent/member-5-deepseek-schema/docs/route-b/README.md) 鈥?Route B / AI candidate provider guide.

The PRD, technical design, and research register are maintained locally and are not tracked in this
repository yet.

---

## Safety boundaries

These are not optional.

- **Never execute an uploaded or repaired binary, or compile model-generated C, on the host.** Parsing, compilation, execution, and symbolic analysis belong to the disposable guest under the broker. When the guest is unavailable, those checks are unavailable.
- **Acceptance is computed once.** The GUI renders outcomes; it never derives them.
- **Missing is not passing.** A check that did not run is `not_run`, never `passed`. Timeouts, solver `unknown`, incomplete exploration, and crashes never read as success.
- **Never weaken a test, oracle, or verification gate to get a green result.**
- **Source separation:** original source, debug info, reference fixes, and evaluator annotations never enter the repair pipeline or a model prompt.
- **Provider data boundary:** client binaries and confidential derived content stay local unless an explicit client authorization covers a specific transfer. The API key reaches only the trusted provider process.
- **Evidence honesty:** exports are review material, not production approval.

---

## Roadmap and known gaps

1. Add the job controller and SQLite schema on `main` (not there yet), then integrate it with the
   acceptance engine (`agent/member-4-verification`) and GUI (`agent/member2-gui`) in one runnable tree.
2. Public CWE-121 fixture with provenance and a frozen test manifest.
3. Disposable Ubuntu VM, toolchain smoke tests, and the broker.
4. Route A instruction-repair chain and Route B recovered-C round trip.
5. Shared acceptance over both final candidates, then export and independent replay.

No completed-MVP date is established; estimates follow the feasibility gates in the technical design.

---

---

# BinaryRepair MVP — GUI + data-source adapter (Member 2)

Graphical interface for Project 11: AI-driven automated binary vulnerability repair and
correctness verification. The three screens are unchanged; data comes through an adapter
layer that can read the synthetic demo store (`mock`), Member 1's controller API (`http`),
or Member 1's local job store (`local`).

Real execution (VM, Route A/B, angr verification) is provided by the other members; the
GUI only consumes the agreed English JSON contract.

> Default `mock` mode is clearly labeled demo fixture data, not a repair result, and must
> never be treated as evidence that a patch is verified. In `http` and `local` modes the
> banner follows the snapshot: it disappears only when the controller reports real data.
> Local mode keeps the banner off but shows a "execution not available" hint.

## Quick start (mock mode, default)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.ps1            # prints a one-time ?token=... URL
```

Open the URL printed by the launcher. A plain <http://127.0.0.1:8123> without the session
cookie returns `401`.

## Local session and CSRF

- The launcher generates a random session token and prints `http://127.0.0.1:8123/?token=...`.
- The first visit sets an `HttpOnly; SameSite=Strict` cookie and redirects to the clean URL;
  the token disappears from the address bar.
- Every non-static request requires the session; missing or wrong sessions receive `401`.
- POST forms include a `_csrf` token derived from the session; a missing or invalid token
  returns `403`, and cross-origin POSTs are rejected by Origin validation.

## Data-source modes (mock / http / local)

`mock` uses `app/demo.py` (synthetic data, no execution, banner shown).

`http` calls Member 1's controller. Until the real controller exists, a local stub can be
used for integration:

```powershell
# Terminal 1: local stub controller (synthetic data; snapshot keeps demo=true)
.\.venv\Scripts\python.exe -m uvicorn tools.stub_backend:app --host 127.0.0.1 --port 8000

# Terminal 2: GUI in http mode
$env:BINARYREPAIR_BACKEND = "http"
$env:BINARYREPAIR_API_BASE = "http://127.0.0.1:8000"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
```

`local` calls Member 1's job controller directly in-process (`app/services/jobs.py`): the
job identity, original bytes, and SHA-256 are persisted in SQLite under
`BINARYREPAIR_DATA_DIR` (default `var/`). Repair execution is not implemented yet, so the
comparison screen shows phases as "not started" and obligations as `not_run`; the start
action is hidden instead of pretending a run exists.

```powershell
$env:BINARYREPAIR_BACKEND = "local"
$env:BINARYREPAIR_DATA_DIR = "var"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
```

Configuration:

- `BINARYREPAIR_BACKEND` — `mock` (default), `http`, or `local`
- `BINARYREPAIR_API_BASE` — controller base URL for `http` (default `http://127.0.0.1:8000`)
- `BINARYREPAIR_API_TIMEOUT` — request timeout in seconds for `http` (default 5)
- `BINARYREPAIR_DATA_DIR` — SQLite and artifact directory for `local` (default `var`)

### Controller contract consumed by the GUI

```
POST /api/jobs                        multipart -> {"id": str, ...}
GET  /api/jobs/{id}                   snapshot JSON (phase, routes, contract, ...)
POST /api/jobs/{id}/start             start (requires an approved contract)
POST /api/jobs/{id}/cancel            cancel
POST /api/jobs/{id}/contract          new contract revision (409 on stale expected_revision)
POST /api/jobs/{id}/approve           approve the current contract hash (409 on stale hash)
GET  /api/jobs/{id}/obligations       {"A": [...], "B": [...]}
GET  /api/jobs/{id}/artifacts         {"A": [...], "B": [...]}
```

Contract approval is bound to the current revision hash: editing any contract field creates
a new revision, clears the approval, and a stale approval or stale revision returns `409`
with an explicit conflict page. A run cannot start until the current contract is approved.

Details are documented at the top of `app/backend.py`; the surface follows Technical
Design section 7. HTTP mode checks responses: CJK characters, missing
`id`/`phase`/`routes`, and network failures become explicit English errors instead of 500
tracebacks.

## Structure

```
app/
├─ main.py            FastAPI entry, three-screen routes, status API, export
├─ backend.py         mock/http/local data-source adapters, error mapping, language checks
├─ demo.py            Synthetic demo data (phases, V0–V5 obligations, artifacts)
├─ i18n.py            Chinese display labels (UI only; never enters API or exports)
├─ db/                Member 1 job store (SQLite connection + schema)
├─ services/jobs.py   Member 1 minimal controller (create_job / get_job)
├─ templates/         base + three screens (Jinja2)
└─ static/            css/app.css, js/poll.js
tools/stub_backend.py Local stub controller (synthetic data) for http-mode integration
tests/
├─ test_smoke.py            Three screens, host check, export
├─ test_language_policy.py  API/exports have no CJK; UI stays Chinese
├─ test_backend_contract.py HTTP mapping, error mapping, CJK rejection, stub shape
└─ test_local_backend.py    Local controller mode: real job persistence, honest not_run states
fixtures/public/      Public samples only
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Covers the three screens, host validation, export attachment and `demo: true`, cancel
state, API/export language policy, HTTP adapter request paths and multipart forwarding,
error mapping (404, network failure, non-English payload), the stub controller's JSON
shape, and local mode (SQLite job persistence, honest `not_run` obligations, hidden start
action).

## Security visualization

The comparison screen renders an interactive code view for each route:

- disassembly (Route A) or recovered C (Route B) with the vulnerable instruction/line highlighted;
- a repaired view with added/patched lines and a diff tab;
- an AI-candidate tab with template id, model, rationale, assumptions and uncertainties.

Click a highlighted line to read the vulnerability or change detail in the panel below.
The visualization data is currently synthetic and labelled as such; the view is ready to
consume worker output once execution is connected.

### Browser end-to-end (Edge + DevTools protocol)

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/e2e
```

No extra dependency or browser download is required: the suite launches headless
Microsoft Edge and drives it over the DevTools protocol. It skips with a clear message
when Edge is not installed. Covered journeys: setup -> start -> comparison -> evidence ->
export, refresh during a run, cancellation with retained evidence, and local-controller
honesty (no start action, real job persisted, `execution=not_started`).

## Language policy

The GUI displays Chinese; uploaded, API, and exported data must be English ASCII.
Non-ASCII form content is rejected with `422` and uploaded filenames are sanitized to ASCII.

## Known limitations

- Stub and demo data are synthetic; no binary is executed.
- Local mode has a real job store but no repair execution: start/cancel return `409`.
- Contract revision and `409 stale approval` handling are not implemented yet.
- The GUI assembles exports locally; the controller export endpoint is future work.
- HTTP mode calls the controller synchronously; fine for a local single-operator demo.

## Sources

- PRD v1.0 (2026-10-15): F1, F4, F5, UI/UX direction, success metrics
- Technical Design v1.0 (2026-10-15): section 6, 7, 9, 11, 12, 13, 14
- `docs/member2-notes.md`: role notes with sources
