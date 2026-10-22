# Gate 3 pass matrix — handoff 11 §3

**Rule:** 6/6 + segment mapping + hash audit is necessary but **not sufficient**.
Gate 3 passes only when all six items below exist. This matrix replaces the
shorter "three technical items" wording used earlier; `6/6` alone is not a pass.

| # | Handoff 11 §3 item | Current evidence | Status |
|---|---|---|---|
| 1 | Separate candidate copy; original and frozen tests unchanged | `original.elf` `aa428157…8393`; `valid.json` `17b2ee39…e76`; `invalid.json` `d493f370…90d`; candidate is separate at `routea/out/cave-probe.elf` | **PASS** |
| 2 | Candidate identity + reproducibility; edit manifest has changed/added intervals, header fields, detour, displaced bytes | `c4a159…aa82`; `regen_c4a159.py` reproduces it; `edit-manifest.json` has detour, mapping, new/old size. **Displaced call bytes are not yet recorded as `original_hex`.** | **PARTIAL** |
| 3 | Structural audit: cave mapped R-X by runtime; p_filesz/p_memsz page-congruent, no overlap, `< file size`, no other header changed; NX/RELRO/canary/W^X preserved; independent readelf + LIEF; no unresolved relocation/import/GOT/PLT edit | Runtime probe and `readelf` pass; `audit.json` checks `rx_extended`, `no_new_segments`, `relocations_unchanged`, `no_wx`. **No LIEF view, no explicit RELRO/NX/canary/dynamic-import diff.** | **PARTIAL** |
| 4 | Six-case run on final candidate hash, from a reverted snapshot, byte-exact outputs | GitHub Actions run `39756691896` is 6/6 on `c4a159…`, but **not from the formal reverted snapshot**. | **PARTIAL** |
| 5 | Isolation evidence for that run (handoff 11 §2: uid 1003, no egress, caps 0, no_new_privs, fixed argv, raw output) | Not present for the 6/6 run. GitHub Actions is not the formal isolation environment. | **MISSING** |
| 6 | Evidence bundle: raw outputs plus hashes for every item | GitHub artifacts + `routea/out` exist, but no formal VM raw bundle tied to the isolation manifest `142849c7…`. | **PARTIAL** |

## Conclusion

**Gate 3 = CONDITIONALLY FEASIBLE.** Items 1 is complete; 2–4 and 6 are partial;
5 is missing. The 6/6 result is feasibility evidence, not a Gate 3 pass.

## What closes the matrix

- Item 2: add `original_hex` / displaced bytes and exact header fields to the
  edit manifest (or state the recorded deviation).
- Item 3: run LIEF 1.0.0 view on `c4a159…` and diff NX/RELRO/canary/imports;
  keep independent `readelf`.
- Item 4: M3 reruns the six frozen cases on `c4a159…` from the reverted snapshot,
  hash recorded before execution.
- Item 5: attach handoff 11 §2 raw isolation evidence for that run.
- Item 6: bundle raw outputs + hashes + image chain manifest `142849c7…`.
