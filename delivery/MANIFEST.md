# Delivery manifest

This curated snapshot keeps delivery evidence in one tracked root:

```text
delivery/      current canonical evidence and hand-off packages
```

The historical distribution root `dist/` remains in the source development
repository (`chenfanaichifan/binary-repair`). It is not duplicated here. Do not
merge the two roots or move a historical package into `delivery/`; new shared
hand-offs belong under `delivery/` and are listed below.

## Current canonical packages

```text
delivery/p1-real-window-2026-11-07/
delivery/p1-routea-v4-symbolic-2026-11-07/
delivery/p1-routea-real-v4-2026-11-07/
delivery/p1-routea-v4-input-2026-11-07/
delivery/p1-routea-package-2026-11-07/
delivery/v4-harness-2026-11-07/
delivery/cwe416-124-v4-rerun-2026-11-06/
delivery/m4/v4-2026-11-07/
delivery/m4-revalidation-ebc92a8/
delivery/p1-v5-logs-2026-11-07/
delivery/p1-v5-logs-2026-11-07.zip
```

## Distribution snapshots included

```text
delivery/p1-v5-logs-2026-11-07.zip
```

Large historical distribution snapshots (`dist/`, `delivery/upload-2026-11-07/`,
`delivery/artifacts-2026-11-07/`) remain in the source repository. This snapshot
selects only the current canonical evidence to keep the public tree readable.

## Verification

Every `delivery/**/SHA256SUMS` in this snapshot verifies in a clean checkout.
The four original V5 replay logs are tracked; see `delivery/INDEX.md`.
