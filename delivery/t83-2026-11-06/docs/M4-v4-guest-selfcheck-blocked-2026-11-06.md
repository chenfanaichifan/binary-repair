# M4 — guest access and selfcheck blocked (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** guest access and selfcheck attempt only. No replay, no marker, no gate
promotion, no merge, no tag.

---

## 0. Verdict

The handoff says: access the guest, run `selfcheck` 18/18, then replay. The guest
is **not reachable from this host**, and the selfcheck scripts are not in the
workspace. So the run stops before the selfcheck; no marker is written.

| Step | Result |
|---|---|
| Guest access | **FAILED** — IPv4 timeout; IPv6 link-local has no route here |
| `selfcheck` 18/18 | **NOT RUN** — guest unreachable; scripts not delivered |
| candidate / original independent run | **NOT RUN** |
| replay ×2 | **NOT RUN** |
| digest `cb2137a2…` | **NOT CHECKED** |
| `replay.verified_by="m4"` | **NOT WRITTEN** |
| V4 | **`not_run`** |
| 124 | **`inconclusive` / `required_check_not_run` / `symbolic`** |

---

## 1. Access attempts

```text
IPv4 192.168.30.128
  ping  -> 100% packet loss
  nc 22 -> exit 1
  ssh   -> connect timeout

IPv6 fe80::20c:29ff:fe94:c60f
  record 129 says the M3 window reached it at %5 when VMware NAT was down
  this Mac has no vmnet interface (en0 = 10.12.0.175; anpi/utun/bridge only)
  ping6 -> nodename/route failure
  ssh6  -> connect timeout

local /opt/angr-venv -> absent
selfcheck.py / run_selfcheck.sh -> not present in the workspace
docs/handoffs/evidence/cwe416-v4-env-2026-11-06/ -> not delivered here
```

Record 129 describes the environment and the 18 checks, but a record is not the
guest. Its own §6 says the install half did not run and the guest was reached
only over IPv6; that route does not exist on this host.

---

## 2. Why the stop is correct

Handoff 131 requires all four environment facts before replay: Python 3.12.x,
angr 10.0.4.post1, z3 5.1.0, and reachable inputs. A recipe or a prose
description of a selfcheck is not a passed selfcheck. Fabricating `18/18` from
record 129 would be exactly the class of evidence the project forbids.

The selfcheck must be run on the guest (or on a host with the same venv), and its
exit code must be 0 with all 18 checks `[ok]`. Until then, V4 stays `not_run`.

---

## 3. What unblocks it

1. Restore the VMware NAT/vmnet segment (or an IPv6 route to the guest) and SSH
   access, **or** provide `/opt/angr-venv` on this host;
2. deliver `run_selfcheck.sh`, `selfcheck.py`, and the
   `cwe416-v4-env-2026-11-06/` evidence directory;
3. run `sh run_selfcheck.sh` → **18/18, exit 0**;
4. run `v4_harness.py` on candidate `46d16e99…fcd0` / original `c9c2632e…` /
   contract `8a2b408c…`, twice;
5. check the five criteria: candidate **unsat** (empty-disjunction,
   `free_calls=0`), original **sat**, two replay digests identical and equal to
   `cb2137a2…cb14`, calibration 1 known-good / 1 known-bad, and property/hook
   match;
6. only then write `replay.verified_by="m4"`.

No step above can be skipped by reading an existing record.

---

## 4. 124

```text
V0 passed, V1 passed, V2 not_run, V3 passed, V4 not_run, V5 passed
outcome = inconclusive
reason  = required_check_not_run
failing = symbolic
```

The current-code ingest view (V2 5/5) is also
`inconclusive / required_check_not_run / symbolic`; the bundle's own gate index
still shows V2/V4 `not_run`. V4 stays `not_run`.

---

## 5. Record 118 and T8.3

`118 = VERIFIED (rebuild evidence package)` remains independent: it does not
promote V0–V5, does not produce a candidate, and does not relieve T8.3.
T8.3 stays **BLOCKED**.

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
| `M4-v4-guest-selfcheck-evidence-2026-11-06.txt` | interface list, IPv4/IPv6 attempts, missing venv/scripts, 124 gate index |
| `129-m3-cwe416-v4-environment-2026-11-06.md` | the environment record (recipe and 18 checks, not a run) |
| `131-lead-verified-by-gate-blocker-2026-11-06.md` | the handoff contract and five criteria |
