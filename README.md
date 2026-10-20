# BinaryRepair

**AI-driven automated binary vulnerability repair and correctness verification — MVP.**

BinaryRepair repairs one known vulnerability in a Linux x86-64 ELF **without original source code**, using two independent AI-assisted routes, and decides the result with one shared **deterministic acceptance engine**. A patch is never accepted because a model says it is fixed: it counts only when every required check passes on the final executable bytes.

- **Target defect:** one public stack-buffer-overflow case (CWE-121), Linux x86-64 ELF.
- **Route A — direct instruction repair:** candidate machine-instruction changes applied to a copy of the binary.
- **Route B — recovered C repair:** recover C-like code for a local region, repair it, compile it, reintegrate it into a copy.
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
| GUI — setup / comparison / evidence screens | `agent/member2-gui`, `agent/member2-backend-adapter` | demo data, banner-labelled | 6 + 5 (language policy, smoke) plus adapter contract tests |
| AI candidate schema + provider failure typing | `agent/member-5-deepseek-schema` | complete slice | 18 + 15 + 11 + 11 + 8 + 3 |
| Acceptance engine (outcomes, decision rules) | `agent/member-4-verification` | complete slice; integration depends on the candidate/job slices | 29 unit |
| Job controller, SQLite schema | `agent/member-1-interface-reply` (identity tests only) | not on `main` yet; the identity suite skips | — |
| Route A analysis kit | `agent/member-3-route-a` | docs and scripts | — |
| Route B feasibility kit | `agent/member-5-deepseek-schema` | provider, schema, kit | — |
| Public fixture + test manifest | not delivered | — | — |
| Disposable Ubuntu VM + broker | not built | — | — |

`main` itself has no root test runner. Each subfolder is a full branch tree; run its suite from that
folder. A skip is not a pass.

---

## Architecture

Two trust boundaries. The trusted host never executes an uploaded or repaired binary.

```
┌────────────────────────────────────┐          ┌────────────────────────────────────┐
│ Trusted host                       │          │ Disposable Ubuntu x86-64 VM        │
│                                    │          │ (untrusted work)                   │
│  Browser GUI (FastAPI + Jinja2)    │◄────────►│  Ghidra / Capstone / LIEF          │
│  SQLite + immutable artifacts      │  broker  │  LLVM/Clang / binutils / angr      │
│  Review approval + acceptance      │  typed   │                                    │
│  DeepSeek provider adapter         │  tasks   │  no network, no credentials,       │
│                                    │          │  snapshot reset between runs       │
│  never runs uploaded binaries      │          │  runs analysis, patching, checks   │
└────────────────────────────────────┘          └────────────────────────────────────┘
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

### Quick start (Ubuntu) — planned

The target platform is Ubuntu 24.04 with Python 3.12. From `agent/member2-gui/`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8123
```

---

## What the demo shows

The GUI runs entirely on **labelled demo data**; a banner says so on every screen.

1. **Setup / review** — pick a file (demo hashes it), enter a defect description, view and edit the security contract.
2. **Progress / comparison** — both routes side by side; stages advance on demo data; Route A shows *rejected* (valid-input regression failure) and Route B shows *inconclusive* (symbolic budget exhausted) on purpose, to demonstrate that unfinished or failed work is never displayed as success.
3. **Evidence / export** — V0–V5 obligations, scope, artifact hashes, diagnostic-candidate labels, and an export JSON that carries `demo: true` and "export is not production approval".

The real controller replaces the demo data; the banner disappears only when real evidence exists.

---

## Language policy

- **UI may use Chinese** (titles, buttons, status badges, explanations).
- **Uploaded data, API payloads, and exports are English ASCII** — defect description, reproduction input, environment, contract fields, obligations, outcome reasons, changed regions, artifact roles, export JSON.
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
  member-1-interface-reply/       identity tests and §4.1 reply (job controller not on main yet)
