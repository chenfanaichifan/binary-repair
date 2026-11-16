# BinaryRepair Product Positioning and Boundaries (2026-11-17)

> Version: v0.1 (M3 productization, P0-1 first increment)
> Status: **internal product positioning document** used to align delivery, demo
> and customer communication. It is not a sales commitment.
> Sources of truth: docs/status/claims.json, docs/acceptance/LIMITATIONS.md,
> benchmark/phase8c/results.json, artifacts/phase8c-*, and
> docs/consolidation/PROJECT-MASTER-REPORT-2026-11-16.md.
> Conflict rule: if this document conflicts with claims.json or
> LIMITATIONS.md, the latter win and this document must be fixed immediately.
> Chinese version: delivery/zh/product/PRODUCT-POSITIONING-2026-11-17.md.

## 0. One-sentence positioning

> **BinaryRepair = bounded binary repair with an auditable evidence package.**
> Input: one known vulnerability location plus one binary. Output: a candidate
> patch for one target function, a reproducible PoC/regression differential, and
> independent verification evidence. When the input is refused, no bytes are
> produced and no success is claimed. It is **not** universal repair of arbitrary
> binaries or arbitrary vulnerabilities, not a whole-program proof, and not a
> vulnerability discovery tool.

**Product wording discipline (mandatory in every material):**

1. Every product/customer material must state: **public benchmark 2/24 verified
   (8.3%) and hidden 0/8 verified**;
2. Phrases such as "arbitrary binaries", "100% repair", "universal repair" and
   "guaranteed safe" are prohibited;
3. Capability numbers may only come from published claims.json /
   LIMITATIONS.md values; do not estimate or extrapolate;
4. Not-run items must be listed explicitly as not_run with a reason; never
   present them as completed or passed.

## 1. Customers and scenarios (ICP)

### 1.1 Who needs this most (ordered by pain)

| # | Customer / scenario | Pain | What this product provides | What it does not provide |
|---|---|---|---|---|
| 1 | **No-source / third-party binary supply chain** (purchased COTS components, closed-source SDKs, unmaintained vendor libraries) | A CVE advisory or pentest report exists, but there is **no source to rebuild**; the only options are waiting for the vendor or replacing the whole component | A bounded candidate patch for the known target sink plus PoC differential evidence, for the security team to review | Full supply-chain scanning, unknown-vulnerability discovery |
| 2 | **Legacy / end-of-life binaries** (toolchain lost, build environment not reproducible) | Even with source it cannot be rebuilt; the patch window is very short | Candidate repair directly on the binary; the evidence package supports change review | Whole-program equivalence proof, large cross-function rewrites |
| 3 | **CVE emergency mitigation** (known CVE plus known sink, hours matter) | Vendor patch not released; mitigation is needed first | Deterministic single-function/single-sink repair attempt plus evidence; on failure an explicit analysis_only/unsupported result | An SLA that says "always repaired" |
| 4 | **Security research / compliance audit / red-team exercise** | Needs a reproducible, auditable repair evidence chain instead of verbal conclusions | Evidence package: original/candidate SHA256, patch plan, gate checklist, independent verifier report, PoC/regression results, limitations, not_run | Formal proofs, third-party certification |

### 1.2 Explicitly out-of-scope scenarios (pre-sales / trial filter)

- **Unknown vulnerability discovery / scanner use**: detection is only
  **3/24 (12.5%)**, and localization/root-cause are 3/24 each. The product
  requires the caller to declare the target function/sink; it does not discover;
- **Whole-program proof / formal equivalence**: verification scope is one
  function plus the supplied PoC/regression cases (LIMITATIONS sections 1 and 9);
- **Arbitrary architectures / containers**: architectures outside the matrix
  (arm32, riscv, mips, ppc, big-endian, 32-bit Mach-O, fat Mach-O rewrite) are
  analyzed only, never rewritten;
