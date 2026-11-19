# 234 — P0 Route A host trust boundary

Date: 2026-11-13
Owner: Lead (implementation + verification in one worktree)
Status: **P0 implementation complete; review artifact, not an acceptance record**
Baseline: `origin/release/v1.2.1-candidate-2026-11-11` resolved to
`612510dbdff5b71b39fe9fb82ae8ec6ef8e38abb` (2026-11-11)
Worktree: `D:\BinRepair\.tmp\p0-routea-release` (detached HEAD, clean before edits)
Current m3 checkout: `eb604683347d803c3a1d2d39ea90d4aabef4380a`, untouched.

## 1. What this record does not claim

* No production gate status changed. Gate 3/4/5/6 and the fixture freeze are
  unchanged by this work.
* No `passed` result was written to production state; no attempt/job/DB in the
  repository or in `var/` was modified. All test databases are synthetic and
  live under the pytest scratch root.
* No guest window was opened; no binary was executed; no candidate was repaired.
* **No host execution of the producer patch tool.** P0 explicitly forbids running
  `patch_routea.py` on the host. V5 replay remains a guest/fresh-context activity;
  the host only validates the replay envelope.
* No formal V5 and no dual-route formal acceptance is claimed. "Legit Route A"
  in the tests is a synthetic, internally consistent bundle that exercises the
  validator and the acceptance path; it is not guest evidence.
* `MEMORY.md` is intentionally not edited in this review worktree. The record is
  the deliverable; it is promoted to `MEMORY.md` only when the patch is accepted.

## 2. Problem and threat model

The production Route A entry used to read a generic declaration JSON
(`BINARYREPAIR_ATTEMPT_INPUT`) and the worker trusted its `results` map. Two
failure modes followed:

1. a hand-written input could claim six `passed` gates; only V2/V4 had typed
   re-validation, and V1/V3/V5 relied on artifact-hash checks whose content was
   never checked;
2. V0 could fall back to the job's original artifact, so identity was not
   required to be the candidate bytes.

The P0 threat model is: a bundle that is *well-formed but not measured* claims
gates; evidence is missing, stale, foreign, bound to another candidate, or
produced by a different contract. The host must recompute what it can recompute
and downgrade everything else before the acceptance engine sees it.

## 3. Design

### 3.1 One production entry, no fallback

* `app/services/attempt_driver.py::_route_a` now reads **only** the canonical
  directory `<data>/jobs/<job>/runs/<run>/attempts/<attempt>.routea`
  (`routea_bundle_dir`). There is no override and no generic-input fallback.
* A missing directory, or a bundle without `route_a/candidate.elf`, exits `3`.
  `app/services/worker.py` maps exit `3` to `EvidenceGapError` and records
  `inconclusive / required_check_not_run` with the driver message in every gate
  detail. It is **not** `error / tool_failed`.
* `attempt_writer --routea-bundle` is the only Route A ingestion mode. The
  generic `--input` mode remains for tests/preview only and is unreachable from
  the driver.

### 3.2 Host recomputation / validation rules (per gate)

New module `app/domain/route_a_evidence.py::validate_route_a_bundle`:

| Gate | Host action | Pass rule |
|---|---|---|
| V0 | Recompute candidate/original bytes; recompute manifest-set hash; require status.json bindings | candidate/original/contract/status hash bindings all match, no missing status/tests |
| V1 | Read audit + edit-manifest + readelf text + LIEF view; bind hashes | `audit.pass=true`, edit-manifest binds candidate and original, required files present |
| V2 | **Product code recomputes** `check_interface(original, candidate, target_entry)` | 5/5 checks true; a bundle `status: pass` observation is ignored |
| V3 | Structural validation of the guest behaviour manifest | candidate hash + contract input_mode match; none-mode 1/1 with `repaired_pass=true`; observed mismatch = definite failure; host never says "replayed" |
| V4 | `validate_v4_evidence(require_independent=True)` + contract binding | typed marker complete, `replay.verified_by="m4"`, candidate/original/contract bound |
| V5 | Replay-envelope validation only | `independent_replay=true`, original/candidate/patch-tool pins, runs>=2, all replay outputs == candidate, byte-identical |

