# Artifact evidence index

Date: 2026-11-08  
Status: P1 `success_within_scope`; P2 `ACCEPTANCE PASSED`; T8.3 `COMPLETE`.

This curated snapshot contains the current canonical evidence only. The full
historical delivery tree remains in the source repository
`chenfanaichifan/binary-repair`.

## Canonical — current

### P1 final (authoritative)

```text
artifacts/p1-real-window-2026-11-07/
  controller/snapshot.json
  controller/ids.json
  api/attempts.json
  p2/p2-rc.txt
  p2/p2-result.txt
  bundle/a1.routeb/
  v5-replay-2026-11-07/      HOST-SHA256SUMS 16/16
```

Job: `9247357c54714546a7ff84891f7766f8`  
P1 verdict: `success_within_scope`  
P2: exit 0, `synthetic=false`, both routes `success_within_scope`.

### Route A V4

```text
artifacts/p1-routea-v4-symbolic-2026-11-07/
artifacts/p1-routea-real-v4-2026-11-07/
artifacts/p1-routea-v4-input-2026-11-07/
artifacts/p1-routea-package-2026-11-07/
artifacts/v4-harness-2026-11-07/
```

### V5 original logs

```text
artifacts/p1-real-window-2026-11-07/v5-replay-2026-11-07/
artifacts/p1-v5-logs-2026-11-07/
artifacts/p1-v5-logs-2026-11-07.zip
```

The four original logs are tracked with `HOST-SHA256SUMS` 16/16 and
`v5/SHA256SUMS` 8/8. No replay was regenerated.

### T8.3 / 124

```text
artifacts/cwe416-124-v4-rerun-2026-11-06/
artifacts/m4/v4-2026-11-07/
artifacts/m4-revalidation-ebc92a8/
```

### Test and e2e logs

```text
artifacts/logs/all-members-full-chrome-2026-11-08.txt
artifacts/logs/e2e-chrome-2026-11-08.txt
```

Recorded result: `714 passed / 2 Linux-only skipped / 0 failed`; Chrome e2e
`12 passed`.

## Historical — not included here

The following remain in the source repository and are not part of this curated
snapshot:

```text
dist/
artifacts/artifacts-2026-11-07/
artifacts/cwe416-124-candidate-2026-11-05/
artifacts/m5-m4verify-2026-11-06/
artifacts/t30-rebuild-2026-11-05/
artifacts/upload-2026-11-07/
```

The earlier `docs/archive/mvp-2026-10-31/evidence/` directory is retained as
historical MVP evidence; do not use it for current gates.

## Redundancy rules

```text
canonical P1       = artifacts/p1-real-window-2026-11-07/
canonical V5       = v5-replay-2026-11-07/ (16/16) + p1-v5-logs-2026-11-07/
canonical Route A  = artifacts/p1-routea-v4-symbolic-2026-11-07/
canonical 124      = artifacts/cwe416-124-v4-rerun-2026-11-06/
old candidate      = cwe416-124-candidate-2026-11-05 (not current)
```

## Not stored

```text
private keys
guest credentials
client binaries or private logs
regenerated V5 logs
```
