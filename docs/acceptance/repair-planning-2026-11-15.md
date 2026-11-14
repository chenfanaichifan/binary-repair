# Repair Planning breakthrough: 3/3 non-loop AI verified (2026-11-15)

## Result

DeepSeek `deepseek-flash`, target-mode allowed-call whitelist, structured
RepairSpec planner then assembly generation, `--abi-strict`, native PoC and
regression through the Linux VM:

| case | candidate SHA-256 | plan SHA-256 | ABI | native gate |
|---|---|---|---|---|
| hard-multicall | `aab33ae71dd942ec10f5f15f5a276e5326b37f1a244851eef63f8ac8de6f5b84` | `3f3fcd1b4d77...` | ok | PASS |
| hard-sprintf | `ea83b591b2591d4d95fc3390e87529267a1edfb55ae3a5a1b42ce2bf70e80583` | `7dff1bbce891...` | ok | PASS |
| hard-nonconst | `2e12599af428c62a4b58cecaad8d248cf76bea4ecc9dcc8edb74c0b7a80ea2b3` | `04adc3f90b73...` | ok | PASS |

All PoC overflows were blocked; all `hi` regression outputs preserved; all
run manifests report `VERIFIED: 1`.

Evidence: `artifacts/ai-repair-planning-2026-11-15/`.

## Root causes fixed

1. **Cave relocation bug:** the injected PT_LOAD cave VA `0x10cf000` lies in the
   virtual range of `.tbss` (SHT_NOBITS).  The old relocation patcher mapped via
   `.tbss` and wrote patched calls to a non-executed file offset, while the
   executed cave retained `e8 00 00 00 00`.  Now cave VA is always mapped
   through PT_LOAD program headers first.
2. **Unstructured assembly:** without a plan, the model emitted a copy with no
   bounds guard.  The RepairSpec stage forces the invariant
   `copy_len < 16` and rejection before assembly.
3. **ABI false positive:** the first stack checker used linear disassembly and
   reported `rsp_not_restored` on valid two-epilogue blocks.  The CFG-aware
   checker now reports `ok=true` for all three candidates.

## Scope

This is three non-loop cases from one hard-case binary, not universal binary
repair.  Reference UAF evidence remains separate and is not counted as AI.
