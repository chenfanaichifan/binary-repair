# 87 — Lead task assignment 2026-11-03: who does what next

**From:** Lead
**To:** M1, M2, M3, M4, M5, VMer
**Date:** 2026-11-03 (Asia/Shanghai)
**Status:** assignment record. No code, no gate change.
**Basis:** records `85` (execution bridge), `86` (agent-style GUI), protocol
`docs/interfaces/execution-bridge-v1.md`, baseline `origin/post-final/host-importer-broker`
@ `1da22ff` (record 85 D0).

---

## 0. First, the factual answer: did the previous product do AI-driven repair?

**No.** The repository contains an AI **provider adapter** and a typed candidate
schema, but no product job flow ever called a model to produce a repair:

| What exists | Evidence | Wired into a job? |
|---|---|---|
| `binaryrepair_ai/` provider (DeepSeek client, JSON mode, settings, pricing, typed failures) | `binaryrepair_ai/client.py`, `provider.py`, `schemas.py` | **No** |
| `app/services/provider.py` (typed failure vocabulary) | `app/services/provider.py` | **No** |
| `CandidateV1` Pydantic schema + generated JSON Schema | `binaryrepair_ai/schemas.py`, `schemas/` | Not called in a job |
| The only provider call site | `scripts/demo_candidate.py:30-33,212` | Demo script only |
| Route A / Route B tooling | `routea/worker.py`, `routea/cave.py`, `routeb/executor.py` | No provider import; no model call |
| Accepted candidates (`c4a159…`, `208574ab…`) | Gate 3/4/5 records | Produced by deterministic fixture steps, not by a model call |

So "AI-assisted repair" was **designed and partially built as an adapter**, but
the accepted MVP pipeline is deterministic: Route A applies a reviewed patch
template; Route B builds from a fixed C file. The `binaryrepair_ai` adapter was
never connected to the worker/controller, so the product could not repair a
new defect class with the model. This is a real product gap, not a wording
issue.

**Decision:** AI-driven repair is a required product behavior, not an optional
demo (record 85 D3 amended by this record). The staged route is:

1. prove the execution loop with the frozen candidate (T6/T7 bridge) — fast and
   verifiable;
2. add the **AI repair proposal** (T6.6): provider proposes `replacement_c` /
   template parameters, validated as `CandidateV1`, built and validated in the
   guest by the same V0–V5 ladder;
3. generic repair types (T8.3) after that. A model proposal that produces a
   different candidate must run the full ladder; if V4/V5 cannot run, the honest
   outcome is `inconclusive`, not success.

The **assistant conversation** (record 86 §1a) is a separate LLM use: it writes
guidance/plans only, with a reserved `AssistantPlan` seam and a deterministic v1.
It never approves, starts runs or writes a verdict.

## 1. Assignment rules

- **One owner per layer.** Host backend = M1; data contracts + assistant = M5;
  guest execution = M3; UI = M2; verification = M4; VM operations = VMer.
  Handoffs between layers are the frozen documents, not chat messages.
- **No forced splitting.** If a piece of work belongs to one layer, it goes to
  that one person even if another is idle. Idle time is allowed and recorded;
  it is not filled with invented tasks.
- **Some people have no task for a period.** M4 stays idle until host deliverables
  exist; that is deliberate. M3/VMer are blocked on the VM staging window; M3 can
  still code the executor against the interface.
- **One-owner rule for rework:** if a task bounces, it returns to its owner, not
  to a new person.
- **Lead (you) does not take implementation tasks.** Lead approves, reviews the
  prototype, decides scope, runs the merge/tag and records gates.

## 2. Per-person task table

### M1 — Host backend owner

| Order | Task | Deliverable | Dep | Deadline |
|---|---|---|---|---|
| 1 | T6.0 baseline | branch from `origin/post-final/host-importer-broker` (`1da22ff`); carry records 84/85/86/87; confirm `expected_sha256`, worker env injection and host-broker tests | — | 2026-11-07 |
| 2 | T6.3 controller read surface | real artifacts list + `GET /api/jobs/{id}/artifacts/{artifact_id}` download; real visuals; `execution` status from sidecar | T6.0 | 2026-11-10 |
| 3 | T6.2a host executor driver | `tools/execute_attempt.py`: read job/meta/original → stage inbox package → spawn the guest command (`BINARYREPAIR_ATTEMPT_CMD`) → poll outbox → hand to the ingest adapter → worker trigger | T6.0, protocol | 2026-11-14 |
| 4 | T7.1 flow endpoints | `agent.current_step`, `execution.status`, `POST/GET /api/jobs/{id}/analysis` (screening), `GET /api/jobs/{id}/comparison` | T6.3 | 2026-11-16 |
| 5 | T6.6 AI-driven repair | host-side provider proposal (`replacement_c` / Route A params), `CandidateV1` validation, typed failures, staging of the approved candidate; integration with T6.2a | T6.2a, guest executor | 2026-11-21 |
| 6 | T8.1 endpoints half | `GET/POST /api/jobs/{id}/assistant` endpoints wired to M5's plan store | M5 schema | 2026-11-18 |

