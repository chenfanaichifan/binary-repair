# 39 — M5 to M3: P3A package rejected by checker

**Package:** `P3A-routea-real-2026-10-29.zip`
**SHA-256:** `2434d7faeb2683d7db84b78862fec2470272ce9908de701f44e25301ac16b575`
**Size:** 33,226 B
**Verdict:** **FAIL — NOT ACCEPTED.** No adapter, worker, or p2 run.

## Checker

```text
python scripts/check_handoff.py . --expect-from M3 --expect-to M5
{
  "errors": [
    "missing handoff.json",
    "expected from=M3, got None",
    "expected to=M5, got None"
  ],
  "status": "FAIL"
}
```

The package has `handoff.md`, not `handoff.json`. That is a hard interface-v1
failure; M5 will not infer machine-readable metadata from prose.

## SHA256SUMS

`SHA256SUMS` is standard and 23/23 lines verify; its own SHA-256 is
`ee430a15045c9d17badb2364ee41f488955a5ec9ccc77dae81b3a3bf5abcb9f0`.
That only proves the listed bytes; it does not make the evidence set complete.

## Result-bundle evidence paths do not resolve

With `result-bundle.json` as input and the package root as evidence root, the
adapter fails immediately:

```text
ValueError: V0 evidence missing: .../P3A/original.elf
```

Declared V0 paths (all absent at package root):

```text
original.elf
contract.json
tests/valid.json
tests/invalid.json
route_a/candidate.elf
route_a/status.json
```

Declared V1 paths:

```text
route_a/edit-manifest.json
route_a/audit.json
route_a/readelf-audit.txt
evidence/v1/lief.json
```

The package actually stores candidate/original/edit-manifest/audit/readelf under
`raw/`, and `raw/lief-diff.json` is not `evidence/v1/lief.json`. No
`contract.json`, `tests/valid.json`, `tests/invalid.json`, `route_a/status.json`
or `evidence/v1/lief.json` exists anywhere in the package.

Declared V3 evidence:

```text
evidence/v3/formal-run.json
```

is absent. The package has `raw/case-01..06.json` and `raw/v0-original-all.json`,
but not the declared formal-run artifact.

## Attempt JSON is not worker-ready

`attempt.json` uses path strings in `evidence`, e.g.:

```json
"V0": "original:original.elf; contract:contract.json; ..."
```

Worker contract requires `evidence: {"V0": "<artifact-id>", ...}`. Even after
path repair, M5 must register artifacts and rewrite the attempt; this file cannot
be posted as-is.

## Required corrections (new package/hash)

1. Add machine-readable `handoff.json` with `id`, `from=M3`, `to=M5`,
   `route=route_a`, `created_at`, and a complete `files` list.
2. Make `result-bundle.json` evidence `relative_path` values match the package
   layout, or move the raw files to the declared paths.
3. Include the missing V0/V1/V3 evidence bytes: contract, both test manifests,
   status, LIEF view, and formal-run artifact (or correct the declarations).
4. Regenerate `SHA256SUMS` over the corrected set; do not reuse
   `2434d7fa…`.
5. Do not hand-edit `attempt.json` into pass; M5 will regenerate it via
   `tools/routea_bundle_to_attempt.py` after checker PASS.

Until then P3A is **NOT ACCEPTED**; no Gate 4 or success claim.
