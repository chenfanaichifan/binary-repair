# Repository file guide

This is a curated delivery snapshot. Start with `README.md`, then
`CHANGELOG.md`, `docs/status/final-status.md` and `artifacts/INDEX.md`.

## Root files

| Path | Purpose |
|---|---|
| `README.md` | Project overview, status, quick start, evidence |
| `CHANGELOG.md` | Release history and version policy |
| `CONTRIBUTING.md` | Development and pull-request rules |
| `CODE_OF_CONDUCT.md` | Community behavior |
| `SECURITY.md` | Private security-reporting policy |
| `LICENSE` | MIT license |
| `CONTRIBUTORS.md` | Contributors |
| `requirements.txt` | Python dependencies |
| `pytest.ini` | Test configuration |
| `conftest.py` | Shared pytest helpers |
| `.env.example` | Environment template; placeholders only |
| `.editorconfig`, `.gitignore`, `.gitattributes` | Editor and repository hygiene |
| `start*.ps1`, `start*.sh`, `start-controller.*`, `start-worker.*` | Local launch scripts |
| `open.bat`, `open.ps1`, `run.bat` | Windows convenience launchers |

## Code and tests

| Path | Purpose |
|---|---|
| `app/` | FastAPI controller/API, domain rules, services, Jinja UI and static assets |
| `binaryrepair_ai/` | Provider adapter and typed AI boundary |
| `routea/` | Route A candidate/repair components |
| `routeb/` | Route B recover/rebuild/re-integrate components |
| `workers/` | Guest executor and Route A worker |
| `tools/` | Bundle ingest, P2 acceptance, MCP adapters |
| `schemas/` | Protocol and evidence schemas |
| `scripts/` | Operator scripts |
| `tests/` | Unit, integration and browser e2e tests |
| `fixtures/` | Public fixtures |

## Documentation

| Path | Purpose |
|---|---|
| `docs/README.md` | Documentation map |
| `docs/overview/product/` | PRD, design, research, verification design |
| `docs/overview/proposal/` | Project proposal |
| `docs/architecture/` | Controller, agent console, importer and worker interfaces |
| `docs/acceptance/` | Acceptance summary and current limitations |
| `docs/operations/` | Run-worker and fixtures guides |
| `docs/reference/interfaces/` | Artifact and execution interfaces |
| `docs/reference/m5/` | M5 tool contracts |
| `docs/development/handoffs/` | Current handoffs 165–182 |
| `docs/development/reviews/` | Review 9–12 and Review 12 records |
| `docs/development/analysis/` | Root-cause and verification analysis |
| `docs/development/routes/` | Route A/B notes |
| `docs/status/final-status.md` | Current acceptance status |
| `docs/assets/screenshots/` | Current UI screenshots |
| `docs/assets/demo/` | Earlier demo screenshots |
| `docs/archive/mvp-2026-10-31/evidence/` | Historical evidence |
| `docs/archive/updates/2026-11-08.md` | Earlier curated update note |

## Artifacts

| Path | Purpose |
|---|---|
| `artifacts/INDEX.md` | Canonical/historical evidence map |
| `artifacts/MANIFEST.md` | Current artifact packages and the historical `dist/` root |
| `artifacts/p1-real-window-2026-11-07/` | Authoritative P1 job, snapshot, P2 result, V5 replay |
| `artifacts/p1-routea-v4-symbolic-2026-11-07/` | Route A V4 marker |
| `artifacts/p1-routea-real-v4-2026-11-07/` | Route A real V4 artifacts |
| `artifacts/p1-routea-v4-input-2026-11-07/` | Route A V4 input package |
| `artifacts/v4-harness-2026-11-07/` | V4 harness package |
| `artifacts/cwe416-124-v4-rerun-2026-11-06/` | 124 V0–V5 rerun evidence |
| `artifacts/m4/v4-2026-11-07/` | M4 V4 marker and five criteria |
| `artifacts/m4-revalidation-ebc92a8/` | M4 revalidation evidence |
| `artifacts/p1-v5-logs-2026-11-07/` | Original V5 replay logs |
| `artifacts/logs/` | Recorded full-suite and Chrome e2e logs |

## Deliberately not included

```text
private keys / credentials / tokens
client binaries or private logs
development scratch worktrees
local caches, __pycache__, .pytest_cache
fabricated or regenerated V5 logs
```

## Reading order

1. `README.md`
2. `CHANGELOG.md`
3. `docs/status/final-status.md`
4. `docs/acceptance/LIMITATIONS.md`
5. `artifacts/INDEX.md`
6. `docs/development/reviews/review-9-12-m4-verdict-2026-11-07.json`
7. `docs/development/handoffs/182-project-audit-2026-11-08.md`
