# M4 — guest replay hold and acceptance sequence (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** key handling and the pending replay sequence. No run, no marker, no
gate promotion, no merge, no tag.

---

## 0. Status

| Item | Result |
|---|---|
| M4 private key | **local only** — `_m4-verify/keys/m4_guest_ed25519` (600), not packaged, not shared |
| M4 public key | `m4_guest_key.pub` — with M3 for installation |
| fingerprint | `SHA256:bRq28b6JG3LXILy3iayXdW/HdSre8mCofnd6B+8L84Q` |
| guest | `m4verify@192.168.30.128:22` still times out |
| `verify_all.sh` | **NOT RUN** |
| 18/18 | **NOT CHECKED** |
| second harness run | **NOT RUN** |
| five criteria | **NOT CHECKED** |
| `replay.verified_by="m4"` | **NOT WRITTEN** |
| T8.3 | **BLOCKED** — wording not unified, V4 not replayed |
| 124 | **`inconclusive` / `required_check_not_run` / `symbolic`** |
| 118 | **VERIFIED** — independent of T8.3 |

---

## 1. Key handling

```text
private  _m4-verify/keys/m4_guest_ed25519      600
public   m4_guest_key.pub                      (only this is delivered)
fingerprint SHA256:bRq28b6JG3LXILy3iayXdW/HdSre8mCofnd6B+8L84Q
```

The previous delivery zip contains **only** `m4_guest_key.pub`; no `keys/`
directory and no private key. No M5 private key was read or used. M3 installs the
public half with `guest/add-m4-key.sh`; M4 keeps the private half local.

Current guest test:

```text
$ ssh -i _m4-verify/keys/m4_guest_ed25519 m4verify@192.168.30.128
ssh: connect to host 192.168.30.128 port 22: Operation timed out
```

Waiting for M3 to install the key **and** restore the VMnet8 route.

---

## 2. Sequence once the guest is reachable

1. `ssh -i _m4-verify/keys/m4_guest_ed25519 m4verify@192.168.30.128`
2. `cd M4-v4-handoff-2026-11-06 && sh verify_all.sh` → **3/3**;
   `run_selfcheck.sh` → **18/18**, same normalised result as
   `expected/selfcheck.expected.json`.
3. Second, independent harness run (the handoff's `run_e2e.sh` runs once):
   `v4_harness.py --candidate … --original … --contract … --replay-runs 2`
   twice; both outputs must equal each other and
   `expected/harness-output.expected.json` (`9c6eeda7…8ca8c`).
4. Five criteria:
   1. `state=passed`, `ran=true`, `scope=model`;
   2. replay `runs=2`, `identical=true`, digest `cb2137a2…cb14`;
   3. calibration: one known-good pass, one known-bad rejected;
   4. candidate `unsat` is the empty-disjunction case (`free_calls=0`), disclosed;
   5. property text matches the contract `forbidden_behavior`; hooks do not
      over-approximate the target.
5. Only if all pass: write `replay.verified_by="m4"` — nowhere else, and not
   before step 4.

A failed criterion is a finding, not a reason to relax the check.

---

## 3. T8.3

The CWE416 no-input bundle exists and calls itself the second sample
(`V0/V1/V2/V3/V5 passed, V4 not_run`), but its own `gate-index.json` still lists
`"a second sample"` under `not_done_by_M3`, and the M4 handoff README says no
second defect class exists there. The wording is not unified.

**T8.3 stays BLOCKED** until (a) the bundle's own count/status wording agrees
with its README, and (b) M4's V4 replay and M4/Lead acceptance are done.

---

## 4. 124 and 118

```text
124: V0 passed, V1 passed, V2 not_run, V3 passed, V4 not_run, V5 passed
     outcome = inconclusive
     reason  = required_check_not_run
     failing = symbolic
```

`118 = VERIFIED (rebuild evidence package)` remains independent: it does not
promote V0–V5, does not produce a candidate, and does not relieve T8.3.

---

## 5. Boundaries

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
| `M4-guest-replay-hold-evidence-2026-11-06.txt` | key perms/fingerprint, zip contains only public key, guest timeout, T8.3 blocked line, 124 gates |
| `m4_guest_key.pub` | public key only |
| `_m4-verify/keys/m4_guest_ed25519` | M4 private key, local (not packaged) |
