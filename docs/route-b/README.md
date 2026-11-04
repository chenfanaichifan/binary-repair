# Role 5 kickoff pack: DeepSeek API integration + Route B (recovered C)

> Corresponds to PRD **F3**, Technical Design **§10 (DeepSeek integration)** and **§14 (fifth member's split of work)**.
> Two things you must deliver this week:
> **① one real, reproducible model call with a cost record; ② a Route B feasibility record (round trip passes or fails explicitly).**
> Not "the environment is installed", and not "the model says it is fixed".

---

> **Real sample:** after member 3 freezes the ELF, run G0–G9 from
> [03-feasibility-checklist.md](03-feasibility-checklist.md);
> the fixtures in this document are only for rehearsing the flow.
>
> **Integration point:** the repository root is the only entry point; for module boundaries and the call chain see
> [04-root-integration.md](04-root-integration.md).
>
> **Gate 4:** Route B unchanged round trip **PASS**, see
> [09-gate4-evidence.md](09-gate4-evidence.md). For the Route A byte-level plan see
> [07-route-a-trampoline-plan.md](07-route-a-trampoline-plan.md); for candidate quality see
> [08-candidate-quality.md](08-candidate-quality.md).
> Concrete Gate 6 evidence is in [06-gate6-evidence.md](06-gate6-evidence.md).

## 0. Let us be clear about the boundary first

You are responsible for:

| Scope | Details |
|---|---|
| DeepSeek adapter | `request_candidate(context, route, limits)`, JSON mode + strict local validation + typed failures |
| Prompts and context | send only reviewed public evidence; binary strings are always data, never instructions |
| Cost and usage | record model / tokens / estimated cost on every call; the budget cap is configurable |
| Route B | Ghidra export → normalization → **unchanged round trip** → model repair → back-fill → verify with the same oracle |

You are not responsible for (but must be able to explain):

- the three GUI pages (member 2)
- the contract / job state machine / acceptance engine (members 1 and 4)
- Route A instruction templates and encoding (member 3)
- symbolic execution (member 4)

One hard rule: **the model only "proposes"; acceptance is always decided by deterministic checks.** No output you write may contain
"AI has fixed / verified / made it safe"; what you may say is "candidate accepted for validation".

---

## 1. How to use the four hours today (10/18)

The meeting schedule is 0–20 retrospective, 20–35 environment check, 35–80 install tools individually, 80–105 each person presents, 105–120 decide scope.
Your time maps as follows.

### 1.1 Environment and one harmless call (about 40 minutes, meeting minutes 20–80)

**You can finish this on a Mac**; you do not need to wait for Ubuntu.

```bash
cd binary-repair
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and fill in DEEPSEEK_API_KEY (this machine only, never into Git)
```

First run the pipeline with fake responses (costs nothing, needs no key):

```bash
python scripts/smoke.py --mock
```

Expected last line: `OK: endpoint, model, json mode and usage reporting are working.`

Then send one **real** harmless request (public synthetic text, containing no binary or client data):

```bash
python scripts/smoke.py
```

You will see, and need to record, these 8 numbers:

```
http_status / model_returned / latency / attempts
prompt_tokens / completion_tokens / cache hit / estimated_cost_usd
```

Expected shape (numbers will differ):

```
== configuration ==
  base_url: https://api.deepseek.com
  model: deepseek-flash
  thinking: False
  ...
== account check (GET /models) ==
  reachable; models: deepseek-flash, deepseek-v4-pro
== one json request ==
  http_status: 200
  model_returned: deepseek-flash
  latency: 1830 ms
  attempts: 1
  ...
  estimated_cost_usd: $0.00004120
OK: endpoint, model, json mode and usage reporting are working.
```

If 401: the key was copied wrong / has extra spaces. 402: insufficient balance. 429: wait a few seconds and retry.
Record all three as they are; do not retry with another account until it "looks successful".

> Why thinking is off by default: DeepSeek's thinking mode is **on by default with effort=high**; it emits
> reasoning before the answer, so both tokens and latency are higher. Turn it off for structured candidate generation; once the baseline is stable,
> run with it on and off on the same sample batch before deciding. `DEEPSEEK_THINKING=enabled` switches it on.

### 1.2 Ghidra and recovered C (about 60 minutes, minutes 35–80)

Do this part on Ubuntu (Ghidra needs JDK 21; it also installs on macOS, but the final target is ELF).

```bash
sudo apt update
sudo apt install -y openjdk-21-jdk unzip
java -version        # must be 21.x

# Download the 11.x PUBLIC zip from the official Ghidra release, unzip it into ~/
export GHIDRA_HOME=$HOME/ghidra_11.4_PUBLIC
$GHIDRA_HOME/support/analyzeHeadless 2>&1 | head -3
```

Then run our own small sample (no client data, purely synthetic):

```bash
cd routeb
./fixture/build.sh

# First confirm the vulnerability really exists: 4 valid inputs behave normally, 2 overlong inputs give guard=CORRUPT
python3 verify.py --binary fixture/vuln --mode vulnerable

# Export the decompiled C of copy_name
./ghidra/export.sh fixture/vuln copy_name
cat out/copy_name.c
cat out/copy_name.c.meta.txt
```

**What you must deliver today is not "it is installed" but this observation table:**

| Question | Your record |
|---|---|
| Can the raw decompiler output be compiled directly? Which classes of error appear? | |
| Do the parameter types/names match the signature in `nm`/meta? | |
| Do `undefined4/undefined8`, `goto`, address constants, `code *` appear? | |
| How many bytes is the function body? How many bytes was the original function? (decides whether in-place replacement is possible) | |
| What is `callees=`? (empty = simple relocation; libc calls = PLT resolution needed) | |
| Which places did you change to make it compile? One sentence of reason per change | |

The reference normalization result is in `routeb/experiment/samples/normalized_reference.c`; **do your own first, then compare**.
For this sample the Ghidra output usually only needs the type names and variable names changed, which is exactly why we chose it.

### 1.3 Record blockers (10 minutes)

In the 105–120 minute slot of the meeting you only need to say three sentences:

1. The real call succeeded/failed, and at which step it failed (key, balance, network, model name).
2. Whether Ghidra exported successfully, and how "compilable" the recovered C is.
3. What the biggest risk to this week's round trip is (e.g. Patcherex2 will not install, ELF segment permissions, relocations).

---

## 2. This week's 5-hour plan

| Time | Task | Output |
|---|---|---|
| 1 h | **schema contract freeze**: candidate/context JSON Schema + examples + drift check, handed to member 2/member 4 for review | `schemas/README.md` + `generated/*.json` + all 64 tests green |
| 1 h | **DB migration**: 002_ai_tables.sql runs through on the v1 baseline; confirm the constraints (idempotency key, composite foreign key, a pass must have evidence) | `app/db/migrate.py` re-runnable, `app/db/README.md` (002 + 003) |
| 1 h | wire `binaryrepair_ai` into the main application (member 1 supplies the job/contract/analysis hashes and evidence ids) | one thin wrapper at `app/services/provider.py` + one real candidate record |
| 1 h | Route B: normalization → round trip (record failures too) | a PASS/FAIL/UNSUPPORTED record (with hashes and commands) |
| 0.5 h | model repair → back-fill → `verify.py --mode fixed` (if the round trip has already passed) | 6/6 results or an explicit blocker |
| 0.5 h | cost/latency measurement + reporting material | one page of numbers + a 3-minute demo script |

Completion criteria (checkable):

- [ ] `scripts/smoke.py` really runs on Ubuntu and its output is saved as an evidence file
- [ ] `pytest` 64+ cases pass (including schema drift, JSON Schema examples, DB constraints, AI boundary contract)
- [ ] one real `request_candidate` produces a `model_calls` record whose fields align with TechDesign §6
- [ ] the Route B round trip has an explicit conclusion: PASS / FAIL / UNSUPPORTED, with the actual output of the 6 cases
- [ ] every number in the report has a source; no "should work"

---

## 3. Code map

```
.
├── binaryrepair_ai/
│   ├── settings.py     environment variables and .env; the key only enters this process
│   ├── pricing.py      official price table + peak/off-peak + worst-case estimate
│   ├── schemas.py      Candidate v1, RepairContext, semantic validation (scope/identity)
│   ├── prompts.py      system/user prompts; <untrusted_...> data fence
│   ├── client.py       HTTP, JSON mode, timeouts, one transient retry, usage parsing
│   ├── provider.py     request_candidate: budget → call → parse → validate → record
│   └── errors.py       stable reason_code (the GUI/acceptance engine branches on it)
├── scripts/
│   ├── smoke.py        today's harmless call (--mock works offline)
│   └── demo_candidate.py  reviewed context → model → validated candidate (can write out C)
├── schemas/            candidate/context JSON Schema (generated artifacts + contract notes + examples)
├── app/db/             v1 schema.sql + 002 migration + connection/notes
├── app/                public entry points: domain/candidates, domain/contracts, services/provider
├── tests/              64 offline cases: provider, schema contract, database constraints, AI boundary
├── routeb/
│   ├── fixture/        synthetic vulnerable sample + build script
│   ├── ghidra/         ExportFunction.java + export.sh
│   ├── verify.py       behavioral oracle (vulnerable / fixed / roundtrip)
│   ├── probe_patcherex2.py  three experiments: doc example + round trip + fixed
│   └── experiment/     normalization/repair reference implementation
└── docs/route-b/
    ├── README.md       this file
    ├── 02-member-5-candidate-provider.md   interface reply for member 4
    ├── 03-feasibility-checklist.md         real-sample G0–G9
    └── 04-root-integration.md              root integration and contract hashes
```

### 3.1 Interface for member 1 (integration)

```python
from binaryrepair_ai import DeepSeekProvider, RepairContext
from binaryrepair_ai.schemas import RepairContext  # same object

provider = DeepSeekProvider.from_env()
result = provider.request_candidate(ctx)     # does not raise (expected failures are values)

if result.ok:
    candidate = result.candidate             # CandidateV1
    record = result.record                   # write to the model_calls table
else:
    failure = result.failure                 # reason_code / message / retryable
```

`model_calls` suggested fields (consistent with TechDesign §6):

| Column | Source |
|---|---|
| `provider_model` | `record.model` (configured name); use `record.model_returned` for the version actually returned |
| `prompt_sha256` | `record.prompt_sha256` |
| `status` | `record.status` |
| `usage_json` | `json.dumps(record.usage)`; write `null` when unknown, **do not write 0** |
| `estimated_cost_usd` | `record.estimated_cost_usd`, `NULL` when unknown |

### 3.2 Display fields for member 2 (GUI)

Each route's AI card should show at least:

- status: `not_run / running / accepted_for_validation / rejected / error`
- model name, elapsed time, tokens, estimated cost (show "unavailable" when missing)
- failure reason: `reason_code` + one plain-language sentence (`Failure.message`)
- **do not** show "AI repair succeeded"; show only "candidate submitted for validation"

`reason_code` → suggested copy:

| reason_code | Display | Acceptance semantics |
|---|---|---|
| `provider_auth_failed` | invalid API key | error (configuration problem) |
| `provider_insufficient_balance` | insufficient account balance | error |
| `provider_rate_limited` | rate limited, already retried | error (can retry) |
| `empty_content` | model returned empty content | error (not "no vulnerability") |
| `invalid_json` / `schema_invalid` | proposal format invalid | rejected (keep diagnostics) |
| `identity_mismatch` / `scope_violation` | proposal out of bounds / does not match the input | rejected |
| `budget_exceeded` | over this job's budget | error (not sent) |
| `provider_timeout` | call timed out | error (never automatically resend a billable request) |

### 3.3 Schema boundaries (the part you own independently)

Two layers; do not mix them:

| Layer | File | Answers | Consumed by |
|---|---|---|---|
| Candidate contract | `schemas/generated/candidate.v1.json` | which fields and types the model may return | GUI, validation, docs |
| Request context | `schemas/generated/context.v1.json` | what the server is allowed to send | integration, review |
| Persistence | `app/db/migrations/002_ai_tables.sql` | how job/run/attempt/evidence/cost are stored | member 1's controller |

Three rules:

1. **Pydantic is the source**; `generated/*.json` may only be produced by `python schemas/generate.py`;
   CI catches drift with `python schemas/generate.py --check`.
2. v1 is a closed contract (`additionalProperties: false`); **adding a field = bump to v2**; it cannot be widened quietly.
3. JSON Schema only covers structure; rules such as "Route A must not carry replacement_c" live in
   `check_candidate()`, and the test `test_json_schema_does_not_encode_route_semantics`
   records that layering.

On the database side, product semantics are written into constraints rather than only into Python:

```sql
-- one idempotency key can start a run only once
idempotency_key TEXT NOT NULL UNIQUE
-- the run's contract must belong to the same job
FOREIGN KEY (job_id, contract_id) REFERENCES contracts(job_id, id)
-- a pass must have evidence
CHECK (result <> 'pass' OR evidence_artifact_id IS NOT NULL)
-- unknown cost is NULL, not 0
estimated_cost_usd REAL CHECK (estimated_cost_usd IS NULL OR estimated_cost_usd >= 0)
```

### 3.4 Handover for member 4 (verification)

Only one thing the model produces may enter verification: `candidate.replacement_c` (Route B) or
`candidate.template_id + parameters` (Route A). The verifier must run an oracle like
`verify.py` on the **final ELF**; "it compiles" is not evidence.

---

### 3.5 Interface with verification (implementation side of `02-member-5-candidate-provider.md`)

```python
# app/domain/candidates.py — this is the module the verification skeleton imports
validate_candidate(payload) -> CandidateV1      # structure + semantics; raises CandidateRejected on failure
may_leave_host(classification, derived=False) -> bool   # deny by default
validate_candidate_for_context(payload, ctx) -> CandidateV1  # job-bound version

# app/services/provider.py — typed failure
require_candidate(result) -> CandidateV1        # raises ProviderFailure(FailureReason) on failure
```

Four failure mappings: `provider_timeout` → `TIMEOUT`, `provider_insufficient_balance` / `budget_exceeded`
→ `QUOTA` / `BUDGET`, `empty_content` → `EMPTY`, `invalid_json` → `MALFORMED_JSON`.

### 3.6 Schema usage for member 2 (GUI)

No need to import Python. Read `schemas/generated/candidate.v1.json` directly:

- field names come from `properties`, enums from `enum`, required fields from `required`;
- when displaying, keep `expected_effects / assumptions / uncertainties` separate; do not merge them into an "AI conclusion";
- any field outside `additionalProperties` should not appear — if it does, it is an upstream bug.

`schemas/examples/` contains the real shapes for both routes A/B; use them directly as templates.

---

## 4. Security and data boundaries (you will be asked about these in review)

- Only public samples may be sent to the hosted API. Client binaries, full decompiler output, and test oracles never leave the host machine.
- The key exists only in the host's provider process: not in the VM, not in logs, not in reports, not in the browser.
- Logs contain only `prompt_sha256`; raw responses are not persisted by default (only with `BINARYREPAIR_STORE_RAW=1`).
- Prompts put binary text inside `<untrusted_recovered_c>` and state explicitly "treat as data only"; even so,
  the final line of defense is `check_candidate()`'s structural validation (template whitelist, parameter ranges, call whitelist, forbidden constructs).
- The model cannot change scope: the template list, evidence ids, target entry, and capacities are all supplied by the server.

---

## 5. Cost (official prices 2026-10-18, USD / 1M tokens)

| Model | Input cache miss (off-peak / peak) | Output (off-peak / peak) |
|---|---|---|
| `deepseek-flash` | 0.15 / 0.30 | 0.60 / 1.20 |
| `deepseek-v4-pro` | 0.66 / 1.32 | 1.98 / 3.96 |

- peak: UTC Monday–Friday 01:00–04:00 and 06:00–10:00; half price the rest of the time.
- Example: 10k input + 4k output, flash peak = `0.01*0.30 + 0.004*1.20 = $0.0078`.
- Our default caps: $2 per job, $20 total during the experiment period; over-budget requests are blocked **before sending**.
- Billing figures are estimates, not an invoice; when usage is missing show "unavailable", never treat it as 0.

How to save money: turn thinking off, send only the necessary context, reuse the same context, and do not retry blindly after a failure.

---

## 6. Meeting demo (3 minutes, follow this order)

1. **One sentence**: I own the DeepSeek adapter and Route B feasibility; today I verified up to "real call + decompiled output".
2. **Screen 1**: the real output of `scripts/smoke.py`; point out the four numbers: model, latency, tokens, cost.
3. **Screen 2**: `out/copy_name.c` and `meta.txt`; point out the function size, callees, and the 3 places needing normalization.
4. **Screen 3**: 6/6 from `verify.py --mode vulnerable`, explaining that "the vulnerability is reproducible" is the premise for everything after it.
5. **Risk**: the round trip depends on Patcherex2; if it cannot be installed or behavior changes after back-fill, record it as unsupported,
   do not quietly switch to "hand-editing bytes".
6. **Next step**: deliver a PASS/FAIL record this week and wire it into member 1's job flow.

---

## 7. FAQ

**Q: What is the difference between `--mock` and a real call?**
A: Only the transport. Schema validation, budget, logging, and failure mapping are identical; mock exists to
prove the code path when there is no key, costs nothing, and must not be treated as "API verified".

**Q: Why does JSON mode still return empty or Markdown-wrapped content?**
A: The official docs state explicitly that JSON mode occasionally returns empty content, and require the prompt to contain "json" plus an example. We have added:
`response_format`, an example, the "json" keyword, one retry on empty content, and tolerant parsing of fences/braces.

**Q: Which model name should be written?**
A: Use `deepseek-flash` (the current documented name, V4.1-Flash). Old aliases may still work but get routed to the new model,
so billing/behavior are not controllable; do not hard-code old names.

**Q: Why does temperature=0 sometimes "have no effect"?**
A: Thinking mode does not support temperature/presence/frequency; passing them raises no error but they are ignored. We
simply do not pass them in thinking mode.

**Q: Ghidra reports a `JAVA_HOME` error?**
A: Install JDK 21 and `export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64`; Ghidra 11.3+ does not accept JDK 17.

**Q: Patcherex2 will not install?**
A: It depends on angr/LIEF; a separate venv is recommended. If it will not install, record the version, the error, and the Python version, and write the conclusion
"backend unavailable — unsupported"; that is a legitimate result, not a failure.

**Q: Can I do Route B directly on a Mac?**
A: The behavioral oracle can be done there (`verify.py` already passes), but the back-fill target is ELF, so the final work must happen on Ubuntu.
Mac artifacts are Mach-O and cannot serve as delivery evidence.

---

## 8. Five questions review may ask you

1. **"JSON mode is on, so why local validation too?"**
   JSON only guarantees "it can be parsed", not that fields, hashes, ranges, and routing fields are correct. The model can return valid
   JSON but write capacity as 4096. `CandidateV1` + `check_candidate()` are the gate.

2. **"Can the model change the repair location or capacity itself?"**
   No. The template list, parameter ranges, target_entry, and evidence ids all come from the server; anything out of bounds goes straight to
   `scope_violation` and never enters verification.

3. **"How are empty output, timeout, and 402 handled respectively?"**
   Empty output: retry once (a known official issue); if still empty then `empty_content`;
   timeout/5xx/429: one bounded retry, then report error; never resend billable requests indefinitely;
   402/401: no retry, report the configuration/balance problem directly.

4. **"How do you prove this candidate is safe?"**
   I do not prove it. I only produce "a candidate that passed schema and scope validation"; safety is judged by member 4's
   oracle + symbolic execution on the final ELF. The model's words are not evidence.

5. **"Why is thinking off by default?"**
   It is on by default with effort=high, which costs more tokens and latency; structured output first needs stability and low cost. Once the baseline
   is stable, run an A/B on the same sample batch, then decide whether to enable it for hard samples.

---

## 9. References

- DeepSeek JSON Output: https://api-docs.deepseek.com/guides/json_mode/
- DeepSeek Models & Pricing: https://api-docs.deepseek.com/quick_start/pricing/
- DeepSeek Thinking Mode: https://api-docs.deepseek.com/guides/thinking_mode
- DeepSeek Error Codes: https://api-docs.deepseek.com/quick_start/error_codes
- Ghidra AnalyzeHeadless: https://ghidra.re/ghidra_docs/api/ghidra/app/util/headless/AnalyzeHeadless.html
- Patcherex2 ModifyFunctionPatch: https://purseclab.github.io/Patcherex2/examples/modify_function_patch/
