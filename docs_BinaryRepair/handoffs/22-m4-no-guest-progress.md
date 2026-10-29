# 22 — M4 no-guest progress: citation fixes, evidence manifest, Gate 4/5/6 checks

**Recipients:** Member 5, Member 3/VMer, Lead
**From:** Member 4
**Date:** 2026-10-22
**Status:** bookkeeping/static work only. **No gate status changes:** Gate 3 `CONDITIONALLY
FEASIBLE` (items 1–2 PASS, 3–6 `NOT VERIFIED`, record DRAFT/unsigned); Gate 4 `NOT RUN` (formal);
Gate 5 Route A half static only; Gate 6 partial; fixture `NOT FROZEN`.

This records what M4 could finish **without the VMer guest run**, so the waiting time does not
leave stale or false evidence behind.

---

## 1. Gate-3 record revision — false citation fixed

A read-only audit found that `docs/route-a/gate3-record.md` §5 and `docs/route-a/SHA256SUMS`
cited `audit.json` = `1b1c7321…` and mislabeled `edit-manifest.json` as `1b1c7321…`; those are
**not repository objects**. Recomputed from `origin/main` `4107836`:

| File | Correct SHA-256 | Size |
|---|---|---|
| `routea/out/edit-manifest.json` (schema 2) | `710657bf9d21068444c4a2d85e05c1e57557625604c589d8f8268edfa1a10fc0` | 2,658 B |
| `routea/out/audit.json` | `e915cb8bb211ed4305400ec02d0cb80847fe98bb1d27b264ac1032ade5165821` | 305 B |
| `routea/out/readelf-audit.txt` | `086ce7c87f535fbc5ed583da529a05ddfae0c75846c6a543bd4aaab1d02825c5` | 7,829 B |
| `fixtures/.../contract.json` (file hash) | `15f6b492608e8c137f2612058bf43b90173284aec86d8c51b25d09903d0ad8df` | 1,998 B |

Also re-measured from main blobs (static identity only): `valid.json` `17b2ee39…e76`,
`invalid.json` `d493f370…90d`, manifest-set `a564f039…3a78` — previously `NOT VERIFIED` in the
record because the files were absent from the docs workspace; they are now verified against the
main/archive blobs (guest re-measure still required for item 1/3).

**New canonical record hash:** `94d7d3148a1f8693fd26116e4f28f4d220f8c184b2cb39122367b7639a4cd1f0`
(`docs/route-a/gate3-record.md` on `member-4-verification`). Previous `bddccbfe…` and
`b6fedd2b…` are **void**; the six-item statuses and signing order are unchanged.

## 2. Evidence manifest rebuilt (handoff 21)

`docs/route-a/SHA256SUMS` was rebuilt: no UTF-8 BOM, LF endings, `LC_ALL=C`-sorted, paths
relative to the main/archive root, one line per file. It now covers the canonical inputs and the
committed Route A evidence (11 entries): original, valid/invalid JSON, `contract.json`,
candidate, edit-manifest, audit, readelf audit, manifest-repaired, runtime.log, and the record.
It verifies: the record line matches the file, and all other hashes were computed from the
`origin/main` blobs. Note the paths resolve from the main tree (`1826505` archive or newer main),
not from this docs branch — the final VMer/M3 evidence manifest (handoff 21) is separate and
supersedes this file for item 6.

## 3. Gate 4 static verification (M4 support, not a formal run)

The kit files on `origin/main` match `docs/route-b/09-gate4-evidence.md` pins:
`gate4_runner.sh` `515c4d60`, `probe_patcherex2.py` `35751f6e`, `verify.py` `851d3ff4`,
`run_manifest_compare.py` `c0bc45e3`, kit v6 `499f510c`. But `environment.txt` records no
Ghidra/clang/ld.lld and two JDKs (21 + 25), and no `gate4-status.json` is committed. Gate 4
therefore stays **NOT RUN (formal)**; the CI 6/6 remains supplementary only.

## 4. Gate 6 stale citation (for M5/M1)

The local gate-6 evidence `gate6-crash-summary.md` hashes `a398821e…` and its `SHA256SUMS`
verifies 3/3 (matches handoff 06). `origin/main:docs/route-b/06-gate6-evidence.md` cites
`cffa8b95…`, which is **not a repository object**. The doc should cite `a398821e…`; Gate 6 stays
**partial** (concrete crash evidence accepted; V4 symbolic pending).

## 5. Original V0 finding — accurate wording (no oracle change)

`origin/main:routeb/out/gate4/manifest-compare.json` shows the original binary:

| Case | Original rc | Original stdout/stderr |
|---|---|---|
| `invalid-first` (50 × A) | **0** | 50 × `A` + LF, stderr empty (silent overflow, **no crash**) |
| `invalid-longer` (100 × A) | **-11** (SIGSEGV) | empty |

So "the original SIGSEGVs on invalid input" is only true for the longer case. V0 still scores
**4/6** (four valid cases pass; both invalid cases fail the repaired-path oracle), but the
record/handoff wording must say: **first invalid = silent overflow, exit 0, no crash; longer
invalid = SIGSEGV**. Do not change the oracle; the corrected fact goes into the V0 evidence.

## 6. Gate 5 Route A half — static placement proof (runtime pending)

Static facts already evidenced by main's schema-2 manifest + readelf audit (no new host ELF
parsing): only `PT_LOAD[3]` changed (`p_filesz`/`p_memsz` `0x8e9`→`0x1000`, same offset/vaddr/
flags/align, page-congruent, next LOAD `0x402000` adjacent, no overlap); the cave
`0x4018e9-0x401fff` lies beyond the original `p_filesz`, inside one page; no section/symbol/
relocation covers it; the 42-byte message is at `0x401930`; no new segment/import/GOT/PLT edit;
no W+X; `GNU_STACK` non-exec and `GNU_RELRO` unchanged. Remaining for Gate 5 Route A: the
**runtime** mapping/bytes/execution probe and the isolation-attested run (VMer), plus the LIEF
independent view (tool absent on the M4 host).

## 7. Remaining blockers (unchanged)

1. VMer/M3: `gate3-harness-v2` snapshot evidence, six cases, original V0, runtime probe,
   isolation attestation, sorted evidence manifest.
2. M5: build/hash replay (`c4a159…`, `24bfe568…`, evidence-manifest hash) and re-review of the
   M4 audit patch `2ac0f66` / `b68aabcd…cab8` (patch base `ad1a1f8` is now behind main; rebase
   only if M5 asks).
3. Lead: approval after 1–2; record signature rows stay blank.

**Confirmation log.** 2026-10-22 — M4 fixes false evidence citations, re-measures valid/invalid/
set from main blobs, rebuilds the evidence manifest without BOM, records Gate 4 static pins and
the Gate 6 stale hash, corrects the V0 crash wording (no oracle change), and writes the static
Gate 5 Route A placement proof. No gate status changed.
