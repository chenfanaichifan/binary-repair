# Runtime verification of the integrated BinaryRepair slice

Status: **measured on 2026-10-29; no repair was performed and no binary was executed.**
This document records what was actually run on this Windows host, what the output
was, and what still has not run. It replaces "should work" with commands and
observed results.

> **Later status (verified at `986a49f`; later commits add handoff tooling and docs; they do not change product code or the test suite):** this file is a pre-merge snapshot. Its test
> count (189/187) was measured on a worktree where `tests/unit/test_acceptance.py`
> was staged but not yet committed, so it is not reproducible from commit
> `4107836` alone. Defects it lists in §7/§8 (no GUI `http` mode; static evidence
> placeholder) were fixed later by the member-2 GUI merge (`381e4ef`) and the
> controller evidence fix shipped in `cc29158`. Current measured totals and the
> independent verdict are in `docs/analysis/VERIFICATION.md`.

| Field | Value |
|---|---|
| Date of measurement | 2026-10-29 (Asia/Hong_Kong) |
| Host | Windows 11, `Microsoft Windows [Version 10.0.26300.9711]`, AMD64 |
| Python | 3.14.6 (MSC v.1944 64-bit), `C:\Users\Lenovo\AppData\Local\Python\pythoncore-3.14-64\python.exe` |
| Repository | `D:\BinaryRepair_Project` |
| Branch | `integration/consolidation-2026-10-29` |
| Commit | `4107836` (`feat(executor): add attempt writer, 409 guard, and p2 acceptance check`) |
| Verifier | runtime-verifier (Team task `task-2`) |
| Production files changed | none (only `scripts/demo_e2e.py`, `scripts/pytest_rt_report.py`, this document; runtime artifacts under `_scratch/runtime_verification/`) |

## 0. Summary

Proven by measurement:

- the SQLite schema can be created from scratch by `app/db/migrate.py` and is
  idempotent on re-run (`schema_migrations` versions `[1, 2, 3]`);
- the GUI app (`app.main:app`) boots under uvicorn on a free loopback port and
  its actual screens render HTTP 200 (`/jobs/new`, `/jobs/{id}`,
  `/jobs/{id}/evidence`), and the controller API (`app.controller_api:app`)
  boots and creates/serves real jobs persisted in SQLite;
- the full controller contract lifecycle works end to end through real HTTP
  routes and the real service layer: create job from the public CWE-121 fixture
  bytes -> 409 before approval -> approve contract -> start run (202) ->
  idempotent re-start (200) -> conflicting idempotency key (409) -> labelled
  synthetic attempt bundles -> real `app.services.worker.run_once` -> persisted
  attempts/obligations/verdicts, readable through the API and directly in
  SQLite;
- the deterministic acceptance engine decides the two synthetic scenarios
  correctly and honestly: incomplete evidence yields `inconclusive /
  required_check_not_run` (never `success`), and a required failed check yields
  `rejected / regression_failed`;
- the approved fixture contract body hashes to
  `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37`, the
  scope hash quoted in `README.md`. The approval path really binds that hash.

Not proven / not run:

- no candidate binary was built, no binary was executed on the host, and no
  repair was validated. Guest execution, Route A/B candidate generation, V1-V5
  real checks, symbolic (V4) verification and V5 independent replay are all
  still `not_run`;
- the GUI was not demonstrated in an HTTP-backend mode against the controller:
  `app/main.py` contains no `BINARYREPAIR_BACKEND` / `BINARYREPAIR_API_BASE`
  handling even though `README.md` and `docs/controller-integration.md`
  advertise it (see section 8);
- the current test-suite situation is measured precisely: 5 modules are
  uncollectable (`capstone` / `pyelftools` missing), the repository's
  documented 146 passed / 2 skipped / 41 errored run was reproduced, and all
  41 errors are the same sandbox temporary-directory defect (no assertion
  failure); replacing only that broken fixture yields **187 passed, 2 skipped**
  (section 6). The "16 passed" figure in the task brief was not reproducible.

## 1. Method and safety boundary

- Every command below was executed in this worktree on this host and the output
  was copied from the actual run.
- The public fixture `fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf`
  was only read as bytes: length, SHA-256, and the four ELF magic bytes were
  checked. It was never executed, loaded, or decompiled on the host.
- No `pip install` was attempted. The installed global Python is the only
  interpreter used (see section 2); `capstone`, `pyelftools`, `lief`, `angr`,
  `patcherex2` and `z3` are absent, and the environment notes say pip installs
  are sandbox-blocked.
