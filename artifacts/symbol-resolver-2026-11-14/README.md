# Symbol resolver (P2, 2026-11-14)

`routeb/symbol_resolver.py` classifies C calls as:

- already available in the target symbol/import set;
- defined by the patch itself;
- satisfiable by a reviewed x86-64 syscall template (`write` -> `br_write`,
  `exit` -> `br_exit`);
- unresolved, in which case the adapter fails closed (exit 3) instead of
  patching a symbol that does not exist.

`resolver-cases.json` records:

- CWE121 final C: no unresolved symbols (the model's `br_fail` is reviewed glue);
- same model C **without** the helper: `br_fail` unresolved -> fail closed;
- a synthetic `write/exit` case: two syscall stubs selected and injected.

This generalizes the CWE121 helper's mechanism; it does not claim automatic
semantic equivalence for arbitrary libc calls.  `scripts/route_a_patch.py
--resolve-gaps` is the CLI entry point.
