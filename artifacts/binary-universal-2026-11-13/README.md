# Unified binary repair — local evidence (2026-11-13)

Command:

```bash
.venv/bin/python -m pytest -q --ignore=tests/e2e \
  --junitxml=artifacts/binary-universal-2026-11-13/junit.xml
```

Result:

```text
900 collected / 895 passed / 4 skipped / 1 failed
```

The failure is the known macOS `readelf` Route B check. See
`docs/acceptance/binary-universal-2026-11-13.md`.

Files:

```text
pytest.log / junit.xml
scan-elf.json / scan-pe.json / scan-macho.json
repair-elf.json / repair-pe.json / repair-macho.json
cli-output.json / cli-report.json / vuln-fixed.elf
```

`repair-pe.json` and `repair-macho.json` are intentionally `unsupported` for the
current fixtures; they demonstrate fail-closed behavior, not a successful PE or
Mach-O repair. Real runtime work is listed in
`docs/acceptance/HANDOFF-TASKS-2026-11-13.md`.
