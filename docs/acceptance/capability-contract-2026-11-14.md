# Unified runtime capability contract (2026-11-14)

Status: implemented and measured. Scope: `app/services/runtime/capabilities.py`,
`app/services/runtime/macho_native.py`, `app/services/repair_matrix.py`
(capability payload only), `app/services/poc_runner.py` (selector/limitation
only), tests `tests/test_runtime_capabilities.py` and
`tests/test_repair_matrix.py`.

The repair matrix **declares** what each cell can prove. This contract is the
single measured statement of what the current host can actually execute for a
`(format, arch)` pair, and of whether the external PoC runner may execute it.
Declared and measured values are exposed side by side; a declared tier is never
turned into an availability claim, and a gap is never silent.

## 1. Single source of truth

```
guest_runner.find_guest_runner / macho_native.execution_tier / Unicorn support
        │  (the only host & arch conditionals)
        ▼
capabilities.probe(format, arch, *, external_poc=False, host=None)
        ▼
capabilities.contract(format, arch, *, host=None)
        ▼
poc_runner._select_runner / run_poc limitation   (external PoC decision)
repair_matrix.matrix_payload()["contract_capabilities"]   (per-cell payload)
```

- `macho_native.execution_tier(arch, *, host_machine=None, engine_ready=None)`
  owns the **only** Mach-O host/arch conditional: `native_run` for a matching
  CPU, `emulated_run` for x86_64 on arm64 (Rosetta) and `unavailable` otherwise.
  `_command`, `run`, `supports_arch` and `capabilities.probe` all read it.
- `capabilities.probe` owns per-format availability measurement (ELF: live
  native/qemu/Lima guest runner; Mach-O: `execution_tier`; PE: Unicorn
  instruction-level path; unknown formats: unavailable).
- `capabilities.contract` adds the matrix declaration (`declared_tier`), the
  evidence semantics (`emulated_available`, `poc_available`) and an explicit
  `reason` whenever the declared tier is not measured.
- `poc_runner._select_runner` and the `run_poc` unavailable limitation read the
  contract, so the external-PoC path can never claim more than the contract.
- `matrix_payload()` exposes `contract_capabilities` per cell (derived only from
  `contract()`; a probe error degrades to `unavailable` + reason). The legacy
  measured view `runtime_capabilities` is kept for existing audit consumers, and
  every cell's declared `runtime_tiers` remain unchanged.

Tests enforce the rule: no Mach-O host/arch branch outside
`macho_native.execution_tier` (probe and `_command` are tested through the same
helper), and every `REPAIR_CELL` is either measured inside its declared
`runtime_tiers` or carries a non-empty reason naming the declared tier.

## 2. Contract fields

`capabilities.contract(format, arch)` returns exactly these keys:

| field | type | meaning |
|---|---|---|
| `declared_tier` | `str` | Tier the repair matrix declares for the cell (`native_run`/`emulated_run`/`unavailable`; strongest declared tier, `unavailable` when no cell exists). |
| `measured_tier` | `str` | Tier this host can actually produce: `native_run`, `emulated_run` or `unavailable`. |
| `poc_available` | `bool` | The external CLI PoC runner can execute the target (full process run). False for function-level-only evidence. |
| `emulated_available` | `bool` | Emulated/function-level execution evidence is available on this host. |
| `available` | `bool` | Some execution evidence is available (`measured_tier != unavailable`). |
| `reason` | `str` | ASCII, deterministic explanation; non-empty whenever a declared tier is not measured, and always for `unavailable`. |
| `source` | `str` | Measurement provider: `guest_runner` / `macho_native` / `unicorn` / `none`. |

Ground truth for parsing/consumer code: `capabilities.CONTRACT_FIELDS`.

## 3. Measured platform limits (this host: macOS arm64, Lima guest)

`matrix_payload()["contract_capabilities"]` is measured, not hard-coded; the
table below is the 2026-11-14 measurement. Re-run the tests on another host
instead of trusting it.

| format/arch | declared | measured | `poc_available` | `emulated_available` | contract decision |
|---|---|---|---|---|---|
| `elf/x86_64` (+`arm64`,`i386`) | `emulated_run` | `emulated_run` | True | True | Lima/qemu guest runner; full external PoC allowed. |
| `macho/arm64` | `native_run` | `native_run` | True | False | Native Mach-O execution on the matching CPU. |
| `macho/x86_64` | `native_run` | `emulated_run` | False | True | Rosetta cross-arch: **function-level evidence only**; external PoC unavailable (`declared native_run is unavailable ...`). |
| `pe/x86_64` (+`arm64`,`i386`) | `emulated_run` | `emulated_run` | False | True | Unicorn instruction-level evidence only; external PoC unavailable. |
| `macho/i386` (32-bit) | `unavailable` (no cell) | `unavailable` | False | False | Not a matrix cell and no Mach-O Unicorn mapping: stays unavailable; no literal `emulated_run` claim. |
| unknown/fat formats | `unavailable` | `unavailable` | False | False | Explicit unavailable with the probe reason (fat Mach-O is a documented non-goal). |

Negative behavior (tested): for every unavailable pair the PoC runner returns
`status="unavailable"` with the contract reason in `limitations`, empty
`poc`/`regression` case lists, and the gate therefore sees `not_run`/no
verified evidence. It never returns `pass` (verified) or `fail` (rejected) for a
pair it did not execute, and never fakes external PoC execution.

One honest nuance: the pipeline's legacy Mach-O runtime selector still labels a
successful Rosetta run `native_run` in `report.verification["tier"]` (process
execution under ISA translation; kept for backward-compatible acceptance), while
this contract reports `emulated_run` with `poc_available=False`. The runtime
evidence now appends an explicit limitation ("Rosetta cross-arch execution ...
function-level evidence only"), so the difference is disclosed rather than
silent. Changing the legacy label is a pipeline change owned elsewhere.

## 4. How to add a new cell

1. **Implement evidence first.** Add the runtime/evidence path (guest runner,
   Mach-O tier, Unicorn emulation, ...). Do not add a matrix cell before an
   implementation exists.
2. **Declare the cell** in `app/services/repair_matrix.py` (`REPAIR_CELLS`,
   strategies, sink classes, `runtime_tiers`).
3. **Teach the contract**: extend `capabilities.probe` if the new
   format/arch is not covered. `contract()` then derives `declared_tier` from
   the cell automatically; `matrix_payload()["contract_capabilities"]` picks it
   up with no hard-coded copy.
4. **Keep the conditional single-sourced**: new Mach-O host/arch logic belongs in
   `macho_native.execution_tier`; new format availability belongs in
   `capabilities.probe`.
5. **Add a negative test** in `tests/test_runtime_capabilities.py` proving the
   pair is `unavailable`/`not_run` with a non-empty reason when the platform
   cannot execute it (never `rejected`, never `verified`), and extend the
   platform-limits table above if the limitation is permanent.
6. **Run**:

```
.venv/bin/python -m pytest -q tests/test_runtime_capabilities.py \
    tests/test_repair_matrix.py tests/test_poc_runner.py \
    tests/test_binary_pipeline_api.py
```

The per-cell consistency test over `REPAIR_CELLS` fails if a cell declares a
runtime tier that is measured unavailable without an explicit reason, so a new
cell cannot silently claim capability.
