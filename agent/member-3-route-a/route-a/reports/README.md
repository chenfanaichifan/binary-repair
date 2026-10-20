# reports/

Command output kept as evidence, one file per check, so that every claim in
`docs/` can be traced back to a command.

## Naming

`NN-<topic>.txt` where `NN` matches the `docs/` page:

| File | Produced by |
|---|---|
| `01-os-release.txt` | `lsb_release -a`, `uname -a` |
| `01-image-sha256.txt` | `sha256sum` of the Ubuntu image |
| `01-toolchain.txt` | `scripts/check-tools.sh` |
| `02-tool-inventory.txt` | `scripts/check-tools.sh` |
| `03-file.txt` | `file samples/<sample>.elf` |
| `03-readelf-h.txt` | `readelf -h` |
| `03-readelf-l.txt` | `readelf -l` |
| `03-readelf-S.txt` | `readelf -S` |
| `04-nm-function.txt` | `nm` for the vulnerable function |
| `04-objdump-function.txt` | `objdump -d` of that function |
| `04-annotated-function.md` | notes written by hand from the disassembly |

## Rules

- Paste the real output, including errors. A failed command is evidence too.
- Keep the command line in the file's first line so it can be replayed.
- Never edit output to make it look better; add a note below it instead.
- Before the shared sample is frozen, any rehearsal output must say
  `REHEARSAL` in the first line.
