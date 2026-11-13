# BinaryRepair v5 — universal binary repair acceptance (2026-11-13)

Status: **feature-branch acceptance**, pushed on `feature/universal-repair`
and fast-forwarded to `workbench-v3`; Ubuntu verification CI is green on the
final commit.  The v1.2.1 release snapshot, `main` and the v7 handoff package
are unchanged.

**Claim discipline:** "100%" below means the approved plan G1–G5 (dynamic
ELF32, PE32 `FF15`, i386 memcpy-immediate, ELF32 extend-rx, fat Mach-O input)
and the deterministic repair matrix are complete.  It does **not** mean
arbitrary-binary/vulnerability repair, and it is **not** a proof of AI repair
increment.  See [`verification-review-2026-11-13.md`](verification-review-2026-11-13.md)
and [`LIMITATIONS.md`](LIMITATIONS.md).

This record documents the v5 "universal binary repair entry" implemented on top
of the v4 container-neutral pipeline. It is a bounded engineering claim: any
input file gets a deterministic triage/disposition, and the deterministic matrix
below produces verified or explicitly unverified candidates. It is **not**
universal vulnerability repair and not a whole-program safety proof. See
[`LIMITATIONS.md`](LIMITATIONS.md), section 9.

## 1. Scope and matrix

The matrix is defined once in `app/services/repair_matrix.py`; pipeline, gate,
HTTP API, CLI and this document all read it.

| container | bits | arch | strategies | runtime tier |
|---|---|---|---|---|
| ELF | 32 | i386 | immediate, guard | `emulated_run` (Unicorn x86-32) |
| ELF | 64 | x86_64 | strict-template, immediate, guard | `emulated_run` |
| ELF | 64 | arm64 | immediate, guard | `emulated_run` |
| PE | 32 | i386 | immediate, guard | `emulated_run` (Unicorn x86-32) |
| PE | 32+ | x86_64 | immediate, guard | `emulated_run` |
| PE | 32+ | arm64 | immediate, guard | `emulated_run` |
| Mach-O | 64 | x86_64 | immediate, guard | `native_run` (macOS only) |
| Mach-O | 64 | arm64 | immediate, guard | `native_run` (macOS only) |

Supported sinks: `unbounded_copy` (strcpy/strcat/stpcpy, guard) and
`immediate_length` / `memcpy_length` / `syscall_length` / `checked_copy`
(immediate clamp) with a recoverable capacity.

Explicitly **outside** the matrix (detected/analysed, no rewrite): 32-bit Mach-O,
fat Mach-O, arm32, riscv, mips, powerpc, big-endian inputs; heap/global
destinations; `sprintf` format expansion; UAF/integer/loop defects; inlined
non-import copies.

### Dispositions

| disposition | candidate | verified | meaning |
|---|---|---|---|
| `verified_patch` | yes | yes | action + native/emulated gate passed |
| `static_only_patch` | yes | no | opt-in only; no runtime evidence; **never success** |
| `not_verified` | no | no | action exists but static-only delivery not requested |
| `analysis_only` | no | no | in-matrix container, no patchable sink |
| `unsupported` | no | no | recognised container outside matrix |
| `rejected` | no | no | gate rejected the candidate |
| `invalid` | no | no | empty/oversized/malformed/unrecognised input |

`repair_binary(..., verify=False)` is kept for compatibility and maps to
`static_only_patch` with `verified=false`; the historical ELF x86-64 fail-open
path is removed (a failed gate clears `candidate_available` and returns no
bytes).

## 2. Fixtures and provenance

New v5 fixtures are built by `scripts/build_binary_fixtures.py` (Zig 0.17.1) and
covered by `fixtures/PROVENANCE.json` (`--check` reports 12 fixtures OK; the v5 bundle remains the historical 11-fixture set, with the new ELF x86-64 guard covered by the v6 AI bundle).

| fixture | format/arch | sha256 | size |
|---|---|---|---|
| `fixtures/elf/vuln-strcpy-x86.elf` | ELF32 i386 (static musl) | `a739546885fcb31ef5936bcab3270bbb597ffffe60eb1c10c107a858554aad0d` | 3,955,228 |
| `fixtures/pe/vuln-strcpy-x86.exe` | PE32 i386 (E8→thunk) | `5c801c4563dabf1bfd7619fe9d0537594e0708f17a7014e1641b84e6cece4634` | 847,872 |
| `fixtures/elf/vuln-strcpy-x86-dyn.elf` | dynamic ELF32 i386 (PLT) | `de051d8a470bbda6...` (see PROVENANCE) | 3,405,212 |
| `fixtures/pe/vuln-strcpy-x86-iat.exe` | PE32 i386 (direct `FF15` IAT call) | `59351c0bc2a3b681...` (see PROVENANCE) | 847,872 |
| `fixtures/elf/vuln-memcpy-x86.elf` | ELF32 i386 (memcpy immediate 64) | `0bbe1c86f88d0646...` (see PROVENANCE) | 3,930,224 |