Not M1's: ingest adapter internals (M5), UI (M2), guest code (M3), verifier rows (M4).

### M5 — Data contracts, adapters, assistant/AI layer

| Order | Task | Deliverable | Dep | Deadline |
|---|---|---|---|---|
| 1 | T6.1 ingest adapter + hardening | `tools/route_bundle_ingest.py`: verify bundle/artifacts/paths/sizes/symlinks, register artifacts, map gates → artifact ids; harden `tools/host_importer.py`/`host_broker.py`; negative tests | T6.0, protocol | 2026-11-12 |
| 2 | T6.5 protocol conformance | reject-list tests, envelope schema, staging path/size/symlink rules, idempotency | T6.1 | 2026-11-13 |
| 3 | T7.2 analysis/comparison ingest | register `analysis_*` artifacts and `behavior-comparison.json`, expose them to the controller; fixture default answers | T6.1, protocol §4a/§4b | 2026-11-15 |
| 4 | T8.1 assistant seam | `app/domain/assistant.py` schema, deterministic planner, `app/db/migrations/004_assistant.sql`, `assistant_plans` persistence | T7.1 shapes | 2026-11-14 |
| 5 | T8.2 LLM planner | `BINARYREPAIR_ASSISTANT_MODE=llm`, prompt with user request + guest analysis, schema validation, fallback, budget/token recording, fake-transport tests | T8.1, T6.2 | 2026-11-24 |
| 6 | T8.3 generic repair plan | second public sample of a different defect class; plan differs by class; acceptance unchanged | T8.2, T7.3 | 2026-12-01 |

Not M5's: controller endpoint bodies (M1 shares T8.1 endpoints), UI (M2), guest binaries (M3).

### M2 — GUI owner (one person owns the whole console)

| Order | Task | Deliverable | Dep | Deadline |
|---|---|---|---|---|
| 1 | T7.0 prototype review | comment pass on `docs/prototype/agent-console.html`; confirm Claude Code / Codex look, step flow, copy | — | 2026-11-06 |
| 2 | T7.4 agent shell | `agent.html`, `agent.css`, `agent.js`: terminal stream, tool blocks, composer, status panel, resume by URL, polling | T7.1 + T8.1 shapes (can start against fixtures) | 2026-11-14 |
| 3 | T7.5 guided inputs | dropzone + real upload progress, plan-rendered questions, default-answer shortcut, inline validation | T7.4 | 2026-11-14 |
| 4 | T7.6 result screens | execution timeline, before/after table, diagnostic table, download panel; `not_run` verbatim | T7.4, T7.2, T6.3 | 2026-11-17 |
| 5 | T8.4 assistant mode UI | `scripted v1` / `llm` badge, fallback banner, model/token metadata | T8.1, T7.4 | 2026-11-17 |
| 6 | T7.8 migration | `/agent` primary; old pages readable; redirects; labelled screenshots | T7.6 | 2026-11-20 |

Not M2's: API behaviour (M1), plan content (M5), acceptance logic (M4 verifies).

### M3 — Guest execution owner

| Order | Task | Deliverable | Dep | Deadline |
|---|---|---|---|---|
| 1 | T6.2 guest executor (host-safe part) | `workers/executor/run_job.py` + `self_test.py`: read staged package, verify hashes, run frozen fixture steps, write `result-bundle.json` + artifacts + `SHA256SUMS`; `purpose: screening` and `purpose: repair` | T6.0, protocol | 2026-11-14 |
| 2 | T6.2 guest conformance | run under jobwrap isolation in the guest; isolation attestation; bundle hashes | VMer staging window | 2026-11-17 |
| 3 | T7.3 screening + comparison | analysis-only mode and `behavior-comparison.json` (original vs candidate on the same cases) | T6.2 conformance | 2026-11-19 |
| 4 | T8.3 guest half | second sample build path for the generic repair demo | T8.2 | 2026-12-01 |

Not M3's: host ingestion (M5), controller (M1), UI (M2), jobwrap binary (VMer).

### M4 — Independent verification (idle until there is something to verify)

