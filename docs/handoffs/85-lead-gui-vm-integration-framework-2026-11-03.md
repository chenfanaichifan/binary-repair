# 85 — Lead task framework: GUI ↔ controller ↔ guest execution (staged ingest)

**From:** Lead
**To:** M1, M2, M3, M4, M5, VMer
**Date:** 2026-11-03 (Asia/Shanghai)
**Status:** decision record + task framework. Implements nothing, changes no gate
status. It fixes the missing link between the GUI and real guest execution with
one protocol, one owner per component, and honest acceptance.
**Companion document:** `docs/interfaces/execution-bridge-v1.md`.

**Numbering note:** this record is 85 because `83-worker-executor-env-contract.md`
already exists on the post-final branch; 84 is reserved for the M4 host-importer
verification row (`80-m4-host-importer-broker-1da22ff.md` in the working tree —
that file must be renumbered 84 when committed). This record replaces the
earlier 2026-11-03 draft that used number 83.

---

## 0. The problem in one paragraph

The GUI, controller, SQLite job store, acceptance engine and Route A/B tools all
exist and are honest. What is still missing is the middle: nothing *executes* a
job in the guest and nothing converts the guest's raw evidence into the
per-attempt bundle with **registered artifact ids** that
`app/services/worker.py` requires. The host ingestion half now exists
(`tools/host_importer.py`, `tools/host_broker.py`), and the worker now injects
verified original/contract paths for an executor
(`BINARYREPAIR_ORIGINAL`, `BINARYREPAIR_CONTRACT`), but no executor consumes
those inputs, nothing produces the guest bundle/artifacts, and the
controller/GUI still cannot show or download real evidence. That is why the
product still reads as a demo.

## 1. Baseline decision (D0) — which line we continue on

There are two divergent lines in this repository:

| Line | Head | Contents |
|---|---|---|
| This local worktree | `integration/consolidation-2026-10-29` @ `5be0e70` | Lead records 79–82 as separate files; no `workers/`, no `INTERFACE-v1`, no host importer, old worker |
| Post-final line | `origin/post-final/host-importer-broker` @ `1da22ff` (tag `mvp-2026-10-31` at `472aa94` is an ancestor) | tagged MVP lineage, recovered `workers/route_a/*` + `docs/handoffs/INTERFACE-v1.md`, `expected_sha256` fix (`9407dfc`/`1406f11`), worker executor env injection (`63b6eb8`), adapter env consumption (`84af51b`, `a9196d9`), host importer/inbox broker (`1da22ff`), updated `tools/p2_acceptance.py` |

**Decision D0: the live-bridge work continues on the post-final line.** Create
one branch from `origin/post-final/host-importer-broker` (suggested name:
`integration/live-bridge-2026-11-03`) and carry this record plus
`docs/interfaces/execution-bridge-v1.md` onto it. Do not merge the two lines
wholesale: this worktree's records 80/81/82 already exist in the post-final
lineage under the same names (`fcbb6e6`, `753c097`), so the local copies are
redundant and must not be re-added as new records.

The rest of this document uses that baseline. Everything below is measured
against `1da22ff` unless stated otherwise.

## 2. Gap inventory on the post-final baseline

