# VM profile — binrepair-u2404-x64-01

Status: profile of the **existing** guest. Read together with
`environment-baseline.md`; where this profile says "not tested", it is not a
claim that the property holds.

## 1. Identity

| Item | Value |
|---|---|
| Display name / folder | `binrepair-u2404-x64-01` — `D:\VMs\binrepair-u2404-x64-01` |
| VMX | `D:\VMs\binrepair-u2404-x64-01\BinRepair-Lab.vmx` (internal name still `BinRepair-Lab`) |
| BIOS UUID | `56 4d 7d 94 06 08 d6 9e-20 8f 8a f9 da 94 c6 0f` |
| Guest OS | Ubuntu 24.04.5 LTS, kernel 6.8.0-147-generic, x86_64 |
| Guest hostname | `binrepair-vm` |
| Resources | 4 vCPU, 8 GiB configured (7.8 GiB visible), 30 GiB disk |
| Guest address | 192.168.30.128 (NAT, DHCP) |
| Host-only / shared folders | none |

## 2. Image identity (SHA-256)

The current disk state is a **chain**, not a single file (2026-10-22):

| Layer | Size (bytes) | SHA-256 |
|---|---:|---|
| `disk.vmdk` | 6,792,544,256 | `7dec112509c833a66b44c2e1aebdc607d33b323ca61351d7cfe0c83886101468` |
| `disk-000001.vmdk` | 33,882,112 | `28451ed9fcf8f54f6fbe0c337c9fe8f6e4823dba08e242daae52855b4647bd92` |
| `disk-000002.vmdk` | 12,320,768 | `b501715b37e954e1ea509ab138d03bb34e45d5672a5b5192dc28dc72bd37100c` |

New writes go to `disk-000003.vmdk` (3,997,696 B,
`b94aa009ea4de3d2087ef1df95ee0f4a45de50fe4966a61f9668c415918b7323`, at the time
of this record). It is **not** part of the baseline: reverting to
`clean-baseline` discards it.

**No single-file hash identifies `clean-baseline`.** Either record the whole
three-layer set above, or consolidate the chain, before publishing an image
hash. A hash of `disk-000003.vmdk` alone identifies only the post-baseline
layer.

Base image and seed, unchanged by the chain:

| Artifact | Size (bytes) | SHA-256 |
|---|---:|---|
| `noble-cloudimg.vmdk` — converted Ubuntu cloud image | 590,749,696 | `9A1E3959C9F4AD9D4752101FD4FF9A43191FB7D72E61FA20E033F9FD235CE794` |
| `seed.iso` — cloud-init seed | 374,784 | `FB343EFCE437844052A604348A226EBC8CC7AD2C24A8E58D46C9D19D88DB15BB` |

The pre-resize base-disk hash (`ED53EE13…`) is **obsolete**, and so are the
2026-10-20 hashes of the previous single-disk state
(`30068DE3…`/`8521F4E8…`): the disk was grown and the chain was rebuilt since.

Limits that must travel with any VMDK hash here:

- a VMDK is a growing sparse file, so a file hash identifies **these bytes at
  this timestamp**, not reproducible guest content — VMware metadata can change
  the file without changing the guest filesystem;
- the chain layers were written at different times (2026-10-20 through
  2026-10-22), so the triple is only meaningful as a set taken together.

Re-verify the triple immediately before any freeze and again in V5; never
present a hash taken while the guest runs.

## 3. Snapshots

Three snapshots exist (2026-10-22). `BinRepair-Lab.vmsd` carries
`snapshot.numSnapshots = "3"`, current uid `6`, and the chain
`4 → 5 → 6`.

| # | Name | uid | Created | Taken | Adds | Disk layer |
|---|---|---|---:|---|---|---|
| 1 | `clean-toolchain` | 4 | 2026-10-20 11:57 | powered off | completed toolchain | `disk.vmdk` |
| 2 | `job-isolation` | 5 | 2026-10-22 16:50 | **while running, includes memory** | `/opt/binrepair/run-isolated.sh` | `disk-000001.vmdk` |
| 3 | `clean-baseline` | 6 | 2026-10-22 16:54 | powered off (28,061-byte `.vmsn`) | the intended repeatable baseline | `disk-000002.vmdk` |

`BinRepair-Lab-Snapshot6.vmsn` is 28,061 bytes; `Snapshot5.vmsn` is 5,329,606
bytes, which is the memory image that makes `job-isolation` a running-state
snapshot.

**Reverting to `clean-baseline`** returns a shut-down VM at the state of
2026-10-22 16:54 and **discards everything in `disk-000003.vmdk`**.

What `clean-baseline` is and is not:

- **is** the intended repeatable baseline for candidate runs — shut down, so a
  revert starts from a defined state;
- **is not** a pre-sample baseline. The fixture was built on 2026-10-20, before
  all three snapshots, so reverting does not return the guest to a state before
  the sample entered;
- `job-isolation` is a running snapshot: reverting to it resumes a powered-on
  VM rather than producing a shut-down one.

Operational note: the stale `BinRepair-Lab.vmx.lck` recorded on 2026-10-20 no
longer applies — the guest powered on, and new snapshots were created on
2026-10-22.

The 2026-10-18 `clean-toolchain` snapshot was deleted by the 2026-10-20 disk
resize (VMware does not resize a chain that still has snapshots). It was
recreated once on 2026-10-20 (uid 4), which is why the uid is 4 and not 3; the
two later snapshots were added on top of it on 2026-10-22.

Before candidate binaries run through the broker, the remaining work is wiring
the isolated wrapper into the broker, a hypervisor-level egress block, and a
read-only tool mount (section 4).