```

Each folder is a full branch tree with its own layout, tests, and README where applicable. Work in the
folder that owns the slice (or on a feature branch); do not edit another slice's folder in place.

The target end-to-end structure — once the slices are integrated into one runnable tree — is:

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

- [`agent/member-4-verification/docs_BinaryRepair/verification-design.md`](agent/member-4-verification/docs_BinaryRepair/verification-design.md) — acceptance semantics, decision precedence, interface contracts, coverage matrix.
- [`agent/member-4-verification/docs_BinaryRepair/handoffs/`](agent/member-4-verification/docs_BinaryRepair/handoffs/) — interface confirmations sent between slices.
- [`agent/member-4-verification/AGENTS.md`](agent/member-4-verification/AGENTS.md) — project instructions for coding agents (constraints, gotchas, safety rules).
- [`agent/member-4-verification/MEMORY.md`](agent/member-4-verification/MEMORY.md) — current state, decisions, known issues.
- [`agent/member2-gui/docs/member2-notes.md`](agent/member2-gui/docs/member2-notes.md) — GUI role notes.
- [`agent/member-5-deepseek-schema/docs/route-b/README.md`](agent/member-5-deepseek-schema/docs/route-b/README.md) — Route B / AI candidate provider guide.

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
# BinaryRepair MVP �� GUI slice (Member 2)

Graphical interface for Project 11: AI-driven automated binary vulnerability repair and
correctness verification. This snapshot contains the three-screen GUI driven by clearly
labeled demo data; it does not execute binaries.

> The demo banner is always visible in mock mode. The data is synthetic fixture data,
> not a repair result, and must never be treated as evidence that a patch is verified.

## Quick start (Windows)

The project uses a local `.venv`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.ps1          # or run.bat
```

Manual start:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
```

Open <http://127.0.0.1:8123>. The service binds to localhost only.

## Demo walkthrough

1. **Setup / Review** �� choose any file as the sample (only its SHA-256 is recorded), fill
   in the defect description and valid-input tests, review the editable security contract.
2. **Progress / Comparison** �� start the demo run; phases advance roughly every 1.2 s and
   the page refreshes every 2 s. Route A ends as `rejected` (valid-input regression failed),
   Route B as `inconclusive` (symbolic exploration budget exhausted). This is intentional:
   incomplete or failed obligations must never be shown as success.
3. **Evidence / Export** �� obligations V0�CV5, scope and assumptions, artifact hashes,
   diagnostic-candidate labeling, replay instructions, and a JSON export that states it is
   not production approval.

## Three screens and requirements

| Screen | Requirement | Implemented in this snapshot |
|---|---|---|
| Setup / Review (`setup.html`) | PRD F1 | Upload, SHA-256 identity, defect/tests/environment, editable contract, pre-execution validation (422 empty, 413 oversized) |
| Progress / Comparison (`comparison.html`) | PRD F5, UI/UX direction | Side-by-side routes, independent phase indicators, six outcome badges, test/verification/compatibility/time/manual-intervention/AI-usage facts, cancel, refresh-safe polling |
| Evidence / Export (`evidence.html`) | PRD F4/F5 | V0�CV5 obligation table, scope and assumptions, artifact hashes, diagnostic-candidate labeling, JSON export, replay notes |

State model: `phase` (draft/screening/analyzing/roundtrip/generating/applying/validating/
finished) and `outcome` (success_within_scope/unsupported/rejected/inconclusive/error/
cancelled) are displayed as two independent axes; `not_run` is never treated as passed.

## Structure

```
app/
���� main.py            FastAPI entry, three-screen routes, status API, export
���� demo.py            Synthetic demo data (phases, V0�CV5 obligations, artifacts)
���� i18n.py            Chinese display labels (UI only; never enters API or exports)
���� templates/         base + three screens (Jinja2)
���� static/            css/app.css, js/poll.js
tests/
���� test_smoke.py            Three screens, host check, export
���� test_language_policy.py  API/exports have no CJK; UI stays Chinese
fixtures/public/      Public samples only
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Covers: screens reachable, Host check rejects foreign hosts, 64-character input hash,
phase progresses after start, evidence shows V0 and the diagnostic label, export is an
attachment with `demo: true`, cancel becomes `cancelled`; API/export contain no CJK while
the UI remains Chinese.

## Known limitations

- Demo data only; no binary is parsed or executed.
- Contract revision and `409 stale approval` handling are not implemented yet.
- No session token or CSRF protection yet; only host validation is in place.
- Exports are assembled by the GUI; the controller export endpoint is future work.

## Language policy

The GUI displays Chinese; uploaded, API, and exported data must be English ASCII.
Non-ASCII form content is rejected and uploaded filenames are sanitized to ASCII.

## Sources

- PRD v1.0 (2026-10-15): F1, F4, F5, UI/UX direction, success metrics
- Technical Design v1.0 (2026-10-15): ��6 state/lifecycle, ��7 three views and API, ��9
  verification ladder, ��11 local-service security, ��12 layout and dev mode, ��13 testing,
  ��14 work allocation
- `docs/member2-notes.md`: role notes with sources