| # | State | Gap |
|---|---|---|
| G1 | OPEN | No guest executor: nothing consumes `BINARYREPAIR_ORIGINAL`/`BINARYREPAIR_CONTRACT` and runs the frozen fixture pipeline inside the guest; `workers/route_a/worker.py` exists but builds a supplied candidate and does not execute anything |
| G2 | OPEN | No staged job package: the host never stages `job.json` + original + contract + tests for the guest, and the guest has no output location |
| G3 | OPEN | No ingest adapter: `tools/host_importer.py` imports an *already-mapped* attempt bundle and triggers the worker, but nothing verifies the guest result bundle, registers its artifacts, or maps gates to artifact ids (G4 of the old draft) |
| G4 | PARTIAL | `tools/host_importer.py` trusts `bundle_path` and the envelope; it does not enforce path confinement, symlink rejection, size caps or unexpected-file rejection |
| G5 | OPEN | Controller read surface: `B` artifacts hardcoded empty, no artifact download, `visuals` unavailable (`app/controller_api.py:704-726`) |
| G6 | OPEN | GUI live states: no broker/executor status, no real code view, browser e2e still pins the legacy bridge text (`tests/e2e/conftest.py:114-118`, `tests/e2e/test_gui_journey.py:98-121`) |
| G7 | OPEN | AI repair is not wired into any job: the provider is only called by `scripts/demo_candidate.py` |
| G8 | RESOLVED on baseline | `expected_sha256` semantics fixed (`9407dfc`/`1406f11`); keep the regression tests |
| G9 | RESOLVED on baseline | `workers/route_a/*` and `docs/handoffs/INTERFACE-v1.md` are present; reuse, do not rewrite |
| G10 | RESOLVED on baseline | Host ingestion tools exist; extend them rather than inventing a second transport |
| G11 | OPEN | GUI contract (4 free-text fields) is not the fixture `SecurityContract` v2 that this pipeline validates; the job must be bound to the frozen contract (`fixtures/public/.../contract.json`) |
| G12 | OPEN | No guest staging mount / snapshot-reset protocol is decided (`docs_BinaryRepair/TechDesign-BinaryRepair-MVP.md:87` requires a dedicated staging mechanism) |
| G13 | OPEN | Record compliance: p2 remains the real-pipeline gate and currently cannot pass without a guest job; no "live" claim before that |

Not a gap any more: the GUI rendering layer, the acceptance engine, the SQLite
store, and the result-bundle schema. Do not rewrite them.

## 3. Lead decisions (2026-11-03)

**D1 — Transport approved: staged inbox/outbox, host ingest.** The guest writes
only regular files into a dedicated host-visible staging directory; the host
polls and ingests them. The guest never opens a network connection, never calls
the controller, never mounts a host home directory, and never holds
`DEEPSEEK_API_KEY`. The host stages the job package (inbox) and owns the
outbox reader. This is the "dedicated staging mechanism" of
`TechDesign-BinaryRepair-MVP.md:87`, implemented by the existing
`tools/host_broker.py`/`tools/host_importer.py` plus one new ingest adapter.
A pull-over-HTTP guest service is *not* adopted; if a future requirement needs
it, it becomes a new interface version.

**D2 — v1 scope is the frozen public fixture only.** Original
`aa428157…8393`, contract `24bfe568…4e37`, Route A candidate `c4a159…aa82`,
Route B candidate `208574ab…6717`, manifest set `a564f039…3a78`. Any other
upload ends as `unsupported/unsupported_profile`; "repair arbitrary ELF" is
research.

**D3 — AI stays host-side; AI-driven repair is required, not optional.**
The trusted host provider proposes the repair (`replacement_c` for Route B,
template parameters for Route A) under the existing `CandidateV1` schema; the
guest builds/tests it; the same V0–V5 ladder decides the outcome. The frozen
deterministic candidate is only the first proof of the execution loop, not the
final product behavior. The **assistant conversation planner** is a separate
LLM use (record 86 §1a): it writes guidance only and is reserved behind a
deterministic v1; it never approves, starts runs or writes a verdict.

**D4 — Reuse the delivered host tools.** Extend `tools/host_importer.py` and
`tools/host_broker.py`; do not build a second ingestion path. Harden them per
`docs/interfaces/execution-bridge-v1.md` and keep the atomic/idempotent/
fail-closed guarantees verified by `tests/integration/test_host_broker.py`.

**D5 — `tools/p2_acceptance.py` stays the pipeline gate.** Live means p2 exit 0
against a guest-produced job with `demo: false` and six persisted obligations
per attempt. A fake guest or hand-written bundle proves wiring only.

**D6 — Conventions.** English ASCII for exchange data, LF, lowercase 64-hex
SHA-256, relative paths with `/`, no BOM. The language-policy tests and the CJK
scan in `HttpBackend` stay in force.

**D7 — No gate status changes.** Gate 4 PASS, Gate 5 A/B PASS, V4 model-level
PASS and the fixture freeze are not reopened. This work may reuse frozen
evidence by candidate-hash binding only.

