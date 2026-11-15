# Phase-8C readiness verdict (C1)

- base_sha: `227f45b39d85a7cd95e8589beb07dcfc89cd22d7` (expected `227f45b39d85a7cd95e8589beb07dcfc89cd22d7`)
- status: **ok**
- reproduction: reproduced
- blockers: 4; warnings: 3

## Answer summary

| question | status | answer |
|---|---|---|
| Q01 | answered | branch=feature/phase8c-ground-truth-v2 head=227f45b39d85a7cd95e8589beb07dcfc89cd22d7 (expected 227f45b39d85a7cd95e8589beb07dcfc89cd22d7); tag release-2026-11-16-phase8b={'ref': 'release-2026-11-16-phase8b', 'sha': '1bfdf674fecef3c3357482a6a05c46cfa09eed93'}; evidence tag={'ref': 'release-2026-11-16-phase8b-evidence', 'sha': '1edcce2d1c8d9d06cddb538e210205ea6a3dbbc7'}; drift_status=ok; findings=['Phase-8B release evidence is bound to gated SHA c5d87b570e4a2d87816d482e22871a7a49a35f7a, not the cur |
| Q02 | answered | 12/12 samples present and lossless=12; required fields missing=False; v2 gaps=['manifest wrapper has no explicit benchmark_version / v1->v2 mapping block (schema_version=1 today)', 'manifest wrapper hidden fields exist but only hidden_available=false and hidden_commitment_sha256=null; no public/hidden split policy or aggregate-only results contract', 'samples have no optional authority block in v1 (contract supports it); Phase-8C samples must declare scope_policy/authorized_changes/plan binding  |
| Q03 | reproduced | status=reproduced; samples=[{'sample_id': 'heap-capacity-x86_64', 'candidate_sha256': '93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2', 'verifier_decision': 'verified', 'independently_verified': True, 'oracle_status': 'pass'}, {'sample_id': 'stack-strcpy-x86_64', 'candidate_sha256': '1bc66b2ee28e2370cca1fcea624378e72afcafeac02c1da4eead689cd64ff6f4', 'verifier_decision': 'verified', 'independently_verified': True, 'oracle_status': 'pass'}] |
| Q04 | answered | contracts=13 (acceptance.schema, benchmark-sample.schema, binary-target.schema, capability.schema, evidence.schema, gap.schema, patch-candidate.schema, patch-plan.schema, reflection.schema, repair.schema, root-cause.schema, verification.schema, vulnerability-finding.schema); benchmark-sample required=19; hidden fields=True; authority=True; patch-plan=True; manifest-wrapper=False; hidden-commitment=False; results=False; checker_exit=0 |
| Q05 | answered | private_root=/Users/huageorge/.binaryrepair/phase8c-hidden exists=False perms=None env=PHASE8C_HIDDEN_ROOT; hidden_available=False; hidden corpus not created/read by C1; isolation is operational, not cryptographic; see phase8c-hidden-isolation-plan.md |
| Q06 | answered | guest_runner={'available': True, 'kind': 'lima', 'tier': 'emulated_run', 'tool': '/opt/homebrew/bin/limactl', 'instance': 'binaryrepair'}; call_site_files=['app/services/guest_runner.py', 'app/services/poc_runner.py', 'scripts/run_hard_benchmark.py', 'scripts/run_repair_benchmark.py', 'scripts/release_gate.py', 'scripts/verify_repair_benchmark.py', 'scripts/verify_repair.py', 'app/services/independent_verifier.py']; lock_status=not_implemented_no_global_lock; proposed={'proposed_path': '$HOME/.b |
| Q07 | answered | tasks=['C01', 'C02', 'C03', 'C04', 'C05', 'C06', 'C07', 'C08', 'C09', 'C10', 'C11', 'C12', 'C13', 'C14']; parallel_groups={'G0': ['C01'], 'G1': ['C02', 'C04', 'C05', 'C07', 'C09'], 'G2': ['C03', 'C06', 'C08'], 'G3': ['C10', 'C11'], 'G4': ['C12', 'C13'], 'G5': ['C14']}; serial=['C01 before any Phase-8C production work', 'C02 contracts before C03/C04/C05/C07/C08/C13', 'C05 before C06/C08/C11 hidden paths', 'C09 before gate/CI shadow real guest runs (C10/C14)'] |
| Q08 | answered | release_gate modes={'pr': 4, 'release': 12, 'nightly': 13}; release=12 nightly=13 pr=4; shadow=shadow_not_gating; claims_g29={'measured_status': 'not_run', 'blocker': 'hidden benchmark unavailable (hidden_available=false); the registry must never fabricate a hidden run'} |
| Q09 | answered | prepare fields (not implemented this phase): benchmark_version (v1/v2) and hidden/public visibility of every sample/result; sample/binary sha + authority/provenance refs so a discovery candidate can point at real bytes; oracle evidence refs (runner/tier/manifest sha) to distinguish oracle gaps from detector gaps; commitment_ref for hidden aggregates (never per-sample hidden identifiers); discovery_source and proposed_experiment for every candidate (already in GapRecord; v2 must preserve them in  |
| Q10 | answered | work breakdown C1-C14 in phase8c-work-breakdown.json; blockers=['B-P8B-EVIDENCE-BINDING:warning', 'B-HIDDEN-ROOT:blocker_for_hidden_paths', 'B-TOOLCHAIN-ZIG:warning', 'B-GATE-COUNT:warning'] |

## Blockers

- `B-P8B-EVIDENCE-BINDING` (warning): Phase-8B release evidence is bound to gated SHA c5d87b5, not the current mainline 227f45b; Phase-8C must bind its own base/gated SHA and may not reuse the evidence as if it covered the Phase-8C tree. blocks=['C12', 'C14']
- `B-HIDDEN-ROOT` (blocker_for_hidden_paths): Hidden private root is Lead-owned and absent; C1 does not create/read it. C05/C06/C08/C11 hidden paths remain blocked/not_run until the Lead provisions the root. blocks=['C05', 'C06', 'C08', 'C11']
- `B-TOOLCHAIN-ZIG` (warning): Zig is not on PATH; public corpus/compiler expansion in C04 is limited to clang/system toolchain unless the Lead provisions Zig. blocks=['C04']
- `B-GATE-COUNT` (warning): Measured release-gate checks: release=12, nightly=13, pr=4; the task premise says 13 required. C10 must confirm the release-mode count with the Lead before claiming it. blocks=['C10']

## Warnings

- Phase-8B release evidence is bound to gated SHA c5d87b570e4a2d87816d482e22871a7a49a35f7a, not the current HEAD 227f45b39d85a7cd95e8589beb07dcfc89cd22d7; Phase-8C must record its own base/gated SHA and cannot reuse the Phase-8B evidence as covering this tree
- the Phase-8B local gate artifact directory referenced by claims is not present in this worktree (evidence branch only); no file-level evidence binding is available locally
- Zig absent: public corpus/compiler expansion limited until Lead provisions Zig

## Verdict

C2 (v2 contracts + migration) and C11 (hidden isolation design/tests) are unblocked to start from this baseline, with the hidden execution paths blocked until the Lead provisions the private root. Phase-8B evidence is not reused as if it covered this mainline; Phase-8C must record its own base/gated SHA.
