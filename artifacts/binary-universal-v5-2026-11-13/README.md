# BinaryRepair v5 — universal repair evidence (2026-11-13)

Generated: `2026-11-13T11:22:45Z` by `scripts/capture_binary_evidence.py`.

| fixture | format/arch | disposition | verified | strategy | runtime tier | gate |
|---|---|---|---|---|---|
| elf-i386 | elf/i386 | verified_patch | True | guard | emulated_run | True |
| elf-i386-dyn | elf/i386 | verified_patch | True | guard | emulated_run | True |
| elf-i386-memcpy | elf/i386 | verified_patch | True | immediate | emulated_run | True |
| pe-i386 | pe/i386 | verified_patch | True | guard | emulated_run | True |
| pe-i386-iat | pe/i386 | verified_patch | True | guard | emulated_run | True |
| elf-x86_64-strict | elf/x86_64 | verified_patch | True | strict-template | emulated_run | True |
| macho-arm64 | macho/arm64 | verified_patch | True | guard | native_run | True |
| macho-x86_64 | macho/x86_64 | verified_patch | True | guard | native_run | True |
| pe-x86_64 | pe/x86_64 | verified_patch | True | guard | emulated_run | True |
| pe-arm64 | pe/arm64 | verified_patch | True | guard | emulated_run | True |
| elf-arm64 | elf/arm64 | verified_patch | True | guard | emulated_run | True |
| pe-i386-no-sink | negative control | analysis_only | — | — | — | candidate=False |
| pe-no-pattern | negative control | analysis_only | — | — | — | candidate=False |
| macho-no-pattern | negative control | analysis_only | — | — | — | candidate=False |
| unknown-bytes | negative control | invalid | — | — | — | candidate=False |

`repair-<fixture>.json` is the complete report v4: disposition, findings,
actions, runtime cases and the deterministic gate.  `negative-*.json` records
fail-closed behavior: no candidate is written for unsupported inputs.

Runtime tiers: `native_run` = the candidate executed on this macOS host;
`emulated_run` = Unicorn instruction-level execution.  Neither is a
hardened guest or a Windows kernel run.

## Bundle contents

This committed bundle keeps the machine-readable evidence (scan/repair report
v4 JSON for all 11 positive fixtures, baseline runtime cases for ELF/PE,
negative controls, macOS + Linux JUnit XML) and `SHA256SUMS`. Repaired candidate
binaries (`*-fixed.*`, several MB each) are not committed; they are reproducible
with `python scripts/capture_binary_evidence.py`.

The v6 AI direct-binary evidence lives separately in
`artifacts/ai-direct-binary-2026-11-13/`.