- **UAF, sprintf format expansion, integer defects, loop defects, obfuscated or
  inlined copies**: the deterministic engine returns analysis_only (AI paths
  only have research evidence, not product capability);
- **Multi-function / whole-image automatic repair**: one candidate repairs
  exactly **one target function/sink**; other vulnerable functions are reported
  as limitations only;
- **Compliance sign-off that a repaired binary is safe for production**:
  LIMITATIONS section 9 explicitly refuses that claim;
- **A compliance process needing genuinely independent two-person review**: in
  this delivery the M4 verification row and the Lead approval row were signed by
  the same operator (role separation, not independent two-person review;
  LIMITATIONS section 4).

## 2. Product commitment (the minimum deliverable)

**One repair delivery = a candidate patch for one target function/sink + a
reproducible PoC/regression differential + an auditable evidence package.**

| Delivery field | Content | Produced by |
|---|---|---|
| disposition | verified_patch / static_only_patch (opt-in, unverified) / analysis_only / unsupported / rejected / invalid | deterministic unified gate (the only acceptance authority) |
| candidate bytes | downloadable only when the gate passed and the independent verifier confirmed | repair_any + writer |
| patch plan | layout, cave, associated changes (e.g. capacity message), ABI block | engine, replayed by the independent verifier |
| PoC / regression differential | original fails / candidate passes plus matching regression outputs | poc_runner (guest/Lima/Unicorn depending on platform) |
| independent verification report | required checks: identity, container reparse, action replay, target scope, authorized associated changes, cave executable/redirect, relocation, ABI, runtime oracle | app/services/independent_verifier.py (never reads the generator verdict) |
| evidence index | SHA256 for every file (original/candidate/plan/report/results) | same evidence layout as scripts/run_repair_benchmark.py |
| limitations + not_run | per-case limitations and not-run reasons | engine + verifier + host probing |

**Three non-negotiable product behaviours (enforced by code, not marketing):**

1. **No bytes on failure/uncertainty**: without a PoC or runtime evidence the
   result fails closed (not_run/inconclusive); no success and no download;
2. **The generator never self-verifies**: even after the deterministic gate
   passes, the independent verifier must return verified; otherwise the claim is
   recorded as false_verified (must be 0) and withdrawn;
3. **The deterministic path uses no network and no API key**: the product demo
   and default CLI call no model. AI is an optional candidate generator and never
   owns acceptance.

## 3. Capability matrix and SLOs

### 3.1 Capability matrix (current real boundary)

| Input family | Support level | Maximum disposition | What can be promised to a customer |
|---|---|---|---|
| ELF x86-64 / i386 / arm64 | parse + rewrite | verified_patch (when gate + independent verifier + oracle pass) | "a target-level repair can be attempted; the evidence package is authoritative" |
| PE x86-64 / i386 / arm64 | parse; rewrite for x86-64/i386 | same (PE runtime evidence is Unicorn instruction-level emulation, not a Windows kernel run) | same, with the evidence tier stated |
| Mach-O thin little-endian x86-64 / arm64 | parse + rewrite | same; **native evidence only on macOS**; not_verified on Linux hosts | same, with the host platform stated |
| ELF32 / PE32 i386 | parse + rewrite | same; 32-bit cdecl push-argument model, fail-closed | same |
| fat Mach-O / 32-bit Mach-O / arm32 / riscv / mips / ppc / big-endian | detect/analyze only | unsupported (never rewritten) | "not repaired, analyzed only" |
| Non ELF/PE/Mach-O (unrecognized container) | - | invalid | "input not accepted" |
| Copy sinks on stack: strcpy/strcat/stpcpy guard; constant-length memcpy/memmove/syscall clamp | deterministic templates | verified_patch reachable | same as above |
| Duplicated inline capacity check (marcx class) equal-length in-place rewrite plus a .rodata message | deterministic template | verified_patch reachable | same |
| Same-function immediate heap destination (malloc/calloc immediate size reaching the copy destination) | deterministic template | verified_patch reachable; wrong capacity is rejected by the runtime oracle | same |
| Global destinations / struct-member capacity / dynamic sizes / cross-function aliases / cross-function allocation | analysis_only | analysis_only | "analysis only, no patch" |
| sprintf / UAF / integer / loop / obfuscated-inlined copies | analysis_only (AI research evidence is not product capability) | analysis_only | "not repaired today" |
| Whole-image (no declared target) | explicit opt-in only | labelled target_policy=whole_image; **never** a target repair claim | "not a target repair; no ownership claim" |

