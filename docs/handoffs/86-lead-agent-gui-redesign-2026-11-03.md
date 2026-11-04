# 86 — Lead task framework: agent-style GUI redesign

**From:** Lead
**To:** M2 (owner), M1, M3, M5, M4, VMer
**Date:** 2026-11-03 (Asia/Shanghai)
**Status:** design + task framework. Implements nothing; changes no gate status.
**Companions:** `docs/handoffs/85` (execution bridge), `docs/interfaces/execution-bridge-v1.md`
(protocol), `docs/prototype/agent-console.html` (visual reference: Claude Code /
Codex-style terminal console).

---

## 0. Goal

Replace the three demo-oriented pages (setup → comparison → evidence) as the
primary journey with **one agent-style console**: the assistant walks the user
through the task one step at a time (upload → describe the defect → AI analysis →
review/approve → execute in the VM → before/after comparison → diagnostics and
downloads). The user never has to understand phases, hashes or JSON.

Important: **v1 ships a deterministic, plan-driven guide; the LLM planner is a
reserved upgrade, not a rewrite.** No assistant text is hardcoded in templates:
every message, question and suggested action comes from a persisted
`AssistantPlan` (section 1a). v1 uses a deterministic planner; v2 swaps in a
host-side LLM planner that produces the **same schema**, so different defect
classes (not only stack overflow) get different questions, plans and
explanations without touching the UI or the acceptance pipeline. The upgrade
slot is reserved now so v1 code never has to be rewritten.

## 1. Design principles

1. **One primary action per step.** The active step card is the only one with an
   enabled primary button; completed steps collapse to a one-line summary.
2. **Guided questions, not an empty form.** Each field is asked in order with
   chips/examples and a "使用公版样本默认值" shortcut when the upload matches the
   frozen fixture.
3. **Server state, not chat memory.** The current step is derived from the
   controller snapshot + job meta, so refreshing the page, closing the browser
   or reopening the URL restores the same place. No hidden client transcript.
4. **Nothing is invented.** The interface renders persisted data; `not_run`,
   `unknown` and "未产生" are shown verbatim; the outcome label comes only from
   the acceptance engine.
5. **No fake progress.** Real byte progress for upload; real stage/elapsed for
   execution; no synthetic typing animations or invented percentages.
6. **Evidence is one click away.** Every claim links to the artifact that backs
   it; the final step lists every artifact and offers the repaired binary.
7. **Keep the product language split.** Chinese labels and assistant copy in the
   template/i18n; all data fields, hashes, verdict labels and exports in English
   ASCII.
8. **Accessibility and low hardware.** Keyboard reachable, works at 1280 px
   width, no build step, no new frontend dependency.

## 1a. Plan-driven assistant and the LLM upgrade slot

The console renders plans, not hardcoded copy. Two different planners produce
the same `AssistantPlan` schema:

| Planner | When | Content | Provider |
|---|---|---|---|
| `DeterministicPlanner` | v1, now | fixture-aware static questions/plans | none |
| `LlmPlanner` | v2, reserved | questions/plan/explanations generated from the user's defect description + guest analysis, for any defect class | DeepSeek via the trusted host provider |

Reserved seam (create the files now, implement the LLM body later):

- `app/domain/assistant.py` — Pydantic `AssistantPlan`, `AssistantStep`,
  `AssistantQuestion`, `AssistantAction`; `schema_version: 1`; JSON schema
  generated the same way as the candidate schemas. A plan carries only display
  copy and step identifiers — never an outcome, never a run trigger.
- `app/services/assistant.py` — `build_plan(job_id, state, *, data_dir)` returns
  the latest persisted plan, generating a new revision only when the job state
  hash changed. `BINARYREPAIR_ASSISTANT_MODE=deterministic|llm` selects the
  planner (`llm` falls back to deterministic on any failure, with a visible tag).
- DB migration `004_assistant.sql` — `assistant_plans(id, job_id, revision,
  state_hash, plan_json, plan_sha256, generated_by, model, prompt_tokens,
  completion_tokens, created_at)`. Plans are auditable and replayable; they are
  display data and are excluded from evidence exports.