- The controller writes to a data directory. The default is `var/`, which the
  DSH sandbox does not allow to be created, so every run used an explicit
  `_scratch/runtime_verification/...` data directory via
  `--db` / `--data-dir` / `BINARYREPAIR_DATA_DIR`. No application code was
  changed to make this work.
- Background uvicorn processes were started as managed background jobs, checked,
  and stopped; a post-check showed no listener on either port. The project's
  reserved port `127.0.0.1:8123` was not used.

## 2. Environment facts (measured)

```text
python --version
Python 3.14.6

python -c "import platform, sys; print(platform.platform()); ..."
platform: Windows-11-10.0.26300-SP0
machine: AMD64
processor: Intel64 Family 6 Model 204 Stepping 2, GenuineIntel
python: 3.14.6 (tags/v3.14.6:c63aec6, Jun 10 2026, 10:26:10) [MSC v.1944 64 bit (AMD64)]

cmd /c ver
Microsoft Windows [Version 10.0.26300.9711]

git rev-parse --short HEAD  -> 4107836
git branch --show-current    -> integration/consolidation-2026-10-29
```

Installed distributions (measured with `importlib.metadata`):

| Package | Version |
|---|---|
| fastapi | 0.141.1 |
| starlette | 1.6.0 |
| uvicorn | 0.52.4 |
| jinja2 | 3.1.6 |
| httpx | 0.28.1 |
| pydantic | 2.13.5 |
| jsonschema | 4.26.0 |
| pytest | 9.1.1 |
| python-multipart | 0.0.32 |
| anyio | 4.15.1 |

Missing modules (measured with `import`): `capstone`, `elftools` (pyelftools),
`lief`, `angr`, `patcherex2`, `z3`. The repository's `requirements.txt` asks for
`pyelftools` and `capstone`; neither has an installed build for this Python
3.14 interpreter, which is why five test modules cannot be imported (section 6).

`python-multipart` being installed matters: the controller's multipart
`POST /api/jobs` route works, and it was exercised.

## 3. Fresh SQLite database

Read first: `app/db/migrate.py` applies `app/db/schema.sql` as baseline version
1, then every `app/db/migrations/*.sql` in version order. It records
`schema_migrations(version, name, applied_at)` and rejects the retired 001
schema before any DDL.

Command and observed output:

```powershell
python -m app.db.migrate --db _scratch/runtime_verification/data_boot
applied; schema versions: [1, 2, 3]
```

Re-running the same command to check idempotency:

```powershell
python -m app.db.migrate --db _scratch/runtime_verification/data_boot
applied; schema versions: [1, 2, 3]
```

Database contents after migration (read with `sqlite3` from Python):

```text
tables: ['artifacts', 'attempts', 'contracts', 'events', 'jobs', 'model_calls',
         'obligations', 'runs', 'schema_migrations', 'sqlite_sequence']
migrations: [(1, 'base', '2026-10-29 04:36:01'),
             (2, '002_ai_tables', '2026-10-29 04:36:01'),
             (3, '003_acceptance_verdict', '2026-10-29 04:36:01')]
jobs columns:        id, original_sha256, filename, defect_description, phase,
                     created_at, classification, cancel_requested
artifacts columns:   id, job_id, role, relative_path, sha256, size_bytes,
                     created_at, attempt_id, media_type
contracts columns:   id, job_id, revision, body_json, sha256, approved_at, reviewer_label
runs columns:        id, job_id, contract_id, manifest_sha256, reviewed_scope_sha256,
                     idempotency_key, phase, outcome, started_at, finished_at, reason,
                     failing_obligation, detail
attempts columns:    id, run_id, route, sequence, phase, outcome, reason,
                     candidate_sha256, started_at, finished_at, failing_obligation, detail
obligations columns: id, attempt_id, kind, required, result, evidence_artifact_id, detail
```

The resulting file was `_scratch/runtime_verification/data_boot/app.db`
(110,592 bytes). This database was then used by the booted controller API.

## 4. Boot verification over real TCP

Free ports were verified first (`Get-NetTCPConnection -LocalPort 18123,18124`
returned nothing for both). Both services were started as managed background
jobs and stopped afterwards.

