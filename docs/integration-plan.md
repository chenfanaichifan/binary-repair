# Integration plan: GUI ↔ controller ↔ workers

Status: P0 is complete (GUI `http` mode against Member 1's controller API; real
job creation, approval, start and polling, `demo:false`). The remaining gap is
the execution pipeline: a job currently stays at `queued` because no worker
consumes the run. This document records the handoffs received from Members 3
and 5, what the GUI will consume, and what is still blocked.

## What is available now

### Member 3 — Route A fixture and verification kit

| Item | Value / path (in `origin/main`) |
|---|---|
| Sample ELF | `fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf` (26,792 B) |
| Sample SHA-256 | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| Candidate path | `routea/out/cave-probe.elf` in tag `controller-api-2026-10-22` (commit `1826505`); 26,792 B, verified SHA-256 `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` |
| Candidate artifacts in tag | `routea/out/audit.json`, `edit-manifest.json`, `manifest-repaired.json`, `readelf-audit.txt`, `runtime.log` (bundle not available locally) |
| Candidate rebuild | `python3 regen_c4a159.py original.elf out.elf` (hash-gated) |
| Contract hash | `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37` |
| Expected result | original 4/6 valid; candidate 6/6 (invalid 50/100 exit 1, stdout empty, exact stderr) |
| Execution environment | Guest Ubuntu 24.04.5, `/opt/angr-venv/bin/python`, JDK 21, GHIDRA_HOME, clang 18.1.3, no network |
| Current entry point | `jobwrap gate3 patched all` (verification harness, not a general worker) |
| Proposed worker (NOT implemented) | `workers/route_a/worker.py` — ownership: **Member 3 + Member 1**; `jobwrap routea` op — ownership: **VMer + Member 3** |

Proposed output contract for `<job_dir>/route_a/`:

- `candidate.elf` — repaired candidate
- `edit-manifest.json` — schema 2: original/candidate hash, changed/added
  regions, header before/after, displaced bytes, detour, writer, termination,
  tool versions
- `audit.json` — segment map, NX/RELRO/canary/W^X, readelf/LIEF summary
- `readelf-audit.txt` — raw `readelf -l/-S/-d`
- `route_a.log` — commands, exit codes, tool versions
- `status.json` — phase / reason_code / candidate_sha256 / evidence[];
  **v1 has no `outcome` field**; the final outcome lives in `decision.json`
  produced by the acceptance step.

### Member 5 — Provider, candidate schema, Route B artifacts

Provider entry: `binaryrepair_ai/provider.py`, thin wrapper
`app/services/provider.py`. `Settings.from_env()` loads `.env`; env overrides.

Required env (host only; never in the guest, logs or browser):

| Variable | Default | Meaning |
|---|---|---|
| `DEEPSEEK_API_KEY` | required for real calls | host provider process only |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | outbound HTTPS needed |
| `DEEPSEEK_MODEL` | `deepseek-flash` | actual returned version in `record.model_returned` |
| `DEEPSEEK_THINKING` | `disabled` | thinking mode costs more |
| `DEEPSEEK_TIMEOUT_S` | `120` | per attempt |
| `DEEPSEEK_MAX_RETRIES` | `1` | up to 2 attempts; only timeout/network/5xx retried |
| `DEEPSEEK_MAX_OUTPUT_TOKENS` | `4000` | single output cap |
| `BINARYREPAIR_AI_BUDGET_USD` | `2.0` | worst-case pre-check before calling |
| `BINARYREPAIR_MODEL_LOG` | `var/model_calls.jsonl` | call record JSONL |
| `BINARYREPAIR_STORE_RAW` | `0` | persist raw response |

- Provider is **synchronous/blocking**; call it in `run_in_threadpool` or a
  dedicated worker, never directly in an async route.
- Worst-case attempt time ≈ 240 s + backoff, so controller job timeout must be
  larger (or cancellation must be wired).
- Failures are values, not exceptions: `ProviderResult.ok` / `.failure`
  (`ProviderFailure` with stable `reason_code`, `CandidateRejected` for
  schema/identity/scope violations).
