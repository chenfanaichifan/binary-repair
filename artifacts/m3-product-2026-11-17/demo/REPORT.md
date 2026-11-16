# BinaryRepair product demo

- Generated at (UTC): 2026-11-16T04:08:29Z
- Run at: 2026-11-16T04:05:41Z; 45.71 s
- Host: darwin/arm64, Python 3.11.8
- Execution path: app.services.binary_pipeline.repair_any | AI used: no | Network: no | API key: not required
- Independent verifier: app/services/independent_verifier.py (available)

## 0. Product boundary (read before any delivery)

| Item | Statement |
|---|---|
| Positioning | bounded binary repair with auditable evidence; not universal repair |
| Public benchmark | 2/24 verified (8.3%) |
| Hidden benchmark | 0/8 verified |
| Detection/localization/root-cause | detection/root-cause/localization 3/24 (12.5%) each |
| Repair scope | one target function/sink per candidate; deterministic matrix only |
| Verification scope | deterministic unified gate + independent verifier; scope is the supplied PoC/regression cases and the one repaired function, not a whole-program proof |

**Not claimed (canonical wording):**

- arbitrary binary / arbitrary vulnerability / whole-program repair
- hidden generalisation or independently verified hidden repairs
- cross-compiler verification with a second toolchain
- new vulnerability-repair capability or automatic capability promotion
- that a repaired binary is safe for production use

## 1. Execution summary

| fixture | expected | verdict | disposition | independent verification | oracle | runtime tier |
|---|---|---|---|---|---|---|
| strcpy-stack-x86_64 | verified | VERIFIED_WITHIN_SCOPE | verified_patch | verified | pass | emulated_run |
| marcx-capacity | verified | VERIFIED_WITHIN_SCOPE | verified_patch | verified | pass | emulated_run |
| unsupported-bigendian | refused | REFUSED | unsupported | not_run | not_run |  |

## 2. Per-fixture results

### 2.1 strcpy-stack-x86_64 - VERIFIED_WITHIN_SCOPE

- Verdict: verified within scope
- Note: verified scope = one target function/sink + the supplied PoC/regression cases + the independent verifier checks. It is not a whole-program proof and does not mean the repaired binary is safe for production use.
- Reason: guard candidate appends 3926 cave/PT_LOAD bytes at file offset 4911312; the call redirect and header/program-header updates are declared as reviewed_site/header_update operations

**Input**: fixtures/elf/vuln-strcpy-x86_64.elf | SHA256 c81017fafff3f57fee32331a6de9a3c77b702069a92f3b19eab77798416295a4

**Scan**: format=elf arch=x86_64 matrix_cell=elf/x86_64/64/little findings=6 repair_supported=True

**Repair**:

| field | value |
|---|---|
| disposition | verified_patch |
| candidate_sha256 | 1bc66b2ee28e2370cca1fcea624378e72afcafeac02c1da4eead689cd64ff6f4 |
| patch_plan_sha256 | 2796f7b76dfe4723e762fe5a044b9b4118fbd4ece5427f76f6ed55b8e1669f7e |
| integrity | True |
| gate_outcome | success_within_scope |
| poc_status | pass |
| runtime_tier | emulated_run |
| layout_status | passed |
| false_verified | False |

**Verification**: independent_decision=verified | verifier_id=independent-verifier/1 | real_verification=True

**Verification checks**

