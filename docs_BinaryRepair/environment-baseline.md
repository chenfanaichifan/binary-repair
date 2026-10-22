# Environment baseline — BinRepair MVP

Status: **measured**, 2026-10-20 10:20–10:35 +08 (02:20–02:35 UTC); guest
resources re-measured 10:52 +08 after the resize described in §3.
Every value below comes from a command run on the machine named; none is taken
from the PRD or Tech Design. Where a measurement contradicts a planning
assumption, the contradiction is recorded, not smoothed over.

## 1. Host workstation

| Item | Measured value | Command |
|---|---|---|
| Machine | LENOVO 21VH | `Get-CimInstance Win32_ComputerSystem` |
| OS | Microsoft Windows 11 Home China, version 10.0.26200, build 26200.9711 | `Get-CimInstance Win32_OperatingSystem`; `HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion` |
| CPU | Intel Core Ultra X7 358H, 16 cores / 16 logical processors | `Get-CimInstance Win32_Processor` |
| RAM | 33,840,197,632 bytes (31.52 GiB); 15.5 GiB free at measurement | `Get-CimInstance Win32_ComputerSystem`; `Win32_OperatingSystem` |
| Free disk (D:) | 404.89 GiB free, 46.57 GiB used | `Get-PSDrive D` |
| Virtualization firmware flag | `VirtualizationFirmwareEnabled = False`; `SecondLevelAddressTranslationExtensions = False`; `HypervisorPresent = True` | `Get-CimInstance Win32_Processor`, `Win32_ComputerSystem` |
| Hypervisor in use | VMware Workstation 17.5.0 build-22583795; `VMAuthdService` running; VMnet8 NAT = 192.168.30.1 | `(Get-Item D:\VMware\vmware.exe).VersionInfo`; `Get-Service` |
| Python on host | 3.15.0 | `python -c "import sys; print(sys.version)"` |

Notes:

- The registry `ProductName` still reports `Windows 10 Home China`. That is a
  legacy field; `Win32_OperatingSystem.Caption` reports Microsoft Windows 11
  Home China at build 10.0.26200.
- `VirtualizationFirmwareEnabled = False` is **not** treated as "no
  virtualization". The measured fact is that a VMware guest boots, runs, and
  answers over SSH on this host. The flag most likely reflects the hypervisor
  already owning VT-x. The measured capability, not the flag, is what the plan
  relies on.

## 2. Guest execution environment

| Item | Measured value |
|---|---|
| OS | Ubuntu 24.04.5 LTS (noble) |
| Kernel | 6.8.0-147-generic, x86_64 |
| vCPU | 4 |
| RAM | 7.8 GiB total, 7.3 GiB free, no swap |
| Disk | 30 GiB virtual disk; 29 GiB root filesystem, 26 GiB available (10 % used) |
| Hostname | `binrepair-vm` |
| Compiler | gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0 |
| binutils / ld | 2.42 |
| GDB | 15.1 |
| Python | 3.12.3 |

Full tool inventory and dependency lock: `docs_BinaryRepair/vm-profile.md`.

## 3. Planned guest allocation vs actual

The Tech Design planning allowance is **4 vCPU / 8 GiB RAM / 30 GiB disk**.

| Resource | Planned | Actual (10:52) | Meets plan? |
|---|---|---|---|
| vCPU | 4 | 4 | Yes |
| RAM | 8 GiB | 7.8 GiB visible | Yes |
| Disk | 30 GiB | 30 GiB (29 GiB root, 26 GiB free) | Yes |

The guest was resized on 2026-10-20 from 2 vCPU / 4 GiB / 10 GiB to
4 vCPU / 8 GiB / 30 GiB. Two facts from that operation matter and are not
cosmetic:

1. **The snapshot chain was rebuilt twice.** The resize deleted the 2026-10-18
   `clean-toolchain`; it was recreated on 2026-10-20 and two more snapshots were
   added on 2026-10-22 (`job-isolation`, then `clean-baseline`). The reset point
   is now `clean-baseline` (uid 6, 16:54, shut down), and because the fixture
   was built on 2026-10-20 it is **not** a pre-sample baseline.
2. **The disk identity changed, and it is now a chain.** The old SHA-256 no
   longer applies. The current three-layer set and the active
   `disk-000003.vmdk` are recorded in `vm-profile.md` §2 and
   `state-change-2026-10-22.md` §4; a VMDK file hash identifies bytes at a
   timestamp, not reproducible guest content.

Positive consequences: fixture timings are now representative of the planning
allowance, and the V4 toolchain is installed (see
`state-change-2026-10-22.md` §1).

## 4. Version-target mismatch

- Documented target: Ubuntu 24.04 with Python 3.12.
- Guest: Ubuntu 24.04.5 with Python 3.12.3 — matches.
- Host: Windows 11 with Python 3.15.0 — **not** the execution target and not
  used to build, run, or debug the sample.

## 5. What this baseline does not establish

- It does not establish that the guest is disposable: `clean-baseline` (uid 6,
  2026-10-22 16:54) is a shut-down reset point, but no revert has been tested
  (see `vm-profile.md` §3).
- It does not establish job-time network isolation: `/opt/binrepair/run-isolated.sh`
  gives a command an empty network namespace as `runner`, but the broker does
  not invoke it and there is no hypervisor-level egress block
  (`state-change-2026-10-22.md` §3).
- It does not establish an unprivileged execution path by default: `lab` keeps
  passwordless sudo, and only the wrapper drops to `runner` (uid 1003).
- It does not establish the toolchain as verified end to end: the V4 tools are
  installed and smoke-tested, but V4 has not been run
  (`state-change-2026-10-22.md` §1).

## 6. Reproduce

```powershell
Get-CimInstance Win32_Processor | Select Name,NumberOfCores,NumberOfLogicalProcessors,
    VirtualizationFirmwareEnabled,SecondLevelAddressTranslationExtensions
Get-CimInstance Win32_OperatingSystem | Select Caption,Version,BuildNumber,
    FreePhysicalMemory,TotalVisibleMemorySize
Get-CimInstance Win32_ComputerSystem | Select Manufacturer,Model,TotalPhysicalMemory,HypervisorPresent
Get-PSDrive D
(Get-Item 'D:\VMware\vmware.exe').VersionInfo | Select FileVersion
```

```bash
lsb_release -a; uname -a; nproc; free -h; df -h /
gcc --version | head -1; ld --version | head -1; gdb --version | head -1; python3 --version
```