**D8 — Evidence binding.** If the live pipeline reproduces a frozen candidate
byte-for-byte, frozen V4/V5 evidence may be referenced with its original hash
and provenance. Different bytes → `not_run` for that candidate.

**D9 — Record numbering.** This record is 85; the untracked
`80-m4-host-importer-broker-1da22ff.md` is 84. Fixed assignments: **86 = agent-style
GUI redesign** (`docs/handoffs/86-lead-agent-gui-redesign-2026-11-03.md`),
**87 = per-person task assignment** (`docs/handoffs/87-lead-task-assignment-2026-11-03.md`),
**88 = VMer staging note**, **89 = M4 live-loop verifier row**. Do not reuse
numbers already present on the baseline (`83-worker-executor-env-contract.md`).

## 4. Target architecture

```text
 Browser
   |  loopback HTTP + session token/CSRF
   v
 GUI (app.main:8123) .................. renders only, never decides
   |  loopback HTTP
   v
 Controller (app.controller_api:8000) .. SQLite, approvals, artifacts, acceptance
   |  queued runs
   v
 Worker (app.services.worker) .......... injects BINARYREPAIR_ORIGINAL/CONTRACT,
   |  BINARYREPAIR_ATTEMPT_CMD            spawns the executor command per attempt
   v
 Guest executor wrapper (new) .......... host-side command OR host-side driver
   |  staged inbox -> guest -> outbox    (staging directory; no network from guest)
   v
 jobwrap (root launcher) + job netns ... uid 1003, caps 0, no_new_privs, rlimits
   |
   +--> Route A: build frozen candidate + static audit
   +--> Route B: build from replacement_c (M2) or frozen candidate + audit
   +--> behaviour: six frozen cases under isolation
   +--> package: result-bundle.json + artifacts/ + SHA256SUMS
   |
   v  host polls outbox
 Ingest adapter (new) ................. verify hashes/paths/sizes, reject symlinks,
   |                                     register artifacts, map gates -> artifact ids
   v
 tools/host_importer.import_bundle() .. atomic write + worker.run_once()
   |
   v
 Worker -> acceptance engine -> controller snapshot -> GUI
```

Trust zones: host-trusted = GUI, controller, worker, ingest adapter, importer,
provider process, acceptance engine. Guest-untrusted = executor, jobwrap, route
workers, candidates, model-generated C. The acceptance engine is the only
outcome writer.

## 5. Work packages

| ID | Work package | Owner | Dep | Deliverable | Acceptance |
|---|---|---|---|---|---|
| T6.0 | Baseline migration + carry records: branch from post-final head, add note 85 + interface v1, confirm existing fixes/tests | **M1** | D0 | `integration/live-bridge-2026-11-03`; records 84/85 carried | branch ancestry from `1da22ff`; acceptance 29/29; host-broker 2/2 |
| T6.1 | Ingest adapter + harden host importer/broker: verify guest bundle and hashes, register artifacts, map gates → artifact ids, confine paths, reject symlinks/unexpected files | **M5** | T6.0, protocol v1 | new `tools/route_bundle_ingest.py` (+ `app/services/artifact_registry.py` if needed); hardened `tools/host_importer.py` | unit tests: pass→artifact id resolvable; tampered hash/traversal/symlink/extra file → no bundle written |
| T6.2 | Guest executor + jobwrap op: consume staged package, run frozen fixture pipeline under isolation, write bundle + artifacts + SHA256SUMS to outbox | **M3** (+**VMer**) | T6.0, protocol v1 | new `workers/executor/` (`run_job.py`, `README.md`, `self_test.py`); jobwrap fixed op | host-safe self-test; in-guest conformance: bundle hashes + isolation attestation |
| T6.3 | Controller read surface: real artifacts list/download, real visuals, executor status in snapshot | **M1** | T6.0 | `app/controller_api.py` endpoints + tests | tests + curl bytes/hash equality; no invented artifacts |
| T6.4 | GUI live states + real code view + artifact links; repoint e2e fixture to canonical controller | **M2** | T6.3 shapes | templates/JS + tests | offline executor shows explicit unavailable; no success without verdict |
| T6.5 | Protocol conformance + staging safety: staging dir layout/permissions, envelope schema, path/size/symlink rules, idempotency | **M5** | T6.1 | `docs/interfaces/execution-bridge-v1.md` enforced by tests | reject-list tests in T6.1 self-test |
| T6.6 | AI proposal step (Milestone 2): host `ai_repair` calls provider with guest analysis, validates `CandidateV1`, stages only `replacement_c` | **M5** + **M1** | T6.2, T6.3 | `app/services/ai_repair.py` + tests | fake-provider tests; missing key → honest error; no key/raw prompt in logs |
| T6.7 | Independent verification of the live loop | **M4** | T6.2, T6.5 | verifier row 89 | p2 exit 0 on guest job; obligations exactly V0–V5; hashes recomputed |
| T6.8 | VM staging: shared staging mount/directory, permissions, snapshot reset, one-window request format | **VMer** | D1 | VM runbook note + evidence dir | host reads outbox; guest has no network; reset leaves no artifacts |

