# BinaryRepair — AI-Assisted Binary Vulnerability Repair

BinaryRepair is a local analyst tool that repairs one known vulnerability in a
Linux x86-64 ELF **without original source**, using two independent repair
routes and one deterministic acceptance engine. A model explanation is never
evidence; only checks on the final bytes count.

This repository is a **curated public snapshot** of the accepted project. The
full development repository and its historical evidence remain at
`chenfanaichifan/binary-repair`; this snapshot selects the current code,
canonical acceptance evidence, and user-facing documentation.

```text
Repository: https://github.com/leesirleesirlee-star/Binary_Repair
Branch:     main
Snapshot:   2026-11-08
Source:     chenfanaichifan/binary-repair
            branch delivery/all-hands-2026-11-07
            commit b61774d04e793b3a5f34574df03ba6e1a034d700
```

## Current status (2026-11-08)

| Item | State |
|---|---|
| T8.3 | **COMPLETE** |
| P1 | **success_within_scope** |
| P2 | **ACCEPTANCE PASSED** |
| Test suite | **714 passed / 2 Linux-only skipped / 0 failed** (recorded Linux/Chrome run) |
| Browser e2e | **12 passed** (Chrome CDP) |
| V4 | **passed at model scope** (not a binary-level proof) |
| 118 | **VERIFIED** (independent) |
| tag / main merge | none in this snapshot |

The canonical acceptance evidence is listed in
[`delivery/INDEX.md`](delivery/INDEX.md). Current status records are listed in
[`docs/INDEX.md`](docs/INDEX.md).

## What it does

- **Route A** produces a candidate by redirecting the vulnerable call into a
  reviewed code cave.
- **Route B** recovers C, recompiles it, and re-integrates the function.
- A shared acceptance engine checks V0–V5 on the final candidate and returns
  `success_within_scope`, `inconclusive`, `rejected`, `unsupported`, `error`, or
  `cancelled`.
- The GUI and API only render verdicts; they never decide them.
- The host never executes uploaded or repaired binaries. Parsing, compilation,
  execution and symbolic analysis belong to the disposable guest under the
  broker.

## Repository layout

```text
app/                  FastAPI controller, services, domain, Jinja UI, static assets
binaryrepair_ai/      provider adapter and typed AI boundary
routea/               Route A components
routeb/               Route B components
workers/              guest executor and Route A worker
tools/                ingestion, P2 acceptance, MCP adapters
schemas/              protocol and evidence schemas
scripts/              operator scripts
tests/                unit, integration and browser e2e tests
fixtures/             public fixtures
delivery/             canonical acceptance evidence
docs/                 product, acceptance, interfaces, reviews, handoffs, screenshots
```

See [`FILES.md`](FILES.md) for a file-by-file orientation and
[`REPO.md`](REPO.md) for canonical paths and commands.

## Quick start

### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.ps1
```

### Linux

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
./start.sh
```

Open the printed `http://127.0.0.1:8123/?token=...` URL. Controller and worker
are separate loopback-only processes; see the start scripts in the repository
root.

Run the test suite:

```bash
python -m pytest -q
```

The recorded acceptance environment is Linux with Chrome CDP for browser e2e.
Windows hosts skip Linux-only cases and POSIX-fixture tests; use Linux for the
full acceptance record.

## Canonical evidence

```text
delivery/p1-real-window-2026-11-07/           P1 job, snapshot, P2, V5 replay
delivery/p1-routea-v4-symbolic-2026-11-07/    Route A V4 marker
delivery/p1-routea-real-v4-2026-11-07/        Route A real V4 artifacts
delivery/p1-routea-v4-input-2026-11-07/       Route A V4 input package
delivery/v4-harness-2026-11-07/               V4 harness package
delivery/cwe416-124-v4-rerun-2026-11-06/      124 V0–V5 rerun evidence
delivery/m4/v4-2026-11-07/                    M4 V4 marker and five criteria
delivery/m4-revalidation-ebc92a8/             M4 revalidation
delivery/p1-v5-logs-2026-11-07/               original V5 replay logs
docs/reviews/review-9-12-m4-verdict-2026-11-07.json
```

## Verification and limitations

Read [`docs/acceptance/LIMITATIONS.md`](docs/acceptance/LIMITATIONS.md) before
citing this project as proof.

- **V4 is model-level.** It is a typed symbolic model claim over the target
  function, not a binary-level whole-program proof.
- **M4 verifier and Lead approver are the same operator.** This is
  role-separated, not independent two-person review.
- **Review 9–12 original text is not recovered.** The review verdict is against
  a canonical reconstruction, not a verbatim original document.
- **Coverage is one public fixture family.** It is not evidence that arbitrary
  binaries, other architectures, other compilers, or stripped production
  binaries work.
- **No private key, client binary, credential, or private log** is included.
- **Not a production product.** This is an accepted course/MVP deliverable.

## License and contributors

See [`LICENSE`](LICENSE) and [`CONTRIBUTORS.md`](CONTRIBUTORS.md).