All five i386 fixtures declare the same 16-byte stack geometry
(`capacity = frame_top - destination = 0x10`) and cover the distinct resolver
and repair paths: static musl direct symbol, dynamic glibc PLT, PE import
thunk (`E8`), PE direct IAT (`FF15`) and immediate-length memcpy. Existing ELF
x86-64, PE x86-64/arm64 and Mach-O x86-64/arm64 fixtures are unchanged.

## 3. Runtime evidence (i386)

Captured by `scripts/capture_binary_evidence.py`; raw JSON in
`artifacts/binary-universal-v5-2026-11-13/`.

| fixture | candidate | action | cave | gate | tier/engine |
|---|---|---|---|---|---|
| ELF32 i386 | `elf-i386-fixed.elf` | guard at `0x33e9a` (cap 16) | ELF32 PT_LOAD `0xda000` | success_within_scope | emulated_run / unicorn-i386 |
| PE32 i386 | `pe-i386-fixed.exe` | guard at `0x4010be` (cap 16) | PE32 `.brfix` `0x4d4000` | success_within_scope | emulated_run / unicorn-i386 |
| dynamic ELF32 i386 | `elf-i386-dyn-fixed.elf` | guard at `0x2f5c2` (cap 16) | ELF32 PT_LOAD `0xc7000` | success_within_scope | emulated_run / unicorn-i386 |
| PE32 i386 direct IAT | `pe-i386-iat-fixed.exe` | guard at `0x4010be` (cap 16) | PE32 `.brfix` `0x4d4000` | success_within_scope | emulated_run / unicorn-i386 |
| ELF32 i386 memcpy | `elf-i386-memcpy-fixed.elf` | immediate 64→16 at `0x33bdf` | in-place imm32 | success_within_scope | emulated_run / unicorn-i386 |

Unicorn cases (patched vs original; `canary_intact`):

| input bytes | patched (both fixtures) | original (both fixtures) |
|---|---|---|
| 0 | canary intact, output 0 | intact, output 0 |
| 1 | intact, output 1 | intact, output 1 |
| 15 | intact, output 15 | intact, output 15 |
| 16 | intact, output 15 | **broken** |
| 17 | intact, output 15 | **broken** |
| 64 | intact, output 15 | **broken** |

Baseline JSON: `baseline-elf-i386.json`, `baseline-pe-i386.json`,
`baseline-elf-i386-dyn.json`, `baseline-pe-i386-iat.json`,
`baseline-elf-i386-memcpy.json`. The dynamic/PLT and direct-IAT originals break
the canary at 16/17/64 input bytes; the memcpy original uses a fixed 64-byte
copy and breaks the canary for every input length, while the patched candidate
(immediate 16) is clean. This is instruction-level emulation of the repaired
function, not a native Linux/Windows kernel run; it is labelled
`emulated_run` everywhere. Length-aware modelling reads the copy-length argument
per ABI for memcpy/memmove; `strcpy`/`strcat` keep C-string semantics.

## 4. Negative controls and fail-closed behavior

| input | disposition | candidate | status |
|---|---|---|---|
| `fixtures/pe/i386-control.exe` (i386, `mov [esp+k],reg` args) | `analysis_only` | no | unsupported; limitation names the unsupported argument form |
| `fixtures/pe/cli-64.exe` (PE x86-64, no copy sink) | `analysis_only` | no | unsupported |
| `fixtures/macho/3D_Image_Toolkit` (Mach-O, no copy sink) | `analysis_only` | no | unsupported |
| unknown bytes | `invalid` | no | unsupported |
| empty / >20 MiB | `invalid` | no | unsupported |
| malformed `MZ` header | `invalid` | no | unsupported |
| runtime unavailable, no opt-in | `not_verified` | no | verification inconclusive |
| runtime unavailable, `allow_static_only=1` | `static_only_patch` | yes, `verified=false` | warning on every surface |
| synthetic fat Mach-O (arm64 + x86_64 slices) | `unsupported` | no | slices reported, `container_rewrite=false` |
| synthetic big-endian ELF32 | `unsupported` | no | `matrix.cell=null` |

