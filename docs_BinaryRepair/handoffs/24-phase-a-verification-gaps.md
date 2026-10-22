# 24 — M4 verification of the Phase A bundle: identity accepted, four blocking gaps

**Recipients:** Member 3 / VMer (fixes), Member 5, Lead
**From:** Member 4 (verifier)
**Date:** 2026-10-22
**Status:** **bundle identity verified; items 3 and 6 remain `NOT VERIFIED`.** Gate 3 stays
`CONDITIONALLY FEASIBLE`; the record stays DRAFT/unsigned with items 1–2 PASS / 3–6
`NOT VERIFIED`. `gate3-summary.json: "gate3": "PASS"` is a producer statement, not the gate
decision. No signature row is filled.

> **Addendum (handoff 25):** after the ruling, items 3–5 are `PASS` (LIEF view substituted by
> readelf+checksec, six cases and isolation verified) and **only item 6 remains `NOT VERIFIED`**
> (missing `harness-v2-manifest.txt` and harness manifest). Record re-pinned to
> `01ecabd5…83d6`. The detail below is retained as the verification history.

---

## 1. What M4 verified and accepts

| Check | Result |
|---|---|
| bundle file | `gate3-bundle-2026-10-22.zip`, 13,530 B, 21 files |
| bundle SHA-256 | `0ef655464459dd0597f8259b3784ee15389884c9a75b26afa1299af7f54bf8d5` — **matches the reported value** |
| inner `SHA256SUMS` | 20/20 entries verify |
| candidate identity | `c4a159…aa82`, before = after, unchanged |
| six cases | 6/6 (valid rc 0 / sizes 1,2,11,50 B; invalid rc 1 / stdout 0 / 42-byte stderr) — usable |
| original V0 | 4/6 with `invalid-first` rc 0 / stdout 51 B, `invalid-longer` rc 139 — usable |
| isolation fields | uid/gid 1003, `CapEff=0`, `NoNewPrivs=1`, `Seccomp: 0`, egress blocked, evaluator unreadable — usable |
| cave probe | `0x401304 → 0x4018e9 → 0x401309` hit; memory at `0x4018e9` equals file at `0x18e9`; page `0x401000-0x401fff` r-xp |

These are inputs M4 can verify; they do **not** yet make items 3/6 PASS.

## 2. Four blocking gaps (all must be fixed before items 3–6 become PASS)

### G1 — LIEF diff is empty and contradicts readelf

`lief-diff.json` has empty `load_segments`/`gnu_stack` arrays and `nx: null`; `"same": true` is
therefore not a valid comparison. Meanwhile `readelf` shows the authorized header change
`p_filesz`/`p_memsz` `0x8e9 → 0x1000` on `PT_LOAD[3]`, which contradicts the Phase A table's
"`p_filesz`/`p_memsz` 相同".

**Fix:** either repair the LIEF extraction (per-PT_LOAD type/flags/offset/vaddr/filesz/memsz/
align for original **and** candidate; GNU_STACK flags; `nx = not (p_flags & PF_X)`; compare
field-by-field and record the one expected difference), or drop LIEF and use `readelf` +
`checksec` output, but then list the actual header lines and explicitly record the expected
`0x8e9 → 0x1000` extension. No `"same": true` without data.

### G2 — Item 6 evidence set incomplete

The bundle lacks `harness-v2-manifest.txt` (`e53253cf…`) and the harness manifest
(`3bdbc339…`). Item 6 is "raw outputs plus hashes for every item", so the chain/harness evidence
must be inside the delivered set (or its own file with a verifiable hash).

**Fix:** add both files (and the vmsd/chain layer hashes if not already inside), rebuild
`SHA256SUMS` over the complete set, and report the new bundle SHA-256. A rebuilt bundle is a new
artifact: the old `0ef65546…f54bf8d5` hash is then superseded.

### G3 — Six-item summary not mapped to the gate's six items

`gate3-summary.json`'s six entries are not the six required items. The canonical set is
handoff 11 §3 / gate3-record §4:

1. separate candidate copy; original untouched;
2. candidate identity + reproducibility + complete edit manifest;
3. structural audit (runtime cave probe, `p_filesz`/`p_memsz` extension, page congruence/no
   overlap, NX/RELRO/canary/W^X, imports/relocations, independent readelf/LIEF view);
4. six-case run on the final candidate hash from a reverted snapshot;
5. isolation evidence for that run;
6. evidence with hashes (raw outputs + sorted `SHA256SUMS` + manifest hash).

**Fix:** re-map the summary to exactly these six labels and state each item's evidence file(s).

### G4 — Operator identity contradiction in `revert.log`

`revert.log` says "user did it, VMer did not", while the agreed split is that **VMer is a
separate window of the same operator** (not two people). The log must name one operator
consistently, note that the revert was done in VMware Snapshot Manager, and record the
post-revert observations as observations only.

**Fix:** rewrite `revert.log` with one operator identity/role, timestamp, and the observation
set; no fake automated command log.

## 3. Acceptance rule after the fixes

1. VMer/M3 deliver a corrected bundle (new SHA-256) + complete evidence set.
2. M4 re-verifies the new bundle hash, `SHA256SUMS`, and every item file; records the result.
3. M5 performs the build/hash replay (candidate `c4a159…aa82`, contract `24bfe568…4e37`,
   evidence-manifest/bundle hash).
4. Only then M4 changes items 3–6 to `PASS` (or reports `FAIL` with the concrete fact), re-hashes
   the record, notifies M3/M4/M5, and (if M4 chooses) fills the verifier row. Lead approval last.

Until then: **items 3–6 stay `NOT VERIFIED`, record DRAFT, signature blank.**

**Confirmation log.** 2026-10-22 — M4 verifies the Phase A bundle identity (hash `0ef65546…`,
20/20 sums) and accepts the six-case/V0/candidate/isolation fields as usable inputs, but keeps
items 3 and 6 `NOT VERIFIED` because of the empty/contradictory LIEF diff, the missing
chain/harness manifest files, the unmapped six-item summary, and the inconsistent revert
operator. No gate status changed.