### 4.1 GUI app (`app.main:app`)

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 18123 --log-level info
```

Observed startup log:

```text
INFO:     Started server process [16720]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:18123 (Press CTRL+C to quit)
```

HTTP probes (real TCP via `httpx`, not the in-process test client):

| Request | Status observed | Notes |
|---|---|---|
| `GET /healthz` | **200** | body `{"ok":true,"demo":true}` |
| `GET /` | **303** | `Location: /jobs/new` (it is a redirect, not a 200 screen) |
| `GET /jobs/new` | **200** | 5,547-byte HTML, contains `<html`, `BinaryRepair`, `setup` |
| `GET /jobs` | **405** | Method Not Allowed. There is no jobs-list screen; only `POST /jobs` exists |
| `GET /jobs/does-not-exist` | **404** | expected not-found path |
| `POST /jobs` (fixture bytes + ASCII form fields) | **303** | `Location: /jobs/job-08ba09f7` |
| `GET /jobs/job-08ba09f7` | **200** | 8,583-byte comparison screen, contains `Route A`, `Route B` |
| `GET /jobs/job-08ba09f7/evidence` | **200** | 10,640-byte evidence screen, contains `V0`, `V5` |
| `GET /api/jobs/job-08ba09f7` | **200** | English ASCII JSON, `demo: true` |
| `GET /api/jobs/job-08ba09f7/export` | **200** | JSON export, `demo: true`, contains `synthetic` disclaimer |

Uvicorn access log (verbatim):

```text
INFO:     127.0.0.1:57807 - "GET /healthz HTTP/1.1" 200 OK
INFO:     127.0.0.1:57807 - "GET / HTTP/1.1" 303 See Other
INFO:     127.0.0.1:57807 - "GET /jobs/new HTTP/1.1" 200 OK
INFO:     127.0.0.1:57807 - "GET /jobs HTTP/1.1" 405 Method Not Allowed
INFO:     127.0.0.1:57807 - "GET /jobs/job-does-not-exist HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:57807 - "POST /jobs HTTP/1.1" 303 See Other
INFO:     127.0.0.1:57807 - "GET /jobs/job-08ba09f7 HTTP/1.1" 200 OK
INFO:     127.0.0.1:57807 - "GET /jobs/job-08ba09f7/evidence HTTP/1.1" 200 OK
INFO:     127.0.0.1:57807 - "GET /api/jobs/job-08ba09f7 HTTP/1.1" 200 OK
INFO:     127.0.0.1:57807 - "GET /api/jobs/job-08ba09f7/export HTTP/1.1" 200 OK
```

### 4.2 Controller API (`app.controller_api:app`)

```powershell
$env:BINARYREPAIR_DATA_DIR="_scratch/runtime_verification/data_boot"
python -m uvicorn app.controller_api:app --host 127.0.0.1 --port 18124 --log-level info
```

Observed startup log:

```text
INFO:     Started server process [23820]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:18124 (Press CTRL+C to quit)
```

HTTP probes:

| Request | Status observed |
|---|---|
| `GET /healthz` | **200**, `{"ok":true,"service":"binaryrepair-controller","backend":"http","demo":null}` |
| `GET /api/jobs/does-not-exist` | **404** |
| `POST /api/jobs` (fixture bytes, multipart) | **201**, `{"id":"3dab99ba46184fba9171b65d2013a5a2","original_sha256":"aa4281...","phase":"draft"}` |
| `GET /api/jobs/3dab99ba46184fba9171b65d2013a5a2` | **200**, snapshot with the same original hash, `phase: draft` |

Uvicorn access log (verbatim):

```text
INFO:     127.0.0.1:57808 - "GET /healthz HTTP/1.1" 200 OK
INFO:     127.0.0.1:57808 - "GET /api/jobs/does-not-exist HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:57808 - "POST /api/jobs HTTP/1.1" 201 Created
INFO:     127.0.0.1:57808 - "GET /api/jobs/3dab99ba46184fba9171b65d2013a5a2 HTTP/1.1" 200 OK
```

The HTTP-created job was verified directly in SQLite, proving the request path
reached the real store and not an in-memory fake:

```text
jobs rows: [('3dab99ba46184fba9171b65d2013a5a2', 'original.elf',
             'aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393', 'draft')]
artifacts rows: [('d374d114cc8947fe9002d485b965c065',
                  '3dab99ba46184fba9171b65d2013a5a2', 'original',
                  'jobs/3dab99ba46184fba9171b65d2013a5a2/original.bin',
                  'aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393', 26792)]
