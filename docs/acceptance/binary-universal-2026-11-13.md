# Direct binary repair pipeline — local acceptance (2026-11-13)

## Scope

This record covers the **local macOS** portion of the unified binary-repair
pipeline:

- format detection and scan for ELF, PE and Mach-O;
- dispatch to the existing ELF x86-64, AArch64 ELF, PE x86-64 and Mach-O
  backends;
- report v2 normalization;
- CLI and `/api/binary/scan` / `/api/binary/repair`;
- static reparse of every candidate;
- Unicorn verification for ELF x86-64.

It does **not** cover Linux native execution, qemu-user, Windows/Wine PE
runtime, macOS Mach-O runtime, or arm64 ELF execution. Those are listed in
`HANDOFF-TASKS-2026-11-13.md`.

## Source

```text
base: workbench-v3 @ 2aca931
local changes: app/services/binary_pipeline.py, app/main.py,
               scripts/repair_binary.py, tests/test_binary_pipeline*.py,
               docs/reference/binary-repair-engine.md
```

## Local test result

Command:

```bash
.venv/bin/python -m pytest -q --ignore=tests/e2e \
  --junitxml=artifacts/binary-universal-2026-11-13/junit.xml
```

Result:

```text
900 collected
895 passed
4 skipped
1 failed
```

The only failure is the known macOS `readelf` Route B view-count check:

```text
tests/test_routeb_executor.py::test_static_routeb_bundle
AssertionError: assert 1 in (0, 5)
```

Linux is expected to run the three platform-gated tests and pass this case:
`900 collected / 899 passed / 1 skipped / 0 failed`; record the actual JUnit on
Linux instead of treating this number as proof.

## Pipeline behavior observed locally

| Input | Scan | Repair |
|---|---|---|
| `artifacts/vuln-elf/vuln.elf` | ELF x86-64, 2 findings | patched, `strict-template`, gate success |
| `fixtures/pe/cli-64.exe` | PE x86-64, 0 copy findings | unsupported, no candidate |
| `fixtures/macho/3D_Image_Toolkit` | Mach-O arm64, 0 immediate findings | unsupported, no candidate |
| arbitrary non-binary | unknown | unsupported, no candidate |

The PE/Mach-O results are intentional: the fixtures do not contain a supported
pattern. The dispatcher still scans them and returns a report; it does not claim
a repair.

## New tests

```text
tests/test_binary_pipeline.py       6 tests
tests/test_binary_pipeline_api.py   4 tests
tests/test_repair_cli.py            1 existing test still passes
```

Coverage:

- format detection for ELF/PE/Mach-O/unknown;
- scan findings and repair-support flags;
- ELF strict repair with report v2 and gate success;
- fail-closed PE/Mach-O/unknown inputs;
- backend mismatch;
- API scan/repair success and 422 fail-closed;
- CLI strict output and legacy top-level `mode`/`capacity` keys.

## Evidence

```text
artifacts/binary-universal-2026-11-13/
  pytest.log
  junit.xml
  scan-elf.json / scan-pe.json / scan-macho.json
  repair-elf.json / repair-pe.json / repair-macho.json
  cli-output.json / cli-report.json
  vuln-fixed.elf
```

## Limitations

- No real Linux guest; Unicorn is a test oracle, not a host-kernel run.
- PE and Mach-O runtime semantics are not verified.
- `sprintf` binary repair and UAF/integer/loop guards are not implemented.
- PE arm64 call/cave is not implemented; it is scan-only.
- Mach-O x86-64 call redirection exists as a primitive but has no auto strategy.
- This is a supported-pattern matrix, not universal binary repair.

## Handoff

The non-local work is enumerated in
[`HANDOFF-TASKS-2026-11-13.md`](HANDOFF-TASKS-2026-11-13.md).
