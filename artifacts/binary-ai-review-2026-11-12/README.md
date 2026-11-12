# Direct ELF AI review experiment — 2026-11-12

**AI was called in this run.**

- commit: `be9564f1256f2d0693aed0f036b84b4a2f1827d2`
- provider requested: `real`
- reviewer mode: `llm`
- reviewer model requested: `deepseek-chat`
- reviewer model returned: `deepseek-flash`
- command: `python scripts/demo_binary_ai_review.py --provider real`

## Result

| case | gate | no AI | with review | AI called | recommendation | changed | new concerns |
|---|---|---|---|---|---|---|---|
| strict_ok | success_within_scope | success_within_scope | success_within_scope | yes | accept | no | 0 |
| unsupported | unsupported | unsupported | unsupported | yes | hold | no | 0 |
| missing_evidence | inconclusive | inconclusive | inconclusive | yes | hold | no | 0 |

The deterministic gate is the only source of success. The scripted `accept`
control returns `accept` for every case; the unsupported and missing-evidence
cases stay non-successful with reason `review_accept_cannot_promote_gate`. The
strict case also has a scripted `hold` control to show that a review can veto a
passing gate.

## What the review added

### strict_ok

- AI called: True (llm, review_ok)
- recommendation: `accept`
- decision changed: False
- summary: All 10 required checks passed; candidate matches the reviewed strict template and boundary runtime cases (0,1,16,17) behave per the stated contract with intact stack sentinels.
- further checks: Runtime evidence is Unicorn x86-64 emulation with modeled syscalls, not a host-kernel execution; a native run would strengthen confidence.; Coverage is limited to four input sizes around capacity 16; partial reads, larger inputs, and other architectures are untested.; No guest replay or independent reproduction of the template hash beyond the packet's own report.

### unsupported

- AI called: True (llm, review_ok)
- recommendation: `hold`
- decision changed: False
- summary: Candidate is a PE file with no produced bytes; format, candidate presence, patched identity, patch scope, and all runtime checks failed or were not run. No supported repair claim exists, so the candidate is outside the reviewed ELF64 x86-64 scope.
- concerns: [format] Input is PE with unknown arch, not supported ELF64 little-endian x86-64.; [candidate.present] Zero candidate bytes were produced.; [candidate.identity.patched] No candidate bytes and hash equals original, so no patch was applied.; [patch.scope] Patch mode is unsupported with no offsets or findings.; [runtime.available] No runtime emulation evidence present.; [runtime.cases] No boundary runtime cases were run.
- missing evidence: Supported ELF64 x86-64 input file; Produced candidate bytes distinct from original; Patch offsets within reviewed scope; Runtime emulation cases and stack sentinel results
- further checks: Confirm input format and architecture before repair; Re-run gate after producing a candidate for a supported ELF target; Add runtime boundary cases and guest replay if a repair is later attempted

### missing_evidence

- AI called: True (llm, review_ok)
- recommendation: `hold`
- decision changed: False
- summary: Static identity, format, and strict-template checks passed, but all four required runtime checks were not run, so the gate is inconclusive and the stated scope (boundary rejection and exact echo) is unsupported by evidence.
- concerns: [runtime.available] Required runtime emulation evidence is absent, so no dynamic behavior was verified.; [runtime.cases] No boundary runtime cases were executed or recorded.; [runtime.no_overflow] Stack sentinel integrity was never exercised.; [runtime.boundary_semantics] Over-limit rejection and exact echo behavior remain unverified.
- missing evidence: Unicorn emulation run of the candidate with modeled syscalls; Boundary input cases around capacity 16 (under, at, over limit); Stack sentinel check results; Evidence that over-limit input is rejected and valid input echoed exactly
- further checks: Re-run with runtime evidence enabled and confirm all four runtime checks pass; Confirm emulation results against a host-kernel execution for the same inputs; Extend coverage to partial reads and additional input sizes; Verify behavior on architectures beyond x86_64 if in scope

The `new_*` counts in the table are a wording heuristic: a phrase that repeats a gate limitation is not new, but a rephrasing may still be counted. Read the lists above, not only the counts.

## Files

- `run.json` — complete packet, baseline/with-review/control decisions and reviews.
- `comparison.md` — compact comparison table.
- `SHA256SUMS` — integrity of the three files above.

## Limitations

- One checked-in fixture family; this is not broad ELF coverage.
- Runtime evidence is Unicorn emulation, not a host-kernel run.
- The missing-evidence case deliberately removes runtime evidence to exercise the gate.
- A real model is non-deterministic; a single run is not a general claim about AI value.
