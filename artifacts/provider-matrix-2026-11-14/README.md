# Provider matrix - 12 hard cases (target-strict measurement)

Generated: `2026-11-14T13:08:04Z`

## Run

```
run_provider_matrix.py --out artifacts/provider-matrix-2026-11-14 --client real --repeats 1 --max-seconds 2700 --max-calls 40 --provider-tag deepseek-chat-real
```

- provider run mode: `real`
- provider: `deepseek` / configured model `deepseek-chat`
- model returned by provider: `deepseek-flash` (identity_ok=False)
- provider status: `ok`
- seed: `None` (seed_supported=False)
- cost: `None` - provider API exposes token usage only; no price table configured
- repeats per case: `1` / contract level `full`
- elapsed: `253694` ms; provider calls `13` (budget `40` calls / `2700` s)

## Per-case matrix

| case | whole-image | target-strict | strict expected | target scope | AI status | AI verified | AI in scope | AI sha256 | ref |
|---|---|---|---|---|---|---|---|---|---|
| inline-byte-loop | rejected | analysis_only | True | True | accepted | True | True | 12aa3371ac22 | verified/True |
| cwe121-unchecked-strcpy | analysis_only | analysis_only | True | True | accepted | False | False | - | source_only/None |
| hard-loop16 | rejected | analysis_only | True | True | accepted | True | True | cd8275d08b4a | verified/True |
| hard-loop32 | rejected | analysis_only | True | True | accepted | True | True | 79e04054cb73 | verified/True |
| hard-reverse | rejected | analysis_only | True | True | accepted | True | True | 426c7e18d6fd | verified/True |
| hard-multicall | rejected | analysis_only | True | True | accepted | False | True | 360415900775 | source_only/None |
| hard-sprintf | rejected | analysis_only | True | True | accepted | False | True | fea2843e63e9 | source_only/None |
| hard-nonconst | rejected | analysis_only | True | True | accepted | False | True | 6247874a4209 | source_only/None |
| hard-loop8 | rejected | analysis_only | True | True | accepted | True | True | ab343eea54a6 | verified/True |
| hard-loop64 | rejected | analysis_only | True | True | accepted | True | True | 2d01ec86126c | verified/True |
| uaf-noinput | analysis_only | analysis_only | True | True | accepted | False | False | - | source_only/None |
| heap-canary | rejected | analysis_only | True | True | accepted | False | False | - | source_only/None |

## Aggregates

| metric | value |
|---|---|
| cases | 12 |
| baseline_whole_image_verified | 0 |
| baseline_target_strict_verified | 0 |
| baseline_target_strict_expected_matches | 12 |
| target_strict_pass_rate | 1.0 |
| target_scope_resolved | 12 |
| target_scope_resolved_rate | 1.0 |
| target_in_scope | 0 |
| target_in_scope_rate | 0.0 |
| ai_target_verified | 6 |
| ai_target_verified_rate | 0.5 |
| ai_target_in_scope | 9 |
| ai_target_in_scope_rate | 0.75 |
| reference_evaluated | 6 |
| reference_verified | 6 |
| reference_source_only | 6 |
| elapsed_ms | 253694 |
| cost_total | None |

## Inconclusive / failure reasons

```json
{
  "ai:accepted/fail": 3,
  "ai:accepted/no_candidate": 3,
  "reference:source_only": 6,
  "whole_image:analysis_only": 2,
  "whole_image:rejected": 10
}
```

## Definitions

- `baseline_whole_image`: deterministic pipeline run under the whole-image policy (`allow_whole_image=True` when the safe-default policy is available; historical whole-image behaviour otherwise).
- `baseline_target_strict`: `repair_any(target=<case target>, require_target=True)`; records the resolved target scope and whether every produced action is inside it. The hard cases are deliberately outside the deterministic templates, so the expected target-strict disposition is `analysis_only` with no actions (empty action lists are not counted as in scope).
- `target_strict_pass_rate` = cases whose deterministic target-strict disposition matches `fixtures/hard-cases/cases.json` `baseline_expected_target_strict` (falling back to `baseline_expected` when that field is omitted), divided by cases.
- `target_in_scope_rate` = deterministic target-strict baselines whose actions all fall inside the resolved target scope, divided by cases (0.0 when no actions are produced).
- `ai_target`: real provider (or `--client reference` scripted) target-assembly mode; accepted only by the native/emulated PoC+regression runner. `ai_target_in_scope_rate` measures how often the injected repair stayed on the declared target function.
- Reference fixes declared as C source have no compiled reference artifact in `cases.json`; they are recorded as `source_only` and counted separately, never as a pass.

## Honesty / limitations

- The provider key, prompts and raw model responses are never stored or printed.
- Cost is not exposed by the provider API; token usage and wall-clock time are recorded instead and `cost` is `null` (never a fabricated zero).
- The seed is recorded but the shared provider client does not marshal a seed to the API (`seed_supported=false`).
- PoC/regression execution uses the native/qemu/Lima guest runner; when no runner is available the PoC evidence is recorded as `unavailable` and is never counted as verified.
- A provider auth/quota/network failure stops the AI phase and is recorded with its typed error; the deterministic/reference evidence for every case is still produced.

Run-specific limitations:
- 6 C-source reference fixes have no compiled reference artifact declared in cases.json and were not PoC-executed (source_only)
- provider returned a different model than requested (model_requested='deepseek-chat', model_returned='deepseek-flash'); results are recorded as served, identity check false, and are not excluded

