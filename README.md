# BinaryRepair

**AI-assisted binary vulnerability repair with deterministic acceptance.**

BinaryRepair is a course project for repairing one known vulnerability in a Linux
x86-64 ELF without rebuilding from source. Two independent routes produce candidate
bytes; one shared acceptance engine decides whether the final executable is
`success_within_scope`. A model's claim is never evidence: only checks on the final
bytes count.

> **Status [2026-10-29, branch `integration/consolidation-2026-10-29`]: consolidation in progress.**
> The controller, GUI, acceptance engine, AI boundary, SQLite schema (v1 baseline +
> 002/003), Route A/B tooling, and the public CWE-121 candidate fixture are in this
> tree. This branch additionally carries the member-4 acceptance unit suite and the
> root governance files; see "What this branch adds" below.
>
> No binary has been repaired and verified end to end on this branch. Gate 4
> (Route B formal) remains **NOT RUN**, no VM/broker execution was performed here,
> and no success claim is made. Do not present demo data as repair evidence.
>
> Gate 3 (Route A): **recorded as APPROVED on 2026-10-22** (`docs_BinaryRepair/handoffs/33-gate3-approved.md`,
> also summarised in `MEMORY.md`). That decision was **not re-measured in this
> consolidation**; the record's scope is limited to Gate 3 and does not cover the
> fixture freeze, Gate 4/5/6, or MVP acceptance.

## What this branch adds

| Slice | Location | State |
|---|---|---|
| Member-4 acceptance unit suite | `tests/unit/test_acceptance.py` | 29 tests, **29 passed** on this host (measured 2026-10-29) |
| Acceptance engine byte-alignment | `app/domain/acceptance.py`, `outcomes.py` | adopted the member-4 bytes (the only difference was a UTF-8 BOM); no content or rule change |
| Governance / agent instructions | `AGENTS.md`, `MEMORY.md`, `REVIEW-CHECKLIST.md` | added from `member-4-verification` |
| Instruction-doc copies used by `AGENTS.md` | `agent_docs/` | byte-identical copies of the four frozen `agent/*.md` files |
| Product and design documents | `docs_BinaryRepair/` | 41 files; byte-identical to `member-4-verification`; pointers in `AGENTS.md` resolve |

The acceptance engine and outcome vocabulary (`app/domain/acceptance.py`,
`app/domain/outcomes.py`) were already on `origin/main` with identical content
except for a UTF-8 BOM. This consolidation adopted the member-4 bytes exactly
(BOM removed - the only diff in these two files), so they are now byte-identical
to `member-4-verification`. No decision rule was changed or weakened.

### Merged earlier (already on this tree)

| Slice | Location | State |
|---|---|---|
| FastAPI + Jinja GUI (setup / comparison / evidence) | `app/main.py`, `app/templates/`, `app/static/` | demo-data UI, labelled |
| Job controller: create / get / approve / start / cancel / retry | `app/services/jobs.py` | identity + state tests pass where they can run |
| HTTP controller API + canonical routes | `app/controller_api.py` | `/api/jobs/{id}/runs`, `/api/attempts/{id}/evidence`; `/start` aliases |
| Acceptance engine and V0–V5 decision rules | `app/domain/acceptance.py`, `outcomes.py` | unit tests |
| Security contract v2 + canonical manifest hash | `app/domain/contracts.py`, `manifests.py` | schema_version=2, shared suite |
| AI candidate boundary + DeepSeek provider | `app/domain/candidates.py`, `app/services/provider.py`, `binaryrepair_ai/`, `schemas/` | typed failures, fake transport |
| SQLite v1 baseline + 002/003 | `app/db/schema.sql`, `app/db/migrations/` | jobs+artifacts baseline; AI tables; verdict columns |
| Route A tooling | `routea/` | cave build/audit scripts; needs `capstone` |
| Route B kit | `routeb/`, `docs/route-b/` | feasibility scripts and notes; needs `pyelftools` |
| Public candidate fixture | `fixtures/public/CWE121_src_char_declare_cpy_51b/` | NOT FROZEN; gates 3–5 in progress |

### Not done / not_run

- Gate 4 (Route B formal): **NOT RUN** (guest access + `gate4-harness`). The
  supplementary GitHub Actions run (6/6 unchanged round trip) recorded in
  `docs/route-b/09-gate4-evidence.md` is not the formal run.
- VM/broker execution, symbolic (V4), and final V5 reproducibility evidence.
- Real repair execution end to end. The controller queues runs and stores evidence;
  it does not execute uploaded binaries on the host.
- Route A/Route B module tests: **not runnable on this host** without `capstone`
  (no cp314 wheel) and `pyelftools` (not installed; a vendored copy was not added).
- Fixture freeze: **NOT FROZEN**. Contract status: see `MEMORY.md`; do not treat
  any contract hash quoted in old notes as re-verified here.

## Measured test state on this host (2026-10-29)

Host: Windows, Python 3.14.6, pytest 9.1.1 (global site-packages; `fastapi`,
`uvicorn`, `jinja2`, `pytest`, `httpx`, `pydantic`, `jsonschema` installed).
`capstone` and `pyelftools` are **not** installed.