Raw records: `negative-*.json`, plus `tests/test_repair_any.py`,
`tests/test_binary_pipeline_v4.py`, `tests/test_container_robustness.py` and
`tests/test_binary_pipeline_v5_advanced.py`.

## 5. Surfaces verified

- **API**: `POST /api/binary/scan` (schema v4), `POST /api/binary/repair`
  (verified/static-only/422), `GET /api/binary/matrix` (English ASCII).
- **CLI**: `scripts/repair_binary.py` single + `--batch` dispositions/summary,
  `--allow-static-only`; i386 candidate written and re-parsed.
- **UI**: `GET /binary` renders the Chinese page and nine test ids; sidebar link
  on shell pages; assets served; static-only badge/download gated by
  `delivery.download_allowed`; no user filename is interpolated into HTML.
- **Gate**: `app/services/unified_verification.py` reads the matrix; only
  `native_run`/`emulated_run` can pass; `static_only` is inconclusive.
- Tests: `tests/test_binary_ui.py`, `tests/test_binary_pipeline_api.py`,
  `tests/test_binary_pipeline_v5.py`, `tests/test_repair_i386_emulated.py`,
  `tests/test_repair_i386_writer.py`, `tests/test_repair_matrix.py`,
  `tests/test_repair_any.py`.

## 6. Test suite results

### macOS 13.5 (arm64), Python 3.11.8, lief 1.0.0 / capstone 5.0.7 / unicorn 2.1.4

```text
.venv/bin/python -m pytest -q --ignore=tests/e2e -p no:warnings \
  --junitxml=artifacts/binary-universal-v5-2026-11-13/macos-junit.xml
```

**1128 tests, 0 failures, 0 errors, 4 skipped** (250.1 s; post-v6 suite including the two AI binary-repair paths, the ELF x86-64 fixture and the evidence verifier; the v5-only tree had 1039). Skips are the
platform-gated Linux-execution cases:

- `tests/test_fixture_v3_manifest.py::test_original_is_v0_on_invalid_inputs_if_binary_present` (ELF execution requires Linux)
- `tests/test_fixture_v3_manifest.py::test_repaired_candidate_matches_v3_if_provided` (ELF execution requires Linux)
- `tests/test_native_linux_runtime.py::test_vulnerable_fixture_native_linux` (Linux x86-64 execution)
- `tests/test_native_linux_runtime.py::test_strict_fixture_native_linux_blocks_long_input` (Linux x86-64 execution)

JUnit: `artifacts/binary-universal-v5-2026-11-13/macos-junit.xml`.

### Linux VM (Ubuntu 24.04 arm64, Lima), Python 3.12.3

```text
cd /tmp/br-v5/binary-repair-gui
.venv/bin/python -m pytest -q --ignore=tests/e2e -p no:warnings \
  --junitxml=artifacts/binary-universal-v5-2026-11-13/linux-junit.xml
```

**1128 tests, 0 failures, 0 errors, 7 skipped** (258.0 s; post-v6 suite including the two AI binary-repair paths, the ELF x86-64 fixture and the evidence verifier). Skips are the
platform-gated cases:

- `tests/test_binary_pipeline_v4.py::test_positive_matrix_returns_verified_candidate[macho-arm64]` (Mach-O native runtime is macOS-only)
- `tests/test_binary_pipeline_v4.py::test_positive_matrix_returns_verified_candidate[macho-x86_64]` (Mach-O native runtime is macOS-only)
- `tests/test_fixture_v3_manifest.py::test_repaired_candidate_matches_v3_if_provided` (`BINARYREPAIR_CANDIDATE_ELF` not set)
- `tests/test_repair_macho_native.py::test_native_run_verdict_pass_for_patched[arm64|x86_64]` (requires macOS + codesign)
- `tests/test_repair_macho_native.py::test_original_binary_fails_the_contract[arm64|x86_64]` (requires macOS + codesign)

Environment notes for reproducing the Linux number:

- the Lima VM defaults to `umask 0002`; the canonical run starts with
  `umask 022` (same environmental workaround as the v7 handoff). Without it the
  five `tests/test_guest_executor.py` cases see group-writable package files and
  fail; that is an environment artifact, not a v5 code change.
- macOS `tar`/copy can leave AppleDouble `._*` sidecars in the transferred tree;
  remove them (`find . -name '._*' -delete`) before running. The first Linux
  attempt (before this cleanup) had 203 failures from those stray files; the run
  above is the clean canonical result.
