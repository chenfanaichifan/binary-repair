# M4 — M2 bundle recheck: still missing; guest key still mismatched (2026-11-07)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** recheck only. No merge, no full suite, no marker, no gate promotion,
no merge/tag.

---

## 0. Status at 10:33

| Item | Result |
|---|---|
| `outputs/m2-06eb7ee.bundle` | **still missing** |
| `06eb7ee` / `2963163` / `d3993555c303` | **not local, not fetched** |
| merge 2963163 → d3993555c303 | **NOT RUN** |
| full suite | **NOT RUN** |
| final SHA | **N/A** |
| `delivery/m4/acceptance-<sha>/` | **N/A** |
| guest route `10.11.0.132:2222` | **UP** |
| guest auth | **`Permission denied (publickey)`** |
| `verified_by="m4"` | **NOT WRITTEN** |
| 124 | **`inconclusive` / `required_check_not_run` / `symbolic`** |
| 118 | **VERIFIED** — independent of T8.3 |

---

## 1. Recheck

```text
$ date
2026-11-07T10:33:52+0800

$ find /Users/huageorge/Desktop /Users/huageorge/Downloads /tmp /Volumes /Users/Shared \
       -name m2-06eb7ee.bundle
(no output)

$ mdfind -name m2-06eb7ee.bundle
(no output)

$ git cat-file -t 06eb7ee / 2963163 / d3993555c303
fatal: Not a valid object name   (all three)

$ nc -z 10.11.0.132 2222
succeeded

$ ssh -p 2222 -i _m4-verify/keys/m4_guest_ed25519 m4verify@10.11.0.132
Permission denied (publickey)
```

No change from the 10:28 record. The two blockers are inputs, not M4 actions.

---

## 2. What is needed

**For the M2 merge:**

1. `outputs/m2-06eb7ee.bundle` (record 96: SHA-256 prefix `6AEF3C73…6CC6`), or
2. a reachable branch/commit containing `06eb7ee`, `2963163`, `d3993555c303`.

Then: `git bundle verify` → `list-heads` includes `06eb7ee` → fetch → branch at
`d3993555c303` → merge `2963163` → full suite → final SHA →
`delivery/m4/acceptance-<sha>/`.

**For V4:**

M3 must install this session's public key (or confirm `FZfxZXkW` belongs to this
M4 machine and deliver its private half through an authorised channel; not the
M5 key):

```text
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBFmDHmwn/0KeulZ32w97zmV2jP+p7kGMdWew2rZnbdq m4-guest-replay-2026-11-06
```

Then `verify_all.sh` 3/3 → 18/18 → second harness → five criteria → marker.

---

## 3. 124 and 118

```text
124: V0 passed, V1 passed, V2 not_run, V3 passed, V4 not_run, V5 passed
     outcome = inconclusive
     reason  = required_check_not_run
     failing = symbolic
```

`118 = VERIFIED (rebuild evidence package)` remains independent.

---

## 4. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 5. Evidence

| File | Content |
|---|---|
| `M4-m2-bundle-recheck-evidence-2026-11-07.txt` | timestamp, missing bundle/commits, route up, auth denied, 124 gates |
| `M4-m2-bundle-missing-2026-11-07.md` | the original missing-bundle record |
| `M4-guest-key-mismatch-2026-11-07.md` | the key mismatch record |
