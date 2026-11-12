# Direct ELF AI review experiment — 2026-11-12

**AI was called in this run.**

- commit: `df82b6c40d78b5eb643a16e0123e10a76b44475a`
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
- further checks: Runtime evidence is Unicorn x86-64 emulation with modeled syscalls, not a host-kernel execution; a host run would strengthen confidence.; Coverage limited to four input sizes around capacity 16; partial reads, larger inputs, and other architectures are untested.; No guest replay or independent reproduction of the template hash beyond the packet's own report.

### unsupported

- AI called: True (llm, review_ok)
- recommendation: `hold`
- decision changed: False
- summary: Candidate is a PE file with no produced bytes; format, candidate presence, patched identity, patch scope, and all runtime checks failed or were not run. No supported repair claim exists, so the candidate is outside the reviewed ELF64 x86-64 scope.
- concerns: [format] Input is PE with unknown arch, not supported ELF64 little-endian x86-64.; [candidate.present] Zero candidate bytes were produced.; [candidate.identity.patched] No candidate bytes and hash equals original, so no patch was applied.; [patch.scope] Mode is unsupported with no offsets or findings.; [runtime.available] No runtime emulation evidence present.; [runtime.cases] No boundary runtime cases were run.
- missing evidence: Supported ELF64 x86-64 input file; Produced candidate byte sequence; Candidate hash distinct from original; Reviewed patch scope with offsets; Runtime emulation cases and sentinel results
- further checks: Re-run repair engine on a supported ELF64 x86-64 binary; Confirm candidate bytes differ from original and match reported hash; Execute boundary runtime cases including partial reads; Validate on host kernel rather than modeled-syscall emulation

### missing_evidence

- AI called: True (llm, review_ok)
- recommendation: `hold`
- decision changed: False
- summary: Static identity, format, and strict-template checks passed, but all four required runtime checks were not run, so the gate is inconclusive and the stated scope (boundary rejection and exact echo) is unsupported by evidence.
- concerns: [runtime.available] Required runtime emulation evidence is absent, so no dynamic behavior was verified.; [runtime.cases] No boundary runtime cases were executed or recorded.; [runtime.no_overflow] Stack sentinel integrity was never exercised.; [runtime.boundary_semantics] Strict boundary contract (over-limit rejection, exact echo) is unverified.
- missing evidence: runtime.available; runtime.cases; runtime.no_overflow; runtime.boundary_semantics
- further checks: Run Unicorn x86-64 emulation with modeled syscalls for the four boundary sizes around capacity 16.; Confirm over-limit input is rejected and valid input is echoed byte-exactly.; Verify stack sentinel is intact after each case.; Note emulation is not a host-kernel run; consider host execution and partial-read coverage.

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
