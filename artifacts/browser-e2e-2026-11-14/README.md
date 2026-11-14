# Browser e2e evidence - 2026-11-14

Local macOS/Chrome run of the repository browser suite (`tests/e2e`). This is
the browser evidence for the release; it is **not** a GitHub Actions run and it
is not the release gate itself. The self-hosted `release-nightly-gate` CI job
stays inert on disk (see `docs/operations/release-gate-2026-11-14.md`).

## Run

```bash
.venv/bin/python -m pytest -q -p no:xdist tests/e2e -rs --junitxml=artifacts/browser-e2e-2026-11-14/junit.xml
```

- workspace: `/Users/huageorge/Desktop/AI驱动的二进制漏洞自动修复与正确性验证/binary-repair-gui` (branch `workbench-v3`, Lead-reported
  SHA `f65ed53`; not re-verified because
  task-19 forbids git commands)
- browser: Google Chrome `157.0.8103.51` at
  `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- driver: Chrome DevTools Protocol (repository helper tests/e2e/cdp.py)
- platform: Darwin/arm64, Python 3.11 (repository .venv)

## Result

| metric | value |
|---|---|
| status | **passed** |
| exit code | 0 |
| total | 12 |
| passed | 12 |
| failed | 0 |
| errors | 0 |
| skipped | 0 |
| duration | 35.742 s |

Two consecutive runs agree (12 passed each); the first run is recorded in
`pytest.log`, the second produced `junit.xml`, and `summary.json` carries the
per-test outcomes. **A skip is not a pass:** this run recorded zero skips; Linux
CI records explicit skips by design (the CDP helper probes macOS/Windows browser
paths only) and those skips are not release evidence.

## Files

- `summary.json` - machine-readable evidence (browser, counts, per-test outcomes,
  skip semantics, provenance, limitations).
- `pytest.log` - exact captured stdout of the run (dots + exit marker; the
  machine-readable count is in `junit.xml`/`summary.json` because the suite's
  quiet invocation prints no summary line).
- `junit.xml` - JUnit XML with the 12 test cases and timings.
- `SHA256SUMS` - sha256 of every file in this directory except itself.

## Reproduce

```bash
.venv/bin/python -m pytest -q -p no:xdist tests/e2e -rs \
  --junitxml=artifacts/browser-e2e-2026-11-14/junit.xml
```

## Limits

- Local macOS Chrome run, not a CI run; it does not prove CI execution.
- Covers the 12 documented GUI flows, not every browser/OS combination.
- The frozen SHA is recorded as reported by the Lead and is not re-verified here.


Re-run on the final integration tree `f2392fd9c0f9cf5a83ae7b04a09e2ec0695c073a`: 12 passed / 0 failed / 0 skipped (0.000s).
