# Baseline vs review

| case | gate | no AI | with review | AI called | recommendation | changed | new concerns |
|---|---|---|---|---|---|---|---|
| strict_ok | success_within_scope | success_within_scope | success_within_scope | yes | accept | no | 0 |
| unsupported | unsupported | unsupported | unsupported | yes | hold | no | 0 |
| missing_evidence | inconclusive | inconclusive | inconclusive | yes | hold | no | 0 |

## strict_ok

- gate: `success_within_scope` (same packet: True)
- baseline: `success_within_scope`
- with review: `success_within_scope`
- AI called: True (llm, review_ok)
- recommendation: `accept`
- effect: `concurred`
- new concerns / missing evidence / further checks: 0 / 0 / 3
- scripted accept control: success=True reason=`gate_success_scripted_review_concurred`
- scripted hold control: success=False reason=`scripted_veto`

- summary: All 10 required checks passed; candidate matches the reviewed strict template and boundary runtime cases (0,1,16,17) behave per the stated contract with intact stack sentinels.
- further checks: Runtime evidence is Unicorn x86-64 emulation with modeled syscalls, not a host-kernel execution; a native run would strengthen confidence.; Coverage is limited to four input sizes around capacity 16; partial reads, larger inputs, and other architectures are untested.; No guest replay or independent reproduction of the template hash beyond the packet's own report.

## unsupported

- gate: `unsupported` (same packet: True)
- baseline: `unsupported`
- with review: `unsupported`
- AI called: True (llm, review_ok)
- recommendation: `hold`
- effect: `reviewed_failure`
- new concerns / missing evidence / further checks: 0 / 4 / 3
- scripted accept control: success=False reason=`review_accept_cannot_promote_gate`
- scripted hold control: success=None reason=`None`

- summary: Candidate is a PE file with no produced bytes; format, candidate presence, patched identity, patch scope, and all runtime checks failed or were not run. No supported repair claim exists, so the candidate is outside the reviewed ELF64 x86-64 scope.
- missing evidence: Supported ELF64 x86-64 input file; Produced candidate bytes distinct from original; Patch offsets within reviewed scope; Runtime emulation cases and stack sentinel results
- further checks: Confirm input format and architecture before repair; Re-run gate after producing a candidate for a supported ELF target; Add runtime boundary cases and guest replay if a repair is later attempted

## missing_evidence

- gate: `inconclusive` (same packet: True)
- baseline: `inconclusive`
- with review: `inconclusive`
- AI called: True (llm, review_ok)
- recommendation: `hold`
- effect: `reviewed_failure`
- new concerns / missing evidence / further checks: 0 / 4 / 4
- scripted accept control: success=False reason=`review_accept_cannot_promote_gate`
- scripted hold control: success=None reason=`None`

- summary: Static identity, format, and strict-template checks passed, but all four required runtime checks were not run, so the gate is inconclusive and the stated scope (boundary rejection and exact echo) is unsupported by evidence.
- missing evidence: Unicorn emulation run of the candidate with modeled syscalls; Boundary input cases around capacity 16 (under, at, over limit); Stack sentinel check results; Evidence that over-limit input is rejected and valid input echoed exactly
- further checks: Re-run with runtime evidence enabled and confirm all four runtime checks pass; Confirm emulation results against a host-kernel execution for the same inputs; Extend coverage to partial reads and additional input sizes; Verify behavior on architectures beyond x86_64 if in scope
