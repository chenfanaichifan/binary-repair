# M1 integration — M5 intake, V3 kinds, guarded writes

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Branch: `m1/t6-host-backend`, plus `canonical/m1-m5-integration`
- Merged: `member-5/complete-m5` @ `ac84862` (no conflicts)

## 1. M5 integrated

Merge `0f97d9a` brings the execution-bridge protocol, evidence envelope, analysis
schema, assistant seam, `004_assistant.sql`, and `tools/route_bundle_ingest.py`
onto the M1 branch. Worker and attempt-writer hunks were disjoint, so no manual
resolution was needed.

Numbering note: M5 ships `docs/handoffs/91-m5-completion-2026-11-05.md` while M1
already had `91-m1-t6.0-baseline-2026-11-05.md`. Different files, same number.
Anyone reading by number should use the full filename.

## 2. Real defect found and fixed in ingest

Feeding the shipped P3A archive through the adapter failed:

```
worker: attempt ... failed: candidate_sha256 c4a159... is not bound to any
verified evidence artifact
```

Cause: `tools/route_bundle_ingest.py` kept only `ids[0]` per gate. Route A's V0
identity carries six files (original, contract, valid/invalid manifests, candidate,
status); the first is `original.elf`, so the candidate artifact was registered but
never linked, and `verify_candidate_binding` — correctly — refused it.

Fix: the gate evidence now prefers the artifact whose bytes hash to the declared
`candidate_sha256`. The binding check was **not** relaxed.

## 3. End-to-end intake of M3's corrected packages

Both shipped archives, ingested and processed by the real worker:

| Package | Route | identity | structure | behaviour | interface | symbolic | reproducibility | Attempt verdict |
|---|---|---|---|---|---|---|---|---|
| `P3A-routea-2026-10-31-v7.zip` | route_a | passed | passed | passed | not_run | not_run | not_run | inconclusive / required_check_not_run |
| `P3B-package-v6-2026-10-31.zip` | route_b | not_run | not_run | not_run | not_run | not_run | not_run | inconclusive / required_check_not_run |

Run verdict: `inconclusive` / `required_check_not_run`, `failing_obligation:
interface` (V2 precedes V4 in the gate order).

P3B is an INTERFACE-v1 handoff without `result-bundle.json`, so all six gates are
`not_run` by design. That is the correct reading of the package, not a defect: the
archive records prose results, not hash-bound per-gate evidence.

## 4. V4 cannot become a success

`tests/integration/test_m3_package_intake.py::test_a_gap_only_in_v4_is_still_inconclusive`
builds the sharpest case: V0, V1, V2, V3, V5 all `passed`, V4 `not_run`.

Result: attempt `inconclusive` / `required_check_not_run`, `failing_obligation:
symbolic`; run verdict unchanged. A missing symbolic check never converts.

## 5. V3 round_trip vs repaired_behaviour

`app/services/attempt_writer.py` now records the two kinds separately:

| Bundle file | Artifact role | V3 result | Credit |
|---|---|---|---|
| `manifest-compare.json` | `routeb_manifest_compare` | `not_run`, detail "round-trip only; not repair V3" | none |
| `manifest-repaired.json` | `routeb_manifest_repaired` | `passed` only when `repaired_pass: true` | V3 |

New endpoint `GET /api/jobs/{id}/v3` returns both kinds plus `v3_credit`, which is
true only for repaired behaviour. Round-trip evidence is kept (it is real work and
must be auditable) but explicitly earns nothing.

## 6. Every content read verifies bytes

- `/api/jobs/{id}/comparison` previously read the file directly. It now hash-checks
  the artifact first, and returns `comparison: null` with the reason instead of
  rendering tampered bytes.
- `/analysis` and `/v3` metadata now verify hashes for the rows they present.
- Downloads already went through `_verified_artifact_response` (size + sha256).
- No endpoint returns artifact content without passing `_artifact_problem(..., verify_hash=True)`.

## 7. Write guard

New middleware on `POST/PUT/PATCH/DELETE`:

- rejects a non-loopback `Origin` (403);
- rejects `Sec-Fetch-Site: cross-site` (403);
- when `BINARYREPAIR_CONTROLLER_TOKEN` is set, requires `X-BinaryRepair-Token` or
  `Authorization: Bearer ...`, compared with `hmac.compare_digest` (401 otherwise).

Reads are unaffected, so the GUI's http adapter keeps working. Every mutating
endpoint (upload, approve, runs, start, cancel, analysis) passes through the same
guard; `test_controller_auth.py` enumerates them.

## 8. One data directory

`controller_api` (`var`), `app/backend.py` (`var`), `worker` (`var`),
`start-controller.ps1`, `start-worker.ps1/.sh`, and `start.ps1` (`var`) already
agreed after T6.2a. The last outlier, the legacy bridge
`tools/controller_service.py`, defaulted to `var/controller`; it now defaults to
`var` and also honours `BINARYREPAIR_DATA_DIR`.

Historical verification records (`RUNTIME-VERIFICATION.md`, `acceptance.txt`,
`M2-MERGE-REPORT.md`) still mention `var/controller`; they describe runs that
happened, so they were left as history rather than rewritten.

## 9. Tests

```
331 passed, 3 skipped, 1 failed
```

New: 11 tests (`test_m3_package_intake.py` 5, `test_controller_auth.py` 6).
The single failure is the pre-existing `test_static_routeb_bundle` (`assert 7 >= 8`,
no `readelf`/`objdump` on this host).

## 10. Canonical branch

`canonical/m1-m5-integration` is created locally at `316ce1b`. **It is not on the
remote**: this host has no GitHub credentials and the push fails with
`could not read Username for 'https://github.com'`. To publish:

```
git -C <repo> push -u origin canonical/m1-m5-integration
```

Until that runs, M3 and M4 cannot fetch it. The branch is a plain fast-forward
target: `1da22ff` → M5 merge → M1 integration.
