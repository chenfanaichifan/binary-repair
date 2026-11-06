# M3 → M5: execution-bridge v1 bundle (Route B)

**From:** M3 (guest executor / evidence producer)
**To:** M5 (contract / adapter / replay)
**Date:** 2026-11-05
**Status:** bundle delivered for M5 ingest; not a new gate result.

## What this is

A Route B execution bundle assembled to the **execution-bridge v1** contract
(`docs/interfaces/execution-bridge-v1.md`, `tools/route_bundle_ingest.py` on
M5's `member-5/complete-m5` branch, head `e30eefd`). It is produced from the
already-frozen P3B v6 evidence (`docs/handoffs/evidence/P3B/`); no value here is
new, and no gate status is newly claimed.

## Bundle contents

All files are flat in the bundle root; every reference in `bundle.json` is a
bare file name (no directory prefix), so `Path(name).name` in the ingest
adapter cannot collide or drop a path.

```text
bundle.json                 manifest: route, candidate_sha256, gates V0..V5, analysis, comparison
candidate.elf               Route B repaired candidate (208574ab…6717)
audit.json                  static audit (pass, 7 checks)
v2-routeb-fixed.json        V2 interface check (16/16 passed)
manifest-repaired.json      V3 repaired behaviour (6/6, repaired_pass=true)
reproducibility.json        V5 byte-identical ×2
expected-effects.json       AnalysisArtifacts schema (analysis_expected_effects)
assumptions.json            AnalysisArtifacts schema (analysis_assumptions)
uncertainties.json          AnalysisArtifacts schema (analysis_uncertainties)
behavior-comparison.json    original-vs-candidate on the same six cases
SHA256SUMS                  integrity record (not read by ingest; for M4 re-hash)
```

## Gate status (all values carry a real artifact unless not_run)

| Gate | Status | Artifact | Basis |
|---|---|---|---|
| V0 | passed | candidate.elf | candidate bytes present, hash == bundle candidate_sha256 |
| V1 | passed | audit.json | static audit pass=true (7/7 checks) |
| V2 | passed | v2-routeb-fixed.json | 16/16 interface checks passed |
| V3 | passed | manifest-repaired.json | 6/6 repaired_pass=true |
| V4 | not_run | — | model-level only (Lead 65); not binary-level |
| V5 | passed | reproducibility.json | byte-identical ×2 |

V4 is deliberately `not_run`: the bounded symbolic verdict is model-level
(Lead ruling 65), not a binary-level proof. It is never converted to `passed`.

## Analysis blocks

The three analysis files match `app/domain/analysis.py::AnalysisArtifacts`
(`candidate_sha256` + `expected_effects` [1..32] + `assumptions`/`uncertainties`
[≤32], no extra fields). They are candidate-derived explanations, display-only;
none of them is mapped to a `passed` obligation.

## behavior-comparison.json

Original-vs-candidate on the **same six frozen cases** (T7.3): 4 valid inputs
return 0 with matching stdout; 2 invalid inputs (50/100 bytes) are a CWE121
stack-buffer-overflow in the original and a clean exit 1 with an exact stderr
message in the candidate. The original binary's clean return code on the
invalid inputs was **not separately recorded**; the comparison marks the
original as `vulnerable` rather than inventing a return code.

## Blockers (unchanged, not fabricated)

- **T8.3** — a second public defect sample of a *different* defect class and
  its guest build path still do not exist. M3/M5 common blocker; no sample is
  invented here.
- **M5 ingest** must re-hash every artifact and reject symlink/traversal/size
  violations (the contract already does). M3 does not run the ingest tool on
  this checkout because `app/` and `tools/` from M5's branch are not present in
  `member-3-route-a`.

## Verification done by M3 (offline)

- `bundle.json` schema_version=1, route=route_b, candidate_sha256 is 64 hex.
- `candidate.elf` SHA-256 == bundle candidate_sha256 (recomputed).
- gates are exactly V0..V5; every `passed` names an existing artifact.
- analysis three blocks validated against the AnalysisArtifacts field set
  (extra-forbid, length limits) without importing pydantic.
- `SHA256SUMS` regenerated in standard sorted format; `sha256sum -c` → 10/10 OK.
