# Direct-callee context export (P2, 2026-11-14)

`scripts/export_with_callees.py` reuses `routeb/ghidra/export.sh` to export a
target function and each direct callee, then writes a JSON context with names,
relative C/meta paths, and unresolved/external callees.

CWE121 target:

```bash
source scripts/ghidra_env.sh
python3 scripts/export_with_callees.py \
  --binary fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf \
  --function CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink \
  --out artifacts/callee-context-2026-11-14
```

Result: `callees=["printLine","strcpy"]`, no missing entries.  This is context
for call-graph-aware repair; it does not itself change the gate and does not
claim a non-loop path-B success.