## 6. Task cards (detail)

### T6.0 — Baseline migration (M1)

1. `git fetch`; create `integration/live-bridge-2026-11-03` from
   `origin/post-final/host-importer-broker` (`1da22ff`).
2. Add `docs/handoffs/85-lead-gui-vm-integration-framework-2026-11-03.md` (this
   file), `docs/interfaces/execution-bridge-v1.md`, and the renumbered M4 row
   (84) when its owner commits it.
3. Confirm the baseline fixes are present: `expected_sha256=None` in
   `evaluate_attempt`, worker `BINARYREPAIR_ORIGINAL`/`BINARYREPAIR_CONTRACT`
   injection, host importer/broker tests.
4. Record observed commands and lines; do not re-add the divergent local records
   80/81/82 — they already exist in this lineage.

### T6.1 — Ingest adapter + hardening (M5)

Goal: turn `result-bundle.json` + `artifacts/` from the outbox into a worker
bundle whose evidence map uses real artifact ids.

1. Validate the guest bundle against `docs/interfaces/execution-bridge-v1.md`
   (required fields, six gates, status enum, candidate hash, bundle hash).
2. For each artifact: reject `..`, absolute paths, non-regular files, symlinks,
   unexpected names, oversize bytes; accept only files listed in the bundle;
   recompute SHA-256 and compare.
3. Register each artifact in the `artifacts` table (job id, role, sha256,
   size_bytes, relative path) and collect ids.
4. Map gates: `pass→passed`, `fail→failed`, `not_run→not_run`,
   `inconclusive→unknown`, `unsupported→unknown`; `evidence` = artifact id per
   passed V1–V5; V0 may fall back to the original artifact.
5. Write the attempt bundle via `tools/host_importer.import_bundle(...)`; never
   write a partial bundle on failure.
6. Harden the importer/broker: `bundle_path` must stay under the configured
   outbox; reject symlinks; size caps; envelope strict schema; keep atomicity,
   idempotency and conflict-rejection. Keep the existing 2 tests green and add
   negative tests.

### T6.2 — Guest executor (M3 + VMer)

1. `workers/executor/run_job.py`: reads the staged package
   (`<staging>/inbox/<job_id>/job.json`, `original.elf`, `contract.json`,
   `tests/valid.json`, `tests/invalid.json`), verifies the staged hashes, runs
   the fixed fixture route steps, and writes
   `<staging>/outbox/<job_id>/<run_id>/<attempt_id>/{result-bundle.json,artifacts/,SHA256SUMS}`.
2. Route A: `routea.worker`/`routea.cave` build of the frozen candidate + static
   audit + readelf. Route B Milestone 2: `routeb.executor` from staged
   `replacement_c`; Milestone 1 uses the frozen candidate and records
   `ai_usage: not_run`.
3. Behaviour: `routeb/run_manifest_compare.py` six frozen cases **in the guest**
   under jobwrap isolation; capture raw rc/stdout/stderr.
4. Package the bundle exactly as the interface doc defines; no outcome field.
5. `workers/executor/self_test.py`: host-safe (argument/hash/schema failures);
   in-guest conformance script that proves isolation and hash-bound artefacts.
6. VMer: jobwrap fixed operation `executor <job_id>` with root-owned config,
   fixed argv, netns/uid/caps/no_new_privs/rlimits/clearenv; staging mounted
   read-only into the job where possible.