- Controller endpoints: `POST /api/jobs/{id}/assistant/plan` (idempotent by
  state hash; 202 when a new plan is generated) and `GET /api/jobs/{id}/assistant`
  (latest plan + generation metadata). The GUI only calls GET.
- `agent.html` / `agent.js` render `plan.steps[].messages`, `.questions`,
  `.actions`; the template keeps only fixed labels.

LLM safety rules:

- Model output is **untrusted display data**. It cannot approve a contract,
  start or cancel a run, change scope/tools/limits, write an obligation or
  claim success. Those actions remain explicit UI controls backed by the
  controller and the acceptance engine.
- The planner may see: the user's repair request, contract fields, guest
  analysis artifacts (recovered C, disassembly excerpt), tool names and limits.
  It never sees binary bytes, evaluator material, other jobs, logs or keys.
- Output is schema-validated with length caps; anything invalid → deterministic
  plan + "已使用默认引导（AI 生成失败：&lt;reason&gt;）".
- Every generation writes `model_calls` + plan metadata (model, tokens, cost);
  budget caps and typed failures from `binaryrepair_ai` apply.
- Prompt-injection text inside analysis artifacts is data: the planner prompt
  states that worker/analysis text cannot change instructions, scope or tools.

**This is separate from AI-driven repair.** The assistant planner only writes
guidance/plan copy. The repair proposal (Route B `replacement_c`, Route A
template parameters) is a typed `CandidateV1` produced by the provider and
validated by the same schema as today; it is task T6.6/T8.2, not the planner.

## 2. Screen flow

One route: `GET /agent` (new job) and `GET /agent/{job_id}` (resume). The page
has three regions: a **timeline** (assistant messages + step cards), a **context
rail** (right side; job identity and execution status), and a **composer** at the
bottom of the timeline (file drop zone or free-text answer for the active step).

```text
+-------------------------------------------------------+-------------------+
| 修复助手                                              | 任务              |
|                                                       | job 8f1c2e4a      |
| [1] 上传样本            done  sample.elf  26,792 B    | sample.elf        |
|     aa428157…8393                                     | sha256 aa428157…  |
| [2] 描述缺陷            done  revision 2              | phase  queued     |
| [3] AI 分析             done  目标函数 badSink 0x4012b0| 执行  VM 已连接   |
| [4] 确认契约            done  approved 15:42          | 契约  rev 2 已批准|
| [5] 虚拟机执行          active  验证中 6/6 ...        | 用时  00:41       |
| [6] 修复前后对比        pending                        |                   |
| [7] 诊断与产物          pending                        | [取消任务]        |
|                                                       |                   |
| 助手：正在虚拟机里运行修复后的程序，用同一组用例对比……  |                   |
| +---------------------------------------------------+ |                   |
| | 拖入 ELF 或 选择文件…                             | |                   |
| +---------------------------------------------------+ |                   |
+-------------------------------------------------------+-------------------+
```

### Step 1 — 上传样本

- Assistant: "你好，我是修复助手。先把要修复的 Linux x86-64 ELF 拖进来。我只做
  静态检查，**不会在本机执行它**。"
- UI: drop zone + file picker + optional "任务备注" (ASCII English field).
- Shows: filename, size, SHA-256 after the server accepts it; if the hash equals
  the frozen fixture, a badge "识别为公版样本，可自动填入默认契约".
- Backend: `POST /jobs` (existing). Validation: size ≤ 20 MiB, non-empty,
  server-side ELF check; errors rendered as an assistant error bubble with the
  server reason (never a toast that hides it).
- Exit: job id assigned → step 2.

### Step 2 — 引导式描述缺陷

The assistant asks in order, one question at a time; each answer is saved to the
job meta via `POST /jobs/{id}/contract` when the block is complete.

1. "这个程序的正常输入是什么范围？" → `valid_domain`
2. "正常输入下应该发生什么？" → `valid_behavior`
3. "什么行为属于被利用/必须禁止？" → `forbidden`
4. "无效输入时应该怎样？" → `invalid_outcome`
5. "有哪些环境假设？"（可跳过）→ `assumptions`

- Each question shows an example and an "使用公版样本默认值" button when the
  fixture badge is present; the button fills all five fields from
  `fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json` (read-only).
