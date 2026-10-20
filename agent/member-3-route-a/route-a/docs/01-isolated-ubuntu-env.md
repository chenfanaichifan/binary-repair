# 01 — Isolated Ubuntu execution environment

Work item 1. Status: ☐ not started

## Purpose

Provide a disposable Ubuntu x86-64 machine where the sample binary is built,
inspected, and (later) executed, without touching the host.

## Decisions to make first

| Question | Decision | Notes |
|---|---|---|
| Host hypervisor / runtime (VirtualBox, VMware, WSL 2, cloud VM) | TBD | must be recorded with version |
| Ubuntu release and architecture | TBD | x86-64 required by the project profile |
| Network access for the VM | TBD | download tooling once, then restrict |
| Snapshot / rollback strategy | TBD | one clean snapshot before any sample work |
| Shared folder policy | TBD | read-only where possible |
| How evidence leaves the VM | TBD | copy files out; do not run on host |

## Setup checklist

- [ ] Create the VM from an official Ubuntu image; record image name and SHA-256.
- [ ] Record `lsb_release -a`, `uname -a`.
- [ ] Create a working user (no root login), install build and inspection tools
      (see `02-tool-inventory.md`).
- [ ] Take a snapshot named `clean-toolchain`.
- [ ] Create the working directory layout, e.g.:
      `~/route-a/{samples,build,reports}`.
- [ ] Confirm the isolation rule: the sample is executed only inside this VM.

## Evidence to save under `reports/`

- `reports/01-os-release.txt` — `lsb_release -a`, `uname -a`
- `reports/01-image-sha256.txt` — image file name + SHA-256
- `reports/01-toolchain.txt` — output of `scripts/check-tools.sh`

## Acceptance for this item

- The environment is reproducible from the notes above alone.
- Tool versions are captured.
- A clean snapshot exists before any binary is copied in.

## If it cannot be set up in time

"An explicit setup blocker" is an accepted result for this slice. Record it
instead of faking execution:

| Date | Tried | Command | Error (paste it) | What stays blocked |
|---|---|---|---|---|
| | | | | |

State clearly what the team can still do without the VM (document review,
sample provenance from a trusted build log, tool documentation), and what
cannot be claimed without it (any execution, crash, or patch result).