```

The fixture `original.elf` is 26,792 bytes and its SHA-256 is
`aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`; the stored
bytes hash to the same value.

### 4.3 Correction to the expected "three screens"

The task summary expected `/`, `/jobs/new` and `/jobs` to all render HTTP 200.
Measured behaviour:

- `/` is a **303 redirect** to `/jobs/new` (this is the app's design, see
  `app/main.py`);
- `GET /jobs` is **405** because only `POST /jobs` is defined; there is no
  "jobs list" screen;
- the three GUI screens are actually **setup** `/jobs/new`, **comparison**
  `/jobs/{id}`, and **evidence** `/jobs/{id}/evidence`; all three return 200 and
  render the template (measured above, after creating a demo job with
  `POST /jobs`).

Both servers were stopped after the probes; `Get-NetTCPConnection` for ports
18123/18124 afterwards returned 0 listeners.

## 5. End-to-end synthetic controller demo

### 5.1 What the demo drives

`scripts/demo_e2e.py` uses `fastapi.testclient.TestClient` in-process against
the **real** `app.controller_api:app` (the same module uvicorn served above) and
the real service layer:

```text
POST /api/jobs                            app/controller_api.py -> app/services/jobs.create_job
POST /api/jobs/{id}/approve               app/services/jobs.approve_contract (SecurityContract v2, canonical hash)
POST /api/jobs/{id}/runs (before approve) expected 409
POST /api/jobs/{id}/runs                  202; app/services/jobs.start_run; 2 attempts pre-created
POST /api/jobs/{id}/runs (same key)       200, created=false (idempotency measured)
POST /api/jobs/{id}/runs (bad key/manifest) expected 409
write labelled SYNTHETIC bundle per attempt under
    <data>/jobs/<job>/runs/<run>/attempts/<attempt_id>.json
app.services.worker.run_once(data_dir)    persists obligations, evaluates both attempts and the run
GET  /api/jobs/{id}                       snapshot incl. route verdicts and obligations
GET  /api/attempts/{id}/evidence          attempt verdict
GET  /api/jobs/{id}/obligations           V0-V5 placeholder groups
GET  /api/jobs/{id}/artifacts             original artifact listing
```

TestClient uses `base_url="http://127.0.0.1"` so the app's local-only Host
middleware accepts the requests. Each demo run gets a fresh, timestamped data
directory under `_scratch/runtime_verification/`; the script refuses a
non-empty `--data-dir` (measured: passing the already-used `data_boot`
directory exits **1** with
`DEMO FAILED: --data-dir ... already contains files; use a fresh directory`).

The demo never builds or executes a binary. The synthetic bundle is labelled
inside the JSON (`"synthetic": true`, `"label": ...`) and every gate carries a
`SYNTHETIC: ...` detail string. The V0 result is also supplied by the harness,
but it is derived from the real stored original bytes hashing to the approved
input hash; the candidate SHA-256 is a clearly named placeholder
(`sha256("SYNTHETIC-PLACEHOLDER-CANDIDATE-NOT-BUILT:<job_id>")`), not a real
candidate.

### 5.2 Command and observed output

```powershell
python scripts/demo_e2e.py
```

Observed (abridged output; full transcript saved in
`_scratch/runtime_verification/demo_e2e_final.txt`; exit code **0**):

```text
== environment (measured) ==
python: 3.14.6
platform: win32
repo root: D:\BinaryRepair_Project
fresh data dir: D:\BinaryRepair_Project\_scratch\runtime_verification\e2e_20261029_044106
fixture: fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf

== real input ==
fixture ELF bytes: 26792
fixture sha256: aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393
ELF magic checked; the binary is NOT executed on this host.

GET /healthz -> 200 {'ok': True, 'service': 'binaryrepair-controller', 'backend': 'http', 'demo': None}

---- scenario honest-wiring: inconclusive expected ----
POST /api/jobs -> 201 id=8a67c96a25874101bdb8aa85fea0d381 phase=draft sha256=aa428157...
POST /api/jobs/{id}/runs before approval -> 409 (No approval for this contract revision.)
POST /api/jobs/{id}/approve -> 200 revision=1 scope_sha256=24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37
POST /api/jobs/{id}/runs -> 202 run=95c3ead3d42c4b52aebae8d32102b360 attempts=['c1e7aa7a...', 'bc105f00...']
POST /api/jobs/{id}/runs (same idempotency key) -> 200 same run, created=false
POST /api/jobs/{id}/runs (same key, different manifest) -> 409
wrote synthetic bundle for route_a: c1e7aa7aa1924f34b1451068bf6ab91b.json
wrote synthetic bundle for route_b: bc105f00360a49ccb51fa9342a7d3bf3.json
app.services.worker.run_once output:
    worker: run 95c3ead3d42c4b52aebae8d32102b360 finished
persisted: run phase=finished outcome=inconclusive attempts=2 obligation_rows=12
stored original bytes: jobs/8a67c96a25874101bdb8aa85fea0d381/original.bin sha256=aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393