- Data fields are English ASCII; non-ASCII input gets an inline server 422
  message.
- Exit: contract saved as a new revision → step 3.

### Step 3 — AI 分析（虚拟机内分析，本机 AI 提议）

- Assistant: "我先在虚拟机里分析目标函数和漏洞位置；分析结果只用来给你看和
  生成修复建议，不会直接判定修复成功。"
- Button "开始分析" → `POST /api/jobs/{id}/analysis` (new): host stages a
  screening package; the guest runs analysis only; the host ingests analysis
  artifacts; the trusted host provider may then propose a repair candidate.
- Analysis card shows: function, address, vulnerability summary, disassembly
  excerpt, recovered C, AI proposal (rationale/assumptions/uncertainties),
  token usage if measured. Missing pieces show "未产生（原因）", never a blank.
- Failure: assistant error bubble with the typed reason (`unsupported`,
  `executor unavailable`, `provider_failed`, `timeout`); retry button.
- Exit: analysis available (or explicitly unavailable) → step 4.

### Step 4 — 确认契约（审批）

- Card: the five contract fields (editable), the bound revision hash, and the
  approval checkbox/button: "我确认本次修复范围" + reviewer label.
- Honesty: "批准后才会在虚拟机执行；批准绑定当前修订哈希，修改后需要重新批准."
- Backend: `POST /jobs/{id}/approve` (existing; stale hash → 409 card with
  reload instruction).
- Exit: approved → step 5.

### Step 5 — 虚拟机执行

- Assistant: "已发送到虚拟机。目标进程在隔离环境里运行，本机不会执行它。"
- Timeline body: two route rows (A/B) with stage chips
  (分析 → 生成 → 应用 → 验证; B adds 往返回填), real elapsed, current phase;
  executor status (staging / executing / ingesting / acceptance); cancel button.
- Polls `GET /api/jobs/{id}` every 2 s (existing) + `GET /api/execution/status`
  (new, cached sidecar; never a live broker call per request).
- Unavailable state: "执行环境不可用：<reason>" with retry; never a fake run.
- Exit: attempt(s) terminal → step 6.

### Step 6 — 修复前后对比

- Assistant: "修复前后，用同一组用例各跑一遍（都在虚拟机里）。"
- Requirement: this screen requires `behavior-comparison.json`
  (`docs/interfaces/execution-bridge-v1.md` §4a.1). Missing → "未产生对比数据
  （V3 not_run）".
- Table: 用例 / 输入 / 期望 / 修复前 (rc, stdout, stderr) / 修复后 / 判定
  (`fixed` / `regressed` / `unchanged` / `still_broken` / `not_run`).
- Summary bar: "样本用例符合率：修复前 2/6 → 修复后 6/6（这是样本通过率，不是
  修复结论）". Never a green "已修复" here.
- Tabs: 行为对比 / 反汇编对比 / C 代码对比; each tab shows "未产生" when its
  artifact is missing.
- Exit: user clicks "查看诊断与产物" → step 7.

### Step 7 — 诊断与产物

- Diagnostic table (V0–V5): 义务 / 结果 / 范围 / 证据 / 原因, rendered from
  persisted obligations (verbatim results).
- Outcome banner: the acceptance engine's label + reason; if not yet decided,
  "等待验收结论".
- Downloads: 修复后的二进制 (candidate artifact), 证据包 (existing export),
  each evidence artifact link.
- Actions: "再修一次"（new attempt), "开始新任务".
- Honesty: the download list only contains artifacts that exist; missing entries
  are disabled with "未产生".

## 3. Component inventory (M2)

| Component | Purpose | data-testid |
|---|---|---|
| `agent.html` | shell: timeline + rail + composer | `agent-console` |
| `assistant_message` | static copy bubble | `assistant-msg-{step}` |
| `step_card` | pending/active/done/error card | `step-{n}` |
| `upload_dropzone` | file input + drag/drop + progress | `upload-dropzone` |
| `guided_question` | one question + chips + default shortcut | `q-{field}` |
| `analysis_card` | function/vuln/summary/disassembly/recovered C/AI proposal | `analysis-card` |
| `contract_approval` | editable fields + hash + approve | `contract-card` |
| `execution_timeline` | per-route stages + elapsed + cancel | `execution-timeline` |
| `comparison_table` | before/after rows + match rate | `comparison-table` |
| `diagnostic_table` | V0–V5 obligations | `diagnostic-table` |
| `download_panel` | binary / evidence / per-artifact links | `download-panel` |
| `context_rail` | identity, phase, executor status | `context-rail` |

