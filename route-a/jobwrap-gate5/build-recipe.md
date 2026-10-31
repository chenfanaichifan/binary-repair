# jobwrap-gate5 — build recipe (GUEST ONLY)

This binary must be compiled **inside the disposable Ubuntu x86-64 guest**, never
on the host (AGENTS.md hard line). This file records the exact build command and
the post-build steps to bind the resulting hash to Gate 5.

## Source

- `jobwrap_gate5.c` — the successor isolation executor (this directory).
- Pinned probe blobs (compile-time constants, fail-closed):
  - Route A: `scripts/m4_gate5_probe.py` = `f39a0302dd1aa42635da80fa4e9160d37a221f5ac383270add3eaedcffd146cb`
  - Route B: `scripts/m4_gate5b_probe.py` = `05d9a2cd417880c9be51e1a4cd4608158d94b50da233b223c2f4a589850edb82`

## Build (run as root inside the guest)

```bash
gcc -O2 -Wall -Wextra -Werror \
    -static \
    -o /usr/local/sbin/jobwrap-gate5 \
    jobwrap_gate5.c
```

Notes:
- `-static` removes the runtime glibc dependency and keeps the seccomp filter
  and isolation self-contained (matches the spirit of a disposable wrapper).
- The pinned SHA-256 lives in `.rodata` (`PROBE_SHA256_HEX`); do not edit it
  without a new probe freeze and a re-binding of the Gate 5 record.
- After build, the binary must be `root:root 0755` and placed at
  `/usr/local/sbin/jobwrap-gate5` (it does NOT overwrite `/usr/local/sbin/jobwrap`).

## Post-build binding

```bash
# 1. record the successor binary hash (from bytes, not from a chat summary)
sha256sum /usr/local/sbin/jobwrap-gate5

# 2. record the isolation attestation it emits on a probe run
#    (uid=1003, gid=1003, CapEff=0, NoNewPrivs=1, egress=blocked, ...)
jobwrap-gate5 probe m4-gate5 -- /path/to/repo /var/tmp/gate5-work
# Route B (fixed invocation):
jobwrap-gate5 probe m4-gate5b -- /path/to/repo /var/tmp/gate5b-work
```

The successor binary hash goes into the Gate 5 record (`51`), alongside the
pinned probe blob `f39a0302…d146cb`. It binds **only Gate 5**; Gate 4 stays
bound to the old `jobwrap b232d60b`, and P4 is NOT re-signed.

## What this does NOT do

- Does not overwrite, rebuild, or re-sign the old `jobwrap` / P4 / Gate 4 chain.
- Does not claim byte- or hash-equivalence to the lost `jobwrap_v3.c`.
- Does not read the probe hash from the environment (fail-closed, hardcoded).
