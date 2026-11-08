# Repository guide

```text
HTTPS  https://github.com/leesirleesirlee-star/Binary_Repair
SSH    git@github.com:leesirleesirlee-star/Binary_Repair.git
branch main
release v1.1.2
```

## Snapshot provenance

```text
source repository  https://github.com/chenfanaichifan/binary-repair
source branch      delivery/all-hands-2026-11-07
source commit      7297076fb973f8cfd95bd5bfb69f50390fc9d808
snapshot date      2026-11-08
```

## Current status

```text
T8.3   COMPLETE
P1     success_within_scope
P2     ACCEPTANCE PASSED
tests  729 collected / 727 passed / 2 Linux-only skipped / 0 failed
e2e    12 passed (Chrome CDP)
V4     passed at model scope, not binary-level proof
```

## Layout

```text
app/                  controller, domain, services, Jinja UI, static assets
binaryrepair_ai/      provider adapter and typed AI boundary
routea/               Route A components
routeb/               Route B components
workers/              guest executor and Route A worker
tools/                ingestion, P2 acceptance, MCP adapters
schemas/              protocol and evidence schemas
scripts/              operator scripts
tests/                unit, integration, browser e2e
fixtures/             public fixtures
artifacts/            canonical acceptance evidence (see INDEX.md)
docs/
  overview/           product, research and verification design
  architecture/       controller/agent/worker interfaces
  acceptance/         acceptance summary and limitations
  operations/         run and fixture guides
  reference/          interface and M5 contracts
  development/        handoffs, reviews, analysis, route notes
  assets/             screenshots and demo images
  archive/            historical MVP evidence
  status/             final status
```

## Canonical paths

```text
Current status
  README.md
  CHANGELOG.md
  docs/status/final-status.md
  docs/acceptance/LIMITATIONS.md
  artifacts/INDEX.md
  artifacts/MANIFEST.md

P1 (authoritative)
  artifacts/p1-real-window-2026-11-07/

Route A V4
  artifacts/p1-routea-v4-symbolic-2026-11-07/
  artifacts/p1-routea-real-v4-2026-11-07/
  artifacts/p1-routea-v4-input-2026-11-07/
  artifacts/v4-harness-2026-11-07/

T8.3 / 124
  artifacts/cwe416-124-v4-rerun-2026-11-06/
  artifacts/m4/v4-2026-11-07/
  artifacts/m4-revalidation-ebc92a8/

V5
  artifacts/p1-real-window-2026-11-07/v5-replay-2026-11-07/
  artifacts/p1-v5-logs-2026-11-07/

Reviews
  docs/development/reviews/
```

## Commands

```bash
python -m pytest -q
python workers/executor/self_test.py
python tools/p2_acceptance.py --job-id <job> --base-url http://127.0.0.1:<port>
```

The GUI is FastAPI + Jinja; there is no Node/React build. Start it with
`start.ps1` (Windows) or `start.sh` (Linux); the terminal prints the session URL.

## Boundaries

```text
V4 is model scope, not a binary-level proof.
M4 verifier and Lead approver are the same operator.
Review 9–12 original text is not recovered; the verdict is reconstruction-based.
Full-suite record is Linux/Chrome; Windows hosts are not the acceptance record.
No private key, client binary, credential or private log is included.
```
