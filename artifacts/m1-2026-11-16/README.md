# M1 evidence - 2026-11-16 (CWE-121 failure_behavior + controlled calls)

This directory holds the P0-1 evidence of the M1 capability increment. Every
artifact is labelled by its authority:

- gate: the native/guest PoC runner (run_poc) is the only acceptance gate;
  the independent verifier makes the independent decision.
- auxiliary: field-level comparisons and scripted plan/assembly evidence are
  diagnostics, never a gate substitute.

## Files

| File | What it is | Authority |
|---|---|---|
| cwe121-failure-behavior-evidence.json | CWE-121 candidate from the repository reference assembly, run through run_poc (limactl) plus a field-by-field comparison against the PoC contract | gate result + auxiliary field comparison |
| cwe121-reference-candidate.bin | candidate bytes produced by the reference assembly and the controlled-call templates | artifact |
| run-cwe121-reference/ | standard hard-benchmark run dir (client=reference): run-manifest.json + summary.json + candidate | gate (PoC) |
| independent-verification-cwe121/ | independent verifier decision for the candidate above | independent gate |
| scripted-plan-assembly-evidence.json | scripted RepairSpec v2 planner + reference assembly through plan validation, template injection and ABI check (no live model) | auxiliary protocol evidence |
| cwe134-plan-diagnostics-evidence.json | P0-2: CWE-134 historical plan shape -> typed field diagnostic; corrected plan -> plan_valid + format_string; scripted minimal format fix through the native PoC gate | gate result + auxiliary diagnostics |
| cwe134-reference-candidate.bin | CWE-134 candidate bytes (fixed "%s" format) | artifact |
| scripts/ | deterministic generators for the evidence files above | tooling |

Key recorded facts:

- run-cwe121-reference: baseline_verified=0, ai_verified=1, ai_increment=1
  (client=reference; this is a protocol/capability demonstration, not a model
  quality result).
- independent-verification-cwe121: decision=verified, 9/9 checks passed,
  runtime-oracle runner=limactl tier=emulated_run.
- cwe121-failure-behavior-evidence.json: gate=pass, 14/14 field checks matched
  (2 PoC cases + 4 regression cases vs the declared candidate expectations).
- scripted-plan-assembly-evidence.json: plan_valid=true,
  templates=[br_exit_group, br_write_stderr], injection ok, ABI ok.
- cwe134-plan-diagnostics-evidence.json: the historical plan shape is
  rejected with field=program_context.addresses and expected scope
  [0x401156, 0x40117f); the corrected in-scope plan validates with
  strategy=format_string; the scripted minimal format fix passes the native
  PoC gate (limactl, tier emulated_run), with PoC and regression matched.

## Claim boundary

- Can claim: the structured failure_behavior contract and the fail-closed
  controlled-call templates work end to end for CWE-121 through the real
  pipeline and reach an independent-verifier "verified" with a deterministic
  reference assembly stand-in.
- Cannot claim: AI/model quality improvement, or the non-loop 3/6 -> 4/6
  matrix movement; no live model was called in this increment.
- not_run: any live provider call (no key use authorised); AI-generated CWE-121
  candidate; AI-generated CWE-134 candidate; uaf-noinput and heap-canary
  reruns.