Styling: reuse the existing palette and hand-drawn accents; the agent timeline
adds a vertical rule, timestamped message rows and collapsible cards. CSS lives
in `app/static/css/agent.css`; JS in `app/static/js/agent.js`; no framework.

## 3a. Visual language: Claude Code / Codex terminal console

Reference: `docs/prototype/agent-console.html`. The console should read as a
coding-agent terminal, not a marketing dashboard.

- **Surface:** warm near-black background (`#141413`), off-white monospace text,
  orange accent (`#d97757`), thin 1 px rules; no large colored cards, no hero
  images, no gradients.
- **Typography:** one monospace family everywhere (Cascadia/JetBrains/Consolas),
  13 px stream, 11.5 px meta; no web fonts, no build step.
- **Stream:** assistant lines start with `⏺`, user input with `❯`, tool results
  with `⎿`; tool calls are bordered blocks with a dim header
  (`⏺ Run six cases  · 2.1s`) that collapse on click.
- **Working state:** a rotating `✻` glyph plus elapsed time (`esc 中断`), not a
  fake typing animation; progress bars only where real numbers exist.
- **Composer:** fixed bottom input with `❯` prompt, placeholder text and a hint
  line (`Enter 发送 · Esc 中断 · / 命令`); the mode badge shows
  `scripted v1` and a struck-through `LLM` until the upgrade lands.
- **Top bar:** product/session name, job id, `plan rev`, mode/model; token usage
  when measured. **Status panel:** optional right panel (`Ctrl+I`) with job
  identity, phase, executor and contract state; hidden by default to keep the
  terminal look.
- **Tables and diffs:** monospace, thin rules, green/red for added/removed lines;
  verdicts as small outlined badges, never colored success banners.
- **Non-goals:** no rounded chat bubbles in pastel colors, no dashboard grid, no
  sidebar navigation, no emoji beyond the agent's text glyphs.

Accessibility: all controls keyboard reachable, focus ring visible, contrast
AA for body text, reduced-motion respected (spinner can freeze).

## 4. Data and API needs

| Need | Endpoint | State |
|---|---|---|
| Create job | `POST /jobs` | exists |
| Contract update | `POST /jobs/{id}/contract` | exists |
| Approval | `POST /jobs/{id}/approve` | exists |
| Snapshot (steps, phases, verdict) | `GET /api/jobs/{id}` | exists; extend with `agent.current_step` and `execution.status` |
| Start / cancel | `POST /jobs/{id}/start`, `/cancel` | exists |
| Obligations | `GET /api/jobs/{id}/obligations` | exists |
| Artifacts metadata | `GET /api/jobs/{id}/artifacts` | extend (T6.3) |
| Artifact download | `GET /api/jobs/{id}/artifacts/{artifact_id}` | new (T6.3) |
| Screening trigger | `POST /api/jobs/{id}/analysis` | new (T7.1) |
| Analysis card | `GET /api/jobs/{id}/analysis` | new (T7.1) |
| Before/after table | `GET /api/jobs/{id}/comparison` | new (T7.1/T7.2) |
| Executor status | `GET /api/execution/status` | new (T7.1) |
| Assistant plan (latest) | `GET /api/jobs/{id}/assistant` | new (T8.1, reserved seam) |
| Assistant plan generation | `POST /api/jobs/{id}/assistant/plan` | new (T8.1, idempotent by state hash) |
| Export bundle | `GET /api/jobs/{id}/export` | exists (GUI-assembled) |

`agent.current_step` is a server-derived display state
(`upload | describe | analyze | approve | run | compare | done | error`); it is
**not** a verdict and must be computed from the persisted job/run state, never
from client memory. Adding it to the snapshot is UI-support data, so the
"acceptance computed in one place" rule is untouched.

## 5. Honesty rules for this screen

