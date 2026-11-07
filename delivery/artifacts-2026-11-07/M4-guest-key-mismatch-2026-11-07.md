# M4 — guest route up, key mismatch blocks replay (2026-11-07)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** access attempt only. No replay, no marker, no gate promotion, no merge,
no tag.

---

## 0. Verdict

The M3 guest route is now **up**, but authentication uses a different M4 key than
the one this session generated and holds. Replay cannot start.

| Item | Result |
|---|---|
| guest route | **UP** — `10.11.0.132:2222` accepts TCP |
| this session's key | `bRq28b6…` — **not authorised** |
| M3-installed keys | `JF1hZZdG…` (M5), `FZfxZXkW…` (claimed M4) |
| `FZfxZXkW` private half | **not on this host**, not in the agent |
| login | **`Permission denied (publickey)`** |
| `verify_all.sh` | **NOT RUN** |
| V4 harness ×2 | **NOT RUN** |
| five criteria | **NOT CHECKED** |
| `replay.verified_by="m4"` | **NOT WRITTEN** |
| T8.3 wording | still lists `"a second sample"` under `not_done_by_M3`; **not unified** |
| 124 | **`inconclusive` / `required_check_not_run` / `symbolic`** |
| 118 | **VERIFIED** — independent of T8.3 |

---

## 1. Route is up

```text
$ nc -z 10.11.0.132 2222
Connection to 10.11.0.132 port 2222 succeeded.   (exit 0)

$ ssh -p 2222 -i _m4-verify/keys/m4_guest_ed25519 \
      -o IdentitiesOnly=yes m4verify@10.11.0.132
m4verify@10.11.0.132: Permission denied (publickey).
```

So this is no longer a routing problem. ICMP is filtered, but TCP/2222 is
reachable and SSH completes the host-key exchange.

---

## 2. Key mismatch

This session generated and holds:

```text
private  _m4-verify/keys/m4_guest_ed25519       600
public   m4_guest_key.pub
fingerprint SHA256:bRq28b6JG3LXILy3iayXdW/HdSre8mCofnd6B+8L84Q
```

M3's `dd2d926` installed a different key for the M4 role:

```text
SHA256:JF1hZZdGsxmEUt0REdbg4X76LCbaA/1q+0IYObh3zgI   m5-v4-access-2026-11-06
SHA256:FZfxZXkWYLEVY+b9/cPRN+VhUf7tVXL4Xd9wKspYDQQ   m4-guest-replay-2026-11-06
```

M3's handoff 145 says to use `~/.ssh/m4_id_ed25519` for `FZfxZXkW…`. On this
host:

- no `m4_id_ed25519` (or any key with that fingerprint) exists;
- `ssh-add -l` reports **no identities**;
- no `.pub` under the home tree matches `FZfxZXkW…`.

So the private half of the installed M4 key is **not available in this session**.
Using it would require importing an unknown private key; using the M5 key
(`JF1h…`) is excluded by the work order. Neither was done.

---

## 3. What unblocks it

One of:

1. **Install this session's public key** (preferred):
   ```text
   ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBFmDHmwn/0KeulZ32w97zmV2jP+p7kGMdWew2rZnbdq m4-guest-replay-2026-11-06
   ```
   `guest/add-m4-key.sh` on M3's side; then `FZfxZXkW…` can be retired.
2. Or confirm that `FZfxZXkW…` belongs to **this** M4 machine and deliver its
   private half through an authorised M4 channel. It must not be the M5 key.

After that, the locked sequence applies unchanged: `verify_all.sh` → 3/3,
`run_selfcheck.sh` → 18/18, second harness run, five criteria, then
`replay.verified_by="m4"`.

The handoff inputs remain intact: 12/12 `SHA256SUMS`, candidate `46d16e99…`,
original `c9c2632e…`, contract `8a2b408c…`, expected output `9c6eeda7…`,
replay digest `cb2137a2…`.

---

## 4. T8.3

`dd2d926` still carries the old `gate-index.json` wording:

```text
blocked.not_done_by_M3 = [verified_by, V4 pass, T8.3 completion, a second sample]
```

while the bundle README calls the CWE416 sample the second sample. The wording
is **not unified**; T8.3 remains **BLOCKED**. V4 in that bundle is `not_run`.

---

## 5. 124 and 118

```text
124: V0 passed, V1 passed, V2 not_run, V3 passed, V4 not_run, V5 passed
     outcome = inconclusive
     reason  = required_check_not_run
     failing = symbolic
```

`118 = VERIFIED (rebuild evidence package)` remains independent: it does not
promote V0–V5, does not produce a candidate, and does not relieve T8.3.

---

## 6. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 7. Evidence

| File | Content |
|---|---|
| `M4-guest-key-mismatch-evidence-2026-11-07.txt` | route up, our key fingerprint, permission denied, no agent/FZfx key, M3 145 lines, T8.3 gate index, 124 gates |
| `m4_guest_key.pub` | the public key this session holds (public only) |
| `_m4-verify/keys/m4_guest_ed25519` | this session's private key, local (not packaged) |