### T6.3 — Controller read surface (M1)

1. `GET /api/jobs/{id}/artifacts` → both routes from the `artifacts` table with
   ids, roles, hashes, sizes. No placeholders.
2. `GET /api/jobs/{id}/artifacts/{artifact_id}` → exact regular-file bytes;
   resolve under the job dir; reject symlinks/non-regular; ASCII filename.
3. `GET /api/jobs/{id}/visuals` → real payload in the `app/visuals.py` schema
   when artifacts exist; otherwise `available:false` with a reason.
4. Snapshot: `execution` reflects the last executor/ingest state from a status
   sidecar; never a broker call per request.
5. Keep the "no invented passed" pin in
   `tests/integration/test_controller_api.py:218-229`.

### T6.4 — GUI live states (M2)

1. Setup: show execution environment (executor/staging available or not) and
   the fixture-only scope note; never a Start button that implies impossible
   execution without saying why.
2. Comparison: execution badge, real stage changes from the snapshot, decoded
   error reasons, real code view when available.
3. Evidence: artifact table + download link + persisted V0–V5 rows.
4. Repoint `tests/e2e/conftest.py:114-128` to `app.controller_api:app`; replace
   the pinned "Execution is not implemented" text with the honest live state
   (queued/no verdict, or explicit unavailable). Keep no-success assertions.
5. ASCII exchange data; Chinese only in templates/i18n.

### T6.5 — Protocol conformance (M5)

Enforce the staging layout, envelope schema, path/size/symlink rules and
idempotency from the interface doc with tests. Update
`docs/handoffs/INTERFACE-v1.md` only if a schema change is unavoidable — then it
becomes v2 with a changelog line and notification to M3/M4/Lead.

### T6.6 — AI proposal (Milestone 2, M5 + M1)

`app/services/ai_repair.py`: request from guest analysis (recovered C, contract,
limits), call `binaryrepair_ai`, validate `CandidateV1`, stage only
`replacement_c`; typed failures (`provider_failed`, `unsupported`); record
`model_calls`; never a fake candidate or pass.

### T6.7 — Independent verification (M4)

p2 exit 0 on a guest job; `demo:false`; six obligation kinds per attempt;
artifact bytes/hashes independently recomputed; bundle hashes stable; no
`outcome` in a bundle; isolation attestation; token/key absence; snapshot reset.
PASS/FAIL/NOT VERIFIED only.

### T6.8 — VM staging (VMer)

Decide and record: staging directory (shared-folder path or scp target),
permissions (guest uid 1003 write only to outbox; inbox read-only), snapshot to
reset after each job, and the one-window request format. Verify host reads
outbox, guest has no egress during a job, reset leaves no artifacts.

## 7. Milestones

| Milestone | Content | Entry | Exit |
|---|---|---|---|
| **M0** | T6.0, T6.1, T6.3 host-only; T6.2 self-test | D0/D1 | ingest adapter turns a synthetic guest bundle into a worker bundle with artifact ids; no invented pass; tests green |
| **M1** | T6.2 guest conformance, T6.5, T6.4, T6.8 | M0 + staging window | guest fixture job → p2 exit 0; GUI shows real evidence |
| **M2** | T6.6 | M1 | provider proposes candidate; guest validates; failures honest |
| **M3** | arbitrary ELF | new record | out of scope |

## 8. Verification matrix

| Check | Where | Command | State |
|---|---|---|---|
| Acceptance | host | `python -m pytest tests/unit/test_acceptance.py` | 29 passed (remeasured 2026-11-03) |
| Host ingestion | host | `python -m pytest tests/integration/test_host_broker.py` | 2 passed on `1da22ff` (M4 row, targeted) |
| Ingest adapter | host | new `tests/integration/test_route_bundle_ingest.py` | missing |
| Guest executor self-test | host | `python workers/executor/self_test.py` | missing |
| Real pipeline | **guest host** | `python tools/p2_acceptance.py --job-id <id>` | BLOCKED exit 2 |
| GUI honesty | host | `pytest tests/e2e tests/test_status_honesty.py tests/test_language_policy.py` | e2e pins legacy bridge |