Additional constraints that must travel with the matrix:

- **One function per candidate**: other vulnerable functions are reported as
  limitations and are not patched;
- **Capacity semantics**: capacity is frame geometry (frame_top - destination) or
  an explicit _chk/immediate size, not DWARF object size; buffers not at the frame
  top can be over-estimated;
- **Input limit**: the universal entry accepts at most 20 MiB; larger input is
  rejected;
- **Platform gaps**: an ELF x86_64 external PoC on an arm64 host is unavailable;
  PE and 32-bit Mach-O external PoC are unavailable. Those cases are recorded as
  not_run/unavailable and are never faked.

### 3.2 SLOs: process and evidence only, never repair success rate

> **Important**: the measured verified repair rate is **2/24 = 8.3%** on the
> public benchmark and **hidden 0/8**. The product therefore offers **no repair
> success SLO**; it is accountable only for process SLOs that code enforces and
> auditors can reproduce.

| SLO item | Commitment | Enforcement point | Status |
|---|---|---|---|
| Disposition completeness | 100% of requests emit at least one explicit disposition (no silent success, no silent failure) | unified gate returns an enum; not_run always carries a reason | implemented (code) |
| Acceptance independence | any verified result must come from the independent verifier (decision=verified); the generator verdict is not accepted | independent_verifier plus false_verified assertion | implemented (code) |
| Fail-closed | no PoC/runtime evidence implies no success and no downloadable bytes | evidence-profile gate | implemented (code) |
| Evidence completeness | every repair produces original/candidate SHA256, patch plan, checklist, verifier report, limitations, not_run | report/evidence bundle structure | implemented (code) |
| Demo reproducibility | deterministic demo path uses **no API key and no external network**; failures are explicit | scripts/product/demo_repair.py + tools/product/run-demo.sh | implemented by this task and verified |
| Demo duration | 3 fixtures complete in under 10 minutes (target; measured value recorded) | run-demo elapsed output | measured about 46 s (artifacts/m3-product-2026-11-17/demo/demo-run.json) |
| Repair success rate | **not committed**; benchmark currently reports 2/24 and hidden 0/8 | - | explicitly not promised |

## 4. Not-claimed list (quoted, do not rewrite)

### 4.1 Current phase not_claimed (claims.json.phase8c_ground_truth.not_claimed, verbatim)

- hidden material availability or distribution
- hidden generalisation or independently verified hidden repairs
- new vulnerability-repair capability
- automatic upgrade or capability promotion
- arbitrary binary/vulnerability/whole-program repair
- cross-compiler verification with a second toolchain
- Phase-8D open-world discovery or Acceptance 2.0
- Phase-9-16 semantic/repair/reflection expansion

### 4.2 LIMITATIONS.md items directly relevant to product promises (verbatim excerpts)

- section 1: "V4 is a typed symbolic claim over the target function. It is not
  binary-level symbolic execution and not a whole-program proof." ... "the
  binary-level claim is not made."
- section 2: "Coverage is a bounded fixture/matrix, not arbitrary binaries";
  "this is still not evidence that arbitrary binaries, other architectures,
  other compilers, stripped production binaries, or client binaries work."
- section 4: "The verification row and approval row were signed by the same
  operator. This is role-separated, not independent two-person review."
- section 6: "V5 is build/replay reproducibility. It does not prove repaired
  behaviour."
