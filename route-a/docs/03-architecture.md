# 03 — Architecture identification

Work item 3. Status: ☐ not started

## Purpose

Prove, from the file itself, what architecture the sample is and whether it
matches the project's supported profile (ELF64 / x86-64 / little-endian).

## Commands

```bash
file samples/<sample>.elf
readelf -h samples/<sample>.elf
readelf -l samples/<sample>.elf      # program headers: PT_LOAD, PT_GNU_STACK
readelf -S samples/<sample>.elf      # sections: .text, .plt, .got, .symtab
readelf -d samples/<sample>.elf      # dynamic section, PIE vs non-PIE hints
```

## Record

| Field | Value |
|---|---|
| `file` output | TBD |
| `Class` (`ELF64` expected) | TBD |
| `Data` (`2's complement, little endian` expected) | TBD |
| `Machine` (`Advanced Micro Devices X86-64` expected) | TBD |
| `Type` (`EXEC` non-PIE / `DYN` PIE) | TBD |
| `Entry point address` | TBD |
| `NX` / `PT_GNU_STACK` | TBD |
| `PIE` / `RELRO` / stack canary | TBD |
| Symbols present (`.symtab` non-empty) | TBD |

## Why it matters

- The project supports one narrow profile; a PIE or stripped binary is a
  recorded limitation, not something to silently work around.
- `ET_DYN` (PIE) changes the addresses shown by `objdump`, so record absolute
  vs. relative addresses explicitly.
- Existing protections (NX, RELRO, canary) must be preserved by any later patch;
  note them now.

## Evidence to save under `reports/`

- `reports/03-file.txt`
- `reports/03-readelf-h.txt`
- `reports/03-readelf-l.txt`
- `reports/03-readelf-S.txt`
