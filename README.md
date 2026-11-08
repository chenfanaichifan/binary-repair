# BinaryRepair

BinaryRepair is a local analyst tool for repairing one known vulnerability in a
Linux x86-64 ELF **without original source**. Two independent repair routes
produce candidate bytes, and one deterministic acceptance engine decides whether
the final bytes are `success_within_scope`. A model explanation is never
evidence.

This is a curated public snapshot of the accepted project. The development
history and historical evidence remain in the source repository
[`chenfanaichifan/binary-repair`](https://github.com/chenfanaichifan/binary-repair).

```text
Repository  https://github.com/leesirleesirlee-star/Binary_Repair
Release     v1.1.0 (2026-11-08)
Source      chenfanaichifan/binary-repair
            delivery/all-hands-2026-11-07 @ b61774d
```

## Current status

| Item | State |
|---|---|
| T8.3 | **COMPLETE** |
| P1 | **success_within_scope** |
| P2 | **ACCEPTANCE PASSED** |
| Test suite | **714 passed / 2 Linux-only skipped / 0 failed** (recorded Linux/Chrome run) |
| Browser e2e | **12 passed** (Chrome CDP) |
| V4 | **passed at model scope** (not binary-level proof) |
| 118 | **VERIFIED** (independent) |

See [`docs/status/final-status.md`](docs/status/final-status.md) and
[`docs/acceptance/LIMITATIONS.md`](docs/acceptance/LIMITATIONS.md) before citing
this project as proof.

## What it does

- **Route A** redirects the vulnerable call into a reviewed code cave.
- **Route B** recovers C, recompiles it, and re-integrates the function.
- A shared engine checks V0–V5 on the final candidate and returns
  `success_within_scope`, `inconclusive`, `rejected`, `unsupported`, `error`, or
  `cancelled`.
- The GUI/API only render verdicts; they never decide them.
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
artifacts/            canonical acceptance evidence
docs/                 product, architecture, acceptance, operations, reviews
```

See [`docs/README.md`](docs/README.md) for the documentation map and
[`docs/development/repository-layout.md`](docs/development/repository-layout.md)
for a file-by-file guide.

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
artifacts/p1-real-window-2026-11-07/           P1 job, snapshot, P2, V5 replay
artifacts/p1-routea-v4-symbolic-2026-11-07/    Route A V4 marker
artifacts/p1-routea-real-v4-2026-11-07/        Route A real V4 artifacts
artifacts/p1-routea-v4-input-2026-11-07/       Route A V4 input package
artifacts/v4-harness-2026-11-07/               V4 harness package
artifacts/cwe416-124-v4-rerun-2026-11-06/      124 V0–V5 rerun evidence
artifacts/m4/v4-2026-11-07/                    M4 V4 marker and five criteria
artifacts/m4-revalidation-ebc92a8/             M4 revalidation
artifacts/p1-v5-logs-2026-11-07/               original V5 replay logs
```

## Verification and limitations

- **V4 is model-level.** It is a typed symbolic claim over the target function,
  not a binary-level whole-program proof.
- **M4 verifier and Lead approver are the same operator.** This is
  role-separated, not independent two-person review.
- **Review 9–12 original text is not recovered.** The verdict is against a
  canonical reconstruction.
- **Coverage is one public fixture family.** Other binaries, architectures,
  compilers and stripped production binaries are not covered.
- **No client binary, credential, private key or private log is included.**
- **Not a production product.** This is an accepted course/MVP deliverable.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md), [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
and [`SECURITY.md`](SECURITY.md). Changes that touch acceptance evidence must
keep `artifacts/**/SHA256SUMS` verifiable.

## License and contributors

See [`LICENSE`](LICENSE), [`CONTRIBUTORS.md`](CONTRIBUTORS.md) and
[`CHANGELOG.md`](CHANGELOG.md).