---- scenario failed-check-control: rejected expected ----
POST /api/jobs -> 201 id=a4ae02c7e0d64882ac8669f7d99a4b85 phase=draft sha256=aa428157...
POST /api/jobs/{id}/runs before approval -> 409 (No approval for this contract revision.)
POST /api/jobs/{id}/approve -> 200 revision=1 scope_sha256=24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37
POST /api/jobs/{id}/runs -> 202 run=ef9c0e1222194d339d686a93207deee1 attempts=['cfb4586a...', '9afd1d3a...']
POST /api/jobs/{id}/runs (same idempotency key) -> 200 same run, created=false
POST /api/jobs/{id}/runs (same key, different manifest) -> 409
app.services.worker.run_once output:
    worker: run ef9c0e1222194d339d686a93207deee1 finished
persisted: run phase=finished outcome=rejected attempts=2 obligation_rows=12

== final verdicts (produced by app/domain/acceptance.py) ==
scenario honest-wiring:
  job phase: finished
  run outcome: inconclusive
  reason: required_check_not_run
  failing obligation: structure
  detail: route_a: V1 structure: not_run
  route_a: outcome=inconclusive reason='required_check_not_run' verification=unknown
    obligations={'behaviour': 'not_run', 'identity': 'passed', 'interface': 'not_run',
                 'reproducibility': 'not_run', 'structure': 'not_run', 'symbolic': 'not_run'}
  route_b: outcome=inconclusive reason='required_check_not_run' verification=unknown
    obligations={'behaviour': 'not_run', 'identity': 'passed', 'interface': 'not_run',
                 'reproducibility': 'not_run', 'structure': 'not_run', 'symbolic': 'not_run'}

scenario failed-check-control:
  job phase: finished
  run outcome: rejected
  reason: regression_failed
  failing obligation: behaviour
  detail: route_a: V3 behaviour: failed
  route_a: outcome=rejected reason='regression_failed' verification=failed
    obligations={'behaviour': 'failed', 'identity': 'passed', 'interface': 'not_run',
                 'reproducibility': 'not_run', 'structure': 'not_run', 'symbolic': 'not_run'}
  route_b: outcome=rejected reason='regression_failed' verification=failed
    obligations={'behaviour': 'failed', 'identity': 'passed', 'interface': 'not_run',
                 'reproducibility': 'not_run', 'structure': 'not_run', 'symbolic': 'not_run'}

== what is real vs synthetic ==
REAL: fixture ELF bytes and sha256; HTTP controller routes; contract approval;
      idempotent run start; SQLite rows (jobs/contracts/runs/attempts/obligations);
      worker/orchestration wiring; acceptance verdicts.
SYNTHETIC: every V1-V5 result and the V0 result are supplied by this script's
      labelled bundle; no candidate binary exists and nothing was executed.
NOT RUN: guest execution, Route A/B candidate generation, V1-V5 real checks,
      symbolic (V4) verification, and V5 independent replay.