## 4. Isolation settings (from the VMX, not from intent)

| Control | State |
|---|---|
| Copy / paste | disabled (`isolation.tools.copy.disable`, `paste.disable`) |
| Drag and drop | disabled (`isolation.tools.dnd.disable`) |
| Shared folders / HGFS | disabled (`isolation.tools.hgfs.disable`) |
| Network | NAT only, one e1000 NIC |
| Sound / floppy | absent |
| Serial | file-backed `serial.log` |

Measured gaps against the requested disposable-VM profile:

1. **Direct execution as `lab` is unprivileged-unsafe.** `lab` is in the
   `sudo` group (and has passwordless sudo from the cloud-init seed), so a
   binary invoked directly as `lab` can become root inside the guest. The
   isolated wrapper (item 2) avoids this by running the candidate as `runner`
   (uid 1003, no sudo), but the broker does not invoke the wrapper yet.
2. **Job-time network (2026-10-22).** Each candidate runs through
   `/opt/binrepair/run-isolated.sh`, which executes it as `runner` (uid 1003, no
   sudo) inside an empty network namespace: `ip addr` shows only `lo` and DNS
   resolution fails after a 15 s timeout. The guest itself keeps NAT for
   administration; SSH from the host is unaffected. Remaining gap: no verified
   egress block at the hypervisor level, and the wrapper is not yet invoked by
   the broker.
3. **The reset point post-dates the fixture build.** `clean-baseline` exists
   (section 3) but was taken on 2026-10-22, after the 2026-10-20 fixture build,
   so reverting to it does not return the guest to a pre-sample state.
4. **No trusted-tool read-only mount.** Tools live in the same writable
   filesystem as the job workspace.

These are reported as gaps, not silently accepted. They block a claim of
"isolated job execution" but do not block fixture construction and V1/V3
measurement.

## 5. Toolchain

Present and versioned:

| Tool | Version | Status |
|---|---|---|
| gcc | 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1) | used to build the fixture |
| binutils (ld, as, objdump, readelf, nm) | 2.42-4ubuntu2.10 | used |
| gdb | 15.1-1ubuntu1~24.04.1 | used for crash capture |
| make | 4.3-4.1build2 | present |
| python3 | 3.12.3-0ubuntu2.1 | used |
| checksec | present | version not captured in this run |
| capstone | pip 5.0.9; imported module reports 5.0.7 | import smoke test only |
| pyelftools | 0.33 | import smoke test only |
| pwntools | 4.15.0 | installed; not exercised |
| libc6 / libc6-dev | 2.39-0ubuntu8.9 | build dependency |

Absent (measured with `command -v` / import on 2026-10-20):

- **clang / LLVM** — missing
- **Ghidra and JDK (`java`)** — missing
- **LIEF** — missing
- **angr / Claripy / Z3** — missing

**Superseded 2026-10-22.** The `clean-toolchain` snapshot metadata and the
smoke tests recorded in
[`state-change-2026-10-22.md`](state-change-2026-10-22.md) §1 show the missing
tools now installed: clang/lld 18.1.3, Ghidra 12.1.4, OpenJDK 21.0.12.1, LIEF
1.0.0, angr 10.0.4.post1, z3 5.1.0/5.3.1, unicorn 2.1.4. The absence list above
is kept as the measured state on 2026-10-20, not as current state.

Consequence: the toolchain is no longer the reason V4 cannot run. **V4 is still
unrun**, and its verdict belongs to Member 4 — tool availability is not a V4
result.

## 6. Dependency lock

Full `python3 -m pip freeze` output: `docs_BinaryRepair/vm-pip-freeze.txt`
(captured in this guest on 2026-10-20). It predates the V4 toolchain install
recorded in `state-change-2026-10-22.md`, so it covers the older Python-side
tools and is **incomplete for angr / z3 / LIEF**; re-capture before freezing.

## 7. Backend / source revision

`D:\BinRepair` is a Git repository (created 2026-10-20 from the working copy at
`%USERPROFILE%\Desktop\binary-repair`, remote `origin` intact). As of
2026-10-22 it is on branch `member-3-route-a`, HEAD **`627d9eb`**, three
commits ahead of `e030cc2`:

```text
627d9eb docs(fixture): confirm manifest-set hash and pin LF checkouts
baefea2 chore(fixture): keep checksum-listed bytes exact on checkout
d1e0741 test(fixture): add gate 6 crash evidence and GDB command record
```

The working tree still has **23 uncommitted entries**, and `git fetch` /
`git push` still fail with `SEC_E_NO_CREDENTIALS` (no credential for the HTTPS
remote; re-probed 2026-10-22 with `GIT_TERMINAL_PROMPT=0`). Until the credential
is fixed, **nothing has been pushed**, so a VM profile still cannot name a commit
that another member can fetch. That remains an open reproducibility gap, and it
is also why `627d9eb` is a local hash only.

## 8. What a job may rely on today

- x86-64 Ubuntu 24.04.5 guest that boots and executes ELF binaries.
- gcc/binutils/GDB/Python for build and concrete measurement.
- Non-PIE, symbol-preserving fixture builds (see the fixture provenance).
- Network and user isolation have a **designed path** (`run-isolated.sh`:
  `runner` uid 1003, empty network namespace) but not an enforced one — the
  broker does not invoke the wrapper and there is no hypervisor-level egress
  block. Isolation is therefore not claimed. A repeatable reset point exists
  (`clean-baseline`, 2026-10-22 16:54, shut down) but it is not a pre-sample
  baseline, and a revert has not been tested.
- No claim that V4 can run.