| check | required | status | detail |
|---|---|---|---|
| identity | True | passed | original=c81017fafff3f57fee32331a6de9a3c77b702069a92f3b19eab77798416295a4 candidate=1bc66b2ee28e2370cca1fcea624378e72afcafeac02c1da4eead689cd64ff6f4 |
| container | True | passed | format=elf arch=x86_64 bits=64 endian=little |
| layout-plan | True | passed | plan 8bd9649e2df10aab replay matches the candidate: operations=9 changed_ranges=9 cave=yes associated=7 |
| action-replay | True | passed | plan replay covers all changed bytes: changed_ranges=9 |
| target-scope | True | passed | policy=target_scoped_associated scope=[0x102bab4, 0x102bae0) ops=9 reviewed_sites=1 |
| abi | True | passed | ABI ok for 1 derived block(s) sources=plan.abi_blocks |
| runtime-oracle | True | passed | independent oracle passed (runner=limactl tier=emulated_run cases=4) |
| evidence-completeness | True | passed | one independent external oracle passed |
| independence | True | passed | generator identity is distinct and its evidence is excluded from the decision |

**Limitations**

- guard candidate appends 3926 cave/PT_LOAD bytes at file offset 4911312; the call redirect and header/program-header updates are declared as reviewed_site/header_update operations

**Not run / fail-closed**

- (none)

**Evidence directory**: evidence/strcpy-stack-x86_64/ (original/candidate/patch-plan/verifier-report/scan; SHA256 in section 4)

### 2.2 marcx-capacity - VERIFIED_WITHIN_SCOPE

- Verdict: verified within scope
- Note: verified scope = one target function/sink + the supplied PoC/regression cases + the independent verifier checks. It is not a whole-program proof and does not mean the repaired binary is safe for production use.
- Reason: plan replay covers every changed byte; raw-diff bytes not declared by the plan are rejected

**Input**: fixtures/elf/vuln-capacity-confusion-x86_64.elf | SHA256 72fb53cbac09f576e037f730b07a7850ce8e129fb8c9a72c2c707c121d54b0d5

**Scan**: format=elf arch=x86_64 matrix_cell=elf/x86_64/64/little findings=1 repair_supported=True

**Repair**:

| field | value |
|---|---|
| disposition | verified_patch |
| candidate_sha256 | 93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2 |
| patch_plan_sha256 | 0fd173593e8e7cc66693521430d7a3c7427182edfcf807f4d557adfadcd2edb7 |
| integrity | True |
| gate_outcome | success_within_scope |
| poc_status | pass |
| runtime_tier | emulated_run |
| layout_status | passed |
| false_verified | False |

**Verification**: independent_decision=verified | verifier_id=independent-verifier/1 | real_verification=True

**Verification checks**

| check | required | status | detail |
|---|---|---|---|
| identity | True | passed | original=72fb53cbac09f576e037f730b07a7850ce8e129fb8c9a72c2c707c121d54b0d5 candidate=93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2 |
| container | True | passed | format=elf arch=x86_64 bits=64 endian=little |
| layout-plan | True | passed | plan 05503398723dc60e replay matches the candidate: operations=3 changed_ranges=3 cave=no associated=1 |
| action-replay | True | passed | plan replay covers all changed bytes: changed_ranges=3 |
| target-scope | True | passed | policy=target_scoped_associated scope=[0x4020d9, 0x4020e9) ops=3 reviewed_sites=2 |
| abi | True | passed | ABI ok for 1 derived block(s) sources=plan.abi_blocks |
| runtime-oracle | True | passed | independent oracle passed (runner=limactl tier=emulated_run cases=8) |
| evidence-completeness | True | passed | one independent external oracle passed |
| independence | True | passed | generator identity is distinct and its evidence is excluded from the decision |

**Limitations**

- plan replay covers every changed byte; raw-diff bytes not declared by the plan are rejected

**Not run / fail-closed**

- (none)

**Evidence directory**: evidence/marcx-capacity/ (original/candidate/patch-plan/verifier-report/scan; SHA256 in section 4)

### 2.3 unsupported-bigendian - REFUSED

- Verdict: refused (outside the capability matrix / unrecognised; no bytes produced)
- Note: the input is outside the deterministic repair matrix or unrecognised; the product fails closed and produces no bytes.
- Reason: big-endian elf/x86_64 is outside the repair matrix

