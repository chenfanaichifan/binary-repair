# 23 — Phase A evidence received: M4 verification checklist and one discrepancy

**Recipients:** Member 4 (verifier), Member 3/VMer, Member 5, Lead
**From:** Lead
**Date:** 2026-10-22
**Status:** **evidence received, not yet accepted by M4.** Gate 3 stays `CONDITIONALLY
FEASIBLE`; the record keeps items 1–2 PASS / **3–6 NOT VERIFIED** and the signature rows blank
until M4 independently verifies the raw evidence and M5 records the build/hash replay. Nothing
here is a gate pass by itself; `gate3-summary.json: "gate3": "PASS"` is a producer statement, not
the gate decision.

---

## 1. What VMer/M3 reported (Phase A)

| Item | Reported value |
|---|---|
| snapshot | `gate3-harness-v2`, uid 10 |
| layer | `disk-000007.vmdk`, 62,193,664 B, `c03843c91a888cc962caf7fba3fe31f48cf447b574f8a3bdb971ea72c562909a` |
| vmsd | 3,125 B, `36879de0e04a145a7399d24abd7250b2d202dd3b147a5d1c4d7b38ba6dccdfcc` |
| chain manifest | `worklogs/2026-10-22/harness-v2-manifest.txt`, 3,929 B, `e53253cf1c3408d832dd4c30b6e75afc4e8c2d621a2c0a3c0959131255878e7c`; previous `ec84ac04…` **void** (orphan layer 000005) |
| guest fingerprint | Ubuntu 24.04.5, kernel 6.8.0-147, x86_64; `jobwrap` `b0371c10…83362b` 0700 root; `cases.conf` `5bad3f20…`; `targets.conf` `ee42166c…`; `gate4.conf` `f240c2f8…`; harness manifest `3bdbc339…`; original `aa428157…8393`; candidate `c4a15921…bcaa82`; contract file `15f6b492…d0ad8df`; canonical `24bfe568…4e37` |
| six cases (patched) | **6/6**; valid rc 0 / stdout 1,2,11,50 B; invalid rc 1 / stdout 0 / stderr 42 B hex `45 52 52 4f 52 3a …` |
| original V0 | **4/6**: `invalid-first` rc 0 stdout 51 B; `invalid-longer` rc 139 |
| candidate hash | before = after = `c4a159…bcaa82` |
| isolation | uid/gid 1003, `CapEff=0`, `NoNewPrivs=1`, `Seccomp: 0`, `lo DOWN`, evaluator unreadable, egress blocked |
| safety diff | RELRO Partial, no Canary, NX enabled, No PIE, no RPATH/RUNPATH, symbols retained, imports/relocations 13 = 13, entry `0x401170` |
| cave probe | hit `0x401304 → 0x4018e9 → 0x401309`; `0x401000-0x402000` r-xp; memory at `0x4018e9` = file at `0x18e9`, first 16 B `4989f031c941803c0800740548ffc1eb` |
| bundle | `D:\BinRepair\dist\gate3-bundle-2026-10-22.zip`, 13,530 B, 21 files, SHA-256 `0ef655464459dd0597f8259b3784ee15389884c9a75b26afa1299af7f54bf8d5` |
| honest note | revert was performed by the operator in VMware Snapshot Manager; VMer recorded post-revert observations only (uptime/hostname/kernel/fingerprint), not a fake automated log |

Cross-checks that already pass from the repository side: candidate `c4a159…aa82`, contract file
`15f6b492…`, canonical contract `24bfe568…`, original `aa428157…`, cave code head matches the
canonical `routea.cave` literal, and the V0 numbers match the corrected record wording (50-byte
invalid exits 0 silently; 100-byte invalid SIGSEGVs). A bundle exists after all; it is accepted as
optional packaging — the no-bundle ruling (handoff 21) still stands, it just is not needed.

## 2. What M4 needs before item statuses change

1. **Raw evidence transport.** The bundle lives on the VMer/M3 machine (`D:\BinRepair\dist\…`),
   which is **not visible** from the M4/Lead workspace (checked: `D:\BinRepair` absent). Copy it
   to an M4-accessible path, e.g. `D:\BinaryRepair_Project\delivery\gate3-bundle-2026-10-22.zip`,
   together with `harness-v2-manifest.txt` and the chain manifest file. Then M4:
   - recompute the bundle SHA-256 (`0ef65546…8d5`) and every line of its `SHA256SUMS`;
   - recompute `gate3-record.md` inputs independently (not from the summary json);
   - keep its own copies and do not edit VMer's files.
2. **M5 build/hash replay** (handoff 19/21): reproduce `c4a159…aa82`, verify contract
   `24bfe568…4e37`, recompute the evidence-manifest/bundle hash, and report. Missing/mismatched
   replay ⇒ record stays `NOT VERIFIED`, signature blank.
3. Only after 1–2 does M4 change items 3–6 to `PASS`/`FAIL`, re-hash the record, notify M3/M4/M5,
   and (if M4 chooses) fill the verifier row. Lead approval remains last.

## 3. One discrepancy to correct before signing

The safety-diff table says **`p_filesz`/`p_memsz` "相同"** (original = candidate). That cannot be
right for this authorized repair: only `PT_LOAD[3]` changed, precisely `p_filesz`/`p_memsz`
`0x8e9 → 0x1000` (this is the tail extension that makes the cave file-backed). The likely intent
is "the two program-header values are unchanged *after* the authorized extension is recorded" or
"all other headers unchanged". M4 cannot sign while the evidence text contradicts the manifest
and readelf audit. Requested: quote the actual `readelf` lines and the LIEF `filesz/memsz` values
for both files (`0x8e9` original vs `0x1000` candidate) and correct the table. The rest of the
safety attributes (RELRO/Canary/NX/PIE/imports/relocs/entry) are consistent and expected.

Other small clarifications:

- confirm the mapping wording: page `0x401000-0x401fff` is `r-xp` (page end `0x402000`), rather
  than claiming a mapped range ending at `0x402000`;
- include the chain-manifest file itself (not only its hash) in the transfer;
- `revert.log` should name the operator/window and note "VMware UI revert, post-revert
  observation only" — that limitation is acceptable, hiding it would not be.

## 4. Status after this report

- Gate 3: `CONDITIONALLY FEASIBLE`; record DRAFT/unsigned, items 1–2 PASS, 3–6 NOT VERIFIED.
- Gate 4: NOT RUN (Phase B; v6 kit awaited; kit v5 withdrawn).
- Gate 6: partial (V4 pending); fix the `cffa8b95…` doc citation separately.
- Fixture: NOT FROZEN.

**Confirmation log.** 2026-10-22 — Lead records Phase A evidence receipt, keeps items 3–6
`NOT VERIFIED` pending M4 independent verification + M5 replay, requests evidence transfer and a
correction of the `p_filesz/p_memsz` claim, and notes the honest UI-revert limitation. No gate
status changed.
