# 28 — v2 bundle reported; M4 verification blocked on bundle access

**Recipients:** Member 4, Member 3/VMer, Member 5, Lead
**From:** Lead
**Date:** 2026-10-22
**Status:** v2 is reported by VMer, but the zip is **not readable** from the M4/Lead workspace
(`D:\BinRepair\dist\gate3-bundle-v2-2026-10-22.zip` does not exist on this host, and no copy is
in `delivery/` or the WeChat temp area). No item status changes, no verifier signature: the
record stays items **1/2/4/6 PASS, 3/5 `NOT VERIFIED`**, DRAFT/unsigned, and Gate 3 remains
`CONDITIONALLY FEASIBLE`.

---

## 1. Reported v2 values (to be verified, not accepted yet)

| Field | Reported |
|---|---|
| path | `D:\BinRepair\dist\gate3-bundle-v2-2026-10-22.zip` |
| size | 18,285 B, 23 files |
| SHA-256 | `8256c850…be64f` (truncated; full 64-hex value still to be confirmed) |
| inner `SHA256SUMS` | 22/22 |
| G1 | LIEF `PT_LOAD[1]` `flags="R E"`, `align="0x1000"`, real import names, `interp=/lib64/ld-linux-x86-64.so.2`; single expected diff `p_filesz`/`p_memsz 0x8e9→0x1000` |
| G2 | `harness-v2-manifest.txt` (`e53253cf…`) + `harness-manifest.json` (`3bdbc339…`) inside; old `0ef65546…` superseded |
| G3 | `gate3-summary` remapped to handoff 11 §3 |
| G4 | `revert.log` operator = VMer (M3, same person, separate AI window), manual VMware Snapshot Manager + post-action observations |

## 2. What is needed to verify

Copy the v2 zip to an M4-accessible path, e.g.:

```text
D:\BinaryRepair_Project\delivery\gate3-bundle-v2-2026-10-22.zip
```

or provide the WeChat temp `@` path (the support package was readable there). Then run:

```bash
python scripts/verify_gate3_v2.py delivery/gate3-bundle-v2-2026-10-22.zip
```

The script is host-safe (zip/JSON/text only, no ELF parsing/execution) and checks: bundle size
and SHA-256, every `SHA256SUMS` line, required files, G1 LIEF fields, G3 six-item mapping, G4
single-operator log, candidate/contract/original hashes, and the six case files. It prints a
PASS/FAIL table; exit 0 only when every check passes.

When the check passes, M4 fills the verifier row and re-hashes the record; M5 then replays the
formal v2 bundle (`SHA256SUMS`/zip hash) and Lead approves. Until then, no signature.

**Confirmation log.** 2026-10-22 — v2 reported; verification blocked because the bundle is not
readable from the M4 workspace; verification script added; record unchanged (1/2/4/6 PASS, 3/5
NOT VERIFIED, DRAFT).