DEMO OK: synthetic attempt data exercised the real controller, database, worker and deterministic acceptance path end to end.
```

### 5.3 Measured results

| Measurement | Scenario 1 "honest-wiring" | Scenario 2 "failed-check-control" |
|---|---|---|
| Job | `8a67c96a25874101bdb8aa85fea0d381` | `a4ae02c7e0d64882ac8669f7d99a4b85` |
| Run | `95c3ead3d42c4b52aebae8d32102b360` | `ef9c0e1222194d339d686a93207deee1` |
| Bundle gate results | V0 `passed`; V1-V5 `not_run` | V0 `passed`; V3 `failed`; V1, V2, V4, V5 `not_run` |
| Attempt outcome (both routes) | `inconclusive` / `required_check_not_run` | `rejected` / `regression_failed` |
| Run outcome | `inconclusive` / `required_check_not_run`, failing obligation `structure` | `rejected` / `regression_failed`, failing obligation `behaviour` |
| Run phase | `finished` | `finished` |
| Obligation rows persisted | 12 (2 attempts x 6) | 12 (2 attempts x 6) |
| Run start before approval | 409 | 409 |
| Same idempotency key | 200, same run id, `created=false` | 200, same run id, `created=false` |
| Same key, different manifest | 409 | 409 |
| Stored original bytes | 26,792 bytes, SHA-256 matches fixture | same |

The approved contract scope hash on both jobs is
`24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37`, computed by
`app/domain/contracts.py` from the fixture's reviewed `contract.json` body. This
matches the hash quoted in `README.md` ("contract `24bfe568...4e37`"), so the
approval and hash path is real, not a stub.

Key point: the acceptance engine did not report either synthetic scenario as a
success. The first scenario reports every unimplemented check as `not_run` and
returns `inconclusive`; the second demonstrates that a definite required
failure outranks missing evidence and returns `rejected`. There is no code path
in this demo in which absent evidence becomes `passed`.

### 5.4 Persisted evidence produced by the demo

Under the run data directory (for example
`_scratch/runtime_verification/e2e_20261029_044106/`):

```text
app.db
jobs/<job>/meta.json                              # contract body, manifest hash, approval
jobs/<job>/original.bin                           # fixture bytes, 26792, SHA-256 verified
jobs/<job>/run-verdict.json                       # run-level verdict
jobs/<job>/runs/<run>/attempts/<attempt_id>.json  # the labelled SYNTHETIC bundle
jobs/<job>/runs/<run>/attempts/<attempt_id>/verdict.json   # per-attempt verdict
```

Example persisted run verdict (scenario 1):

```json
{
  "job_id": "8a67c96a25874101bdb8aa85fea0d381",
  "route_a": {"detail": "V1 structure: not_run", "failing_obligation": "structure", "outcome": "inconclusive", "reason": "required_check_not_run"},
  "route_b": {"detail": "V1 structure: not_run", "failing_obligation": "structure", "outcome": "inconclusive", "reason": "required_check_not_run"},
  "verdict": {"detail": "route_a: V1 structure: not_run", "failing_obligation": "structure", "outcome": "inconclusive", "reason": "required_check_not_run"}
}
```

Direct SQLite check performed by the script for each scenario: run phase
`finished`, persisted run outcome equals the API outcome, 2 attempt rows with
the same outcome, 12 obligation rows, and the contracts row hash equals the
canonical contract hash. The script exits 1 on any mismatch or unexpected
exception; on this run it exited 0.

## 6. Test-suite measurement

### 6.1 The command from the task

```powershell
New-Item -ItemType Directory -Force -Path pytest_tmp_rt | Out-Null
python -m pytest tests/ --basetemp=pytest_tmp_rt -p no:cacheprovider -q
```

Observed: pytest 9 stops at collection and **no test executes**:

```text
ERROR tests/test_routea_cave.py
ERROR tests/test_routea_manifest.py
ERROR tests/test_routea_worker.py
ERROR tests/test_routeb_attempt_writer.py
ERROR tests/test_routeb_executor.py
!!!!!!!!!!!!!!!!!!! Interrupted: 5 errors during collection !!!!!!!!!!!!!!!!!!!
```

Exit code: 2. The five modules cannot even be imported:

- `tests/test_routea_cave.py`, `tests/test_routea_manifest.py`,
  `tests/test_routea_worker.py`: `ModuleNotFoundError: No module named 'capstone'`;
- `tests/test_routeb_attempt_writer.py`, `tests/test_routeb_executor.py`:
  `ModuleNotFoundError: No module named 'elftools'` (via `routeb/executor.py`).

Those five files contain 13 test functions, all uncollected. A skip is not a
pass and an uncollected test is not a pass.

### 6.2 Adding `--continue-on-collection-errors` is not enough on this host

With `--continue-on-collection-errors` pytest starts running tests, but pytest's
own temporary-directory handling breaks under the DSH Windows sandbox: after the
first `tmp_path` directory is created, later tests fail to set up with
`PermissionError: [WinError 5]` while listing the base temporary directory, and
session teardown crashes in `_pytest.tmpdir.cleanup_dead_symlinks`. A
pre-created `--basetemp` directory (as the README note suggests) does **not**
prevent this: the first `tmp_path` subdirectory poisons the base directory for
the rest of the run. This is an environment defect, not a test result. Two
measured variants:

| Variant | Observed |
|---|---|
| default temp area (`%TEMP%`) | 146 passed, 2 skipped, 41 errors (`PermissionError`, tmp_path setup), 5 collection errors; pytest exits 1 |
| explicit pre-created `--basetemp` in the repo | same `PermissionError` pattern; session teardown raises `PermissionError` before the normal summary |

The first row reproduces the record now in `README.md` ("Measured test state on
this host", 2026-10-29): 189 items execute, 146 passed, 2 skipped, 41 errored,
and the 41 errors are all `tmp_path` fixture setup failures - no assertion is
reached, so no test failure is hidden behind them.

After a run, the affected directories (for example `pytest_tmp_rt` at the
repository root) are no longer listable by the same user (`Get-ChildItem`,
`icacls`: access denied). This was reproduced repeatedly and is why pytest
cannot give a clean summary on this host.

### 6.3 Measurement workaround and the actual test results

To measure the tests that *can* run, without changing any test, oracle, or
application code, `scripts/pytest_rt_report.py` was added as a measurement-only
pytest plugin. It:

1. records every collection/test report to JSON and prints its own summary;
2. replaces pytest's unusable `tmp_path` fixture with a per-test unique empty
   directory under `_scratch/runtime_verification/` (same contract tests expect);
3. tolerates the sandbox's teardown `PermissionError` so the summary is printed.

It does not skip, weaken, reorder, or rewrite any test, and it never converts a
failure into a pass.

Command and result:

```powershell
$env:PYTHONPATH="scripts"
$env:RT_REPORT_PATH="_scratch/runtime_verification/pytest_report_final.json"
$env:RT_TMP_ROOT="_scratch/runtime_verification/pytest_tmp_shim_final"
python -m pytest tests/ -p pytest_rt_report -p no:cacheprovider -q --continue-on-collection-errors
```

Observed result (from the plugin's report JSON and console summary):

```text
collected=189 counts: passed=187, skipped=2, collection_errors=5 pytest_exitstatus=1
```

- 187 tests **passed**;
- 2 tests **skipped**:
  `tests/test_fixture_v3_manifest.py::test_original_is_v0_on_invalid_inputs_if_binary_present`,
  `tests/test_fixture_v3_manifest.py::test_repaired_candidate_matches_v3_if_provided`
  (runtime/guest evidence not provided; skip is not a pass);
- 5 test modules remain uncollectable (13 test functions never executed):
  `test_routea_cave.py`, `test_routea_manifest.py`, `test_routea_worker.py`
  (missing `capstone`), `test_routeb_attempt_writer.py`, `test_routeb_executor.py`
  (missing `pyelftools`);
- pytest exit status is **1**, solely because collection errors count as a
  failure even with `--continue-on-collection-errors`.

Full report: `_scratch/runtime_verification/pytest_report_final.json`.

### 6.4 Recorded claim vs measured state

The task brief said "16 passed, 5 files uncollectable (no capstone/elftools on
Python 3.14)"; the repository's current measured record in `README.md` says
"189 items execute: 146 passed, 2 skipped, 41 errored". Measured on this
worktree at commit `4107836`:

| Source | Statement | Reproduced here? |
|---|---|---|
| task brief | 16 passed | **no** - not reproducible; the same command yields 146 passed, 2 skipped, 41 errored |
| `README.md` (measured 2026-10-29) | 146 passed, 2 skipped, 41 errored, 5 collection errors, no summary | **yes** - exact match (section 6.2) |
| this verification | the 41 errors are all `tmp_path` fixture setup failures; with an equivalent per-test temp directory all 41 pass -> 187 passed, 2 skipped, 5 uncollectable modules, pytest exit 1 from collection errors only | **yes** (section 6.3) |

So the honest current test statement is: 187 of the 189 collected tests pass and
2 are genuinely skipped; 13 test functions in 5 modules never run because
`capstone` and `pyelftools` are not installed; pytest's exit code is 1 because
of those uncollectable modules, not because of a failing assertion. The "16
passed" figure should not be quoted. No test was edited or weakened.

## 7. What is still `not_run`

| Item | State |
|---|---|
| Execution of any uploaded or repaired binary | not_run (forbidden on the host; belongs to the disposable guest) |
| Guest VM broker and six-case runtime manifest | not_run (no guest access) |
| Route A candidate generation (capstone/LIEF based) | not_run (dependencies absent; tests uncollectable) |
| Route B candidate build via Patcherex2 | not_run (patcherex2/angr/z3 absent) |
| V1 structure/placement checks | not_run (only placeholder obligations exist in the tested paths) |
| V2 interface/compatibility checks | not_run |
| V3 concrete behaviour (reproducer, invalid-input oracle, valid-input regression) | not_run; only a synthetic `failed` control was fed to show rejection precedence |
| V4 bounded symbolic security | not_run (no symbolic engine installed) |
| V5 reproducibility / independent replay | not_run |
| Real DeepSeek provider call | not_run in this verification (no API key used; scripts/smoke.py `--mock` path not needed for this task) |
| GUI in HTTP-backend mode against the controller | not_run; advertised but not implemented in `app/main.py` (section 8) |
| `routeb.executor.make_bundle` real bundle | not_run (requires `pyelftools`) |
| Any claim that a repair is verified | **no such claim is made** |

The strongest honest statement supported by this evidence: the controller, GUI
rendering, SQLite schema, acceptance engine, worker and orchestration are wired
together and function on labelled synthetic attempt data; **a real repair has
not been built or verified**, and no evidence exists that the CWE-121 fixture
was fixed.

## 8. Defects and integration gaps observed (not fixed; outside write scope)

These are recorded because they affect how the claimed integration should be
described, not patched here.

1. **`GET /jobs` is not a screen (405), and `/` is a 303 redirect.** The task
   expected both to return 200. The real screens are `/jobs/new`,
   `/jobs/{id}`, `/jobs/{id}/evidence`; all three render 200.
2. **The GUI's HTTP-backend mode does not exist in code.** `README.md` and
   `docs/controller-integration.md` describe `BINARYREPAIR_BACKEND=http` /
   `BINARYREPAIR_API_BASE`, but a repository-wide search finds no code
   reference outside comments/docs: `app/main.py` is a demo-only app
   (`DEMO = True`) backed by the in-memory `app/demo.py`. The browser GUI was
   therefore verified for rendering only; the real controller was verified
   directly over HTTP. Wiring the GUI to the controller is still open work.
3. **`GET /api/attempts/{id}/evidence` does not serve persisted evidence.**
   `app/controller_api.py` returns `_obligations()`, a static placeholder list
   where V0 is always `passed` and V1-V5 are always `not_run`, for both routes,
   regardless of the rows in the `obligations` table. The demo reads the real
   persisted rows from `GET /api/jobs/{id}` instead. This endpoint must be
   rewired before it can be cited as evidence.
4. **Snapshot `route.verification` becomes `"unknown"` for mixed results.**
   With results `{passed, not_run}` the set comparison in
   `app/controller_api.py::_snapshot` falls through to `"unknown"`. It is not
   dishonest (nothing says `passed`), but the UI vocabulary is less precise than
   the engine's `inconclusive`.
5. **Two run-start paths, two approval checks.** `/api/jobs/{id}/start` checks
   the `meta.json` approval revision/hash, while the canonical
   `/api/jobs/{id}/runs` only checks that a persisted contract row exists. Both
   reject a never-approved job with 409 (measured), but the canonical route does
   not re-validate approval freshness itself.
6. **pytest temporary-directory handling is broken in this sandbox** (section
   6.2). This affects every developer on this Windows host and should be fixed
   in the test harness or by running tests in a POSIX environment; it is not a
   product-code defect.

## 9. Reproduction commands (exact)

```powershell
# environment
python --version
python -c "import fastapi, uvicorn, jinja2, httpx, pydantic, jsonschema, pytest; print(fastapi.__version__, uvicorn.__version__)"