- section 8: "This is a course/MVP deliverable, not a supported commercial
  vulnerability remediation service."
- section 9 (excerpt): "it is still not universal vulnerability repair"; "a
  candidate repairs one function per run"; "report v4 dispositions are bounded
  claims: no whole-program proof, no arbitrary-vulnerability discovery, no claim
  that a repaired binary is safe for production use."
- section 12 (AI): "The two AI direct-binary paths prove
  protocol/validator/writeback/gate integration with a scripted client." ...
  "no AI increment is measured"; "Real-LLM quality, a gate-blind increment suite
  and PoC-based evaluation remain future work; AI never owns acceptance."
- section 19: "it does not prove full side-effect equivalence (buffered I/O,
  errno, libc state); no-PoC assembly paths remain a known blind spot."
- section 21: "Global destinations, dynamic sizes, pointer+offset aliases and
  cross-function allocations stay analysis-only."; "the legacy quick-repair gate
  refuses external PoC evidence"; "Mach-O x86_64 external PoC remains unavailable
  on an arm64 host; PE and 32-bit Mach-O external PoC are unavailable by design."

### 4.3 claims.json.explicitly_unimplemented items that must be disclosed to customers (verbatim)

- "sprintf/format-expansion, UAF/lifetime and integer/loop deterministic repair
  templates (no deterministic engine; AI path research only, non-loop AI verified
  0/6)"
- "whole-program proof: verification is scoped to the supplied PoC/regression
  cases and the one repaired function, not the whole binary"
- "external-PoC replay for PE and 32-bit Mach-O; Mach-O x86_64 external PoC on
  arm64 hosts (native function-level Unicorn/emulation remains the only tier
  there)"
- "global destination and struct-member bounds inference"
- "multi-provider/multi-model statistics and independent-case confidence
  intervals; target/PoC/contract product API; puts side-effect gate"
- "register/stack native trace (gdb unavailable)" / "AFL/fuzzing campaign"

### 4.4 Not-run list (must be listed in product materials)

| Item | Status | Reason |
|---|---|---|
| self-hosted Lima nightly | not_run | no self-hosted runner; only the local frozen-tree nightly gate exists (claims.json.ci_evidence.self_hosted_nightly) |
| international 5-6 model matrix | not_run (blocked) | SiliconFlow international balance insufficient (HTTP 402); no fifth provider key |
| external ingestion (external corpora/datasets) | not_run | no local external corpus provided; CI performs no network ingestion |
| hidden generalization | not_run | hidden private material is not distributed; only an opaque commitment and aggregate are published (0/8 verified) |
| GDB / native register-stack trace | not_run | gdb unavailable |
| AFL / fuzzing campaign | not_run | not started |
| Phase-8D / 13-16 autonomy facilities | not_run (deprioritized) | Lead decision: capability and product first |

## 5. Positioning versus competitors/alternatives

> Note: the following are factual differences at the public-positioning level.
> **No side-by-side measured comparison was run (not_run)**; this is not a
> competitive evaluation and does not disparage any alternative. Sales material
> must not invent competitor prices or performance numbers.

