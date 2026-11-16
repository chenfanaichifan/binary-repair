# Phase-8D hidden isolation audit

- status: `ok`
- generated_at: `2026-11-17T00:00:00Z` (fixed)
- private root mode: 0o700
- counts: {"analysis_only_count": 2, "material_entries": 8, "runtime_count": 6, "sample_count": 8}
- operational isolation: true; cryptographic isolation: **false**
- public leak findings: 0
- no hidden paths/ids/content are published by this artifact; the private root path is omitted.

## Checks

- root-exists: passed (exists=True dir=True)
- root-not-symlink: passed (private root must not be a symlink)
- root-owner-only-0700: passed (mode=0o700 owner_ok=True)
- commitment-shape: passed (commitment kind/counts are 8/6/2)
- commitment-public-manifest-sha: passed (commitment binds the current public manifest bytes)
- private-manifest-kind: passed (private hidden manifest kind)
- private-manifest-commitment: passed (private manifest commitment digest matches the public commitment)
- private-manifest-public-sha: passed (private manifest binds the current public manifest)
- private-sample-count: passed (samples=8)
- private-runtime-analysis-counts: passed (runtime=6 analysis_only=2)
- private-material-integrity: passed (0 problem(s))
- commitment-private-material-match: passed (opaque commitment samples match the private manifest)
- private-material-count: passed (material_entries=8)
- aggregate-consistency: passed (sample_count=8 executed=8 verified=0 false_verified=0)
- aggregate-no-per-sample-fields: passed (0 forbidden field(s))
- results-hidden-aggregate-consistent: passed (results.hidden_aggregate matches the aggregate file)
- no-hidden-id-or-material-in-public-files: passed (dynamic tracked-file scan; findings=0)
- no-hidden-binary-material-in-public-files: passed (dynamic tracked-file scan; exact-digest matches=0)
- no-private-root-reference: passed (private root material/ids are not referenced by public findings)

## Limitations

- isolation is operational, not cryptographic: same-UID/root processes can read the private root
- the audit reads private metadata/material only to hash and compare; it never copies hidden bytes, ids, paths or content into public artifacts
- a green isolation audit does not imply hidden benchmark quality, hidden generalisation or capability promotion
- the hidden aggregate is aggregate-only; no per-sample hidden identifiers are permitted
- the tracked-file scan is dynamic; the exact count is not retained because this artifact itself becomes tracked
