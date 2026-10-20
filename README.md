# BinaryRepair

**AI-driven automated binary vulnerability repair and correctness verification — MVP.**

BinaryRepair repairs one known vulnerability in a Linux x86-64 ELF **without original source code**, using two independent AI-assisted routes, and decides the result with one shared **deterministic acceptance engine**. A patch is never accepted because a model says it is fixed: it counts only when every required check passes on the final executable bytes.

- **Target defect:** one public stack-buffer-overflow case (CWE-121), Linux x86-64 ELF.
- **Route A — direct instruction repair:** candidate machine-instruction changes applied to a copy of the binary.
- **Route B — recovered C repair:** recover C-like code for a local region, repair it, compile it, reintegrate it into a copy.
- **Same input for both routes:** one original ELF, one reviewed security contract, one frozen test set.
- **Verification first:** structural, compatibility, behavioural, and bounded symbolic checks on the actual final patched executables.

> **Status: MVP in progress.** The GUI skeleton and the AI candidate layer run on `main`. The repair
> controller, the public fixture, and the two real repair routes are not implemented yet. No binary
> has been repaired or verified. Do not present the demo data as repair evidence.

---

## Current status (2026-10-20)

| Slice | State | Tests |
|---|---|---|
| GUI — setup / comparison / evidence screens | on `main`, demo data, banner-labelled | 6 + 5 (language policy, smoke) |
| AI candidate schema + provider failure typing | on `main` | 18 + 15 + 11 + 11 + 8 + 3 |
| Acceptance engine (outcomes, decision rules) | on `member-4-verification`, not merged yet | 29 |
| Job controller, SQLite schema, API | **not started** | — |
| Public fixture + test manifest | **not delivered** | — |
| Route A / Route B execution chain | **not started** | — |
| Disposable Ubuntu VM + broker | **not built** | — |

`main` currently runs **83 tests passing**. The acceptance engine adds **29** more once merged.

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

Prerequisite: Python 3.13 and a `.venv` in the project directory.

```powershell
.\start.ps1          # PowerShell one-command start
```

```bat
run.bat              :: double-click also works
```

Or manually:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
```

Open <http://127.0.0.1:8123>. The service binds to loopback only.

If `.venv` does not exist:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Quick start (Ubuntu) — planned

The target platform is Ubuntu 24.04 with Python 3.12. A `start.sh` equivalent does not exist yet;
until it does, use:

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
- Guarded by `tests/test_language_policy.py`.

---

## Repository layout

Target structure (sorted by the project design):

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

Current `main` contains the GUI slice and the AI candidate layer under `app/`; the other directories
are still being merged from member branches. An `agent/` directory on `main` holds a read-only
per-branch subtree archive for reference — **it is not the place to develop**.

---

## Tests

Run from the repository root:

```bash
python -m pytest tests/ -q -p no:cacheprovider
```

- Current `main`: **83 passed**.
- The verification branch adds **29 acceptance tests**; expected total after merge: **112**.
- One contract skeleton skips until `app.services.jobs` exists
  (`tests/integration/test_identity_state.py`); a skip is not a pass.
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

- [`docs_BinaryRepair/PRD-BinaryRepair-MVP.md`](docs_BinaryRepair/PRD-BinaryRepair-MVP.md) — product requirements.
- [`docs_BinaryRepair/TechDesign-BinaryRepair-MVP.md`](docs_BinaryRepair/TechDesign-BinaryRepair-MVP.md) — architecture, data model, routes, verification ladder.
- [`docs_BinaryRepair/research-BinaryRepair.md`](docs_BinaryRepair/research-BinaryRepair.md) — dated research record.
- [`docs_BinaryRepair/verification-design.md`](docs_BinaryRepair/verification-design.md) — acceptance semantics, decision precedence, interface contracts, coverage matrix.
- [`docs_BinaryRepair/handoffs/`](docs_BinaryRepair/handoffs/) — interface confirmations sent between slices.
- [`AGENTS.md`](AGENTS.md) — project instructions for coding agents (constraints, gotchas, safety rules).
- [`MEMORY.md`](MEMORY.md) — current state, decisions, known issues.
- [`REVIEW-CHECKLIST.md`](REVIEW-CHECKLIST.md) — checks to report before marking work complete.

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

1. Job controller + SQLite + API on `main` (blocks the identity/state tests and all integration).
2. Public CWE-121 fixture with provenance and a frozen test manifest.
3. Disposable Ubuntu VM, toolchain smoke tests, and the broker.
4. Route A instruction-repair chain and Route B recovered-C round trip.
5. Shared acceptance over both final candidates, then export and independent replay.

No completed-MVP date is established; estimates follow the feasibility gates in the technical design.
