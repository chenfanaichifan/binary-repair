# Phase-8C readiness verdict (C1)

- base_sha: `910e4f7b8361dca25bb765a34cc603afff2e11f3` (expected `a1755a5e661665218da93e967a535e359932975a`)
- status: **ok_rebaselined**
- reproduction: reproduced
- blockers: 3; warnings: 5

## Answer summary

| question | status | answer |
|---|---|---|
| Q01 | answered | branch=feature/phase8c-ground-truth-v2 head=910e4f7b8361dca25bb765a34cc603afff2e11f3 (audit commit; parent=a97dd703b6e4210883658a08dd013f118b37f4b2, rebased mainline=a1755a5e661665218da93e967a535e359932975a, original C1 baseline=227f45b39d85a7cd95e8589beb07dcfc89cd22d7); tag release-2026-11-16-phase8b={'ref': 'release-2026-11-16-phase8b', 'sha': '1bfdf674fecef3c3357482a6a05c46cfa09eed93'}; evidence tag={'ref': 'release-2026-11-16-phase8b-evidence', 'sha': '1edcce2d1c8d9d06cddb538e210205ea6a3dbbc |
| Q02 | answered | 12/12 samples present and lossless=12; required fields missing=False; v2 gaps=['external P16-R3 already added v2 contracts (benchmark-manifest-v2, benchmark-results-v2, ground-truth-sample-v2, hidden-benchmark-commitment: contracts dir is now 17); C2 must reconcile/adopt them, not recreate them', 'the v1 manifest is still schema_version 1: the lossless v1->v2 migration builder/mapping artifact (C03) is still required', 'v1 samples do not carry optional authority/plan binding fields even though t |
| Q03 | reproduced | status=reproduced; samples=[{'sample_id': 'heap-capacity-x86_64', 'candidate_sha256': '93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2', 'verifier_decision': 'verified', 'independently_verified': True, 'oracle_status': 'pass'}, {'sample_id': 'stack-strcpy-x86_64', 'candidate_sha256': '1bc66b2ee28e2370cca1fcea624378e72afcafeac02c1da4eead689cd64ff6f4', 'verifier_decision': 'verified', 'independently_verified': True, 'oracle_status': 'pass'}]; stability=one_off_flake_not_reproduced |
| Q04 | answered | contracts=17 (acceptance.schema, benchmark-manifest-v2.schema, benchmark-results-v2.schema, benchmark-sample.schema, binary-target.schema, capability.schema, evidence.schema, gap.schema, ground-truth-sample-v2.schema, hidden-benchmark-commitment.schema, patch-candidate.schema, patch-plan.schema, reflection.schema, repair.schema, root-cause.schema, verification.schema, vulnerability-finding.schema); benchmark-sample required=19; hidden fields=True; authority=True; patch-plan=True; manifest-wrappe |
| Q05 | answered | private_root=/Users/huageorge/.binaryrepair/phase8c-hidden exists=True perms=0o700 env=PHASE8C_HIDDEN_ROOT; hidden_available=False; hidden corpus not created/read by C1; isolation is operational, not cryptographic; see phase8c-hidden-isolation-plan.md |
| Q06 | answered | guest_runner={'available': True, 'kind': 'lima', 'tier': 'emulated_run', 'tool': '/opt/homebrew/bin/limactl', 'instance': 'binaryrepair'}; call_site_files=['app/services/guest_runner.py', 'app/services/poc_runner.py', 'scripts/run_hard_benchmark.py', 'scripts/run_repair_benchmark.py', 'scripts/release_gate.py', 'scripts/verify_repair_benchmark.py', 'scripts/verify_repair.py', 'app/services/independent_verifier.py']; lock_status=not_implemented_no_global_lock; proposed={'proposed_path': '$HOME/.b |
| Q07 | answered | tasks=['C01', 'C02', 'C03', 'C04', 'C05', 'C06', 'C07', 'C08', 'C09', 'C10', 'C11', 'C12', 'C13', 'C14']; parallel_groups={'G0': ['C01'], 'G1': ['C02', 'C04', 'C05', 'C07', 'C09'], 'G2': ['C03', 'C06', 'C08'], 'G3': ['C10', 'C11'], 'G4': ['C12', 'C13'], 'G5': ['C14']}; serial=['C01 before any Phase-8C production work', 'C02 contracts before C03/C04/C05/C07/C08/C13', 'C05 before C06/C08/C11 hidden paths', 'C09 before gate/CI shadow real guest runs (C10/C14)'] |
| Q08 | answered | release_gate modes={'pr': 4, 'release': 12, 'nightly': 13}; release=12 nightly=13 pr=4; shadow=shadow_not_gating; claims_g29={'measured_status': 'not_run', 'blocker': 'hidden benchmark unavailable (hidden_available=false); the registry must never fabricate a hidden run'} |
| Q09 | answered | prepare fields (not implemented this phase): benchmark_version (v1/v2) and hidden/public visibility of every sample/result; sample/binary sha + authority/provenance refs so a discovery candidate can point at real bytes; oracle evidence refs (runner/tier/manifest sha) to distinguish oracle gaps from detector gaps; commitment_ref for hidden aggregates (never per-sample hidden identifiers); discovery_source and proposed_experiment for every candidate (already in GapRecord; v2 must preserve them in  |
| Q10 | answered | work breakdown C1-C14 in phase8c-work-breakdown.json; active blockers=['B-P8B-EVIDENCE-BINDING:warning', 'B-TOOLCHAIN-ZIG:warning', 'B-GATE-COUNT:warning']; runtime_repeat_evidence=repeat_sha_a477ea3cbea062c03f3ee91b8fdd779ecf70f6bbb6e119a37e19fd881e688b4a; flake=documented_warning_not_blocker |

## Blockers

- `B-P8B-EVIDENCE-BINDING` (warning): Phase-8B release evidence is bound to gated SHA c5d87b5, not the current mainline 227f45b; Phase-8C must bind its own base/gated SHA and may not reuse the evidence as if it covered the Phase-8C tree. blocks=['C12', 'C14']
- `B-TOOLCHAIN-ZIG` (warning): Zig is not on PATH; public corpus/compiler expansion in C04 is limited to clang/system toolchain unless the Lead provisions Zig. blocks=['C04']
- `B-GATE-COUNT` (warning): Measured release-gate checks: release=12, nightly=13, pr=4; the task premise says 13 required. C10 must confirm the release-mode count with the Lead before claiming it. blocks=['C10']

## Warnings

- post-audit rebase: original C1 baseline 227f45b39d85a7cd95e8589beb07dcfc89cd22d7 -> f42e6c4f39b584575f59b13d67f40572b3ca278c -> current mainline a1755a5e661665218da93e967a535e359932975a; branch head 910e4f7b8361dca25bb765a34cc603afff2e11f3 is 10 first-parent commit(s) after the mainline; C1 facts/reproduction were refreshed on the final rebased tree
- Phase-8B release evidence is bound to gated SHA c5d87b570e4a2d87816d482e22871a7a49a35f7a, not the current HEAD 910e4f7b8361dca25bb765a34cc603afff2e11f3; Phase-8C must record its own base/gated SHA and cannot reuse the Phase-8B evidence as covering this tree
- the Phase-8B local gate artifact directory referenced by claims is not present in this worktree (evidence branch only); no file-level evidence binding is available locally
- documented flake warning (not a C12/C14 blocker): one-off f42 reproduction attempt failed with false_verified=1; it was not reproduced across the two serialized C6/C10 repeats under the C11 lock. Unconditional stability is still not claimed; attempt history and repeat sha a477ea3c... are recorded in runtime_repeat_evidence
- Zig absent: public corpus/compiler expansion limited until Lead provisions Zig

## Verdict

Final C1 baseline record for release: C1-C13 commits are on the a1755a5e-ordered tree, the two Phase-8B samples reproduce 2/2 as independently verified, the two serialized C6/C10 repeats are identical (results sha a477ea3c..., published false_verified=0), and the hidden aggregate is 8/6/2 with 0 verified/0 false. The earlier one-off flake remains a documented warning, not a C12/C14 blocker; unconditional stability is not claimed. Phase-8B evidence is not reused as if it covered this tree; Phase-8C records its own base commit and gated evidence.
