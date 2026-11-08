# Artifact manifest

This curated snapshot keeps canonical acceptance evidence in one tracked root:

```text
artifacts/     current canonical evidence and hand-off packages
```

The historical distribution root `dist/` remains in the source development
repository (`chenfanaichifan/binary-repair`). It is not duplicated here. New
shared hand-offs belong under `artifacts/` and are listed below; do not create a
second authoritative root.

## Current canonical packages

```text
artifacts/p1-real-window-2026-11-07/
artifacts/p1-routea-v4-symbolic-2026-11-07/
artifacts/p1-routea-real-v4-2026-11-07/
artifacts/p1-routea-v4-input-2026-11-07/
artifacts/p1-routea-package-2026-11-07/
artifacts/v4-harness-2026-11-07/
artifacts/cwe416-124-v4-rerun-2026-11-06/
artifacts/m4/v4-2026-11-07/
artifacts/m4-revalidation-ebc92a8/
artifacts/p1-v5-logs-2026-11-07/
artifacts/p1-v5-logs-2026-11-07.zip
artifacts/p1-routea-kit-2026-11-07/
artifacts/legacy-m5-evidence/
```

## Distribution snapshots included

```text
artifacts/p1-v5-logs-2026-11-07.zip
artifacts/p1-routea-kit-2026-11-07/
artifacts/legacy-m5-evidence/
```

Large historical distribution snapshots (`dist/`,
`artifacts/upload-2026-11-07/`, `artifacts/artifacts-2026-11-07/`) remain in the
source repository. This public snapshot selects only the current canonical
evidence.

## Verification

Every `artifacts/**/SHA256SUMS` verifies in a clean checkout. The four original
V5 replay logs are tracked; see `artifacts/INDEX.md`.
