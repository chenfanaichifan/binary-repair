# 30 — v2 bundle located and content-verified; hash/size mismatch vs report

**Recipients:** Member 4, Member 3/VMer, Member 5, Lead
**From:** Lead
**Date:** 2026-10-22
**Status:** the only v2 artifact on the accessible filesystem was found in the WeChat received
files, copied to `delivery/`, and its **content passes** the v2 verification (21/21 checks).
However its **hash/size does not match the reported values**, and the v1 bundle is not present
anywhere accessible. Record items stay **1/2/4/6 PASS, 3/5 `NOT VERIFIED`** until the artifact
identity is confirmed; no verifier signature, no gate change.

---

## 1. File found

| Item | Value |
|---|---|
| source | `D:\电脑管家迁移文件\微信聊天记录搬家\xwechat_files\...\msg\file\2026-10\gate3-bundle-v2-2026-10-22.zip` |
| copied to | `D:\BinaryRepair_Project\delivery\gate3-bundle-v2-2026-10-22.zip` |
| actual size | **18,318 B** |
| actual SHA-256 | **`6151a80633fdde0d9b1ce87c126b01994a730625557d17297828468799710a65`** |
| reported | 18,285 B / `8256c850…be64f` — **does not match** |
| entries | 23; inner `SHA256SUMS` 1,838 B |
| inner sums | **22/22 pass** |
| evidence-manifest | `SHA256SUMS` file SHA-256 = **`4ba6ebad30a4035c6a16c62c1fbab53dda67bce60db2b87510b83aa97f876934`** |

Extracted manifest: `delivery/evidence-manifests/gate3-bundle-v2-SHA256SUMS.txt`
(same hash `4ba6ebad…6934`).

## 2. Content verification (21/21 PASS)

`python scripts/verify_gate3_v2.py delivery/gate3-bundle-v2-2026-10-22.zip`:

- G1: `PT_LOAD[1]` `flags="R E"`, `align="0x1000"`; imports real names; `interp` =
  `/lib64/ld-linux-x86-64.so.2` for both; single expected diff `p_filesz/memsz 0x8e9→0x1000`;
- G2: `harness-v2-manifest.txt` `e53253cf…` and `harness-manifest.json` `3bdbc339…` present;
- G3: `gate3-summary` six items mapped to handoff 11 §3 with evidence lists;
- G4: `revert.log` single operator VMer (M3), manual VMware Snapshot Manager, post-hoc
  observation;
- six case files 6/6 `ok`; candidate/contract/original hashes present.

So the **content** is consistent with a correct v2. The open question is which file is the
official artifact.

## 3. v1 bundle

Not found on any accessible path (`dir /s` for `*gate3-bundle*.zip` finds only the v2 artifact
and the support package). It is not needed for M5 **if v2 is the formal evidence bundle**: v2
contains the complete set (summary, six cases, V0, isolation, revert, LIEF/readelf/checksec,
cave probe, manifests, `SHA256SUMS`), so M5 can replay v2 zip + v2 manifest hash
`4ba6ebad…6934` without v1. If the team insists on v1 as the raw evidence identity, its
`SHA256SUMS` must be delivered separately.

## 4. What is needed to close

1. M4/VMer confirms whether `6151a806…0a65` (18,318 B) is the intended v2 or provides the
   `8256c850…` copy. **No record may cite the wrong hash.**
2. Then M4 re-verifies items 3/5 against the confirmed artifact (content already passes here),
   updates the record, and fills the M4 verifier row.
3. M5 replays: candidate `c4a159…aa82`, contract `24bfe568…4e37`, v2 zip
   `6151a806…0a65` (or the confirmed one), v2 evidence-manifest `4ba6ebad…6934`.
4. Lead approves last.

**Confirmation log.** 2026-10-22 — v2 located in WeChat files, copied to `delivery/`,
content-verified 21/21; actual hash/size differ from the reported values; v1 absent but
superseded by v2 if confirmed; record remains 1/2/4/6 PASS, 3/5 NOT VERIFIED, DRAFT.
