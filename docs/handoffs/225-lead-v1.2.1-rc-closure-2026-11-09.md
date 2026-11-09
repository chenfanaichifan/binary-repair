# 225 — Lead closure for M1/M4/M5 scope

Date: 2026-11-09

## Verification

```text
source 61e30a9
729 collected / 727 passed / 2 Linux-only skipped / 0 failed

release/v1.2.1 91fd404
737 collected / 735 passed / 2 Linux-only skipped / 0 failed
browser e2e 12 passed
P2 exit 0 / success_within_scope

public rc candidate 3c0c9a0
737 collected / 735 passed / 2 Linux-only skipped / 0 failed
```

M5 key/API/provider targeted: pass.
Real DeepSeek smoke: pass (redacted).
Linux real-key UI: pass.
Windows DPAPI fake-key: pass.
Windows real-key UI: NOT RUN.

## Decision

```text
v1.2.0 public stable: CLOSED
v1.1.3: FROZEN
v1.2.1-rc1: approved prerelease only
v1.2.1 stable: HOLD
public main: 9439340 / v1.2.0 unchanged
public rc push: blocked by GitHub credentials; M4 must execute
```

## Handoff

```text
delivery/handoff-v1.2.1-rc1-2026-11-09.zip
SHA256 19e4097c32aaafc63ec3b16e5f04fb90b4f3e7b3fa16729c5c893f4a7d88ff6f
```
