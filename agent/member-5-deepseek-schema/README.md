# binary-repair

AI-driven binary vulnerability repair and correctness verification (MVP prototype).

## Workstreams

- **Route B / AI candidate provider** — [docs/route-b/README.md](docs/route-b/README.md)
  DeepSeek adapter, candidate schema v1, SQLite schema, Route B feasibility kit.
- **Verification interface** — [docs/route-b/02-member-5-candidate-provider.md](docs/route-b/02-member-5-candidate-provider.md)
  `validate_candidate` / `may_leave_host` contract and typed provider failures.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python schemas/generate.py --check
python db/migrate.py --db var/app.db
```

The repair pipeline itself (GUI, job controller, binary workers) is being integrated
from the other workstreams; this branch currently contains the candidate/provider and
Route B feasibility slice.
