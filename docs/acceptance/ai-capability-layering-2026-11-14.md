# AI capability layering - acceptance note (2026-11-14)

This note separates the capability evidence into layers so that no layer is
silently promoted into a stronger claim. The deterministic gate remains the only
acceptance authority; provider runs, reference fixes and benchmark-expectation
matches are reported at their own layer and are never combined into one score.

Artifacts:
[`artifacts/provider-matrix-2026-11-14/`](../../artifacts/provider-matrix-2026-11-14/)
(real 12-case provider matrix) and
[`artifacts/provider-coverage-2026-11-14/`](../../artifacts/provider-coverage-2026-11-14/)
(provider/model coverage, statistics, identity policy; reproducible via
`scripts/build_provider_coverage.py`). Both are SHA-256 bound (`SHA256SUMS`).

## Layer 0 - deterministic gate (acceptance authority)

- `verified_patch` is only claimed when every required gate check passes with
  native/emulated PoC+regression evidence; `static_only` is never a success.
- Benchmark hard cases: deterministic whole-image baseline is 0/12 verified
  (2 analysis_only + 10 rejected); the deterministic target-strict baseline is
  12 analysis_only, 0 verified, and matches the declared
  `baseline_expected_target_strict` disposition 12/12.
- An expectation match is a benchmark-oracle consistency measure, **not** a
  repair success. Deterministic target-strict verified rate: 0/12
  (Wilson 95% CI [0.0, 0.242501]).

## Layer 1 - deterministic repair capability (template classes)

- The deterministic pipeline repairs its declared classes (strict template,
  immediate-length, guard injection, reviewed capacity-check rewrite, heap guard
  with PoC profile) on product fixtures; those are covered by the product
  acceptance artifacts, not by the hard-case AI benchmark.
- The hard-case benchmark cases are deliberately outside the deterministic
  templates (runtime-length inline loops, semantic/multi-layer copies, UAF,
  heap guard), so the deterministic baseline is expected to be non-verified on
  all 12; this is the baseline for measuring AI increment.

## Layer 2 - AI target-mode repair (real provider dimension)

- Real provider target-assembly mode, accepted only by the native/emulated
  PoC+regression gate. Pooled identity-verified evidence: 4 models, 8 runs,
  96 cases, **36 verified (rate 0.375)**, Wilson 95% CI [0.284725, 0.474895],
  60 inconclusive.
- Per identity-verified model (DeepSeek official, exact model identity):
  `deepseek-flash` 3 runs x 6/12 = 18/36 (0.5, CI [0.344741, 0.655259]);
  `deepseek-v4-pro` 3 runs x 6/12 = 18/36 (0.5, same CI).
- SiliconFlow China free tier (exact identity): `Qwen/Qwen3-8B` 0/12 and
  `Qwen/Qwen2.5-7B-Instruct` 0/12 (real free-tier calls; 0/12 is a
  model-capability result, not a pass).
- The increment is **loop-family only**: all six loop variants verify (6/6) for
  the DeepSeek models while all six non-loop families (CWE121/multicall/sprintf/
  nonconst/UAF/heap) stay 0/6 for every model and every run. Model choice does
  not remove the non-loop ceiling.
- Served-model-only run: the single-provider matrix requested `deepseek-chat`
  but was served `deepseek-flash` (`identity_ok=false`). Its 6/12 verified
  repairs are attributed to the **served** model `deepseek-flash` and are
  **excluded** from the requested-model identity evidence and from the pooled
  identity-verified statistics above (stored separately in
  `statistics.ai_target.served_model_only`).

### Decomposition of the 6/12 AI result

The 6/12 figure is **not** a uniform capability statement: it decomposes into
loop family 6/6 verified and non-loop family 0/6 verified. The two families are
reported separately and are not interchangeable. The served-model-only 6/12 run
is a third, separate bucket and is never counted as requested-model coverage.

### 6/12 failure classification (non-loop cases, `provider-matrix` per-case evidence)

Each non-verified non-loop case has a different cause; none is silently called a
success, a rejection of the whole provider, or a platform failure. Evidence paths
are `artifacts/provider-matrix-2026-11-14/per-case/<case-id>.json`.

| case | family | AI attempt evidence | classification | next step |
|---|---|---|---|---|
| `cwe121-unchecked-strcpy` | non-template semantic validation | model returned assembly; injection rejected by assembly validation: `call target is not allowed: call 0x401380`; PoC `no_candidate` | **capability**: the leaf-only assembly path forbids the external call a semantic length check needs; the model output was well-formed | evaluate the allow-calls whitelist path (`--allow-calls`) and a deterministic semantic-validation profile; retest only with gate evidence |
| `uaf-noinput` | heap lifetime / UAF | assembly rejected: `call target is not allowed: call 0x401150` | **non_goal**: use-after-free lifetime repair is an explicit non-goal (`docs/acceptance/LIMITATIONS.md`, repair matrix non-goals) | keep as non-goal; no provider research until runtime lifetime modelling is productized |
| `hard-multicall` | semantic / multi-layer copy | candidate produced (`sha256 360415900775f8069cb2b6d04f4bd173e62692aed6e2e841f5553cd15b109f9c`), PoC gate **failed** (`runner=limactl`, `tier=emulated_run`) | **acceptance**: a candidate was produced but the deterministic acceptance gate rejected it | model research on multi-layer copy semantics; the gate remains the authority |
| `hard-sprintf` | semantic / multi-layer copy | candidate produced (`sha256 fea2843e63e9cd72e5d1d50622d612f4a2000746e4d3a00e3a54e824a45d7d54`), PoC gate **failed** | **acceptance**: candidate rejected by the gate; `sprintf`/format-string expansion stays a separate non-goal class | model research on bounded formatting semantics; do not relax the gate |
| `hard-nonconst` | semantic / multi-layer copy | candidate produced (`sha256 6247874a42091316d19ad652c60ecfa50f3997f54ce6d7a5f4bd5469e2b58476`), PoC gate **failed** | **acceptance**: candidate rejected for dynamic-length/validation semantics | model research on non-constant length validation |
| `heap-canary` | heap silent overflow / guard | assembly rejected: `call target is not allowed: call 0x10982d0` | **capability**: the leaf-only path cannot express the guard/report call it needs; heap-destination classes are also non-goals today | evaluate a heap-guard profile or keep as non-goal; no provider claim either way |
| platform | - | all candidate-producing cases executed the native/emulated PoC through the Linux guest (`limactl`, tier `emulated_run`) | **platform: not the blocker** for these cases | keep guest runtime; no platform claim needed |