| Order | Task | Deliverable | Dep | Deadline |
|---|---|---|---|---|
| 1 | prepare T6.7/T7.7 checklists | honesty matrix, command list, artifact-hash recomputation criteria; review `docs/handoffs/85`/`86` for testable claims | — | 2026-11-08 |
| 2 | verify T6.1 ingest adapter when delivered | independent run of negative cases; tampered hash/traversal/symlink rejection; report PASS/FAIL/NOT VERIFIED | T6.1 | 2026-11-13 |
| 3 | verify T6.3/T7.1 endpoints | artifact bytes/hash equality, no invented obligations, status derivation | T6.3/T7.1 | 2026-11-17 |
| 4 | T7.7 UI acceptance | honesty matrix + e2e for the agent flow | T7.4–T7.6 | 2026-11-19 |
| 5 | T8.5 LLM verification | injection corpus, no key leak, deterministic replay | T8.2/T8.4 | 2026-12-03 |

Explicitly: M4 has **no implementation task**. If nothing is ready to verify,
M4 stays idle rather than writing product code. Same-person M4=Lead limitation
stays recorded on every verifier row.

### VMer — VM operations (no product code)

| Order | Task | Deliverable | Dep | Deadline |
|---|---|---|---|---|
| 1 | T6.8 staging note (record 88) | staging directory + permissions, snapshot to reset, one-window request format, host→guest transfer method | — | 2026-11-07 |
| 2 | jobwrap fixed operation | fixed-argv `executor <job_id>` op: root-owned config, netns, uid 1003, caps 0, NNP, rlimits, clearenv; hash-checked runner; fail-closed tests | M3 interface | 2026-11-14 |
| 3 | guest conformance window | run M3's executor in the guest; return raw output + SHA256SUMS + isolation attestation | M3 T6.2, jobwrap op | 2026-11-17 |
| 4 | reset/verify after each run | snapshot reset evidence; no leftover inbox/outbox | staging | per run |

Not VMer's: product code, evidence verdicts, commit content.

### Lead (you)

1. Approve/amend records 85/86/87 (D0–D9, T6/T7/T8 ownership).
2. Review the prototype with M2 (1 day), then freeze the visual direction.
3. Keep the baseline decision: no wholesale merge of the two lineages.
4. Own the gate records, merge order and final tag; do not implement.
5. Ask VMer for the record 88 staging note before M3 needs the window.

## 3. Execution order (why this is efficient)

```text
Week 1 (host-only, no VM)
  M1: T6.0 → T6.3            M5: T6.1 → T6.5        M2: T7.0 + T7.4 skeleton
  M4: checklists (idle otherwise)                    VMer: T6.8 note (88)
Week 2 (first guest loop)
  M1: T6.2a → T7.1           M5: T7.2              M3: T6.2 + conformance
  M2: T7.5/T7.6 + T8.4       M4: verify T6.1/T6.3  VMer: jobwrap + window
Week 3 (AI-driven repair + first honest end-to-end)
  M1: T6.6                   M5: T8.1/T8.2         M3: T7.3
  M2: finish T7.6/T7.8       M4: T7.7              VMer: conformance reruns
Week 4+ (generic repair)
  M5: T8.3                   M3: guest half         M4: T8.5
```

## 4. What to tell each person (one message each)

**M1:** You own the host backend. Start with T6.0 on a branch from
`origin/post-final/host-importer-broker` (`1da22ff`) and carry records 84–87;
then T6.3 endpoints, then the host executor driver, then T7.1, then AI repair
T6.6. Do not touch the ingest adapter (M5) or the UI (M2).

**M5:** You own data contracts and the assistant/AI layer. Start with T6.1
(ingest adapter + hardening), then T6.5, then T7.2, then the assistant seam
T8.1 (schema + deterministic planner + migration + persistence), then the LLM
planner T8.2. Never let a plan or a model output write a verdict or approve.

**M2:** You own the whole console. Review the prototype first (T7.0), then build
the shell T7.4 and guided inputs T7.5 against API fixtures, then T7.6 result
screens, then T8.4 mode UI and T7.8 migration. No other person edits the
agent templates.

**M3:** You own guest execution. Write the executor and its host-safe self-test
now (T6.2), then the guest conformance with VMer, then screening + comparison
(T7.3). Do not wait for the VM window to start coding.

**M4:** You own verification and nothing else. Prepare the T6.7/T7.7 checklists
now; verify T6.1 and T6.3/T7.1 as they land; run T7.7 when the UI and real loop
exist. If nothing is ready, stay idle — do not write product code.

**VMer:** Prepare the staging note (record 88) this week: directory,
permissions, snapshot reset, transfer method. Then build the fixed-argv jobwrap
`executor` op and run M3's conformance window. No API keys, no guest network.

## 5. Signature

| Role | Name | Date | Assignment accepted |
|---|---|---|---|
| Lead | Lead | 2026-11-03 | published |
| M1 | — | — | pending |
| M2 | — | — | pending |
| M3 | — | — | pending |
| M4 | — | — | pending |
| M5 | — | — | pending |
| VMer | — | — | pending |
