# BinaryRepair v4 — universal repair evidence (2026-11-13)

Generated: `2026-11-13T07:53:39Z` by `scripts/capture_binary_evidence.py`.

| fixture | format/arch | status | strategy | runtime tier | gate |
|---|---|---|---|---|---|
| elf-x86_64-strict | elf/x86_64 | patched | strict-template | emulated_run | True |
| macho-arm64 | macho/arm64 | patched | guard | native_run | True |
| macho-x86_64 | macho/x86_64 | patched | guard | native_run | True |
| pe-x86_64 | pe/x86_64 | patched | guard | emulated_run | True |
| pe-arm64 | pe/arm64 | patched | guard | emulated_run | True |
| elf-arm64 | elf/arm64 | patched | guard | emulated_run | True |
| pe-i386 | negative control | unsupported | — | — | candidate=False |
| pe-no-pattern | negative control | unsupported | — | — | candidate=False |
| macho-no-pattern | negative control | unsupported | — | — | candidate=False |
| unknown-bytes | negative control | unsupported | — | — | candidate=False |

`repair-<fixture>.json` is the complete report v3: findings, actions,
runtime cases and the deterministic gate.  `negative-*.json` records
fail-closed behavior: no candidate is written for unsupported inputs.

Runtime tiers: `native_run` = the candidate executed on this macOS host;
`emulated_run` = Unicorn instruction-level execution.  Neither is a
hardened guest or a Windows kernel run.