- No success label anywhere except the acceptance engine verdict label.
- `not_run` / `unknown` / `timed_out` are rendered verbatim; "no data" is
  "未产生（原因）", not zero and not pass.
- The before/after table is display evidence; the match rate is labelled
  "样本用例符合率", never "修复成功" or a percentage claim of security.
- The analysis card never says the binary is fixed; it describes analysis and
  the AI proposal.
- Buttons that would imply unavailable execution are disabled with the reason,
  not silently hidden.
- No demo/mock data in the live console; the demo banner stays only on the old
  mock pages.

## 6. Task cards

| ID | Task | Owner | Dep | Deliverable | Acceptance |
|---|---|---|---|---|---|
| T7.0 | UX spec + static prototype: this record + `docs/prototype/agent-console.html` (Claude Code / Codex look), copy deck, component list | M2 | — | prototype + review notes | prototype opens offline; all 7 steps walkable; labelled "prototype" |
| T7.1 | Controller support for the flow: `agent.current_step`, `execution.status`, `POST/GET analysis`, `GET comparison`, artifact download | M1 | T6.3 | endpoints + tests | pytest; step derivation table tests; no invented state |
| T7.2 | Screening/comparison ingestion: analysis artifacts and `behavior-comparison.json` registered and exposed; fixture default answers endpoint/field | M5 | T6.1 | adapter updates + tests | analysis/comparison payloads resolvable; missing → null with reason |
| T7.3 | Guest screening mode + comparison production (original vs repaired on same cases) | M3 (+VMer) | T6.2 | executor `purpose: screening` + `behaviour_compare` artifact | guest bundle has analysis + comparison artifacts; hashes bind |
| T7.4 | Agent shell: plan-rendered stream, tool blocks, composer, status panel, resume by URL, polling | M2 | T7.1 shapes, T8.1 scaffold | `agent.html`, `agent.css`, `agent.js` | refresh restores step; no copy hardcoded outside the plan; no state from client memory |
| T7.5 | Guided inputs: dropzone + real progress, plan-driven questions, default-answer shortcut, inline validation | M2 | T7.4 | components + unit tests | bad/oversize/non-ASCII rejected with visible reason; questions come from the plan |
| T7.6 | Execution + comparison + diagnostics + downloads | M2 | T7.4, T7.2, T6.3 | cards + tests | rendered data matches API fixtures; not_run verbatim; downloads byte-identical |
| T7.7 | UI acceptance: honesty matrix + e2e journey for the agent flow | M4 | T7.4–T7.6 | verifier row + tests | no success without verdict; comparison missing → not_run; no demo data in live mode |
| T7.8 | Migration: make `/agent` primary, keep old pages readable (evidence/export), redirects, screenshots/docs | M2 | T7.6 | routes + docs | old URLs still work; e2e updated; screenshots labelled |

### T8 — reserved LLM upgrade (scaffold now, model later)

This is the "auto-generate conversation for different repair requirements"
upgrade the client asked for. The scaffold is small and must land with T7 so the
UI never has to be rewritten.

| ID | Task | Owner | Dep | Deliverable | Acceptance |
|---|---|---|---|---|---|
| T8.1 | Assistant schema + planner seam: `app/domain/assistant.py`, deterministic planner, migration `004_assistant.sql`, `GET/POST /assistant` endpoints, `assistant_plans` persistence | M5 (+M1 for endpoints) | T7.1 | scaffold + tests | deterministic plan persisted with `plan_sha256`; GET returns latest; refresh-safe; no outcome fields |
| T8.2 | LLM planner: `LlmPlanner` behind `BINARYREPAIR_ASSISTANT_MODE=llm`, prompt with repair request + guest analysis, schema validation, typed failures, fallback to deterministic, budget/token recording | M5 | T8.1, T6.2 | `app/services/assistant.py` llm branch + fake-transport tests | invalid/slow/unauthorized → deterministic fallback with visible tag; no key/prompt in logs; tokens recorded |
| T8.3 | Generic repair use case (non-CWE121): plan questions/analysis for another defect class end-to-end on a second public sample | M5 + M3 | T8.2, T7.3 | second-fixture run + plan | plan differs by defect class; acceptance unchanged; honest `unsupported` when out of scope |
| T8.4 | UI mode switch + labels: show `scripted v1` / `llm` badge, fallback banner, model/token metadata | M2 | T8.1, T7.4 | UI + tests | mode visible; fallback message shown; no layout change |
| T8.5 | Verification of the LLM layer: prompt-injection corpus, no-success claims, key absence, deterministic replay of stored plans | M4 | T8.2, T8.4 | verifier row | injection text cannot change scope/actions; stored plan replays byte-identically; no key in artifacts/logs |

