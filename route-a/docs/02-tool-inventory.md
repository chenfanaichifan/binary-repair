# 02 — Binary-inspection tool inventory

Work item 2. Status: **done, with recorded gaps** (2026-10-20).

## Purpose

Know which basic binary-inspection tools are present in the isolated Ubuntu
environment, what each one is for, and which version was actually used.

## Inventory

Versions come from `docs_BinaryRepair/vm-profile.md` §5, measured in the guest.
"Verified" means the tool was actually used for this fixture, not merely
installed.

| Tool | Purpose | Package | Version | Verified |
|---|---|---|---|---|
| `file` | quick ELF type / architecture / linkage | `file` | 5.45 | used on the rehearsal sample; not re-run on this fixture |
| `readelf` | ELF header, program headers, sections, symbols | `binutils` | 2.42-4ubuntu2.10 | **yes** — `evidence/02-readelf-h.txt`, `02-readelf-l.txt` |
| `objdump` | disassembly of the function under test | `binutils` | 2.42-4ubuntu2.10 | **yes** — `evidence/02-objdump-badsink.txt`, `02-objdump-main.txt` |
| `nm` | symbol table: is the sink visible? | `binutils` | 2.42-4ubuntu2.10 | **yes** — `evidence/02-symbols.txt` |
| `objcopy` | copy sections, strip/keep symbols | `binutils` | 2.42-4ubuntu2.10 | not used yet |
| `strings` | printable strings, version and error text | `binutils` | 2.42-4ubuntu2.10 | not used yet |
| `gdb` | registers and stack at the overflow | `gdb` | 15.1-1ubuntu1~24.04.1 | **yes** — `evidence/04-gdb-crash-100.txt` |
| `gcc` | build the fixture | `build-essential` | 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1) | **yes** — built `original.elf` |
| `make` | fixture build driver | `make` | 4.3-4.1build2 | present |
| `python3` | helper scripts, manifest runner | `python3` | 3.12.3-0ubuntu2.1 | **yes** — `build/run_manifest.py` |
| `checksec` | protection summary | `checksec` | present; version not captured in this run | **yes** — `evidence/02-checksec.txt` |
| `capstone` (python) | instruction decoding for Route A | `pip` | module reports 5.0.7 (pip 5.0.9) | import smoke test only |
| `pyelftools` (python) | ELF parsing in Python | `pip` | 0.33 | import smoke test only |
| `pwntools` (python) | ELF helpers / crash automation | `pip` | 4.15.0 | installed, not exercised |
| `libc6` / `libc6-dev` | build and runtime dependency | `apt` | 2.39-0ubuntu8.9 | build dependency |

## Absent (measured, not assumed)

| Tool | State | Consequence |
|---|---|---|
| `clang` / LLVM | **not installed** | Route B recompilation currently uses gcc; a clang-based pipeline is untested |
| Ghidra / JDK (`java`) | **not installed** | no decompiler; Route B code recovery must use another route or be recorded as blocked |
| LIEF | **not installed** | binary rewriting through LIEF is not available |
| angr / Claripy / Z3 | **not installed** | **V4 bounded symbolic verification cannot run** — see `docs_BinaryRepair/fixture-freeze-record.md` O1 |
| radare2 | not installed | optional; no gate requires it |

Absence is stated here because a missing tool is a recorded limitation, never a
blank cell. V1 and V3 can run on this guest today; V4 cannot.

## Notes

- `objdump` / `readelf` / `nm` / `strings` / `objcopy` all come from
  `binutils`; one install covers them.
- One Python package disagrees with its own metadata (`capstone` pip 5.0.9
  reports 5.0.7). Record the module-reported value, which is what code sees.
- `01-toolchain.txt` and `02-tool-inventory.txt` in the 2026-10-18 rehearsal
  snapshot are byte-identical duplicates. They describe the *pre-resize*
  guest, so they are historical, not the current toolchain record.

## Evidence

- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/02-readelf-h.txt`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/02-readelf-l.txt`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/02-objdump-badsink.txt`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/02-symbols.txt`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/02-checksec.txt`
- `docs_BinaryRepair/vm-profile.md` §5 (versions and absences, measured in guest)
- `worklogs/2026-10-18/evidence/01-toolchain.txt` (rehearsal-era toolchain,
  historical)
