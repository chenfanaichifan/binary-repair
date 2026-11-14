# AI Repair Planning: 3/3 non-loop verified (2026-11-15)

Real DeepSeek `deepseek-flash`, target-mode allowed-call whitelist, structured
`RepairSpec` planning followed by assembly generation, `--abi-strict`, native
PoC/regression via Linux VM. Input binary sha256
`7e915860fce0d54c0c06ec0211f933dd85a4212af88e6e312362db232f1dfd4f`.

| case | candidate SHA-256 | plan SHA-256 | ABI |
|---|---|---|---|
| hard-multicall | `aab33ae71dd9...` | `3f3fcd1b4d77...` | ok |
| hard-sprintf | `ea83b591b259...` | `7dff1bbce891...` | ok |
| hard-nonconst | `2e12599af428...` | `04adc3f90b73...` | ok |

All three cases are **AI verified**, not reference-fix results:

- PoC overflow inputs are blocked (original crashes, candidate exit 0);
- regression `short` input is preserved (`hi\n`);
- ABI static check reports no fatal findings;
- `run-manifest.json` records one `VERIFIED` per run.

This follows the cave-relocation fix in `cave-mapping-broken.summary.json`:
the old candidate kept zero call displacements in the executed PT_LOAD; after
mapping cave relocations through program headers and enforcing a repair spec,
the planner produced guarded code and the model output passed.