- Mock path for demos: `scripts/smoke.py --mock` (no network/key/cost) and
  `FakeTransport` in provider tests. The GUI itself must not call the provider;
  the demo AI card should be injected mock data, clearly labelled.
- Candidate v1 schema (`binaryrepair_ai/schemas.py`): 14 fields, extra=forbid,
  `schema_version=1`, route `route_a|route_b`; identity hashes
  (`original/contract/analysis`), scope (`target_entry`, `evidence_ids`),
  Route A `template_id` + `parameters`, Route B `recovered_function_sha256` +
  `replacement_c`, plus `expected_effects`, `assumptions`, `uncertainties`.
  Validation: `validate_candidate()` and `validate_candidate_for_context()`.
- Route B artifacts: `routeb/ghidra/export.sh <binary> <function> [outdir]` →
  `<function>.c` + `.meta.txt`; roundtrip via
  `routeb/probe_patcherex2.py --mode roundtrip --skip-verify` → `roundtrip.elf`;
  Gate 4 manifest compare via `routeb/run_manifest_compare.py` (6/6 cases,
  `gate4_pass=true`); repaired checks via `routeb/run_manifest_repaired.py`.
  These files already exist in `origin/main` under `routeb/out/gate4/`, but the
  formal Gate 4 state remains NOT RUN (no guest access).

## What the GUI needs from the pipeline

| GUI surface | Source of truth | Current state |
|---|---|---|
| Job phase / routes / stages | controller snapshot (`GET /api/jobs/{id}`) | works; stays `queued` until worker exists |
| V0–V5 obligations | controller `GET /api/jobs/{id}/obligations` | placeholder `not_run` |
| Artifacts (candidate, manifest, audit, logs) | controller `GET /api/jobs/{id}/artifacts` | empty |
| Code view (disassembly / recovered C / AI candidate) | controller `GET /api/jobs/{id}/visuals` | `available:false` |
| Evidence page details | obligations + artifacts + export | renders empty honestly |
| AI candidate card | Candidate v1 fields (via attempt evidence) | synthetic demo card only |

Required snapshot/contract shape is documented in
`docs/controller-integration.md`. All payload strings must stay English ASCII;
the GUI rejects non-ASCII controller payloads with `502`.

## Member 1 status (2026-10-22, worker commit)

- Controller + worker live at `origin/main` commit `ad1a1f8`; the published tag
  `controller-api-2026-10-22` (`1826505`) predates the worker, so
  `start-controller.ps1` pins `ad1a1f8` until Member 1 tags the worker commit.
- Worker command: `python -m app.services.worker --data-dir <abs> --once`.
  Verified: it consumes queued runs, moves phases to `screening`/`analyzing`,
  and **does not execute binaries**. It needs one result bundle per attempt at
  `<data>/jobs/<job>/runs/<run>/attempts/<attempt>.json` (schema in the worker
  docstring) or an executor command in `BINARYREPAIR_ATTEMPT_CMD`.
- Without a bundle it prints `has no result bundle yet` and the run stays at
  `screening`; no verdict is invented.
- With bundles it persists V0–V5 obligations and calls
  `orchestration.evaluate_attempt` / `evaluate_run`.
- `app/controller_api.py` is unchanged in `ad1a1f8`: snapshot routes remain
  placeholders and `/obligations` is still static, so the API cannot surface a
  consumed bundle's verdict yet (controller TODO).
- Same idempotency key with a different contract must return `409`; canonical
  check still pending.

`tools/p2_acceptance.py` now supports a one-shot worker:
`--worker-command "<python> -m app.services.worker --data-dir <abs> --once"`.
Live result: `BLOCKED phase='screening'` (no result bundle), exit 2.

## Blockers and owners