**This Windows host cannot run guest checks**: no VMware/VirtualBox, no
`192.168.x` interface, no WSL/Docker, no `.venv`, no `D:\VMs`. M0 is verifiable
here; M1/M2 evidence must come from the VM host and be labelled with host,
commit and command.

### What the leader can show today (verified 2026-11-03)

Canonical controller + GUI in `http` mode gives a real, non-demo job: upload the
fixture → approve → Start returns `202 queued`, snapshot `demo:false`,
`execution: queued`, both routes `queued`, `verdict:null`,
`visuals.available:false`, artifacts list only the original, GUI shows no demo
banner and "no conclusion yet". With a worker running the run falls back to
`screening` and still never finishes. **That queued/never-finished state is the
gap this framework closes — not a GUI defect.**

## 9. Leader's next actions (48 hours)

1. Accept or amend D0–D9 in this record.
2. Tell M1 to create the branch from `origin/post-final/host-importer-broker`
   and carry records 84/85; nothing else can succeed before that baseline is fixed.
3. Give M5 the T6.1 card first (host-only, testable today); M3 starts T6.2's
   host-safe self-test with the VMer staging window as the only blocker.
4. Ask VMer for the T6.8 staging note (path, permissions, snapshot, window
   format); record it as 88.
5. Keep `main` runnable: the live path stays opt-in via
   `BINARYREPAIR_ATTEMPT_CMD`; p2 stays BLOCKED until a guest job exists.
6. No live-MVP tag and no gate flip before T6.7 has a PASS row.

### Copy-paste task messages

**To M1:** Create `integration/live-bridge-2026-11-03` from
`origin/post-final/host-importer-broker` (`1da22ff`); carry records 84/85
(`docs/handoffs/85-…`, `docs/interfaces/execution-bridge-v1.md`); confirm the
baseline fixes and the host-broker tests. Then take T6.3. Do not re-add the
divergent local records 80/81/82.

**To M5:** Take T6.1 now: verify the guest result bundle, register artifacts,
map gates to artifact ids, harden `tools/host_importer.py`/`host_broker.py`
(path confinement, symlinks, sizes, strict envelope), extend
`tests/integration/test_host_broker.py` with negative cases. T6.6 comes after
M1.

**To M3:** Take T6.2: `workers/executor/run_job.py` for the frozen fixture,
staging inbox/outbox I/O, bundle + artifacts + SHA256SUMS, no outcome field.
Start with `self_test.py` (host-safe); the in-guest conformance run needs
VMer's T6.8 window.

**To M2:** Take T6.4. Repoint `tests/e2e/conftest.py:114-128` to
`app.controller_api:app` and replace the legacy "not implemented" pin with the
honest live state; keep no-success-without-verdict assertions.

**To M4:** Prepare the T6.7 checklist; execute only when a guest-produced p2 job
exists. Also commit your host-importer row as record 84 (it currently uses the
taken number 80).

**To VMer:** Provide T6.8: staging directory and permissions, the snapshot to
reset after each job, and the one-window request format. No API key, no guest
network during a job.

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Two lineages are merged wholesale | D0: branch from post-final; carry only 84/85 |
| "Live" claimed from a fake guest | D5: p2 is the only pipeline gate |
| Guest writes into the controller data dir | D1: staging only; ingest validates paths/symlinks/sizes |
| Artifact ids faked or evidence missing | T6.1 negative tests; worker already rejects |
| Host executes an uploaded binary | forbidden by AGENTS.md; execution only under jobwrap in the guest |
| AI key or prompt leaks | D3/T6.6 host-only provider; log reason codes only |
| Snapshot drift invalidates evidence | T6.8 reset + recorded snapshot id |
| Scope creep to arbitrary ELF | D2 `unsupported` path; new record required |

## 11. Signature

| Role | Name | Date | Decision |
|---|---|---|---|
| Lead | Lead | 2026-11-03 | Framework v2 published against post-final head `1da22ff`; D0–D9 proposed |
| M1 | — | — | pending |
| M2 | — | — | pending |
| M3 | — | — | pending |
| M4 | — | — | pending |
| M5 | — | — | pending |
| VMer | — | — | pending |
