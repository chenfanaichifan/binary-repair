# 25 — Lead ruling on Phase A verification: items 3–5 PASS, item 6 still blocked

**Recipients:** Member 4 (record), Member 3/VMer, Member 5, Lead
**From:** Lead
**Date:** 2026-10-22
**Status:** resolves the four gaps in handoff 24. **No M5 replay yet, no signature:** the record
moves to items **1–5 PASS / 6 NOT VERIFIED**, stays DRAFT/unsigned, and Gate 3 remains
`CONDITIONALLY FEASIBLE` (Gate 4 `NOT RUN`, Gate 6 partial, fixture `NOT FROZEN`).

> **Addendum (handoff 26):** the v1 bundle is superseded and the supplement is not a v2
> delivery. The v1-based `PASS` for items 3–5 is **withdrawn**; the record is back to
> **1–2 PASS / 3–6 `NOT VERIFIED`** until a v2 bundle with fixed LIEF fields, merged
> chain/harness manifests, remapped summary and single-operator `revert.log` is re-verified.
> Canonical record hash from handoff 26: `810bb893…378f`.

Basis: M4's independent bundle check (`SHA-256 0ef65546…f54bf8d5`, 13,530 B, 21 files, inner
`SHA256SUMS` 20/20), the reported six-case/V0/isolation fields, and the readelf/checksec outputs
in the bundle. The bundle itself was not readable from the Lead agent workspace, so this ruling
records **M4's verification as the verifier's result** and does not claim an agent-side re-hash of
the zip.

---

## 1. G3 — six-item summary mapping: not blocking

`gate3-summary.json` grouping labels are a producer convenience. The record's §4 is the
authoritative six-item mapping (handoff 11 §3); the summary does not need to be re-cut and no
item status depends on its labels. Closed as cosmetic.

## 2. G1 — LIEF view: readelf + checksec substitution allowed

`lief-diff.json` is unusable (empty `load_segments`/`gnu_stack`, `nx: null`), but the bundle
contains `readelf-original.txt`/`readelf-candidate.txt` and
`checksec-original.txt`/`checksec-candidate.txt`. For this fixture the independent structural
view is satisfied by **readelf + checksec** when the record states:

- the exact `readelf` program-header change: only `PT_LOAD[3]`, `p_filesz`/`p_memsz`
  `0x8e9 → 0x1000`, offset/vaddr/flags/align unchanged, page-boundary end `0x402000`, no overlap;
- `checksec`: RELRO partial, Canary absent (unchanged), NX enabled, no PIE, no RPATH/RUNPATH,
  symbols retained, imports/relocations identical (13 = 13), entry `0x401170` unchanged;
- the LIEF failure is recorded as a tooling gap, not as evidence.

This substitutes an independent second parser, it does not drop the structural requirement.

## 3. G4 — operator wording: closed

VMer is **M3 operating in a separate AI window** (one person, not two people). The record notes the revert was
done in VMware Snapshot Manager and that the revert log is post-revert observation; no fake
automated command log. Closed.

## 4. G2 — item 6 remains NOT VERIFIED (only blocker)

The bundle lacks `harness-v2-manifest.txt` (`e53253cf1c3408d832dd4c30b6e75afc4e8c2d621a2c0a3c0959131255878e7c`)
and the harness manifest (`3bdbc339…`). Item 6 is "raw outputs plus hashes for every item", so
these files (or a supplementary evidence file with verifiable hashes) must be delivered. A
supplementary file set is acceptable — **no bundle rebuild required** under handoff 21: deliver
the two manifest files plus a sorted `SHA256SUMS` over the supplementary set and its hash. Once
M4 verifies them, item 6 becomes PASS.

## 5. Record effect

`docs/route-a/gate3-record.md` is updated to:

| # | Item | Status |
|---|---|---|
| 1 | separate copy; original untouched | PASS |
| 2 | identity + reproducibility + manifest | PASS |
| 3 | structural audit (readelf + checksec substitution; cave runtime probe hits; header extension recorded) | PASS |
| 4 | six cases on the final candidate hash from the reverted snapshot | PASS |
| 5 | isolation evidence for that run | PASS |
| 6 | evidence with hashes (complete raw set + manifest hash) | **NOT VERIFIED** |

Still required before signature: item 6 files + M5 build/hash replay. The verifier row stays
blank until both exist; Lead approval last.
Canonical record hash after this ruling:
`0b3b51e49f24c5759ff5d37a0569d44149af989dd4e72af6e51b279f0901f2da` (supersedes
`94d7d314…`, `b6fedd2b…`, `bddccbfe…`, `3dcdc862…`).

**Confirmation log.** 2026-10-22 — Lead closes G3/G4, allows the readelf+checksec substitution
for the failed LIEF view (G1), and keeps item 6 `NOT VERIFIED` until the two missing manifest
files/hashes are delivered and verified. Items 3–5 move to PASS on M4's verification; no
signature, no gate pass.
