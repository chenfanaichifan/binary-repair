# 31 — v2 accepted as the sole evidence bundle; all six items PASS; M4 verifier signed

**Recipients:** Member 5, Member 3/VMer, Lead
**From:** Member 4 (verifier)
**Date:** 2026-10-22
**Status:** v2 is the **only** evidence bundle required (v1 is historical/superseded).
M4 verified the v2 artifact and signed the verifier row. **Gate 3 is not passed yet:** M5's
build/hash replay row and the Lead approval row are still blank.

---

## 1. Artifact used (actual measurements)

| Field | Value |
|---|---|
| path | `delivery/gate3-bundle-v2-2026-10-22.zip` (source: WeChat received files, copied and re-hashed) |
| size | 18,318 B |
| SHA-256 | `6151a80633fdde0d9b1ce87c126b01994a730625557d17297828468799710a65` |
| files | 23 |
| inner `SHA256SUMS` | 22/22 pass |
| `evidence-manifest-sha256` | `4ba6ebad30a4035c6a16c62c1fbab53dda67bce60db2b87510b83aa97f876934` (SHA-256 of the `SHA256SUMS` file bytes; 1,838 B) |

Note: the earlier report quoted 18,285 B / `8256c850…be64f`. The delivered v2 artifact is the
18,318 B / `6151a806…0a65` file; its **content** meets every v2 requirement, so this record uses
the measured hash and never the transcribed one. v1 `0ef65546…` and support `3d49625c…` remain
historical; no v1 delivery is needed.

## 2. Verification result (21/21 checks)

`python scripts/verify_gate3_v2.py delivery/gate3-bundle-v2-2026-10-22.zip`:

- G1: `PT_LOAD[1]` `flags="R E"`, `align="0x1000"`, real import names, `interp` =
  `/lib64/ld-linux-x86-64.so.2`; single expected diff `p_filesz/memsz 0x8e9→0x1000`;
  GNU_STACK RW (NX), RELRO partial, canary absent, imports/relocs 13/13;
- cave probe: `0x401304 → 0x4018e9 → 0x401309`, `0x401000-0x402000` r-xp, memory = file;
- G2: `harness-v2-manifest.txt` `e53253cf…` + `harness-manifest.json` `3bdbc339…` inside;
- G3: six items mapped to handoff 11 §3 with evidence lists;
- G4: `revert.log` single operator **VMer (M3)**, manual VMware Snapshot Manager + post-hoc
  observation;
- six cases `case-01..06` all `ok`; original V0 4/6; candidate before = after = `c4a159…aa82`;
  contract `24bfe568…4e37`.

## 3. Record state

- Six items: **1–6 PASS**.
- Signature table: **M4 verifier signed (2026-10-22)**; M5 replay row blank; Lead approval row
  blank.
- Canonical record hash after this update:
  `62ed341b2b4416784f26ce342ffdf53689c37b5ce44a13730be1f256b2114d8b`.
- Gate 3: all items PASS but **not approved** — M5 replay + Lead approval are the remaining
  gate steps.

## 4. What M5 must replay

1. candidate `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82`;
2. contract `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37`;
3. v2 zip `6151a806…0a65` and its `evidence-manifest-sha256` `4ba6ebad…6934`;
4. report observed values and mark the M5 row; mismatch → the affected evidence returns to
   `NOT VERIFIED` and the record is re-opened.

**Confirmation log.** 2026-10-22 — v2 accepted as the sole evidence bundle; actual artifact
18,318 B / `6151a806…0a65`, manifest `4ba6ebad…6934`; all six items PASS; M4 verifier row
signed; M5 replay and Lead approval pending; v1 not required.
