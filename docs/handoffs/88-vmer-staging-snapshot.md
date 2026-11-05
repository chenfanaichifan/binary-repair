# 88 — VMer staging / snapshot record

**From:** VMer (M3 acting as VM operator)
**To:** M3 (guest executor), Lead (approval), M4 (independent verifier — waived)
**Date:** 2026-11-05
**Status:** DRAFT — staging and snapshot state **as of 2026-10-31**, consolidated
from measured records (`vm-profile.md`, `environment-baseline.md`,
`BOARD.md`, `route-a/jobwrap-gate5/build-recipe.md`). Values marked `not_run` /
`unconfirmed` are recorded as such and must not be read as passing.

> This record answers VMer's task-2: it pins the VM staging/snapshot procedure
> and the executor's fixed-argv operation list so a repair run can be reproduced
> from a clean checkout. It is a **procedure + state record**, not new evidence.

---

## 1. Guest identity (measured)

| Item | Value | Source |
|---|---|---|
| Host hypervisor | VMware Workstation 17.5.0 build-22583795 | `environment-baseline.md` §1 |
| VM folder | `D:\VMs\binrepair-u2404-x64-01` | `vm-profile.md` §1 |
| VMX | `D:\VMs\binrepair-u2404-x64-01\BinRepair-Lab.vmx` | `vm-profile.md` §1 |
| Guest OS | Ubuntu 24.04.5 LTS, kernel 6.8.0-147-generic, x86_64 | `vm-profile.md` §1 |
| Resources | 4 vCPU, 8 GiB, 30 GiB disk | `vm-profile.md` §1 |
| Guest address | 192.168.30.128 (NAT, DHCP) | `vm-profile.md` §1 |

---

## 2. Snapshot chain (measured, 2026-10-22 → 2026-10-31)

| uid | Name | Taken | State | Purpose |
|---|---|---|---|---|
| 4 | `clean-toolchain` | 2026-10-20 11:57 | powered off | completed toolchain |
| 5 | `job-isolation` | 2026-10-22 16:50 | **running (incl. memory)** | `/opt/binrepair/run-isolated.sh` |
| 6 | `clean-baseline` | 2026-10-22 16:54 | powered off | clean baseline, no V4 tools |
| 7 | `toolchain-v4-ready` | 2026-10-22 17:14 | powered off | Patcherex2/angr stack in `/opt/angr-venv` |
| 11 | `gate4-harness` | 2026-10-30 | powered off | V2/V5 probes (current baseline) |
| 12 | `routeb-harness-wip` | 2026-10-30 | powered off | Route B harness WIP |
| 13 | `routeb-harness` | 2026-10-30 | powered off | Route B execution (resume target) |

Current `.vmsd snapshot.current = "11"` — the guest was booted to uid 11 for the
V2/V5 probes and powered off cleanly at 20:40 on 2026-10-30; no `vmware-vmx`,
no `.lck`. (`BOARD.md` "Guest state".)

**Chain manifest** (uid 4..11 + `.vmsd`, hashed powered off):
`docs/handoffs/evidence/P4/chain-manifest.json`.

Key operational facts (from `vm-profile.md` §2–§3):

- The disk identity is a **chain**, not a single VMDK hash. A VMDK file hash
  identifies bytes at a timestamp, not reproducible guest content.
- uid 5 (`job-isolation`) is a **running** snapshot: reverting to it resumes a
  powered-on VM, not a shut-down one.
- Reverting to uid 11 **discards** the active `disk-000004.vmdk`, including
  `/usr/local/bin/jobwrap` (created 17:17, in no snapshot).
- Revert to uid 13 to resume Route B execution work.

---

## 3. Staging procedure (the reproducible path)

Purpose: take the VM from a clean powered-off state to "ready to run one repair
job", and back. Each step is a host-side VMware action or an in-guest command.

### 3.1 Before a run (staging in)