**Input**: tools/product/fixtures/unsupported-bigendian-elf64.bin | SHA256 edab70b4d85df86a65e9732954db669fd4aad7b2347ec36e042d150aaa5b98c4

**Scan**: format=elf arch=x86_64 matrix_cell=None findings=0 repair_supported=False

**Repair**:

| field | value |
|---|---|
| disposition | unsupported |
| candidate_sha256 |  |
| patch_plan_sha256 |  |
| integrity |  |
| gate_outcome |  |
| poc_status |  |
| runtime_tier |  |
| layout_status | not_run |
| false_verified | False |

**Verification**: independent_decision=not_run | verifier_id=None | real_verification=False

**Verification checks**

| check | required | status | detail |
|---|---|---|---|
| independent_verification | True | not_run | no verified candidate exists to independently verify |

**Limitations**

- no executable section; nothing to analyze
- elf/x86_64/64: outside the repair matrix
- negative control: the input is a synthetic header-only container, not a real program or vulnerability

**Not run / fail-closed**

- independent verification not_run: no verified candidate exists to independently verify
- runtime oracle status=not_run; no runtime evidence
- no candidate produced (disposition=unsupported); nothing is downloadable

**Evidence directory**: evidence/unsupported-bigendian/ (original/candidate/patch-plan/verifier-report/scan; SHA256 in section 4)

## 3. Fail-closed self-check

- Result: passed (no violations)


## 4. Evidence index (SHA256)