Every detail starts with a machine-readable reason prefix:
`host_verified:`, `guest_observed:`, `missing:`, `invalid:`,
`check_failed:`, `inconclusive:`. The first two are only ever attached to a
`passed` state.

### 3.3 Evidence registration and why records exist

`attempt_writer._routea` registers:

* V0 → the candidate ELF (bytes must equal the attempt's candidate hash);
* V2 → the host-recomputed product interface report;
* V4 → the typed marker;
* V1/V3/V5 → a **host-written verification record**
  (`record_kind="route_a_verification"`) plus the raw guest source files as
  separate provenance artifacts. The record lists the source artifact ids and
  hashes; `obligations.persist_obligations` re-validates the record and each
  source artifact (existence, job store containment, size, re-hashed sha256)
  before a gate may stay `passed`.

This keeps a single write path: raw guest output is never enough on its own,
and the host record is never enough on its own without its bound source bytes.

### 3.4 Obligations boundary

`app/services/obligations.py` now also enforces:

* V0 claimed pass requires evidence artifact bytes that hash to the candidate
  (the old "V0 may fall back to the original artifact" corner is closed);
* for Route A attempts, a `route_a_verification` record for V1/V3/V5 must
  re-validate, including all bound source artifacts;
* legacy Route A payloads without a host record keep their previous mapping and
  are marked in the detail as `legacy route_a evidence (not a host verification
  record)`; they are only reachable through non-production paths (generic
  preview input or the legacy `tools/route_bundle_ingest.py` route A path),
  because the driver no longer has such an entry;
* invalid or foreign evidence is **downgraded to `not_run`** (inconclusive)
  instead of raising `ObligationWriteError` (error/tool_failed). This follows
  the existing evidence-labelling ruling: unverifiable evidence established
  nothing; it did not fail a check. A real measured mismatch is still a
  definite `failed` and rejects the candidate.

### 3.5 V3 execution binding (explicit)

V3 is a guest observation. The host requires the manifest to bind
`candidate_sha256`, the contract `input_mode`, and the case count; for none-mode
it requires exactly one case with `repaired_pass=true` and `passed=total=1`.
The host states `guest_observed` and never reruns the candidate. Formal V3 still
requires the guest isolation evidence from the real window; P0 only prevents a
non-guest or wrong-candidate manifest from being read as a pass.

### 3.6 V4 reuse rules and source record

An existing M4 marker may be reused only when all pins match:
`candidate_sha256`, `original_sha256`, the reviewed contract canonical hash,
`replay.runs>=2`, `replay.identical=true`, `replay.verified_by="m4"`, and the
marker's `source` section records the harness/contract provenance. The marker is
model-scope evidence: `verified_by="m4"` is a role-separated declaration, not
independent human review and not a binary-level proof. Reused markers are
registered as the V4 artifact with their bytes re-hashed; the record names the
source file and hash.

### 3.7 V5 replay (deferred by constraint)

P0 does not execute `patch_routea.py` on the host. V5 pass requires a replay
envelope that pins the original, candidate, patch tool, at least two runs with
identical output bytes, a replayer identity (`replayed_by`) and a method. The
formal independent replay is deferred to a fresh-context agent in the guest; the
host will validate that envelope when it is delivered and will not re-run the
tool.

## 4. Files changed

| File | Change |
|---|---|
| `app/domain/route_a_evidence.py` (new) | validator, reason taxonomy, host records, record re-validation |
| `app/services/attempt_driver.py` | canonical Route A staging path, exit 3 evidence gap, no generic fallback |
| `app/services/attempt_writer.py` | `--routea-bundle` mode, host-record + artifact registration, generic mode documented as test/preview only |
| `app/services/obligations.py` | V0 candidate binding; Route A record re-validation; missing/invalid evidence downgraded |
| `app/services/orchestration.py` | per-gate detail override for evidence-gap verdicts |
| `app/services/worker.py` | exit-3 → evidence gap → `inconclusive / required_check_not_run` |
| `tools/routea_bundle_to_attempt.py` | fixed recorded path (`jobs/<job>/artifacts/attempts/...`), V0 selects `candidate.elf`; documented test/preview only |
| `tests/routea_fixtures.py` (new) | synthetic Route A/B bundle builders (no execution) |
| `tests/test_route_a_evidence.py` (new) | per-gate positive/negative validator tests |
| `tests/integration/test_routea_trust_boundary.py` (new) | legit A+B, forged A + legit B, missing-bundle evidence gap, invalid V4/V5 |
| `tests/test_attempt_driver.py` | Route A no-fallback test replaces the old exit-4 expectation |
| `tests/integration/test_worker.py`, `tests/integration/test_attempt_writer.py`, `tests/integration/test_evidence_envelope.py`, `tests/test_routea_adapter.py` | updated expectations for the new boundary semantics (V0 candidate binding, evidence downgrade, fixed artifact path) |

## 5. Verification (commands actually run)

All commands were run from the worktree with the plugin used for this Windows
sandbox (`-p no:tmpdir -p pytest_rt_report`, `RT_TMP_ROOT` on the workspace to
avoid the sandbox temp-directory defect). No test was skipped or weakened.

```text
python -m pytest tests/test_route_a_evidence.py -q -p no:tmpdir -p pytest_rt_report
  -> collected=16 passed=16 failed=0

python -m pytest tests/integration/test_routea_trust_boundary.py -q -p no:tmpdir -p pytest_rt_report
  -> collected=5 passed=5 failed=0

python -m pytest <17 affected/regression files> -q -p no:tmpdir -p pytest_rt_report
  -> collected=149 passed=147 skipped=2 failed=0

python -m pytest tests/ --ignore=tests/e2e -q -p no:tmpdir -p pytest_rt_report
  -> collected=751 passed=730 skipped=13 failed=8
```

The 8 failures are all `tests/test_guest_executor.py` and all are
`PermissionError` raised inside `tempfile.TemporaryDirectory()` cleanup on this
host (the DSH sandbox denies the mode-0700 temp area). The same 8 tests failed
on this host before this change (previously measured in the Route A audit), and
they do not touch the changed modules. They are recorded as an environment
limitation, not as a pass and not as a code failure.

Patch self-containment check on a fresh baseline worktree
(`612510dbdff5b71b39fe9fb82ae8ec6ef8e38abb`, detached):

```text
git apply --check .tmp/p0-routea.patch   -> exit 0
git apply .tmp/p0-routea.patch           -> exit 0
python -m py_compile <changed modules>   -> exit 0
python -m pytest <new + affected tests>  -> collected=48 passed=47 skipped=1 failed=0
```

## 6. Residual risks and follow-ups

1. **V3 is a trust assumption.** The host cannot replay the candidate, so a
   forged guest manifest that is internally consistent could still claim V3.
   Formal acceptance still needs the guest isolation evidence and the independent
   replay; P0 prevents host-side manufacture of V3 from a declaration only.
2. **V4 independence is a string.** `replay.verified_by="m4"` is validated but
   cannot prove who ran what; the M4 = Lead same-operator limitation remains
   recorded.
3. **V5 formal replay is outstanding.** It must be produced by the fresh-context
   guest agent and then ingested; the host will only validate the envelope.
4. **Legacy non-production paths remain.** Generic `--input` and the legacy
   `tools/route_bundle_ingest.py` Route A path still exist for tests/preview;
   they are not reachable from the production driver and must not be used for a
   production verdict. A follow-up should retire or reroute them.
5. **Executor `--out` wiring defect is unchanged.** This P0 does not fix the
   known V3 collection path in the release executor; without that fix a guest
   run records V3 as `not_run`. That fix and its guest rerun are the next step.

## 7. Rollback

* The work is confined to `D:\BinRepair\.tmp\p0-routea-release` (a detached
  worktree) and `.tmp` scratch files. `git worktree remove` removes everything.
* The m3 checkout at `eb60468` is untouched; the release branch tip is unchanged.
* No database, artifact store, production gate record, or `MEMORY.md` was
  modified outside the worktree's test scratch.

## 8. Deliverables

* Design/patch record: this file.
* Patch: `.tmp/p0-routea.patch` — 119,615 B, SHA-256
  `438bf795229ea5fc08c802c283a0cb8b15bdc0d968dedcdf7e185b35138ffa82`
  (generated from the worktree diff, including new files; verified to apply
  cleanly to the baseline commit above).
* Test reports: `.tmp/ptest-*.json` (pytest_rt_report output) in the worktree.