1. Confirm no prior VM is running and no `.lck` exists:
   `D:\VMs\binrepair-u2404-x64-01\` must show no `vmware-vmx` and no `*.lck`.
2. Power on / revert to the target snapshot (uid 7 for toolchain work, uid 11
   for V2/V5, uid 13 for Route B execution).
3. In the guest, verify the toolchain interpreter: `/opt/angr-venv/bin/python`
   for the V4/Patcherex2 stack; system `python3` for pwntools-only ops. Pin the
   interpreter per operation (`environment-baseline.md` §2 caveat).
4. Record the boot identity: snapshot name, chain-manifest hash, tool versions,
   `date`, operator (10-line section, per `34-m3-m5-task-split.md` T3.0).

### 3.2 After a run (staging out / reset)

1. Copy all produced artifacts out (they live only in the current disk state;
   a revert discards them).
2. Power off cleanly; verify `snapshot.current` and no `.lck`.
3. Revert to the baseline uid for the next run **unless** the disk state itself
   is the deliverable (in which case snapshot it and record the new uid).

### 3.3 Not yet fixed (carried from Nick's review, item 6)

- A **canonical, single** launch/config procedure does not yet exist: the
  Windows controller defaults to `var/controller` while the worker defaults to
  `var` in a separate terminal (`Improve.md` §6). `unconfirmed` — to be unified
  before a clean-checkout replay is claimed.
- `routeb/out/gate4/roundtrip.elf` is the hardcoded test path; the actual
  binary is at `docs/handoffs/evidence/P4/roundtrip.elf`. The retrieval/rebuild
  procedure is not yet documented. `unconfirmed`.

---

## 4. Executor fixed-argv operation list (guest side)

The executor accepts **typed manifests and artifact IDs only** — never a shell
string, never an arbitrary path (AGENTS.md §3).

### 4.1 `jobwrap` (Gate 4, unchanged)

Bound to the old `jobwrap b232d60b`; not re-signed by Gate 5.

### 4.2 `jobwrap-gate5` (Gate 5 successor, fixed argv)

Built in-guest, `-static`, placed at `/usr/local/sbin/jobwrap-gate5` (does NOT
overwrite `/usr/local/sbin/jobwrap`).

| Invocation | Purpose |
|---|---|
| `jobwrap-gate5 probe m4-gate5 -- <repo> <work>` | Route A probe (`f39a0302…d146cb` pinned) |
| `jobwrap-gate5 probe m4-gate5b -- <repo> <work>` | Route B probe (`05d9a2cd…edb82` pinned) |

Fail-closed: a tampered probe → `blob mismatch`, exit 1. Isolation attested:
uid 1003, CapEff=0, NoNewPrivs=1, seccomp, netns `net:[4026532222]`, no default
route.

### 4.3 `jobwrap routea` (Route A executor — mode added, compiled, and run)

CLI accepts exactly `jobwrap routea <job-id>` (single id, `[A-Za-z0-9._-]{1,64}`);
no path, no argv array; bad argument → exit 2. Root-owned config
`/usr/local/etc/binrepair/routea.conf`. Exit codes: 2 bad arg, 3 unknown job,
4 candidate hash mismatch.

**Status as of 2026-11-05: implemented, compiled in the guest, and executed.**
The `routea <job-id>` mode was added to `route-a/jobwrap-gate5/jobwrap_gate5.c`
under Lead record `72` (path 4 — a successor mode, not a rebuild of the lost
source). It compiles with `gcc -O2 -Wall -Wextra -Werror -static` (exit 0, no
warnings, built in the guest), and the conformance window then scored it
**10/10 pass** including `pos-routea-exec` (a real worker run) and the four
`routea` refusals (rc 2/3/4/1). Evidence: `docs/handoffs/evidence/T15/`,
record `95` §6.

The conformance build lives at `/var/tmp/conformance/jobwrap-gate5`
(`293df727…`). `/usr/local/sbin/jobwrap` (`b232d60b…`) and
`/usr/local/sbin/jobwrap-gate5` (`0066973d…`) were **not** replaced.

Source recovery checked 2026-11-05: the original `jobwrap_v3.c` is **confirmed
lost** (git history holds only the `jobwrap_gate5.c` successor; the deployed
binary ships `gate3|probe|gate4` — no `routea`). The hand-decompiled
`.tmp/jobwrap-recovery/jobwrap_v3_reconstructed.c` is audit-only and explicitly
**not buildable**. So the gap is not "recover the source" but "add a `routea`
mode", which Lead record `72` (path 4) already authorises as a successor-mode
pattern — the same route used for `jobwrap-gate5`.

**Updated 2026-11-05 (superseded — see the Status above):** the
`routea <job-id>` mode was written into
`route-a/jobwrap-gate5/jobwrap_gate5.c` (dispatch, tab-separated config parse
with 6-field/ownership/mode checks, candidate hash gate at exit 4, worker exit
code propagated, isolation reused from `enter_isolation()`), sample config at
`route-a/jobwrap-gate5/routea.conf.sample`. It has since been **compiled in the
guest and executed**; the earlier "not compiled / never executed" caveat no
longer applies.

---

## 5. Honest status

- **Measured / pinned:** guest identity, snapshot chain uid 4..13, executor argv
  forms for `jobwrap-gate5`, isolation attestation values.
  **Update 2026-11-05:** `snapshot.current` was `14` at 18:30 (snapshot
  `t15-t6-work`, a *running-state* snapshot parented to uid 11). The clean
  baseline is still uid 11; the one-window **reset has not been performed**.
- **Not yet fixed (`unconfirmed`):** canonical config/launch procedure; the
  `roundtrip.elf` retrieval/rebuild path (now documented in
  `docs/handoffs/evidence/P4/ROUNDTRIP-ELF-RETRIEVAL.md`).
- **Resolved 2026-11-05:** `jobwrap routea` — the mode is implemented in the
  successor, compiled in the guest, and executed under conformance
  (`docs/handoffs/evidence/T15/`, 10/10 pass). No longer `not_run`.

---

*Record owner: VMer (M3). Review: Lead.*
