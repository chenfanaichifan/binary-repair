# Route B/provider executor bundle

- mode: `fixed`
- function: `CWE416_Use_After_Free__malloc_free_char_01_bad`
- original: `c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9`
- candidate: `46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0`
- static audit: `pass`
- reproducibility: `not_run`
- runtime manifest: `measured`

This bundle is static unless `runtime_manifest.state == measured`.
- input mode: `none`
A static bundle is not a Gate 4 pass; run the frozen cases in the guest under
the isolation controls and attach the raw output.
