# 01 — Isolated Ubuntu execution environment

Work item 1. Status: **done, with recorded gaps** (2026-10-20).

## Purpose

Provide a disposable Ubuntu x86-64 machine where the sample binary is built,
inspected, and (later) executed, without touching the host.

## Decisions

| Question | Decision | Notes |
|---|---|---|
| Host hypervisor / runtime | VMware Workstation Pro 17.5.0, build 22583795, on Windows 11 Home 26200 | Version recorded; no cloud VM, no WSL 2 |
| Ubuntu release and architecture | Ubuntu 24.04.5 LTS (noble), x86-64, kernel 6.8.0-147-generic | Built from the official cloud image, not the 26.04 desktop ISO |
| Network access for the VM | NAT (VMnet8, 192.168.30.0/24), DHCP address 192.168.30.128 | Guest NAT is kept for administration. Candidates are meant to run through `/opt/binrepair/run-isolated.sh` (empty network namespace, `runner` uid 1003); the broker does not invoke it yet and there is no hypervisor-level egress block |
| Snapshot / rollback strategy | `clean-baseline` (uid 6, 2026-10-22 16:54, shut down), on top of `clean-toolchain` and `job-isolation` | Three-snapshot chain; reverting to `clean-baseline` discards `disk-000003.vmdk` |
| Shared folder policy | None. HGFS, copy/paste and drag-and-drop are disabled in the VMX | Evidence leaves over SSH only |
| How evidence leaves the VM | `ssh` / `scp` to the host; only text leaves | No binary is copied back to the host |

## Setup checklist

- [x] Create the VM from an official Ubuntu image; image identity recorded in
      `docs_BinaryRepair/vm-profile.md` §2.
- [x] Record `lsb_release -a`, `uname -a` — see
      `docs_BinaryRepair/environment-baseline.md` §2 and §6.
- [x] Create a working user (non-root `lab`) and install the build and
      inspection tools — see `02-tool-inventory.md`.
- [x] Take a snapshot named `clean-toolchain`.
- [x] Create the working directory layout `~/route-a/{samples,build,reports}`.
- [ ] Confirm the isolation rule: the sample is executed only inside this VM —
      **not yet satisfiable**, see Gaps.

## Measured state

| Item | Value |
|---|---|
| vCPU / RAM | 4 / 7.8 GiB visible |
| Disk | 30 GiB virtual disk; 29 GiB root filesystem, 26 GiB free |
| Hostname | `binrepair-vm` |
| Tools | gcc 13.3.0, binutils 2.42, gdb 15.1, python3 3.12.3; V4 set added 2026-10-22 (clang/lld 18.1.3, Ghidra 12.1.4, JDK 21.0.12.1, LIEF 1.0.0, angr 10.0.4, z3 5.1.0, unicorn 2.1.4) |

Full values, commands and the host-side measurements:
`docs_BinaryRepair/environment-baseline.md`.

## Gaps

These are recorded rather than accepted. They block a claim of "isolated
execution"; they do not block fixture construction.

1. The execution user `lab` has passwordless sudo, so a binary invoked directly
   as `lab` can become root. Only the wrapper drops to `runner` (uid 1003).
2. The isolated wrapper exists but is not wired into the broker, and there is no
   hypervisor-level egress block; the guest itself still has outbound NAT.
3. Tools are not mounted read-only to the execution user.
4. A snapshot revert is the only reset mechanism; a job that damages the disk
   outside a snapshot still affects later jobs. Reverting to `clean-baseline`
   discards `disk-000003.vmdk`, and no revert has been tested.

## Evidence

No evidence is stored in this directory. The measured values and the commands
that produced them live in:

- `docs_BinaryRepair/environment-baseline.md` — host and guest measurements,
  the reproduce block in §6.
- `docs_BinaryRepair/vm-profile.md` — image identity, isolation settings,
  toolchain versions, dependency lock.

Fixture evidence is stored with the fixture, under
`fixtures/public/<fixture-id>/evidence/`.

## Acceptance for this item

- [x] The environment is reproducible from the notes above alone.
- [x] Tool versions are captured.
- [ ] ~~A clean snapshot exists before any binary is copied in.~~ **False as
      written**: all three snapshots post-date the 2026-10-20 fixture build, so
      no snapshot was taken before the sample entered the guest. The reset point
      exists; the "before any binary" ordering does not.

## If it cannot be set up in time

Not applicable — the environment was set up. The gaps above are the honest
residual, not a setup blocker.
