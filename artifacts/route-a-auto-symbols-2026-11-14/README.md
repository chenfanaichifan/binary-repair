# Route A auto symbols and failure metadata (2026-11-14)

`route_a_patch.py` now builds the symbol map from the target ELF:

- `ContainerInfo.symbols` (local/global functions);
- `ContainerInfo.imports` (x86-64 `.plt/.plt.sec` and import entries);
- duplicate names are resolved to a single executable PLT address when exactly
  one exists, otherwise marked ambiguous;
- explicit `--symbols` and `export_with_callees` context symbols still override.

CWE121 with **no explicit `--symbols`**:

- resolver result: `available=["printLine"]`, `defined_in_source=["br_fail"]`,
  `stubs=[]`, `blocked=[]`, `unresolved=[]`;
- Patcherex2 output SHA-256 equals the previous explicit-symbol fixed artifact:
  `463a9758f9eb45a8d80d5af340ffd0861997b0ccaa5c5b6be41406616589636f`.

Failure metadata is now typed.  A deliberately missing symbol produced
`error_class=compile_error` with `c_source_sha256`, binary hash, symbol map and
the underlying compiler error (`missing_symbol_failure.json`).

Patcherex2's own `ModifyFunctionPatch` detours when the replacement is larger
than the original function; the CWE121 replacement demonstrates that path.  No
manual trampoline was needed for this case.
