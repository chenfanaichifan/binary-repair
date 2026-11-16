# Phase-8D D05: hidden no-candidate stage attribution

## Purpose

Phase-8C correctly reported that the six hidden runtime samples produced no
candidate, but it did not say where the deterministic pipeline stopped. D05
adds a private, report-derived stage diagnostic and a public counts-only
distribution. It does not change the Phase-8C frozen results, the hidden
commitment or the hidden aggregate under `benchmark/phase8c/` and
`artifacts/phase8c-*`.

## Stage model

The diagnostic observes these stages in order:

1. `parsing`
2. `function_cfg_recovery`
3. `detection`
4. `root_cause`
5. `localization`
6. `repairability`
7. `strategy_selection`
8. `plan_validation`
9. `candidate_generation`
10. `pre_verification`

A stage is `observed` only when the engine report contains the corresponding
evidence. A missing finding/candidate is `not_observed`; a stage after the first
blocking stage is `not_reached`. `analysis_only` samples are
`not_applicable`/expected-no-candidate and are excluded from the runtime
no-candidate taxonomy.

## Closed reason taxonomy

`not_vulnerable`, `unsupported_binary_format`, `unsupported_architecture`,
`decode_incomplete`, `function_boundary_unknown`, `control_flow_unknown`,
`detection_missed`, `root_cause_unknown`, `localization_incomplete`,
`alias_unknown`, `path_condition_unresolved`, `no_repair_strategy`,
`repair_plan_rejected`, `abi_unknown`, `no_safe_code_space`,
`relocation_unsupported`, `patch_generation_failed`,
`resource_budget_exhausted`, `environment_unavailable`, `other`,
`inconclusive`.

The private diagnostic adds `analysis_only` only for an expected analysis-only
sample; that value never enters the public runtime reason counts.

## Latest measured result

`artifacts/phase8d-hidden-attribution-2026-11-17/aggregate.json`:

- 8 samples = 6 runtime + 2 analysis-only;
- runtime no-candidate: 6; runtime candidates: 0;
- first blocking stage: `detection` = 6;
- no-candidate reason: `detection_missed` = 6;
- parsing and target-scope recovery observed for the 6 runtime samples;
- all later stages were not reached.

The engine report claimed `detected=true`/`repairable=true` while producing zero
findings and zero candidates for each runtime sample. D05 records this as a
**detection miss**, not as a successful detection or a repair strategy failure.
That inconsistency is retained in the private diagnostics and is a candidate
for the D06 root-cause capability work.

## Privacy rules

- Public `aggregate.json`, `README.md` and `SHA256SUMS` contain counts and
  distributions only.
- Private per-sample diagnostics are under `private/`, which is git-ignored;
  they contain opaque sample ids but no binary bytes or case paths.
- The checker rejects per-sample fields, path separators, opaque digests in
  public payloads and inconsistent denominators.
- Hidden corpus material was read only; no hidden bytes/ids/paths were copied
  into public artifacts.

## Reproduce

```bash
python scripts/run_phase8d_hidden_attribution.py --write
python scripts/run_phase8d_hidden_attribution.py --check
pytest -q tests/test_phase8d_hidden_attribution.py tests/test_phase8c_runner.py
```

The actual run requires the Lead-owned private root
`~/.binaryrepair/phase8c-hidden` (or `PHASE8C_HIDDEN_ROOT`) and its Lima guest
runner. Missing root/guest is reported as not-run, never fabricated.

## Limitations

- Attribution is derived from the deterministic report; it is not a proof of
  the missing semantic capability.
- `not_reached` does not prove a stage would fail if reached.
- Detection/root-cause remains a real capability gap; D05 does not add a
  detector or a repair.
- Hidden results are not generalisation evidence; hidden material remains
  private and only aggregate counts are published.
