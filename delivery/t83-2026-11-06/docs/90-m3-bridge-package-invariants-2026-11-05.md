# 90 — M3 bridge package invariants (2026-11-05)

**Owner:** M3 (guest execution / evidence producer)
**Scope:** every bundle ZIP handed from M3 to M5, present and future.
**Status:** rules only. This document is not an implementation, not a second
ingest, and not a verdict. No M5 file is modified here.

## 0. Boundary

- M3 does **not** write `tools/`, `docs/interfaces/`, `app/domain/` or any M5
  interface contract. Those belong to M5; a second implementation would be
  created otherwise. M3 only fetches and consumes them.
- The corrected package is **ingested by M5**, not by M3. M3 has no M5 app
  environment (`app/db/`, `app/services/jobs.py`, `tools/host_importer.py`),
  so ingest itself cannot be run in this checkout. M3 verifies offline.
- Honest boundary: `missing is not passing`, `not_run is not passed`.

## 1. Package shape

- The deliverable is a **real ZIP** (`PK\x03\x04`), produced with Python
  `zipfile` (ZIP_DEFLATED). `tar -a -cf out.zip` produces a tar stream with a
  `.zip` suffix and must never be used again.
- Flat layout: every file sits at the ZIP root, no subdirectories, no `./`
  prefix entries.
- Every reference inside `bundle.json` (`gates[].artifacts`, `analysis[].path`,
  `comparison`) and inside `result-bundle.json` (`gates[].evidence[].relative_path`)
  is a **bare filename**, never a path. M5's `_register_file` uses
  `Path(relative).name`, so flat unique names avoid collisions.

## 2. Four mandatory files (keep this structure)

| File | Role |
|---|---|
| `bundle.json` | execution-bridge v1 manifest: route, candidate_sha256, gates V0..V5, analysis, comparison |
| `handoff.json` | INTERFACE-v1 envelope: from=M3, to=M5, route, created_at, files |
| `SHA256SUMS` | integrity record, hash-binds every file that is read |
| `result-bundle.json` | per-gate status + evidence; **required to obtain `passed`** |

- `result-bundle.json` MUST appear in `handoff.json.files` AND in `SHA256SUMS`.
  M5 rejects an unbound result bundle (`test_legacy_result_bundle_must_be_in_sums`).
- A legacy package without `result-bundle.json` is structurally accepted but
  every gate is `not_run`.

## 3. result-bundle.json — how `passed` is earned

- All six gates V0..V5 must carry an explicit `status` and an `evidence` array.
  Accepted status words are the M5 `LEGACY_STATUS` keys
  (`pass|passed|fail|failed|not_run|unknown|timed_out`).
- Each `passed` gate MUST name at least one per-gate evidence **file object**
  (`relative_path` + `sha256`), and that path must be hash-bound in `SHA256SUMS`
  with a matching hash. A `passed` gate with no evidence is rejected by M5.
- `V4` stays `not_run`, `evidence: []`, reason explicitly `model-level`
  (Lead ruling 65). Never describe model-level as binary-level to gain a pass.
- Narrative numbers such as `V2 16/16` or `V3 6/6` belong in `details` / `notes`
  **as explanation only**. They are not per-gate hash evidence and must never be
  put into an `evidence` entry or used to promote a gate to `passed`.
- `bundle.json` and `result-bundle.json` must report the **same** V0..V5 states.
  A dual interpretation of one package is not allowed.

## 4. V0 and candidate binding

- V0 may list several artifact names. M5 (`3b4e492`) selects the artifact whose
  bytes hash to `candidate_sha256`, not the first list entry.
- M3 must guarantee the binding is **unique**: exactly one file in the package
  hashes to `candidate_sha256`, it is `candidate.elf`, and it is listed in V0
  evidence. No decoy with the same hash.
- `identity.candidate_sha256` in `result-bundle.json`, `candidate_sha256` in
  `bundle.json` / `behavior-comparison.json`, and the actual rehash of
  `candidate.elf` must all agree.

