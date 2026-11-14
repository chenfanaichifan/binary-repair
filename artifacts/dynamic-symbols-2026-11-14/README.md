# Dynamic symbol whitelist (CWE121 vs CWE416)

`available_symbols()` measures target ELF symbols plus x86-64 PLT/imports.
Duplicate GOT+PLT names are resolved to the single executable address; otherwise
the name is ambiguous and not used.

- CWE121: `malloc`/`free` absent -> `symbol_resolver` reports `blocked`.
- CWE416: `malloc`/`free` present in the PLT -> resolver accepts them as
  available, so Route A can pass explicit symbols and let Patcherex2 link them.
- `fork/execve/system/...` remain absolute policy refusals regardless of PLT.

Inventory including measured addresses is in `symbol-inventory.json`.
