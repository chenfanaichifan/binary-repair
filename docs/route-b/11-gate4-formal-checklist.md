# Gate 4 formal acceptance checklist (member3 VM)

**Current status: NOT RUN.** The supplementary GitHub Actions run (09) is not a
substitute for the required member3-provided disposable VM.

## Required environment

| Field | Requirement |
|---|---|
| Image | Ubuntu 24.04 x86-64 cloud image / snapshot ID recorded |
| Disposable | fresh snapshot; reset after the run; no host mounts |
| Network | disabled before candidate execution (`ip link`, netns, or hypervisor NIC off) |
| User | unprivileged execution user; passwordless sudo only for setup, ideally not at all |
| JDK | 21 (record exact build) |
| Ghidra | 12.2 PUBLIC (or recorded 11.x); record build date |
| Patcherex2 | record pip version (0.2.14 in the supplementary run) |
| Compiler | gcc 13 / clang-15 + ld.lld-15 for Patcherex2 |
| Candidate | `original.elf`, SHA-256 `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |

## What member3 must provide

1. VM access (SSH or console) with the image/snapshot ID.
2. Confirmation that the snapshot is disposable and will be reset.
3. A way to disable network before execution (or a network-off snapshot).
4. Permission to install JDK21/Ghidra/Patcherex2 inside the VM, or these preinstalled
   with versions recorded.

Do **not** use the shared guest with 0 snapshots, passwordless sudo and NAT.

## Run commands

```bash
sha256sum original.elf                 # must be aa428157...8393
java -version; ghidra --version; python3 -m pip show patcherex2
./routeb/ghidra/export.sh original.elf CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink routeb/out/gate4
python3 routeb/probe_patcherex2.py --mode roundtrip --binary original.elf \
  --func CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink \
  --c-source routeb/experiment/samples/juliet_badSink.normalized.c \
  --out routeb/out/gate4/roundtrip.elf --skip-verify
# disable network here, then:
python3 routeb/run_manifest_compare.py --original original.elf \
  --patched routeb/out/gate4/roundtrip.elf \
  --tests fixtures/public/CWE121_src_char_declare_cpy_51b/tests \
  --out routeb/out/gate4/manifest-compare.json
```

## Acceptance

- `manifest-compare.json`: `gate4_pass=true`, 6/6 cases same;
- record image/snapshot ID, JDK/Ghidra/Patcherex2 versions, network-off proof;
- result is **pass** or **fail**; if the VM is not provided, the only honest
  status is **NOT RUN**.

## Current blocker

No member3 VM/snapshot/offline access has been provided. The supplementary GitHub
Actions run is recorded in `09-gate4-evidence.md`; it is not counted as formal
Gate 4.
