# 136 — M5 m4verify public key and pending-merge risk

- Date: 2026-11-06
- Owner: Member 1
- Scope: key handoff and merge-risk record. No canonical pin change.
- T8.3 blocked. No merge to `main`, no tag, no live-success claim.

## 1. M5 public key (public half only)

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFsAfbyV0vW0um1nzzkV40ZbJXwLtQyFyOozC+Eoet9o 2761163826@qq.com
```

- fingerprint: `SHA256:OHp8LjckI8lQ3kArUPz2CJ/4OxqzWB5URI8idmZzSOc`
- public-key sha256: `ca565494b41ecc1de3ed15252d547b9de88466722d9fc54a9dc20a0547634e93`
- provenance: local `~/.ssh/id_ed25519.pub`; comment matches the M5 commit
  author `2761163826@qq.com`. No private key is copied.

Handoff package: `delivery/m5-m4verify-2026-11-06/`.
M3 installs it with the existing `add-m4-key.sh` into `m4verify` and records
the fingerprint above.

## 2. Canonical pin is unchanged

`canonical/m1-m5-integration` remains **`d1ce352`**. Adding a guest key or
guest access does not move the canonical pin.

Fresh `ls-remote` at this record:

```
d1ce352  canonical/m1-m5-integration
7817a20  integration/live-bridge
e231777  integration/live-bridge-2026-11-03
```

## 3. Pending-merge risk

The user-reported "97 commits ahead of main" is recorded as a risk claim, not
silently copied. Fresh counts against `origin/main @ 472aa94` are:

| Ref | Ahead | Behind |
|---|---:|---:|
| `d1ce352` canonical | 64 | 0 |
| `788f5c7` M1 | 112 | 0 |
| `7817a20` live-bridge | 126 | 0 |

No currently advertised branch measured 97. The exact count must be rechecked
before any merge decision; the risk is real regardless of the number. Do not
merge `main` until T8.3 closes.

## 4. Preserved behavior

- canonical partial aggregation / passthrough / plan fallback `partial=false`;
- CWE121 v2 hash and 120 contract gate unchanged;
- 124 remains `inconclusive / required_check_not_run / symbolic`;
- T8.3 blocked.