| # | Blocker | Owner | What is needed |
|---|---|---|---|
| 1 | Worker exists but nothing produces attempt result bundles (no Route A/B executor) | Member 3 + VMer (+ Member 5) | implement `jobwrap routea`/Route A worker and Route B/provider executor that write the per-attempt result bundle; worker then persists verdicts |
| 2 | No Route A worker (`workers/route_a/worker.py` is proposed only) | Member 3 + Member 1 | implement worker; VMer + Member 3 implement the fixed `jobwrap routea` op; publish the candidate bundle (candidate itself is already in tag `1826505` under `routea/out/`) |
| 3 | No broker/jobwrap integration for the general route-a op | Member 1 | broker API, fixed op/argv, guest path conventions; never pass shell strings |
| 4 | Controller API does not expose attempts/obligations/verdicts (unchanged in `ad1a1f8`) | Member 1 | snapshot routes from attempts, obligations endpoint from persisted rows, verdict fields (`outcome/reason/failing_obligation/detail`) |
| 5 | Provider not called by any worker | Member 1 (+ Member 5) | host-side provider step in orchestration; which env/process; where candidate/attempt evidence is stored; timeout budget alignment |
| 6 | Route B artifacts not imported into job artifacts | Member 1 / Member 5 | artifact import paths + hashes; Gate 4 manifest-compare fields exposed to evidence page |

## Exact asks (reply format)

### Member 1

1. Worker/orchestration command + env; which process consumes runs; is it a loop,
   a subprocess per attempt, or a controller background task?
2. `jobwrap routea` fixed op spec + broker request/response; how status.json,
   artifacts and evidence are imported; phase update rules.
3. Run timeout/cancel semantics (must exceed ~240 s provider worst case).
4. Does the orchestration worker call the provider on the host (and where the
   Candidate is persisted)? Which table/endpoint exposes attempt evidence?
5. Stable controller ref: should the launcher pin a tag/commit instead of
   `origin/main`? (Currently `start-controller.ps1` follows `origin/main`.)

### Member 4

1. Acceptance engine entry (`evaluate_attempt` / `evaluate_run`) and exact
   input objects; who calls them and when.
2. Verdict schema and how V0–V5 results, scope and reason reach the snapshot /
   obligations endpoint.
3. One success fixture and one failure fixture (inputs + expected verdict) so
   the GUI can assert honest outcomes end-to-end.
4. Who writes `outcome` (acceptance engine vs controller) and how cancellation
   is represented.

### Member 3

1. Confirm the `workers/route_a/worker.py` + `jobwrap routea` implementation plan
   (ownership: Member 3 + Member 1; VMer + Member 3) and the target date.
2. Confirm `status.json` v1 (no `outcome`) and the `decision.json` handoff to the
   acceptance step; who writes each file.
3. Candidate is verified in tag `1826505` at `routea/out/cave-probe.elf`
   (SHA-256 `c4a159…aa82`); confirm whether the full bundle (routea/out/*) should
   be imported into job artifacts by the worker.

### Member 5

1. Confirm Candidate v1 schema commit/tag and `.env.example` location.
2. Confirm provider is called only by the host orchestration worker; how
   provider failures map to attempt evidence shown in the GUI.
3. Which Route B artifacts (roundtrip.elf, manifest-compare.json, repaired
   cases) should be imported and displayed, and by whom.

## Integration sequence

1. Member 1 exposes worker entry; Member 3 provides the route-a op and worker.
2. Run the sample in the guest; controller phase goes `queued → running →
   screening → ...`; `status.json`/artifacts land in the job directory.
3. Member 4 evaluates V0–V5; controller persists the verdict; obligations and
   artifacts endpoints stop being placeholders.
4. GUI starts showing real code views, obligations, artifacts, and final
   outcomes; extend `tools/p0_acceptance.py` with a P2 path that asserts a real
   run reaches `finished` with an honest outcome.
5. Only then update the proposal/screenshots; never label `queued` or `not_run`
   as success.

## Demo boundary (unchanged)

- `mock` mode: synthetic fixtures, labelled demo data.
- `http` mode: real controller store, `demo:false`; execution stays `queued`
  until the blockers above are resolved.
- AI candidate card in the current GUI is synthetic and must remain labelled;
  Member 5's mock provider result should replace it once injected by the worker.
