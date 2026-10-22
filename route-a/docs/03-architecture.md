# 03 — Architecture identification

Work item 3. Status: **done** (2026-10-20), fixture
`CWE121_src_char_declare_cpy_51b`, `original.elf`
`aa428157…8393`.

## Purpose

Prove, from the file itself, what architecture the sample is and whether it
matches the project's supported profile (ELF64 / x86-64 / little-endian).

## Commands

```bash
file original.elf
readelf -h original.elf
readelf -l original.elf      # program headers: PT_LOAD, PT_GNU_STACK
readelf -S original.elf      # sections: .text, .plt, .got, .symtab
readelf -d original.elf      # dynamic section, PIE vs non-PIE hints
checksec --file=original.elf
nm -S -C original.elf | grep -E "badSink| main$|printLine"
```

Captured in this run: `readelf -h`, `readelf -l`, `checksec`, `nm -S`.
**`readelf -S` and `readelf -d` were not captured** — see Gaps.

## Record

| Field | Value | Source |
|---|---|---|
| `file` output | `ELF 64-bit LSB executable, x86-64, dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2, with debug_info, not stripped` | `file`, recorded in `provenance.md` §6 |
| `Class` | `ELF64` | `evidence/02-readelf-h.txt` |
| `Data` | `2's complement, little endian` | `02-readelf-h.txt` |
| `Machine` | `Advanced Micro Devices X86-64` | `02-readelf-h.txt` |
| `Type` | `EXEC` — non-PIE | `02-readelf-h.txt`, `02-checksec.txt` |
| `Entry point address` | `0x401170` | `02-readelf-h.txt` |
| Program headers | 13, starting at file offset 64 | `02-readelf-l.txt` |
| Section headers | 37, starting at file offset 24,424 | `02-readelf-h.txt` |
| `NX` / `PT_GNU_STACK` | `NX enabled`; `GNU_STACK` flags `RW` (not executable) | `02-checksec.txt`, `02-readelf-l.txt` |
| `PIE` | `No PIE (0x400000)` | `02-checksec.txt` |
| `RELRO` | `Partial RELRO`; `GNU_RELRO` covers `.init_array` … `.got` | `02-checksec.txt`, `02-readelf-l.txt` |
| Stack canary | `No canary found` | `02-checksec.txt` |
| CET | `SHSTK: Enabled`, `IBT: Enabled`; `GNU_PROPERTY` note present | `02-checksec.txt`, `02-readelf-l.txt` |
| Stripped | No (`.symtab` present) | `02-checksec.txt`, `02-symbols.txt` |
| Symbols present | `badSink` `0x4012b0` (104 B), `main` `0x401256` (90 B), `printLine` `0x401380` (38 B) | `02-symbols.txt` |

## Segment layout that matters for Route A

| Segment | vaddr range | flags | contents |
|---|---|---|---|
| LOAD #0 | `0x400000`–`0x400788` | R | ELF headers, `.interp`, notes, dynsym, relocations |
| LOAD #1 | `0x401000`–`0x4018e9` | R E | `.init .plt .plt.sec .text .fini` |
| LOAD #2 | `0x402000`–`0x4027a4` | R | `.rodata`, `.eh_frame_hdr`, `.eh_frame` |
| LOAD #3 | `0x403df8`–`0x40409f` (memsz `0x2a8`) | RW | `.init_array`, `.dynamic`, `.got`, `.data`, `.bss` |

Consequences for an instruction patch:

- the executable image ends at `0x4018e9`, and the highest code symbol
  (`printLine`) ends at `0x4013a6`; the space between them is the candidate
  region for added code, but its exact size **requires `readelf -S`**, which
  was not captured;
- `GNU_STACK` is `RW`, so the stack cannot host executable payload;
- IBT is enabled: any **indirect** branch into added code needs an `endbr64`
  landing pad. Direct `call`/`jmp` to a fixed address does not.

## Why it matters

- The project supports one narrow profile; a PIE or stripped binary is a
  recorded limitation, not something to silently work around.
- `ET_DYN` (PIE) would change the addresses shown by `objdump`; this binary is
  `ET_EXEC`, so the addresses in this page are absolute and stable across runs.
- Existing protections must be preserved by any later patch. NX is on, Partial
  RELRO covers `.got`, and CET is enabled — a patch that adds an indirect
  branch without `endbr64` would fault under IBT. Canary is absent in the
  original, so "canary preserved" is vacuous here and must not be claimed.
- Registered profile match: ELF64, x86-64, little-endian, non-PIE, symbols and
  debug info retained — the preferred shape.

## Gaps

1. `readelf -S` was not captured, so section boundaries, exact free bytes after
   `.text`, and section flags are not on record. Gate 3/5 (safe placement)
   needs them.
2. `readelf -d` was not captured; the dynamic section is inferred from the
   `GNU_RELRO`/`DYNAMIC` program headers only.
3. `file` was run on the rehearsal sample and on `original.elf` during
   provenance write-up, but its output for this fixture is quoted from
   `provenance.md` §6 rather than a dedicated `03-file.txt` capture. The
   `checksec` and `readelf` captures cover the same properties.

## Evidence

- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/02-readelf-h.txt`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/02-readelf-l.txt`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/02-checksec.txt`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/02-symbols.txt`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/provenance.md` §6