## 5. SHA256SUMS covers every file that is read

- Cover **all** files in the package except `SHA256SUMS` itself: the four
  mandatory files, all gate artifacts, the three analysis JSONs,
  `behavior-comparison.json`, and `README.md`.
- Format is exactly `<64 hex>  <bare filename>` — **two spaces, no asterisk**,
  LC_ALL=C sorted, no duplicates, no `./`, no backslashes.
  Generate with Python `hashlib`. Do **not** use Windows Git Bash `sha256sum`,
  which emits `<hash> *<path>` (binary marker) and makes M5's
  `check_handoff.py` report `sums_entries: 0`.
- `handoff.json.files` entries must all appear in `SHA256SUMS`.

## 6. Gate / evidence honesty (T7.3, T8.3)

- `behavior-comparison.json` uses the **same six frozen cases** (4 valid +
  2 invalid) and the **same original candidate** as the V3 evidence
  (`manifest-repaired.json`). Behaviour is not re-interpreted on the host.
- Where the original binary has no clean recorded return code on an invalid
  input, mark it `vulnerable` (CWE121). Never invent a return code.
- **T8.3 remains blocked**: no second public sample of a different defect
  class, no guest build path. Neither exists; neither is fabricated.

## 7. Offline verification to re-run on every package

1. ZIP magic is `PK`, and `zipfile` can open it.
2. Extract to a temp dir, run M5's `scripts/check_handoff.py` with
   `--expect-from M3 --expect-to M5` -> `PASS`, `errors: []`.
3. Rehash every file against `SHA256SUMS`; assert full coverage.
4. Assert `result-bundle.json` is in `handoff.files` + `SHA256SUMS`, and that
   every V0..V5 status/evidence is explicit, with `passed` gates bound.
5. Assert V0 candidate uniqueness, V4 `not_run`, and that the two manifests
   agree on all six gates.
6. Assert all references are bare filenames and all referenced files exist.

## 8. Current baselines (verified 2026-11-05, offline only)

### 8.1 Single-artifact V0 — kept for history, unchanged

```text
docs/handoffs/evidence/P3B-execution-bridge/          (source dir)
dist/P3B-execution-bridge-2026-11-05.zip              real ZIP (PK), 14 entries
internal SHA256SUMS                                   13/13, two-space format
check_handoff.py                                      PASS (errors=0, files=12)
package sha256                                        e1cbaeb6…9efbf
V0                                                     passed, 1 artifact (candidate.elf)
```

### 8.2 Multi-artifact V0 — current delivery

```text
docs/handoffs/evidence/P3B-execution-bridge-v0multi/  (source dir)
dist/P3B-execution-bridge-2026-11-05-v0multi.zip      real ZIP (PK), 15 entries
internal SHA256SUMS                                   14/14, two-space format
check_handoff.py                                      PASS (errors=0, files=13)
package sha256                                        5e653586…892c8
V0 artifacts                                          ["original.elf", "candidate.elf"]
                                                      original first on purpose
hash == candidate_sha256                              exactly 1 file: candidate.elf
```

Why `original.elf` is listed first: it makes list-order binding visibly wrong.
A first-entry binding yields `original.elf` (sha256 `aa428157…8393`), which is
not the candidate. Only a hash binding yields `candidate.elf`
(`208574ab…6717`). Ingesting 8.2 therefore also checks that M5's `3b4e492` fix
is live; if M5 reports the candidate unbound, that fix is not in the ingest path.

Both baselines share: V0/V1/V2/V3/V5 passed with hash-bound artifacts,
V4 `not_run` (model-level), T8.3 blocked, `result-bundle.json` hash-bound.

M5 ingest has **not** been run in this checkout; that step belongs to M5.
M5's own record (`91-m5-completion`) notes the branch-available package is a
different fixed ZIP; M3 does not claim either of these ZIPs is branch-verifiable
by M4.
