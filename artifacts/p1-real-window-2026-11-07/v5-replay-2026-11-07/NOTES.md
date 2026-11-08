# V5 replay evidence — 2026-11-07 (host copy)

**Result: `pass = true`. Build reproducibility only; it does not prove behaviour.**

Guest: `binrepair-vm`, Ubuntu 24.04.5, kernel 6.8.0-147-generic, user `uid=1000(lab)`.
Baseline snapshot: `p1-prewindow-20261107` (uid 15), layer `disk-000010.vmdk`.
Kit: `p1-v5-replay-kit-2026-11-07.zip`, sha256
`8bc4aa0d05cf325c897e5e5f3c72fa45917a8112b01160aa2127107d2d3a01a4`
(its own `SHA256SUMS`: 10 entries, all verified before the run).

## Outcome

```
replay.sh exit code          0
original-1 == original-2     c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9
candidate-1 == candidate-2   46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0
p1-candidate.elf             46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0
V5-replay.json               pass = true
```

`SHA256SUMS` of this directory itself: `a89b4ec83570e8d969992e6b10d7b1fdca94a1bbd8c10792f77bc0e1c89093a2`.

## Three defects in the kit (fixed in the guest copy only)

The kit as shipped cannot run as-is. Fixes were applied to the guest copy of the
kit, not to the evidence files, and every hash below is recorded so the changes
are auditable.

1. **UTF-8 BOM on `replay.sh`.** The shebang arrived as `\xef\xbb\xbf#!/usr/bin/env`,
   so bash reported `#!/usr/bin/env: No such file or directory`.
   `31fa40e978d049cc0c6b2249106ae1147806c3d544e6ecf515ccf33b02b04c74` -> BOM stripped.
2. **Missing `juliet/C/testcasesupport/std_testcase_io.h`.** `std_testcase.h:124`
   includes it unconditionally; the kit only shipped `std_testcase.h` and `io.c`.
   The header was taken from the guest's Juliet 1.3 checkout
   `/home/lab/evaluator/src/juliet-v1.3/C/testcasesupport/std_testcase_io.h`,
   sha256 `6459df50d22697bb61619e2effd688ebb98915db25f7eb1bdbb767f888066fb6`.
   Three independent copies on the guest (evaluator checkout, two CWE416 kits)
   agree on that hash.
3. **CRLF on the last line of `replay.sh`.** Only `exit "$rc"` carried a `\r`, so it
   became `exit "0\r"` -> `bash: exit: 0: numeric argument required` -> the script
   returned 2 even though `V5-replay.json` said `pass: true`.
   `sed -i 's/\r$//' replay.sh` -> `09cdd6ca166038a1b5baaa949905dddb23b441a0372ee172106b8913909dff25`.

Final working `replay.sh` sha256: `09cdd6ca166038a1b5baaa949905dddb23b441a0372ee172106b8913909dff25`
(shipped form was `31fa40e9…4c74`).

## Two runs

- Run A (after defect 1+2 fixed, before defect 3): `pass: true`, script exit **2**.
- Run B (after defect 3 fixed): `pass: true`, script exit **0**. This directory holds
  Run B.

`V5-replay.json` is byte-identical between the two runs
(`8e5ccc3e3e7a0608f9e713b8226355a95c155838cc694499b315cb205d2cc065`); only
`environment.txt` differs, because it embeds the run timestamp.

## Environment (Run B)

```
date_utc=2026-11-07T05:28:54Z
uname=Linux binrepair-vm 6.8.0-147-generic #147-Ubuntu SMP PREEMPT_DYNAMIC Thu Sep 24 11:33:16 UTC 2026 x86_64 x86_64 x86_64 GNU/Linux
gcc=gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
python=Python 3.12.3
sha256sum=sha256sum (GNU coreutils) 9.4
user=uid=1000(lab) gid=1000(lab) groups=1000(lab),4(adm),27(sudo)
```

## Boundary

- Compilation happened only in the guest; the host neither compiled nor executed
  anything.
- The candidate was **not** executed. This is build reproducibility, not behaviour.
- P1 bundle stays frozen; this directory is separate evidence.
- Reset target: `p1-prewindow-20261107` (uid 15). Reset details are recorded below.

## Reset evidence (recorded after the run)

Source: host-side `D:\VMs\binrepair-u2404-x64-01\vmware.log` and
`BinRepair-Lab.vmsd`. The revert was a manual action in VMware Workstation; the
log records it verbatim.

```
2026-11-07T05:31:23.159Z Vix: VMAutomation_InitiatePowerOffImpl: going to revert to snapshot uid 15 upon poweroff
2026-11-07T05:31:23.594Z SnapshotVMXRevertToSnapshot: Reverting to snapshot UID: 15
2026-11-07T05:31:23.595Z SNAPSHOT: Snapshot_Revert: 'BinRepair-Lab.vmx' : 15
2026-11-07T05:31:23.682Z SNAPSHOT: SnapshotDeleteDisks 'D:\VMs\binrepair-u2404-x64-01\disk-000013.vmdk'
2026-11-07T05:31:23.778Z Revert to snapshot 15 succeeded.
```

- `snapshot.current` = `15` (verified in `BinRepair-Lab.vmsd` after the revert).
- `disk-000013.vmdk` — the delta that held every write from this session — was
  deleted by the revert. The filesystem state of the baseline is unchanged.
- `revertToSnapshot` return code: **unavailable**. `vmrun` cannot start on this
  host (`Error: vmrun was unable to start`, rc=-1, reproduced 2026-11-07), so the
  revert could not be issued through the CLI. The log line
  `Revert to snapshot 15 succeeded.` is the equivalent evidence.
- Post-revert boot id: **not captured**. The VM was left powered off after the
  revert; a boot id only exists once the guest boots. Powering it on does not
  modify snapshot 15 (writes go to a fresh overlay), so the value can be collected
  on the next boot if the review needs it.

## Chain fingerprint after reset

```
disk-000010.vmdk        372,834,304 B  68de9beb115788f852788182fd0a5199c91902961e10434b2b55b82792ad7c0c
BinRepair-Lab.vmsd            5,451 B  acc4ce50fb3004128e1ac48d0538bb2b181f002678e95a6a53dd6a25fa0178b9
```


## Self-containment addendum (host, 2026-11-07)

The evidence directory as delivered did not include the two files that Run B
actually used; both are added here unchanged:

- `replay.sh` sha256 `09cdd6ca166038a1b5baaa949905dddb23b441a0372ee172106b8913909dff25`
- `std_testcase_io.h` sha256 `6459df50d22697bb61619e2effd688ebb98915db25f7eb1bdbb767f888066fb6`

No evidence file was edited; only `HOST-SHA256SUMS` was recomputed over the
expanded directory.