- Linux aarch64 means the macOS-only Mach-O tests skip and the Linux-native
  x86-64 tests are not applicable; all i386/other candidates are verified by
  Unicorn (`emulated_run`) on both hosts.

JUnit: `artifacts/binary-universal-v5-2026-11-13/linux-junit.xml`.

### GitHub Actions (Ubuntu verification)

- Workflow: `Ubuntu verification` (`.github/workflows/ubuntu-verify.yml`,
  `ubuntu-24.04`, Python 3.11, full non-browser suite).
- Feature commit `47465e0`: run
  [43411767923](https://github.com/chenfanaichifan/binary-repair/actions/runs/43411767923)
  — **success** (15 steps, `test` job).
- Evidence-doc commit `f65c2dc`: run
  [43412399232](https://github.com/chenfanaichifan/binary-repair/actions/runs/43412399232)
  — **success**. Because this acceptance record itself is committed after that
  run, the workflow re-runs the same non-browser suite for the docs-only
  commit; the branch run history records the final conclusion.
- The workflow publishes its own JUnit/artifacts (`artifacts/ubuntu-verification/`);
  local macOS/Linux VM counts above are the authoritative detailed counts, and
  the CI conclusion covers the same `pytest -q --ignore=tests/e2e` command on
  Ubuntu 24.04 x86-64.
- At the time of the v5 CI runs, `feature/universal-repair` and the
  CI-trigger branch `workbench-v3` both pointed at `72db891`; `workbench-v3`
  was later fast-forwarded to the AI-path feature commit.  `main` and
  `handoff-v4-local` are untouched.

### macOS readelf / Route B note

The earlier macOS `test_static_routeb_bundle` one-view failure was caused by
GNU `readelf` being absent; it was resolved by installing Homebrew GNU readelf
2.47, **not** by replacing the backend or weakening the assertion.  The test's
0-or-5-view logic has been unchanged since `5932df3`; a stock macOS without
GNU readelf can still reproduce the failure.  Ubuntu CI installs binutils and
takes the five-view path.  Historical failing JUnit remains in
`artifacts/binary-universal-2026-11-13/junit.xml`.

### Content hashes

`python scripts/verify_evidence.py` recomputes fixture/source SHA-256 and every
bundle `SHA256SUMS` entry.  On the final tree: 11 fixture rows + 110 source
rows PASS; v5 bundle 38 files PASS; AI bundle 9 files PASS.  Git blob object ids
are SHA-1 and are not compared with content SHA-256.

## 7. Reproduce

```bash
cd binary-repair-gui
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q --ignore=tests/e2e
.venv/bin/python scripts/capture_binary_evidence.py
```

The evidence bundle includes `README.md`, per-fixture scan/repair JSON, baseline
runtime JSON and `SHA256SUMS` over all files. Rebuild fixtures with
`python scripts/build_binary_fixtures.py --force` (Zig 0.17.1).

## 8. What this does not prove

- No whole-program proof; no claim that a repaired binary is safe for
  production use.
- No universal vulnerability discovery: only the matrix/sink classes above.
- Unicorn evidence is instruction-level emulation, not a hardened guest or a
  native Windows/Linux run. Mach-O native evidence exists only on macOS.
- The Linux VM is arm64; it runs the Unicorn-backed cases and the full test
  suite, not a native x86-64 execution.
- v5 repairs **one function per candidate**: additional vulnerable functions
  are reported as limitations and left unpatched, so that every shipped action
  is covered by the runtime case that executes that function.
- No new release tag or v8 handoff package for this branch; v1.2.1/v7
  records remain the released artifacts.  CI exists and is recorded above.

## 9. Changed surfaces

`app/services/repair_matrix.py` (new), `app/services/binary_pipeline.py`,
`app/services/unified_verification.py`, `app/services/repair/analyzer_i386.py`
(new), `app/services/repair/guards_i386.py` (new),
`app/services/repair/{analyzer,guards,writer}.py`, `app/services/code_cave.py`,
`app/services/pe_repair.py`, `app/services/containers.py`,
`app/services/runtime/emulated.py`, `app/main.py`, `/binary` template + JS + CSS,
`base.html`, i18n overrides, `scripts/{repair_binary,build_binary_fixtures,capture_binary_evidence}.py`,
fixtures/provenance, docs (`README`, `CHANGELOG`, `LIMITATIONS`,
`docs/reference/binary-repair-engine.md`) and the tests listed above.
