# M4 — own guest keypair, handoff, T8.3 sample check (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** M4-owned keypair and handoff readiness. No replay, no marker, no gate
promotion, no merge, no tag.

---

## 0. Status

| Item | Result |
|---|---|
| M4 keypair | **generated** — ed25519, M4-owned |
| public key | `_m4-verify/m4_guest_key.pub` — ready for M3 to install |
| private key | `_m4-verify/keys/m4_guest_ed25519` (600); **not shared** |
| M5 private key | **not read, not used** |
| guest login | **not yet** — `m4verify@192.168.30.128:22` times out |
| handoff package | `ea5cc9e:M4-v4-handoff-2026-11-06` — **12/12 SHA256SUMS OK** |
| `verify_all.sh` | **NOT RUN** |
| V4 harness ×2 | **NOT RUN** |
| five criteria | **NOT CHECKED** |
| `replay.verified_by="m4"` | **NOT WRITTEN** |
| T8.3 second sample | CWE416 no-input bundle present; **V4 not_run; T8.3 still blocked** |
| 124 | **`inconclusive` / `required_check_not_run` / `symbolic`** |
| 118 | **VERIFIED** — independent of T8.3 |

---

## 1. M4 keypair

```text
private  _m4-verify/keys/m4_guest_ed25519      (600)
public   _m4-verify/keys/m4_guest_ed25519.pub  (644)
copy     _m4-verify/m4_guest_key.pub
fingerprint  SHA256:bRq28b6JG3LXILy3iayXdW/HdSre8mCofnd6B+8L84Q
public sha256 ab8fbd7dc23bf900dc1597da8025a689feed55f77275c87869e55fa4dca5a703

ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBFmDHmwn/0KeulZ32w97zmV2jP+p7kGMdWew2rZnbdq m4-guest-replay-2026-11-06
```

This is a newly generated key. No M5 private key was read, copied, or used, and
no existing default key was reused.

**M3 action:** install the public key on the guest with
`guest/add-m4-key.sh <path-to-m4_guest_key.pub>` (append idempotently to
`m4verify`'s `authorized_keys`, mode 600). The account is password-locked and has
no sudo; the key is the only way in.

Current test:

```text
$ ssh -i _m4-verify/keys/m4_guest_ed25519 m4verify@192.168.30.128
ssh: connect to host 192.168.30.128 port 22: Operation timed out
$ nc -z 192.168.30.128 22
exit 1
```

So either the key is not installed yet, the VMnet8 route is down, or both. The
key alone cannot fix a network route; M3 must also confirm the guest is up.

---

## 2. Handoff package

Extracted from M3's branch `ea5cc9e`:

```text
M4-v4-handoff-2026-11-06/
  verify_all.sh          3 steps: SHA256SUMS, selfcheck, e2e rerun
  run_selfcheck.sh       environment check + expected comparison
  run_e2e.sh             harness rerun + byte comparison
  scripts/selfcheck.py   18 checks
  inputs/{v4_harness.py,candidate.elf,original.elf,contract.json}
  expected/{selfcheck.expected.json,harness-output.expected.json}
```

Integrity: **12/12 files OK** against `SHA256SUMS`. Inputs match the frozen
digests:

```text
candidate 46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0
original  c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9
contract  8a2b408c9b1463ca8cb14692d11f1580f80816a74e81cc13310852f3700e3c3b
expected  9c6eeda7684f2e405fbceb83fec4a3962687559b1d35e738431c631b7d58ca8c
```

`verify_all.sh` runs the harness **once** (e2e) and compares byte-for-byte. The
request is harness **twice** plus five criteria, so after login M4 will:

```sh
cd M4-v4-handoff-2026-11-06
sh verify_all.sh                       # 3/3
/opt/angr-venv/bin/python inputs/v4_harness.py \
  --candidate inputs/candidate.elf --original inputs/original.elf \
  --contract inputs/contract.json --out /tmp/run1.json --replay-runs 2
# repeat to /tmp/run2.json
sha256sum /tmp/run1.json /tmp/run2.json expected/harness-output.expected.json
```

and check the five criteria before writing anything.

---

## 3. T8.3 second sample

The T8.3 bundle is present and contains a **CWE416 no-input, lifetime/heap**
sample — its README calls it the second sample, deliberately different from the
CWE121 bounds/stack case.

```text
V0 passed, V1 passed, V2 passed 5/5, V3 passed 1/1, V4 not_run, V5 passed
V4-not-run.json: producer evidence exists; M4 replay + verified_by missing
```

**Unresolved inconsistency:** the same bundle's `gate-index.json` still lists
`"a second sample"` under `blocked.not_done_by_M3`, and the M4 handoff README
says “T8.3 stays blocked: no second defect class exists here.” The T8.3 README
calls this bundle the second sample. So the sample's status is **not settled**:
it exists, its V4 is `not_run`, and T8.3 remains **BLOCKED** pending M4 replay
and M4/Lead acceptance. M4 does not treat the README title as acceptance.

---

## 4. 124

```text
V0 passed, V1 passed, V2 not_run, V3 passed, V4 not_run, V5 passed
outcome = inconclusive
reason  = required_check_not_run
failing = symbolic
```

The handoff and T8.3 bundle do not change 124's gate state.

---

## 5. Record 118 and boundaries

`118 = VERIFIED (rebuild evidence package)` remains independent: it does not
promote V0–V5, does not produce a candidate, and does not relieve T8.3.

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 6. Evidence

| File | Content |
|---|---|
| `M4-keypair-handoff-evidence-2026-11-06.txt` | key fingerprint/perms, guest ssh/nc failure, 12/12 handoff integrity, input hashes, T8.3 gate index, 124 gates |
| `m4_guest_key.pub` | the public key to install (public only) |
| `_m4-verify/m3-handoff-ea5cc9e/` | extracted handoff and T8.3 evidence |
| `_m4-verify/keys/` | M4 private key (not packaged) |
