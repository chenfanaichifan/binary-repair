# M2 cross-function fixtures (Phase-9 E-02 prototype)

Two minimal binaries that the current same-function/leaf-only analyzer cannot
resolve, used by the M2 cross-function analysis prototype as positive evidence.

Build (offline; bundled zig 0.17.1, no network, no dependencies):

    fixtures/crossfn/build.sh

Outputs (deterministic; SHA256 recorded in `original.sha256`):

    crossfn_param.elf   7800 bytes   sha256 ac08f993...cf68c62
    crossfn_global.elf  7456 bytes   sha256 31479ffb...52950cb8

## crossfn_param.elf

The sink (strcpy) lives in `copy_payload(char *dst, const char *src)`; the
16-byte destination capacity lives in the **callers**:

* `wrapper()`: `char buf[16]` in the caller frame, copied through a pointer
  alias into `copy_payload`. Frame geometry gives an upper bound of 32 bytes
  (the buffer does not sit at the frame top; without DWARF the exact 16 is not
  recoverable - documented residual, see LIMITATIONS.md section 21);
* `wrapper2()`: the destination is the **return value** of `ret_buffer()`,
  which returns the static `s_ret[16]`. The ELF STT_OBJECT symbol gives the
  exact capacity 16.

Current deterministic engine on this fixture (read-only probe, evidence in
`artifacts/m2-analysis-2026-11-16/engine-probe.json`):

* target `copy_payload`: `disposition=analysis_only`,
  `error="target-scoped mode: no patchable sink lies inside target copy_payload"`;
* target `wrapper`: same `analysis_only` outcome;
* no target: safe default `analysis_only`.

## crossfn_global.elf

The sink (strcpy) lives in `store_out(const char *src)` and writes to the
file-scope `static char g_out[16]`. The capacity is the ELF STT_OBJECT symbol
size (16), not frame geometry; the copied value comes from the caller
(`main` -> argv[1]). The current engine treats global destinations as
analysis-only (LIMITATIONS.md section 21).

Current deterministic engine on this fixture: target `store_out` ->
`analysis_only`, `error="target-scoped mode: no patchable sink lies inside
target store_out"`.

## PoC / regression manifests

`poc-crossfn-param.json` and `poc-crossfn-global.json` are **declared
expectation manifests** for a future repair candidate (the M2 increment does
not produce any candidate). They carry `fixture_sha256` and an explicit
`evidence_level: "declared_not_run"`: this host is macOS arm64 and the
fixtures are x86-64 Linux ELF, so runtime observation is not available here;
a Linux x86-64 environment with a reference fix must produce the measured
values before any manifest field may be treated as observed.

## Honesty notes

* The prototype's analysis output is **evidence only**: it is not wired into
  `repair_any`, the unified gate, or any planning path, and it produces no
  candidate.
* No DWARF is emitted (`-g0`): the stack capacity residual above is
  intentional and reported as `frame_geometry_upper_bound`.
* `-fno-sanitize=all` keeps the binaries small and deterministic and removes
  unrelated ubsan runtime code from the analysis evidence.