Sequencing: T7.0/T7.1/T8.1 start now (no guest needed); T7.2/T7.3 follow the
bridge tasks in record 85; T7.4–T7.6 and T8.4 can be built against mocked API
fixtures before the guest loop is real; T7.7 gates any "GUI done" claim; T8.2
(multi-defect plans) starts only after the first real guest loop exists.

## 7. Milestones

| Milestone | Content | Exit |
|---|---|---|
| **T7-A** | T7.0 + T7.1 + T7.4/T7.5 against fixtures | prototype reviewed; agent shell walks steps 1–4 offline |
| **T7-B** | T7.2 + T7.6 against synthetic but schema-valid artifacts | comparison/diagnostic/download screens render; honesty tests pass |
| **T7-C** | T7.3 + real guest loop | guest-produced job → agent console shows real before/after and diagnostics; M4 row |

## 8. Test plan

Host-only (this Windows host can run these):

- Jinja render tests per step (no browser): step card states, not_run verbatim,
  missing artifact text, outcome banner from a fixture verdict.
- API contract tests for the new endpoints (`analysis`, `comparison`,
  `execution/status`, artifact download).
- Honesty unit tests: a snapshot with `verdict.outcome=success_within_scope` but
  no obligations must not render a success label; a comparison table with
  `verdict=not_run` rows must show "未产生".
- Playwright e2e (Windows Edge if available; otherwise recorded as environment
  gap like the current suite): step 1→7 mock journey, refresh resume, cancel.

Guest-only: real analysis/comparison content comes from T7.3/M1 evidence; the UI
task cannot pass T7.7 without it.

## 9. Migration and compatibility

- New route `/agent` (new job) and `/agent/{job_id}` (resume). Keep `/jobs/new`,
  `/jobs/{id}`, `/jobs/{id}/evidence` working until T7.8 lands; then make the old
  comparison page link to `/agent/{job_id}`.
- Existing tests that pin the old templates (`tests/test_smoke.py`,
  `tests/test_verdict_view.py`, `tests/test_local_backend.py`,
  `tests/e2e/test_gui_journey.py`) are updated in T7.6/T7.8, not deleted; the
  no-success and language-policy assertions move to the new page.
- DB migration `004_assistant.sql` is additive; jobs created before it have no
  plan row and fall back to the deterministic plan on first render. The legacy
  `mock`/`local` backends keep their current pages until T7.8.
- No new build step, no frontend framework, no CDN assets.

## 10. Risks

| Risk | Mitigation |
|---|---|
| The assistant is expected to be a free chat in v1 | v1 is plan-driven and honest; the mode badge says `scripted v1` and `LLM` is visibly reserved |
| LLM upgrade forces a UI rewrite | T8.1 scaffold lands with T7: schema + planner seam + migration + endpoints now, model body later |
| LLM output changes scope or claims success | planner output is display-only and schema-validated; approval/start/verdict remain controller+engine actions |
| Comparison screen read as a proof | match rate labelled sample-case rate; outcome banner only from engine |
| Analysis-before-run needs a new guest mode | T7.3 `purpose: screening`; the run flow is unchanged |
| UI ships before the bridge | T7-A/T7-B are fixture-driven; T7-C requires the real loop |
| Old and new pages diverge | T7.8 migration task; tests moved, old pages redirect |
| Over-scoping the UI | one terminal console, seven steps, no settings/chat-history theme |

## 11. Signature

| Role | Name | Date | Decision |
|---|---|---|---|
| Lead | Lead | 2026-11-03 | GUI redesign framework published; T7.0–T7.8 assigned |
| M2 | — | — | pending |
| M1 | — | — | pending |
| M3 | — | — | pending |
| M4 | — | — | pending |
| M5 | — | — | pending |
| VMer | — | — | pending |
