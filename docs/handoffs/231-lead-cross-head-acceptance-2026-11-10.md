# 231 — Lead cross-head acceptance for v1.2.1-rc1

Date: 2026-11-10

## Accepted

```text
Linux real-key UI: PASS
Windows real-key UI: PASS on 8f0908a (cross-head, Lead accepted)
0d5791a/99d1550 real-key replay: NOT RUN
real key file: cleared (record 228)
key status: configured=false, file absent
```

This acceptance is for **v1.2.1-rc1 prerelease only**. It is not a claim that a
real-key replay occurred on 0d5791a or 99d1550.

## Package

```text
source     99d1550
candidate  6f9d60b
tag        v1.2.1-rc1 (local)
bundle     delivery/v1.2.1-rc1-public-2026-11-09/v1.2.1-rc1.bundle
SHA256     83cca51063a007f291a0bcccb3b130bc89114e16e617b8e5576bae1d9b76c789
handoff    delivery/handoff-v1.2.1-rc1-2026-11-09.zip
SHA256     a8c41ba9969cb1ea65dd98c9ef6b407b957a5ea7b49821dd4620a162f0b543f7
```

## Boundaries

```text
public main 9439340 / v1.2.0 unchanged
v1.1.3 367d29b frozen
v1.2.1 stable: HOLD
F2 hardening: M5/M1 tested; M3 focused re-review not repeated
public push: blocked by credentials
```