| file | bytes | SHA256 |
|---|---|---|
| REPORT.md | 14046 | 130580ae2cff1dca907d869d188661d93aa417e2078375df5025c7d959395528 |
| REPORT.zh.md | 13948 | c3ed982692d74d8acee4a96f104611eb0b095cea9eddb30a3ca61dc57ebeac20 |
| demo-run.json | 22175 | 5f94f5f8f27a0c04054323d975ae13511e90731b0605fcc90629cd868c5cf13a |
| evidence/marcx-capacity/engine-evidence/README.md | 3083 | e419c6e6fbac4eea61839bbe41fbcbe2842f341a1af7faf944ad3b98893d3f0f |
| evidence/marcx-capacity/engine-evidence/SHA256SUMS | 593 | 0b0ca09bd2daa459a0226a0749f53adbf864bc79bb634364923c853281716c4a |
| evidence/marcx-capacity/engine-evidence/results.json | 5968 | 87a2ecc5d4e161db12dd5364ed7155b64bb358444c5cf053f6f59499c218e9a5 |
| evidence/marcx-capacity/engine-evidence/samples/heap-capacity-x86_64/metadata.json | 4267 | 7dd67186ef82f4fa287881d4df1a4a5d52826aad0b75e3251a33eea1a0804f17 |
| evidence/marcx-capacity/engine-evidence/samples/heap-capacity-x86_64/outcome.json | 484 | 5435698b98f77a60d610f701343900c106d7ba4c26d403f28e0154215d4ebbd3 |
| evidence/marcx-capacity/engine-evidence/samples/heap-capacity-x86_64/plan.json | 2149 | b487762001dbfbedafdffcade1f2eb47999f16ee75f3f27e2454341dac1cff50 |
| evidence/marcx-capacity/engine-evidence/samples/heap-capacity-x86_64/verifier-report.json | 16432 | 5457f70bbf72ccaec3063e5c580ea2aa329991c25405c04214052858c742a12d |
| evidence/marcx-capacity/scan.json | 1163 | 7b704a781176bfaaaa4713dfae9045f5435d38d9633619bbbc9f2d330f095be9 |
| evidence/strcpy-stack-x86_64/engine-evidence/README.md | 3040 | 26af1c9cfc7878c366386ceb531b06fb7d7156d8e52d530e7514b5ae2796a988 |
| evidence/strcpy-stack-x86_64/engine-evidence/SHA256SUMS | 589 | 0a407c4573477a84a49e5cbd56fed29ff813301290520be21a6997e41ef080f6 |
| evidence/strcpy-stack-x86_64/engine-evidence/results.json | 5971 | 58d59e1bb38a51be62caf2380514ee2cb2fcd0ee993439b2682ae91b44599178 |
| evidence/strcpy-stack-x86_64/engine-evidence/samples/stack-strcpy-x86_64/metadata.json | 13036 | 92c4189a3629c0d0a4027998a904b8c76009fe026d617dee01e41046232ba921 |
| evidence/strcpy-stack-x86_64/engine-evidence/samples/stack-strcpy-x86_64/outcome.json | 481 | 238bdf5b66541559dd1dcf5f2f9b62794b27a6f4d33a3946974fb2c1a7b32088 |
| evidence/strcpy-stack-x86_64/engine-evidence/samples/stack-strcpy-x86_64/plan.json | 11768 | 7634f180989b5ed76780eba5e6641ff6b1b8c38ce86b3fd80fec60c92f9f9032 |
| evidence/strcpy-stack-x86_64/engine-evidence/samples/stack-strcpy-x86_64/verifier-report.json | 272314 | 5bb93b285d6c97ef8fe9c56676f064a559f5148a42ac98ee3cd654786866320d |
| evidence/strcpy-stack-x86_64/scan.json | 2675 | f1a293e4e6aa3bc1a28e5e370bcf9c0a48811a05ece54a8375dd211b81590f68 |
| evidence/unsupported-bigendian/engine-evidence/README.md | 3244 | c200a54f08348d3faafeb7ac8c3248a9c57d97171bdbea605312cf6da52d64f3 |
| evidence/unsupported-bigendian/engine-evidence/SHA256SUMS | 542 | c6a28814495e08f15bd78edfe664345a89c1745e0f1aa2125de19d40a2552ff0 |
| evidence/unsupported-bigendian/engine-evidence/results.json | 5555 | c2b8e6cae8b3e6fc62214cca57d3673b4e0a8586721094ed688f1ac402858bf6 |
| evidence/unsupported-bigendian/engine-evidence/samples/unsupported-bigendian-negative-control/metadata.json | 485 | 7b2df9566d9dc96c4e685f0381476de8b4dfe7f0d0dfc5ab7fa00de8c65466cf |
| evidence/unsupported-bigendian/engine-evidence/samples/unsupported-bigendian-negative-control/outcome.json | 436 | f679e5362623bbd89c151cf0368966e4ec1059a45ce98f0b266c91aa9a158131 |
| evidence/unsupported-bigendian/engine-evidence/samples/unsupported-bigendian-negative-control/verifier-report.json | 96 | 98b82362019023ec475cbab1db33ebc7cf1abb75e84442a5f9da6f40ab3fea2c |
| evidence/unsupported-bigendian/scan.json | 835 | bb734a0fa4a49e661a2f89023199b3cc38b1f2790d7df993d1f95d0f160a808c |
| report.html | 15830 | 1b74c7bdbb28b0015e70975eda3b2dfe30d25287c8920def94e4206338efe634 |
| report.zh.html | 15745 | 69c507ae0a03f9940353b2fa3eec507d32cc6f929e9ebf179ed7c1c061f4159e |

Full checksum list: SHA256SUMS; verify with: shasum -a 256 -c SHA256SUMS

## 5. Not-claimed list (customer communication wording)

- public benchmark is only 2/24 verified (8.3%) and hidden is 0/8; do not claim generalisation;
- no arbitrary-binary / arbitrary-vulnerability / whole-program repair claim;
- no claim that a repaired binary is safe for production use; verification covers only the supplied PoC/regression and one target function;
- not_run items are listed explicitly and must not be treated as passed;
- AI is only a candidate generator and never owns acceptance; this report used the deterministic path and called no AI.

---

Reproduce: tools/product/run-demo.sh <fixture> <outdir>; regenerate reports: python scripts/product/export_report.py <outdir>.