Classification counts for the six non-loop cases: **capability 2, acceptance 3,
non_goal 1, platform 0**. This table is descriptive evidence for research
planning, not an acceptance authority.

## Layer 3 - reference fixes

- 6 assembly reference fixes (`.S`) are injected into the declared target and
  accepted by the same native/emulated PoC+regression gate: **6/6 verified**.
- 6 C-source reference fixes have no compiled reference artifact declared in
  `fixtures/hard-cases/cases.json`; they are recorded as `source_only` and
  counted separately. `source_only` is never counted as a pass.

## Layer 4 - non-goal / experimental classes (not claimed)

- Non-loop hard-case families are not repaired by the assembly target path while
  it is leaf-only and forbids external calls: 0/6 for every model. The six
  failures are classified explicitly as capability (2), acceptance (3),
  non_goal (1) and platform-not-the-blocker (0) in the table above; none is
  reported as a capability success or as a blanket failure.
- Heap/global destinations with dynamic sizes, cross-function allocations,
  format-string expansion, UAF fixes, integer/loop defects and other classes
  remain explicit non-goals or analysis-only results in the matrix and
  limitations docs; they are not silently promoted by provider evidence.
- Provider dimension: the international 5-6 model matrix is **not satisfied**.
  Three SiliconFlow international models passed identity probes but every
  benchmark call returned HTTP 402 insufficient balance; GLM-Z1 timed out on
  the probe; no DashScope key/artifact exists. Four models completed 12-case
  benchmarks, not 5-6. This is recorded in
  `artifacts/provider-coverage-2026-11-14/summary.json`
  (`aggregate.not_satisfied`, `aggregate.blocked_reasons`) and is never reported
  as a provider capability success.

## Rules enforced by the artifacts and tests

1. Deterministic gate authority: AI output and provider claims never promote a
   failed gate.
2. Identity policy: `identity_ok=false` rows are never identity-verified and are
   never pooled as requested-model coverage; their verified counts are
   attributed to the served model with a limitation note.
3. Separate metrics: deterministic target-strict and AI target statistics are
   reported separately; completion of a benchmark is not a pass.
4. Provenance: every number in the coverage artifact cites SHA-256-bound source
   files; the artifact is reproducible (`scripts/build_provider_coverage.py
   --check`).
5. No fabricated runtimes: blocked/unavailable providers are `not_run` /
   `blocked_unavailable`, never `rejected`-as-success or fabricated verified.
6. The 6/12 AI target result is decomposed into loop 6/6 and non-loop 0/6, and
   every non-loop failure is classified (capability/acceptance/non_goal/
   platform) against the `provider-matrix` per-case evidence.

## Summary table

| layer | scope | evidence | result | claim |
|---|---|---|---|---|
| 0 deterministic gate | acceptance authority | product acceptance packets + provider-matrix per-case gate | gate pass required for any verified claim | binding |
| 0 benchmark oracle | target-strict expectation | `provider-matrix` per-case strict baselines | 12/12 expectation matches, 0/12 verified | consistency only |
| 1 deterministic repair | template classes | product acceptance artifacts | declared classes verified on product fixtures | bounded |
| 2 AI target mode | real providers, 12 hard cases | `provider-matrix`, `multi-model-matrix-*`, per-case failure classification | identity-verified pooled 36/96 (0.375, CI [0.285, 0.475]); **6/12 = loop 6/6 + non-loop 0/6**; served-model-only 6/12 excluded | model-robustness for loop family only; non-loop failures classified |
| 3 reference fixes | 6 `.S` / 6 `.c` | `provider-matrix` reference rows | 6/6 `.S` verified; 6 `.c` source_only (not a pass) | bounded reference check |
| 4 non-goals / international | non-loop families, blocked providers | matrix, limitations, provider coverage | explicit non-goals; international matrix not satisfied | not claimed |

## Next steps

1. Obtain a funded SiliconFlow international or DashScope/Bailian key and run the
   12-case benchmark for the remaining identity-probed models; then rerun the
   total 5-6 model matrix in CI with strict identity and native/emulated PoC.
2. Keep the deterministic-vs-AI layering and served-model attribution rules when
   adding providers; never re-label source_only or expectation matches as
   verified repairs.
3. Only then update release claims to a 5-6-model / 3-provider AI matrix.
