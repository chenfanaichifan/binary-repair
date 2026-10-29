# 41 — M3 execution paths: gate4-harness, v6 kit, routeb jobwrap

**Date:** 2026-10-29  
**Owner of the execution:** M3/VMer. M5 does not enter the VM.

## Gate 4 harness

| Item | Value |
|---|---|
| snapshot | `gate4-harness` (M3/VMer-owned) |
| snapshot path/hash | **not in M5 repo; M3/VMer must report the exact vmsd/chain hash** |
| v6 kit | `dist/m5-routeb-kit-2026-10-22-v6.zip` |
| v6 kit SHA-256 | `499f510c9fda660826ea6b7f5b1969839334ba7cd63cc0c975a1e4ca951e4b1d` |
| runner | `routeb/gate4_runner.sh` |
| runner SHA-256 | `515c4d609495dea723c6fe6ff9e55b34fca078a3bf450770ebb3c744f07bd357` |
| invocation | `jobwrap gate4` (no arguments; root-owned `gate4.conf` supplies runner/repo/work) |

Wrapper: `b232d60b…` (M3/VMer-owned). Runner environment:

```bash
PYTHON=/opt/angr-venv/bin/python
CLANG=clang
LLD=ld.lld
GHIDRA_HOME=/opt/ghidra
EXPECTED_UID=1003
```

No `sudo -u runner jobwrap`; no `unshare` inside the runner. The runner writes
`gate4-status.json`, `environment.txt`, and the native
`manifest-compare.json` under the work dir. It does not emit native
`case-01..06.json`; any six-case rows are derived
(`runner_native=false`, `derived_from=manifest-compare.json`).

**Missing:** the `gate4-harness` snapshot itself and its chain/manifest hash are
M3/VMer-side. M5 cannot supply or hash them.

## Route B under jobwrap

Decision B wrapper (added with this handoff):

| Item | Value |
|---|---|
| wrapper | `routeb/jobwrap_routeb.sh` |
| wrapper SHA-256 | `70b50f927a41694fdfaabf0c515ec15ca77f4302bf0ce8a95acc134fa7b64621` |
| invocation | `jobwrap routeb -- <repo>/routeb/jobwrap_routeb.sh <repo> /var/tmp/routeb-work` |

Wrapper behavior:

- runs `python -m routeb.executor` from the repo;
- uses `original.elf`, normalized C, frozen tests;
- `--run-manifest` produces real `manifest-compare.json` in isolation;
- no sudo/unshare/network inside the wrapper.

The **jobwrap routeb binary/artifact** itself is not in the M5 repo; M3/VMer
must provide its path + SHA-256 and confirm decision B. The wrapper hash above is
the exact artifact M5 contributes; the jobwrap binary hash is M3/VMer-owned.

## Required P4/P3B package shape

Both packages must use `handoff.json` (INTERFACE v1), sorted `SHA256SUMS`, and:

```bash
python scripts/check_handoff.py <pkg> --expect-from M3 --expect-to M5
```

P4 native files: `gate4-status.json`, `manifest-compare.json`, `candidate.elf`,
`original.elf`, `environment.txt`, `isolation.json`, `revert.log`,
`harness-v2-manifest.txt`, `harness-manifest.json`.

The runner does **not** emit native `case-01..06.json`. If the package includes
six cases, they are derived:

```json
{"derived_from":"manifest-compare.json","runner_native":false}
```

Native evidence is only `manifest-compare.json`. Missing native case raw is
recorded as a missing item; do **not** write `gate4_pass`.

P3B files: `candidate.elf`, `edit-manifest.json`, `manifest-compare.json`,
`logs/executor.log`.

Until those exist: **P4 NOT RUN, P3B NOT RUN, Gate 4 NOT RUN.** No static-only
or kit-only pass.