pytest needs a **pre-created** basetemp directory, otherwise its own temp area
becomes unreadable on this host. Create one per run, for example:

```powershell
New-Item -ItemType Directory pytest_tmp_int -Force
```

Commands and observed results:

```powershell
python -m pytest tests/unit/test_acceptance.py --basetemp=pytest_tmp_int -p no:cacheprovider
# -> 29 passed in 0.03s (exit 0)
```

```powershell
python -m pytest tests/ --basetemp=pytest_tmp_int -p no:cacheprovider
# -> "Interrupted: 5 errors during collection" (exit 2); 0 tests run
#    tests/test_routea_cave.py, test_routea_manifest.py, test_routea_worker.py
#      -> ModuleNotFoundError: capstone
#    tests/test_routeb_attempt_writer.py, test_routeb_executor.py
#      -> ModuleNotFoundError: elftools
```

```powershell
python -m pytest tests/ --continue-on-collection-errors --basetemp=pytest_tmp_int -p no:cacheprovider
# -> 189 items execute: 146 passed, 2 skipped, 41 errored
#    all 41 errors are tests that request the pytest `tmp_path` fixture: the host
#    refuses to create the fixture directory (PermissionError), so no assertion is
#    reached. pytest then crashes in its own sessionfinish hook when it lists the
#    basetemp directory, so no summary line/exit 0 is produced. Counts above were
#    parsed from the progress output (72+72+45 = 189 characters: 146 '.', 2 's',
#    41 'E', 0 'F' - i.e. no assertion failures).
```

```powershell
python -m pytest tests/test_fixture_v3_manifest.py --basetemp=pytest_tmp_int -p no:cacheprovider
# -> 6 passed, 2 skipped in 0.03s (exit 0)
#    skips: "ELF execution requires Linux" (the host is Windows)
```

The host limitation is a Windows/sandbox ACL problem, not a repository defect:
tests that need no `tmp_path` run normally. On a Linux host, or where pytest can
create its temp directories, the expected result still has to be measured - it is
**unverified** here.

## Repository layout

```text
app/                 GUI + controller + domain + SQLite layer
  domain/            acceptance engine, contracts, manifests, candidate boundary
  services/          jobs, orchestration, DeepSeek provider
  db/                connection, migrate, schema.sql, migrations/002-003
binaryrepair_ai/     provider implementation (internal; import app.* instead)
schemas/             candidate/context JSON Schema + examples
routea/              Route A cave build / audit tooling (needs capstone)
routeb/              Route B fixture, Ghidra export, Patcherex2 probes
fixtures/public/     candidate ELF + frozen test manifests + SHA256SUMS
tests/               unit + integration + fixture contract tests
  unit/              member-4 acceptance unit suite
docs/route-b/        Route B design, DB v2, gate 6 notes
docs_BinaryRepair/   PRD, Tech Design, research, verification design, handoffs
agent_docs/          instruction-doc copies referenced by AGENTS.md
agent/               frozen per-document archive (do not edit)
```

Governance/instruction files: `AGENTS.md` (rules for coding agents),
`MEMORY.md` (dated progress and decisions), `REVIEW-CHECKLIST.md` (review gates).

Historical branch snapshots were removed from `main`; the pre-cleanup tree is
preserved by the tag `archive/2026-10-22/pre-cleanup`.

## Quick start (unverified on this host)

The commands below are the intended entry points, **not run during this
consolidation**. Label them unverified until they actually pass on the machine
they are meant for. The task target is Ubuntu; Windows is only a development host.

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

### Ubuntu (target runtime, unverified)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8123
```

## Historical issues now closed or recorded

- **DB v2 `contracts.body_json`**: v2 stores canonical SecurityContract text in
  `body_json`; the old 001 schema is retired. Free-text contract fields need no
  schema change; a new revision changes `contracts.sha256` /
  `reviewed_scope_sha256`.
- **V3 manifest line endings**: the fixture JSON is pinned as exact bytes; a fresh
  checkout keeps `valid.json` `17b2ee39…`, `invalid.json` `d493f370…`, manifest-set
  `a564f039…`. Older Windows checkouts that produced `7f984a…` are recorded as a
  line-ending artifact, not an oracle change.
- **Vendored test dependencies**: `pytest_deps/`, `_scratch/`, `pytest_tmp*/`,
  `pip_tmp/`, `pip_cache/` and `/delivery/` are local scratch and gitignored. A
  vendored `pyelftools` (pure Python) would be put under `pytest_deps/` and used
  through `PYTHONPATH`; **not done** in this consolidation.

## Documentation

- [AGENTS.md](AGENTS.md) - coding-agent rules; read before editing
- [MEMORY.md](MEMORY.md) - dated progress, decisions, known issues
- [REVIEW-CHECKLIST.md](REVIEW-CHECKLIST.md) - review gates
- [PRD](docs_BinaryRepair/PRD-BinaryRepair-MVP.md) and [Tech Design](docs_BinaryRepair/TechDesign-BinaryRepair-MVP.md)
- [Verification design](docs_BinaryRepair/verification-design.md)
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
copies. `integration/consolidation-2026-10-29` is one such short-lived branch: it
exists to make the tree coherent before the next PR, not to replace `main`.
