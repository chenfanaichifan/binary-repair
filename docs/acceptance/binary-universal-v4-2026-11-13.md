# Direct binary repair v4 — universal container acceptance (2026-11-13)

## Scope

This record covers the **local macOS** run of the container-neutral repair
pipeline:

- ELF, PE and Mach-O detection (thin; fat detected but not rewritten);
- imported call resolution: ELF PLT/GOT and symbols, PE IAT and
  `jmp [rip+disp]`/`adrp-ldr-br` thunks, Mach-O stubs and bindings;
- stack-frame capacity analysis (`sub rsp/rsp`/`rbp` and `sub sp/sp`);
- two repair actions: in-place immediate clamp and bounded-copy guard injection
  with call redirection;
- native Mach-O execution evidence on macOS, Unicorn instruction-level evidence
  for PE and AArch64 ELF;
- report schema v3 (`schema_version=3`) with actions, runtime cases and a
  deterministic gate.

It does **not** cover 32-bit x86/ARM repair, big-endian binaries, heap/global
sinks, `sprintf` format expansion, fat Mach-O rewriting, Windows kernel
execution, or a hardened guest. Those are explicitly fail-closed or listed as
limitations.

## Matrix

| fixture | container | arch | strategy | runtime tier | gate |
|---|---|---|---|---|---|
| `artifacts/vuln-elf/vuln.elf` | ELF | x86-64 | strict-template | emulated | pass |
| `fixtures/macho/vuln-strcpy-arm64` | Mach-O | arm64 | guard | native | pass |
| `fixtures/macho/vuln-strcpy-x86_64` | Mach-O | x86-64 | guard | native (Rosetta) | pass |
| `fixtures/pe/vuln-strcpy-x64.exe` | PE32+ | x86-64 | guard | emulated | pass |
| `fixtures/pe/vuln-strcpy-arm64.exe` | PE32+ | arm64 | guard | emulated | pass |
| `fixtures/elf/vuln-strcpy-arm64.elf` | ELF | arm64 | guard | emulated | pass |

Negative controls (no candidate, explicit reason):

```text
fixtures/pe/i386-control.exe      pe/i386   no repair backend
fixtures/pe/cli-64.exe            pe/x86_64 no patchable copy sink
fixtures/macho/3D_Image_Toolkit   macho/arm64 no patchable copy sink
arbitrary non-binary bytes        unknown   unrecognized container magic
```

## Fixtures

Built by `scripts/build_binary_fixtures.py` from `fixtures/src/`:

- Mach-O arm64/x86-64: system clang, ad-hoc signed;
- PE x86-64/arm64 and AArch64 ELF: the Zig toolchain already vendored under
  `.tmp/zigpkg/site/ziglang/zig` (offline, no network install);
- the vulnerable function is a small assembly routine that places a 16-byte
  buffer at the top of the callee frame, so
  `capacity = frame_top - destination = 0x10` is exact.

`fixtures/PROVENANCE.json` records the toolchain version, source hashes and
artifact hashes. `scripts/build_binary_fixtures.py --check` verifies them.

## Runtime evidence

Native Mach-O: the repaired candidate is ad-hoc re-signed (`codesign -s -`) and
executed with inputs `0, 1, 15, 16, 17, 64` bytes. The original binaries crash
(SIGSEGV) on the 64-byte input; repaired binaries exit `0` and truncate to 15
bytes. Ad-hoc signing is for local loading only; the original signature is not
forged and `codesign_invalidated` is reported.

Emulated PE/AArch64: Unicorn maps the image, builds a controlled stack and
input buffer, stubs `puts`, executes the repaired function and checks a canary
after the 16-byte capacity. Original binaries fail the canary at capacity;
repaired binaries pass every case.

## Evidence

```text
artifacts/binary-universal-v4-2026-11-13/
  README.md                 matrix + provenance
  scan-<fixture>.json       analysis
  repair-<fixture>.json     report v3 + runtime cases + gate
  negative-<fixture>.json   fail-closed controls
  <fixture>-fixed.<ext>     candidate bytes
  junit.xml, pytest.log     full local suite
  SHA256SUMS
```

## Test result

The full local run is recorded in `junit.xml` / `pytest.log` in
`artifacts/binary-universal-v4-2026-11-13/`:

```text
950 collected / 946 passed / 4 skipped / 0 failed
```

This host has GNU `readelf` installed, so the historical Route B view-count
failure does not appear. Record the actual JUnit on the target Linux host
instead of copying this count.

## Limitations

- Frame capacity is frame geometry (`frame_top - destination`), not DWARF
  object size. The fixtures place the buffer at the frame top; for arbitrary
  binaries where the buffer is not at the frame top, the inferred capacity can
  be larger than the object.
- PE/AArch64 evidence is emulation, not a Windows/Linux kernel run.
- Mach-O runtime evidence is macOS-only; on Linux the tier is
  `static_only`/`not_verified`, not success.
- The guard clobbers only caller-saved registers (`rax/r10`, `x9/x10/w0`).
  Callers that rely on those registers across `strcpy` are already outside the
  C ABI.
- 32-bit, big-endian, fat Mach-O rewrite, heap and format-string sinks are
  detected/reported but not repaired.
