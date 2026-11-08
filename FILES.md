# File and directory guide

This is a curated delivery snapshot. Start with `README.md`; open
`FINAL-STATUS.md` for the acceptance summary and `delivery/INDEX.md` for the
evidence map.

## Root files

| Path | Purpose |
|---|---|
| `README.md` | Project overview and current status |
| `REPO.md` | Repository map, source provenance, canonical paths, commands |
| `FILES.md` | This file/style guide |
| `FINAL-STATUS.md` | Final acceptance status and recorded limitations |
| `UPDATE-2026-11-08.md` | What changed in this curated update |
| `requirements.txt` | Python dependencies |
| `pytest.ini` | Test configuration |
| `conftest.py` | Shared pytest helpers |
| `.env.example` | Environment variable template; contains no secrets |
| `.gitignore`, `.gitattributes` | Repository hygiene |
| `start*.ps1`, `start*.sh`, `start-controller.*`, `start-worker.*` | Local launch scripts |
| `open.bat`, `open.ps1`, `run.bat` | Windows convenience launchers |
| `LICENSE`, `CONTRIBUTORS.md` | License and contributors |

## Code directories

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
| `docs/product/` | Product requirements, design, research and verification design |
| `docs/acceptance/` | Acceptance summary and current limitations |
| `docs/interfaces/` | Interface contracts (artifact roles, execution bridge) |
| `docs/reviews/` | Review 9–12 canonical reconstruction, M4 verification and verdict |
| `docs/handoffs/165-182...` | Current acceptance/status records only; older handoffs stay in the source repository |
| `docs/m5/` | M5 tool contracts |
| `docs/route-a/`, `docs/route-b/` | Route-specific notes |
| `docs/analysis/` | Root-cause and verification analysis |
| `docs/screenshots/` | Current UI screenshots (agent console and main pages) |
| `docs/demo/` | Demo screenshots retained from the earlier MVP snapshot |
| `docs/evidence/` | Historical pre-2026-11-08 gate evidence; current evidence is in `delivery/` |

## Delivery evidence

| Path | Purpose |
|---|---|
| `delivery/INDEX.md` | Canonical/historical evidence map |
| `delivery/MANIFEST.md` | Current `delivery/` packages and the historical `dist/` root |
| `delivery/p1-real-window-2026-11-07/` | Authoritative P1 job, snapshot, P2 result, V5 replay |
| `delivery/p1-routea-v4-symbolic-2026-11-07/` | Route A V4 marker |
| `delivery/p1-routea-real-v4-2026-11-07/` | Route A real V4 artifacts |
| `delivery/p1-routea-v4-input-2026-11-07/` | Route A V4 input package |
| `delivery/v4-harness-2026-11-07/` | V4 harness package |
| `delivery/cwe416-124-v4-rerun-2026-11-06/` | 124 V0–V5 rerun evidence |
| `delivery/m4/v4-2026-11-07/` | M4 V4 marker and five criteria |
| `delivery/m4-revalidation-ebc92a8/` | M4 revalidation evidence |
| `delivery/p1-v5-logs-2026-11-07/` | Original V5 replay logs |
| `delivery/logs/` | Recorded full-suite and Chrome e2e logs |

## Deliberately not included

```text
private keys / credentials / tokens
client binaries or private logs
_scratch/ and development-only working trees
local caches, __pycache__, .pytest_cache
fabricated or regenerated V5 logs
```

## Reading order

1. `README.md`
2. `FINAL-STATUS.md`
3. `delivery/INDEX.md`
4. `docs/acceptance/LIMITATIONS.md`
5. `docs/reviews/review-9-12-m4-verdict-2026-11-07.json`
6. `docs/handoffs/182-project-audit-2026-11-08.md`
