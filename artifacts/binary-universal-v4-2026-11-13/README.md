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


## Linux VM check

`linux-vm-junit.xml`, `linux-vm-pytest.log` and `linux-vm-environment.txt`
record an Ubuntu 24.04 arm64 Lima VM run with binfmt/qemu-x86_64:

```text
950 collected / 943 passed / 7 skipped / 0 failed
```

The 7 skips are 1 optional candidate-env test, 4 native Mach-O tests and 2
Mach-O positive pipeline cases. Mach-O native runtime is macOS-only; on Linux
those candidates are `not_verified`, not success.


## Extra runtime evidence

`macho-original-64.log` records the original Mach-O binaries with 64 x `A`:
arm64 exits 138 (SIGBUS), x86-64 exits 139 (SIGSEGV). The repaired artifact bytes
are unchanged; ad-hoc signed copies exit 0 and print 15 bytes. `codesign --verify`
on the artifact bytes is invalid/unsigned, as expected after a patch.
