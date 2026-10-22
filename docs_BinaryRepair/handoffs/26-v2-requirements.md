# 26 — Supplement received, v2 bundle not ready: four-item re-verification plan

**Recipients:** Member 3/VMer, Member 4, Member 5, Lead
**From:** Lead
**Date:** 2026-10-22
**Status:** v1 bundle is **superseded**; the supplement (`dist/gate3-supplement-2026-10-22/`) is
directionally right but **not a v2 delivery**. Gate 3 stays `CONDITIONALLY FEASIBLE`, the record
goes back to items **1–2 PASS / 3–6 `NOT VERIFIED`** until a v2 bundle with merged fixes and new
hashes is independently re-verified, and the signature rows stay blank. M5 replay is still
pending. No gate status changes.

**Identity ruling (explicit):** **VMer is M3 operating in a separate AI window** — one person,
not two people and not a fourth member. All records must say exactly that.

---

## 1. Four-item status after the supplement

| # | Status | What is still wrong |
|---|---|---|
| G1 | **partial** | supplement `lief-diff.json` (`e1e27295…`) now records `p_filesz`/`p_memsz` `0x8e9→0x1000`, but field parsing is buggy: `PT_LOAD[1]` `flags` = `"R"` and `align` = `"E"` (must be `"R E"` / `0x1000`); `imports` are `"(2)"…`, not function names; `interp` = `null` although an `INTERP` segment exists. These fields cannot be written as "same". |
| G2 | **not merged** | `harness-v2-manifest.txt` (`e53253cf…`) and `harness-manifest.json` (`3bdbc339…`) exist in the supplement but are not in the v2 bundle; `SHA256SUMS`/zip hash not rebuilt; old `0ef65546…` is still cited. |
| G3 | **not done** | `gate3-summary.json` still uses fixture/static/cave/six/isolation/snapshot labels instead of the six gate items. |
| G4 | **not done** | `revert.log` still says "user did it, VMer did not", contradicting the identity ruling above. |

## 2. G1 — exact expected-diff block (LIEF must state this, with real fields)

The corrected LIEF diff must be parsed from actual segments and say:

```text
Unique expected difference:
  PT_LOAD[1] (RX): p_filesz/p_memsz 0x8e9 -> 0x1000
  other 3 PT_LOADs: offset/vaddr/filesz/memsz/flags/align unchanged
  GNU_STACK: RW (NX enabled)
  GNU_RELRO: vaddr 0x403df8, memsz 0x208, flags R
  imports/relocations: 13/13, none added
  canary: absent (unchanged)
```

Field rules: `flags` = `"R E"` for the RX load (not `"R"`/`"E"`), `align` = `"0x1000"`;
`imports` must be real names from `readelf --dyn-syms` (not `"(2)"…`); `interp` must come from
the `INTERP` segment (not `null`). Only then may the record call the readelf/LIEF view
authoritative.

## 3. G2 — v2 bundle composition and hashes

Merge the supplement into a v2 bundle:

- include `harness-v2-manifest.txt` (`e53253cf…`) and `harness-manifest.json` (`3bdbc339…`);
- rebuild a sorted `SHA256SUMS` over the complete v2 set (`LC_ALL=C`, relative paths,
  `SHA256SUMS` self-excluded), recompute the zip SHA-256, and report both;
- mark v1 `0ef65546…f54bf8d5` **superseded** (keep the file, do not cite it as current);
- no need to change the evidence-manifest rules (handoff 21/25).

## 4. G3 — summary mapping to handoff 11 §3 (use exactly this structure)

```json
{
  "gate3": "PASS",
  "items": [
    {"item": 1, "name": "independent candidate copy; original and frozen tests unchanged", "evidence": "..."},
    {"item": 2, "name": "candidate identity + reproducibility + complete edit manifest", "evidence": "..."},
    {"item": 3, "name": "structural audit: runtime cave, page congruence/no overlap, NX/RELRO/canary/W^X, imports/relocs, readelf+LIEF", "evidence": "..."},
    {"item": 4, "name": "six frozen cases on final candidate hash from reverted snapshot", "evidence": "..."},
    {"item": 5, "name": "isolation evidence (uid 1003, caps 0, NNP, no egress, wrapper attestation)", "evidence": "..."},
    {"item": 6, "name": "raw outputs + SHA256SUMS + image chain/harness manifest hashes", "evidence": "..."}
  ]
}
```

Do not use "static tests" as item 2; each item's `evidence` must point at its file(s).

## 5. G4 — `revert.log` template (identity consistent)

```text
Operator: VMer — the same person as M3, operating in a separate AI window.
Action: manual revert in VMware Workstation Snapshot Manager
        (confirmation dialog: current state discarded).
Automation: none. This log records post-action observations only.
Target: gate3-harness-v2 (uid 10, disk-000007.vmdk)
Boot check: hostname binrepair-vm, kernel 6.8.0-147-generic, x86_64
Fingerprint: matches harness-v2-manifest.txt; candidate-before == c4a159…
```

Remove every "user did / VMer did not" phrase; there is one operator.

## 6. Re-verification and status rule

When the v2 bundle arrives, M4 re-verifies in this order:

1. v2 zip SHA-256 and its rebuilt `SHA256SUMS` (every line);
2. every G1 field above against `readelf` (no "same" without fields);
3. G3 mapping and per-item evidence pointers;
4. G4 operator wording;
5. only then re-assess items 3–6 as `PASS`/`FAIL`/`NOT VERIFIED` and re-hash the record.

M5 build/hash replay (candidate `c4a159…aa82`, contract `24bfe568…4e37`, evidence-manifest/bundle
hash) remains required before signature. Until v2 passes, the record keeps 3–6 `NOT VERIFIED`,
reads DRAFT and the signature rows blank.

Canonical record hash after this ruling:
`62ed341b2b4416784f26ce342ffdf53689c37b5ce44a13730be1f256b2114d8b` (supersedes
`01ecabd5…`, `94d7d314…`, `b6fedd2b…`, `bddccbfe…`, `3dcdc862…`).

**Confirmation log.** 2026-10-22 — v1 bundle superseded; supplement accepted as direction only;
G1 partial with three field-level LIEF bugs, G2/G3/G4 not merged; identity fixed as **VMer = M3
in a separate AI window**; items 3–6 back to `NOT VERIFIED`; v2 bundle with new hashes is the
next gate-3 artifact.
