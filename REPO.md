# Repository

```text
HTTPS  https://github.com/chenfanaichifan/binary-repair
SSH    git@github.com:chenfanaichifan/binary-repair.git
branch delivery/all-hands-2026-11-07
head   fb1b74b18832b9cf68543e348c187449b7d78591
```

## Current status

```text
T8.3  COMPLETE
P1    success_within_scope
P2    ACCEPTANCE PASSED
tests 714 passed / 2 Linux-only skipped / 0 failed
e2e   12 passed (Chrome CDP)
```

## Layout

```text
app/                    controller, domain, services, UI templates/static
tools/                  ingest, P2 acceptance, MCP adapters
workers/                guest executor and Route A worker
routea/ routeb/         route-specific components
tests/                  unit, integration, e2e
fixtures/               public fixtures
delivery/               evidence and handoff packages (INDEX.md)
docs/                   handoffs, interfaces, reviews, screenshots (INDEX.md)
```

## Canonical evidence

```text
delivery/INDEX.md
delivery/p1-real-window-2026-11-07/
delivery/p1-routea-v4-symbolic-2026-11-07/
delivery/cwe416-124-v4-rerun-2026-11-06/
docs/reviews/review-9-12-m4-verdict-2026-11-07.json
docs/handoffs/182-project-audit-2026-11-08.md
```

## Commands

```bash
python -m pytest -q
python workers/executor/self_test.py
python tools/p2_acceptance.py --job-id <job> --base-url http://127.0.0.1:<port>
bash scripts/run_all.sh   # if present; otherwise use pytest
```

## Boundaries

```text
V4 model scope, not binary-level proof
M4 = Lead same operator
no tag
main not merged
private keys not tracked
```
