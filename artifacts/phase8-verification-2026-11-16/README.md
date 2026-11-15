# Phase-8 verification schema-conformance sample

This directory contains one **schema-conformance sample**, not repair evidence:
`report.json` was produced by the independent verifier against
`fixtures/elf/vuln-strcpy-x86_64.elf` plus an 8-byte candidate, and the verifier
correctly rejected it because no independent runtime oracle was available on
this host and the generator identity was not independent. The decision is
`rejected`; it is committed only so the canonical `verification.schema.json`
integration path is exercised by `scripts/check_contract_schemas.py`.

It must never be cited as a verified repair, a capability promotion, or PoC
evidence. A real end-to-end verification report requires an independent
native/emulated oracle run and is tracked by Phase 8B+.

## Files

- `report.json`: fail-closed verification report (decision `rejected`).
- `SHA256SUMS`: integrity digests for this directory.
