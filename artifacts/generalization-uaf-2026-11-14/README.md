# Non-loop UAF reference-locked toolchain PASS (2026-11-14)

This is a **reference-locked** result, not an AI-generated repair:

- source: `fixtures/hard-cases/uaf_fix.c` (read before free);
- target: `CWE416_Use_After_Free__malloc_free_char_01_bad` in
  `fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/original.elf`;
- Route A auto symbols resolved `exit/free/malloc/memset/printf` directly from
  the target ELF (no explicit `--symbols`);
- Patcherex2 patched candidate SHA-256:
  `bd070ae79b371e92fd904dfe48124323cd28720a512d7f0f949df42cf674c21b`;
- native PoC `uaf-noinput`: **pass**; original prints `05040a`, candidate prints
  the 99-byte `A...` buffer; no regression cases.

The AI non-loop triage remains 0/3 verified; this UAF case proves the
symbol/PLT/dynamic-allocator path works when a correct C repair is supplied.
It is not evidence that the model generated this repair.
