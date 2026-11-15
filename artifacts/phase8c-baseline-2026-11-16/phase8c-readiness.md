# Phase-8C readiness verdict (C1)

- base_sha: `6d7ad861694e287cf446cdc195990bcf7889dd2c` (expected `f42e6c4f39b584575f59b13d67f40572b3ca278c`)
- status: **ok_rebaselined_with_flaky_reproduction**
- reproduction: reproduced
- blockers: 5; warnings: 5

## Answer summary

| question | status | answer |
|---|---|---|
| Q01 | answered | branch=feature/phase8c-ground-truth-v2 head=6d7ad861694e287cf446cdc195990bcf7889dd2c (audit commit; parent=f42e6c4f39b584575f59b13d67f40572b3ca278c, rebased mainline=f42e6c4f39b584575f59b13d67f40572b3ca278c, original C1 baseline=227f45b39d85a7cd95e8589beb07dcfc89cd22d7); tag release-2026-11-16-phase8b={'ref': 'release-2026-11-16-phase8b', 'sha': '1bfdf674fecef3c3357482a6a05c46cfa09eed93'}; evidence tag={'ref': 'release-2026-11-16-phase8b-evidence', 'sha': '1edcce2d1c8d9d06cddb538e210205ea6a3dbbc |
| Q02 | answered | 12/12 samples present and lossless=12; required fields missing=False; v2 gaps=['external P16-R3 already added v2 contracts (benchmark-manifest-v2, benchmark-results-v2, ground-truth-sample-v2, hidden-benchmark-commitment: contracts dir is now 17); C2 must reconcile/adopt them, not recreate them', 'the v1 manifest is still schema_version 1: the lossless v1->v2 migration builder/mapping artifact (C03) is still required', 'v1 samples do not carry optional authority/plan binding fields even though t |
| Q03 | reproduced | status=reproduced; samples=[{'sample_id': 'heap-capacity-x86_64', 'candidate_sha256': '93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2', 'verifier_decision': 'verified', 'independently_verified': True, 'oracle_status': 'pass'}, {'sample_id': 'stack-strcpy-x86_64', 'candidate_sha256': '1bc66b2ee28e2370cca1fcea624378e72afcafeac02c1da4eead689cd64ff6f4', 'verifier_decision': 'verified', 'independently_verified': True, 'oracle_status': 'pass'}]; stability=flaky_observed_1_of_2_defaul |
| Q04 | answered | contracts=17 (acceptance.schema, benchmark-manifest-v2.schema, benchmark-results-v2.schema, benchmark-sample.schema, binary-target.schema, capability.schema, evidence.schema, gap.schema, ground-truth-sample-v2.schema, hidden-benchmark-commitment.schema, patch-candidate.schema, patch-plan.schema, reflection.schema, repair.schema, root-cause.schema, verification.schema, vulnerability-finding.schema); benchmark-sample required=19; hidden fields=True; authority=True; patch-plan=True; manifest-wrappe |
| Q05 | answered | private_root=/Users/huageorge/.binaryrepair/phase8c-hidden exists=True perms=0o700 env=PHASE8C_HIDDEN_ROOT; hidden_available=False; hidden corpus not created/read by C1; isolation is operational, not cryptographic; see phase8c-hidden-isolation-plan.md |
| Q06 | answered | guest_runner={'available': True, 'kind': 'lima', 'tier': 'emulated_run', 'tool': '/opt/homebrew/bin/limactl', 'instance': 'binaryrepair'}; call_site_files=['app/services/guest_runner.py', 'app/services/poc_runner.py', 'scripts/run_hard_benchmark.py', 'scripts/run_repair_benchmark.py', 'scripts/release_gate.py', 'scripts/verify_repair_benchmark.py', 'scripts/verify_repair.py', 'app/services/independent_verifier.py']; lock_status=not_implemented_no_global_lock; proposed={'proposed_path': '$HOME/.b |
| Q07 | answered | tasks=['C01', 'C02', 'C03', 'C04', 'C05', 'C06', 'C07', 'C08', 'C09', 'C10', 'C11', 'C12', 'C13', 'C14']; parallel_groups={'G0': ['C01'], 'G1': ['C02', 'C04', 'C05', 'C07', 'C09'], 'G2': ['C03', 'C06', 'C08'], 'G3': ['C10', 'C11'], 'G4': ['C12', 'C13'], 'G5': ['C14']}; serial=['C01 before any Phase-8C production work', 'C02 contracts before C03/C04/C05/C07/C08/C13', 'C05 before C06/C08/C11 hidden paths', 'C09 before gate/CI shadow real guest runs (C10/C14)'] |
| Q08 | answered | release_gate modes={'pr': 4, 'release': 12, 'nightly': 13}; release=12 nightly=13 pr=4; shadow=shadow_not_gating; claims_g29={'measured_status': 'not_run', 'blocker': 'hidden benchmark unavailable (hidden_available=false); the registry must never fabricate a hidden run'} |
| Q09 | answered | prepare fields (not implemented this phase): benchmark_version (v1/v2) and hidden/public visibility of every sample/result; sample/binary sha + authority/provenance refs so a discovery candidate can point at real bytes; oracle evidence refs (runner/tier/manifest sha) to distinguish oracle gaps from detector gaps; commitment_ref for hidden aggregates (never per-sample hidden identifiers); discovery_source and proposed_experiment for every candidate (already in GapRecord; v2 must preserve them in  |
| Q10 | answered | work breakdown C1-C14 in phase8c-work-breakdown.json; blockers=['B-P8B-EVIDENCE-BINDING:warning', 'B-HIDDEN-ROOT:coordination_required_for_hidden_paths', 'B-TOOLCHAIN-ZIG:warning', 'B-GATE-COUNT:warning'] |

## Blockers

- `B-P8B-EVIDENCE-BINDING` (warning): Phase-8B release evidence is bound to gated SHA c5d87b5, not the current mainline 227f45b; Phase-8C must bind its own base/gated SHA and may not reuse the evidence as if it covered the Phase-8C tree. blocks=['C12', 'C14']
- `B-HIDDEN-ROOT` (coordination_required_for_hidden_paths): Hidden private root is Lead-owned and now exists with mode 0700; C1 stats it only and never reads hidden contents. hidden_available remains false and no hidden run is claimed; C05/C06/C08/C11 still require Lead coordination and must keep hidden results not_run until executed under the private root. blocks=['C05', 'C06', 'C08', 'C11']
- `B-TOOLCHAIN-ZIG` (warning): Zig is not on PATH; public corpus/compiler expansion in C04 is limited to clang/system toolchain unless the Lead provisions Zig. blocks=['C04']
- `B-GATE-COUNT` (warning): Measured release-gate checks: release=12, nightly=13, pr=4; the task premise says 13 required. C10 must confirm the release-mode count with the Lead before claiming it. blocks=['C10']
- `B-POST-REBASE-REPRODUCTION-FLAKY` (warning_for_verification_claims): on the rebased tree the same two-sample default run both failed (false_verified=1, verifier rejected a claim) and later reproduced 2/2 independently verified; the reproduction is not deterministically stable, so Phase-8C evidence claims must record the attempt history and cannot claim unconditional 2/2 stability blocks=['C12', 'C14']

## Warnings

- post-audit rebase: original C1 baseline 227f45b39d85a7cd95e8589beb07dcfc89cd22d7 -> branch head 6d7ad861694e287cf446cdc195990bcf7889dd2c (parent f42e6c4f39b584575f59b13d67f40572b3ca278c, rebased mainline f42e6c4f39b584575f59b13d67f40572b3ca278c); C1 facts/reproduction were refreshed on the rebased tree
- Phase-8B release evidence is bound to gated SHA c5d87b570e4a2d87816d482e22871a7a49a35f7a, not the current HEAD 6d7ad861694e287cf446cdc195990bcf7889dd2c; Phase-8C must record its own base/gated SHA and cannot reuse the Phase-8B evidence as covering this tree
- the Phase-8B local gate artifact directory referenced by claims is not present in this worktree (evidence branch only); no file-level evidence binding is available locally
- post-rebase reproduction is flaky across attempts: one default run failed with false_verified=1 while the diagnostic withdraw run and a second default run verified both samples; C12/C14 must not claim unconditional stability until the flake is triaged
- Zig absent: public corpus/compiler expansion limited until Lead provisions Zig

## Verdict

C2 (v2 contracts + migration) and C11 (hidden isolation design/tests) are unblocked to start from this baseline, with the hidden execution paths blocked until the Lead provisions the private root. Phase-8B evidence is not reused as if it covered this mainline; Phase-8C must record its own base/gated SHA.
