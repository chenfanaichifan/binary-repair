# BinaryRepair v5 — universal repair evidence (2026-11-13)

Generated: `2026-11-13T09:51:33Z` by `scripts/capture_binary_evidence.py`.

| fixture | format/arch | disposition | verified | strategy | runtime tier | gate |
|---|---|---|---|---|---|
| elf-i386 | elf/i386 | verified_patch | True | guard | emulated_run | True |
| pe-i386 | pe/i386 | verified_patch | True | guard | emulated_run | True |
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
v4 JSON, baseline runtime cases, negative controls, JUnit XML) and the
`SHA256SUMS`. Repaired candidate binaries (`*-fixed.*`, several MB each) are not
committed; they are byte-for-byte reproducible from the fixtures with:

```bash
python scripts/capture_binary_evidence.py
```

`baseline-*.json` is the instruction-level runtime evidence for the *original*
i386 fixtures used by the acceptance record. macOS native Mach-O cases are
verified on the macOS acceptance host only; on Linux those tests skip by
design.