# fresh database
python -m app.db.migrate --db _scratch/runtime_verification/data_boot
python -m app.db.migrate --db _scratch/runtime_verification/data_boot   # idempotent

# GUI boot (background job), then probe
python -m uvicorn app.main:app --host 127.0.0.1 --port 18123 --log-level info

# controller boot (background job), then probe
$env:BINARYREPAIR_DATA_DIR = "_scratch/runtime_verification/data_boot"
python -m uvicorn app.controller_api:app --host 127.0.0.1 --port 18124 --log-level info

# end-to-end synthetic demo (fresh data dir is created automatically)
python scripts/demo_e2e.py

# test suite: baseline command (stops at collection on this host)
New-Item -ItemType Directory -Force -Path pytest_tmp_rt | Out-Null
python -m pytest tests/ --basetemp=pytest_tmp_rt -p no:cacheprovider -q

# test suite: measurement run with the sandbox workaround
$env:PYTHONPATH = "scripts"
$env:RT_REPORT_PATH = "_scratch/runtime_verification/pytest_report_final.json"
$env:RT_TMP_ROOT = "_scratch/runtime_verification/pytest_tmp_shim_final"
python -m pytest tests/ -p pytest_rt_report -p no:cacheprovider -q --continue-on-collection-errors
```

Raw console transcripts and machine-readable reports are kept under
`_scratch/runtime_verification/` (untracked runtime artifacts):
`pytest_run1.txt` (baseline interrupted run), `pytest_run2_continue.txt`,
`pytest_with_report.txt`, `pytest_report.json` (default-temp run report),
`pytest_final.txt`, `pytest_report_final.json`, `demo_e2e_final.txt`,
`data_boot/` (SQLite database).

## 10. Verdict

- The integrated slice **runs** on this Windows host: database migration, GUI
  boot with three rendering screens, controller boot with real HTTP + SQLite,
  and the full synthetic controller lifecycle all worked and were measured.
- The deterministic acceptance engine behaves honestly on the synthetic data:
  incomplete evidence -> `inconclusive` (`required_check_not_run`), failed
  required check -> `rejected` (`regression_failed`); nothing absent was ever
  reported as `passed`.
- A **real repair and its verification remain not_run**. Gate 3/Gate 4 status
  should stay "in progress / not run" until guest execution and real candidate
  checks are attached.
- The GUI-to-controller HTTP adapter and the canonical attempt-evidence endpoint
  are visible integration gaps that should be fixed before the integration is
  described as complete.
