# BinaryRepair

**AI-assisted binary vulnerability repair with deterministic acceptance.**

BinaryRepair is a course project for repairing one known vulnerability in a Linux
x86-64 ELF without rebuilding from source. Two independent routes produce candidate
bytes; one shared acceptance engine decides whether the final executable is
`success_within_scope`. A model's claim is never evidence: only checks on the final
bytes count.

> **Status: integration complete; Route B round trip PASS; repair not yet demonstrated.**
> The controller, GUI, acceptance engine, AI boundary, SQLite schema (v1 baseline +
> 002/003), and the public CWE-121 candidate fixture are in `main`. Gate 4 (unchanged
> Route B round trip) is **PASS** on a disposable Ubuntu runner (6/6 behaviour-identical;
> `docs/route-b/09-gate4-evidence.md`). Gate 3 (Route A) is **NEEDS SCOPE RULING**.
> No binary has been repaired and verified end to end. Do not present demo data as
> repair evidence.

## What is in `main`

| Slice | Location | State |
|---|---|---|
| FastAPI + Jinja GUI (setup / comparison / evidence) | `app/main.py`, `app/templates/`, `app/static/` | demo-data UI, labelled |
| Job controller: create / get / approve / start / cancel / retry | `app/services/jobs.py` | identity + state tests pass |
| HTTP controller API + canonical routes | `app/controller_api.py` | `/api/jobs/{id}/runs`, `/api/attempts/{id}/evidence`; `/start` aliases |
| Acceptance engine and V0–V5 decision rules | `app/domain/acceptance.py`, `outcomes.py` | unit tests |
| Security contract v2 + canonical manifest hash | `app/domain/contracts.py`, `manifests.py` | schema_version=2, shared suite |
| AI candidate boundary + DeepSeek provider | `app/domain/candidates.py`, `app/services/provider.py`, `binaryrepair_ai/`, `schemas/` | typed failures, fake transport |
| SQLite v1 baseline + 002/003 | `app/db/schema.sql`, `app/db/migrations/` | jobs+artifacts baseline; AI tables; verdict columns |
| Route B kit | `routeb/`, `docs/route-b/` | feasibility scripts and notes |
| Public candidate fixture | `fixtures/public/CWE121_src_char_declare_cpy_51b/` | NOT FROZEN; gates 3–5 pending |

### Not yet done

- Route A segment/trampoline backend. Gate 3 stays **UNSUPPORTED** until the
  LIEF/Patcherex2 layout audit exists; after that it is **CONDITIONALLY FEASIBLE**.
- Gate 4 round trip. **PASS** (unchanged round trip, 6/6) on GitHub Actions
  Ubuntu 24.04 with JDK21, Ghidra 12.2 and Patcherex2 0.2.14; evidence in
  `docs/route-b/09-gate4-evidence.md`. This does not validate an edited candidate.
- Real repair execution. The controller queues runs and stores evidence; it does
  not execute uploaded binaries on the host.
- VM broker, symbolic (V4), and final V5 reproducibility evidence.

## Repository layout

```text
app/                 GUI + controller + domain + SQLite layer
  domain/            acceptance engine, contracts, manifests, candidate boundary
  services/          jobs, orchestration, DeepSeek provider
  db/                connection, migrate, schema.sql, migrations/002-003
binaryrepair_ai/     provider implementation (internal; import app.* instead)
schemas/             candidate/context JSON Schema + examples
routeb/              Route B fixture, Ghidra export, Patcherex2 probes
fixtures/public/     candidate ELF + frozen test manifests + SHA256SUMS
tests/               unit + integration + fixture contract tests
docs/route-b/        Route B design, DB v2, gate 6 notes
```

Historical branch snapshots were removed from `main`; the pre-cleanup tree is
preserved by the tag `archive/2026-10-22/pre-cleanup`.

## Quick start (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# GUI on http://127.0.0.1:8123
.\start.ps1
```

Controller service (separate process, loopback only):

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.controller_api:app --host 127.0.0.1 --port 8000
```

GUI in http-adapter mode:

```powershell
$env:BINARYREPAIR_BACKEND = "http"
$env:BINARYREPAIR_API_BASE = "http://127.0.0.1:8000"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
```

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

## Documentation

- [Route B overview](docs/route-b/README.md)
- [Root integration map](docs/route-b/04-root-integration.md)
- [DB v2 decisions](docs/route-b/05-db-v2-spec.md)
- [Gate 6 evidence notes](docs/route-b/06-gate6-evidence.md)
- [Candidate handoff / gate status](docs/route-b/03-feasibility-checklist.md)

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