| Alternative | Public facts | Difference from this product | Where this product is weaker (honest) |
|---|---|---|---|
| Manual reverse engineering + expert patching | A security expert locates the sink in Ghidra/IDA and rewrites instructions | We pipeline locate/rewrite/accept/evidence for a bounded defect class; evidence is reproducible and auditable | Experts handle more complex/unknown defects; we cover only matrix-internal classes and the candidate still needs human review |
| Source-level repair (vendor patch / rebuild) | Most reliable when source exists; full test suite possible | We target the **no-source** case; when source exists, source repair should not be replaced | No full regression without source; evidence covers only the supplied PoC/regression |
| angr (open-source symbolic execution framework) | General framework for symbolic execution/program analysis | We do not claim symbolic execution as a product capability; our acceptance is a deterministic gate + independent verifier + PoC differential | Analysis depth is far below a dedicated symbolic executor; detection is only 3/24, so it cannot be used as a scanner |
| Patcherex2 (binary rewriting framework) | Provides binary rewriting/reassembly capabilities | We ship an end-to-end defect-class to patch-template to gate to evidence pipeline, and fail closed | Rewrite coverage is far below a general rewriting framework; outside the matrix we analyze only |
| Ghidra workflow (scripts/plugins) | Analysis platform with extensible scripting | We require an explicit target and PoC/regression, and emit an auditable evidence package | Less flexible than interactive Ghidra analysis; we are a pipeline, not a platform |
| Commercial binary hot-patching / virtual patching (WAF, runtime memory patches) | Typically effective at runtime (memory/network layer) and does not change on-disk binaries | We produce **offline candidate bytes + reproducible differential + evidence package** that can enter a customer change review | No measured data on commercial products; no runtime protection/virtual patching; no production-safety promise |

**Relationship to AI coding/repair tools**: AI is a **candidate generator** in this
product (asm_roundtrip / binary_direct); acceptance belongs to the deterministic
gate and the independent verifier. The current AI evidence is: 3/3 non-loop hard
cases with one model only (deepseek-flash; 3/6 non-loop in the same 12-case
matrix, v4-pro 0/3), and a 4-model pooled 36/96 (Wilson 95% CI [0.285, 0.475]).
**This is not a general AI repair claim**; the AI increment is unmeasured
(LIMITATIONS section 12).

## 6. Canonical number quick reference (all materials cite the same set)

| Metric | Value | Source |
|---|---|---|
| Public benchmark verified | **2/24 = 8.3%** (24 eligible repair cases) | benchmark/phase8c/results.json, claims.json.phase8c_ground_truth.public_benchmark |
| Public benchmark detection / root-cause / localization | **3/24 (12.5%)** each | same |
| Public sample scale | 32 samples (30 executed / 2 unsupported; dev 18 / validation 14; 24 runtime-oracle + 8 analysis-only) | same |
| false_verified (public) | **0**; 1 deterministic claim rejected by the independent verifier and withdrawn (heap-malloc) | same |
| Hidden verified | **0/8** (8/8 executed; 0 candidates; 0 false_verified; hidden_available=false) | claims.json.phase8c_ground_truth.hidden_benchmark |
| Non-loop AI hard cases | 3/3 (single model deepseek-flash; 3/6 non-loop across the 12-case matrix; v4-pro 0/3) | Lead review section 1.5.2, claims.json |
| AI model matrix | 4 models / 2 providers; pooled AI-target 36/96 = 0.375 (CI [0.285, 0.475]) | claims.json.provider_coverage.ai_target_pooled |
| Deterministic target-strict baseline | 0/12 verified (12/12 expectation match) | same |
| Verification authority | deterministic unified gate + independent verifier (9 required checks); not a whole-program/formal proof | claims.json.phase8b_verifier_semantics |
| Runtime evidence tiers | native Linux / macOS, qemu, Lima, Unicorn instruction-level emulation (not a kernel run) | claims.json, LIMITATIONS section 9 |

## 7. Wording checklist (tick before publishing)

- [ ] The document states "public 2/24 (8.3%)" and "hidden 0/8";
- [ ] No "arbitrary binary / 100% / universal repair / guaranteed safe" wording;
- [ ] Every not_run item is listed with a reason;
- [ ] Every capability statement matches claims.json / LIMITATIONS.md (fix the
      document first on conflict and report to the Lead);
- [ ] No unverified market or competitor data is used;
- [ ] Customer-facing material contains no API keys, internal paths or
      unredacted credentials (re-check with tools/handoff/scan-secrets.sh).

---

Change log:
- 2026-11-17 v0.1: initial draft (M3 P0-1). Facts locked to Phase-8C.
  Chinese version: delivery/zh/product/PRODUCT-POSITIONING-2026-11-17.md.
