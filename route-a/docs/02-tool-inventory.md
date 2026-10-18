# 02 — Binary-inspection tool inventory

Work item 2. Status: ☐ not started

## Purpose

Know which basic binary-inspection tools are present in the isolated Ubuntu
environment, what each one is for, and which version was actually used.

## Inventory

Fill the `Version` and `Verified` columns from `scripts/check-tools.sh` output.
Do not copy version numbers from the internet.

| Tool | Purpose | Package | Version | Verified |
|---|---|---|---|---|
| `file` | quick ELF type / architecture / linkage | `file` | | ☐ |
| `readelf` | ELF header, sections, symbols, relocations | `binutils` | | ☐ |
| `objdump` | disassembly, section and symbol listing | `binutils` | | ☐ |
| `objcopy` | copy sections, strip/keep symbols | `binutils` | | ☐ |
| `nm` | symbol table (is the vulnerable function visible?) | `binutils` | | ☐ |
| `strings` | printable strings, version and error text | `binutils` | | ☐ |
| `gdb` | breakpoints, registers, stack state at the overflow | `gdb` | | ☐ |
| `gcc` | build the sample fixture | `build-essential` | | ☐ |
| `python3` | run helper scripts | `python3` | | ☐ |
| `capstone` (python) | instruction decoding for later Route A work | `pip` | TBD | ☐ |
| `pwntools` (python) | ELF helpers / crash automation | `pip` | TBD | ☐ |
| `radare2` or `ghidra` | interactive disassembly (optional) | TBD | TBD | ☐ |

## Notes

- `objdump`/`readelf`/`nm`/`strings`/`objcopy` all come from `binutils`; one
  install covers them.
- Route A in the technical design relies on instruction-level decoding
  (Capstone) and assembly/writeback tooling, so record those versions too, even
  if they are installed later.
- If a tool is missing, write "not installed" rather than leaving the cell blank.

## Evidence to save under `reports/`

- `reports/02-tool-inventory.txt` — `scripts/check-tools.sh` output
