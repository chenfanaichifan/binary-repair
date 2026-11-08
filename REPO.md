# Repository map

```text
HTTPS  https://github.com/leesirleesirlee-star/Binary_Repair
SSH    git@github.com:leesirleesirlee-star/Binary_Repair.git
branch main
```

## Snapshot provenance

This is a curated snapshot, not the development repository.

```text
source repository  https://github.com/chenfanaichifan/binary-repair
source branch      delivery/all-hands-2026-11-07
source commit      b61774d04e793b3a5f34574df03ba6e1a034d700
snapshot date      2026-11-08
```

## Current status

```text
T8.3   COMPLETE
P1     success_within_scope
P2     ACCEPTANCE PASSED
tests  714 passed / 2 Linux-only skipped / 0 failed
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
delivery/             canonical acceptance evidence (see INDEX.md)
docs/                 product, acceptance, interfaces, reviews, handoffs, screenshots
```

## Canonical paths

```text
Current status
  README.md
  FINAL-STATUS.md
  delivery/INDEX.md
  docs/INDEX.md

P1 (authoritative)
  delivery/p1-real-window-2026-11-07/

Route A V4
  delivery/p1-routea-v4-symbolic-2026-11-07/
  delivery/p1-routea-real-v4-2026-11-07/
  delivery/p1-routea-v4-input-2026-11-07/
  delivery/v4-harness-2026-11-07/

T8.3 / 124
  delivery/cwe416-124-v4-rerun-2026-11-06/
  delivery/m4/v4-2026-11-07/
  delivery/m4-revalidation-ebc92a8/

V5
  delivery/p1-real-window-2026-11-07/v5-replay-2026-11-07/
  delivery/p1-v5-logs-2026-11-07/

Reviews
  docs/reviews/review-9-12-canonical-2026-11-07.md
  docs/reviews/review-9-12-m4-verification-2026-11-07.md
  docs/reviews/review-9-12-m4-verdict-2026-11-07.json
  docs/reviews/review-12-m4-verification-2026-11-08.md
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
No private key, client binary, or credential is included.
No tag or merge to the original repository's main.
```
