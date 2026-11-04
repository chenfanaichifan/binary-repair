# Execution bridge v1 — staged guest execution and host ingest

**Status:** frozen 2026-11-03 by Lead decision `docs/handoffs/85` (D1). Version
bumps require a changelog line at the end of this file plus notification to
M1/M3/M4/Lead in the same commit. Consumers must reject unknown
`schema_version` values instead of coercing them.

**Owners:** M5 (ingest adapter + host tools hardening), M3 (guest executor),
VMer (jobwrap/isolation/staging mount), M1 (worker/controller read surface),
M4 (verification), Lead (approval).

This is the **only** protocol for the live pipeline. The delivered host tools
`tools/host_importer.py` and `tools/host_broker.py` are part of this protocol;
extend them, do not fork them.

---

## 0. What this bridge is

```text
trusted host                                      untrusted guest
------------                                      ---------------
worker --attempt cmd--> executor driver
   | stage job package (inbox)  ------------------>  jobwrap exec:
   |                                                  - reads inbox package
   |                                                  - runs fixed route steps
   |                                                  - writes outbox bundle+files
   | <------------------------------- outbox (host-visible staging directory)
   v
ingest adapter: verify hashes/paths/sizes, register artifacts, map gates
   v
tools/host_importer.import_bundle() -> atomic attempt bundle -> worker -> verdict
```

- The **host initiates** by staging a job package and by reading the outbox.
- The **guest never opens a network connection**, never calls the controller,
  never mounts a host home directory, and never receives host secrets.
- The guest writes only regular files into its own outbox subtree.
- The guest executor never decides an outcome; it reports gate evidence.
- The host acceptance engine is the only outcome writer.
- v1 accepts only the frozen public fixture (`docs/handoffs/85` D2). Everything
  else is `unsupported` and produces no candidate.

## 1. Staging directory (the transport)

The staging directory is a dedicated directory visible to both sides (for
example a VMware shared folder or an scp-transfer directory). It is **not** the
controller data directory and **not** a host home mount.

```text
<staging>/
  inbox/
    <job_id>/
      job.json              # host-written package descriptor (section 2)
      original.elf          # exact uploaded bytes
      contract.json         # frozen SecurityContract v2
      tests/
        valid.json
        invalid.json
      route_a/
        expected-candidate.elf   # optional frozen expected bytes
      route_b/
        replacement.c            # Milestone 2 only; absent in Milestone 1
      SHA256SUMS            # hashes of every file above (except itself)
  outbox/
    <job_id>/<run_id>/<attempt_id>/
      result-bundle.json
      artifacts/            # files listed by the bundle, basenames only
      SHA256SUMS
    screening/<job_id>/<screen_id>/
      screening-result.json # analysis-only result (section 4b)
      artifacts/analysis/   # recovered C, disassembly, vulnerability summary
      SHA256SUMS
```

Rules:

| Item | Rule |
|---|---|
| Ownership | host creates `inbox/<job_id>/` and writes it; guest uid 1003 reads it |
| Guest write scope | only `outbox/<job_id>/<run_id>/<attempt_id>/` (repair) or `outbox/screening/<job_id>/<screen_id>/` (screening); nothing else |
| File types | regular files only; no symlinks, FIFOs, sockets, device nodes |
| Names | `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`; no `/` in artifact names |
| Sizes | `job.json` ≤ 1 MiB; `original.elf` ≤ 20 MiB; each artifact ≤ 20 MiB; whole outbox attempt ≤ 64 MiB |
| Hashes | lowercase 64-hex SHA-256 everywhere; `SHA256SUMS` uses `sha256sum` format, sorted with `LC_ALL=C`, one space-space separator |
| Extra files | any unlisted file in an outbox attempt directory fails ingest; never ignored |
| Missing files | any file listed in the bundle but absent fails ingest |
| Cleanup | host removes `inbox/<job_id>` and `outbox/<job_id>` only after ingest or after a recorded failure |
| Network | no route from the guest during execution; the staging mount is the only channel |
| Secrets | no `DEEPSEEK_API_KEY`, tokens, SSH keys or host home content in staging |

Artifact `relative_path` values in the bundle are relative to
`outbox/<job_id>/<run_id>/<attempt_id>/` and must point inside it. Absolute
paths, `..`, and backslashes are rejected.

## 2. Job package descriptor (`inbox/<job_id>/job.json`)

Strict schema; unknown top-level fields are rejected.

```json
{
  "schema_version": 1,
  "purpose": "repair",
  "job_id": "8f1c2e4a-6b7d-4e90-9a1b-2c3d4e5f6a7b",
  "run_id": "0d9e7c55-2f7e-4c55-9f11-2a33a8f1c001",
  "attempt_id": "b0c6f6e0-2d44-4a90-9c2f-7b1a8e3f9d02",
  "route": "route_a",
  "original_sha256": "aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393",
  "contract_sha256": "24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37",
  "manifest_set_sha256": "a564f0397a741b1a4fc386a3149d54550c1bfe7c02958309e021fb6f03333a78",
  "fixture": {
    "id": "CWE121_src_char_declare_cpy_51b",
    "original_sha256": "aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393"
  },
  "limits": {"wall_seconds": 600, "max_candidate_bytes": 1048576},
  "route_a": {
    "mode": "frozen_fixture",
    "expected_candidate_sha256": "c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82"
  },
  "route_b": {
    "mode": "frozen_fixture",
    "expected_candidate_sha256": "208574ab5b7753fab6f28860830069770622fb7b1fcb8d181fa50453f8656717",
    "replacement_c_sha256": null
  }
}
```

Rules:

- `purpose` is `repair` (default) or `screening`. A `screening` package carries
  `original_sha256`, `contract_sha256` (optional), `fixture`, `limits` and the
  original bytes only; it must not carry `route`/`route_a`/`route_b`, and it
  produces `screening-result.json` + analysis artifacts instead of a result
  bundle (section 4b).
- `route` selects which block must be valid; the other block may be `null`.
- `contract_sha256` is the canonical hash from `app/domain/contracts.py`
  (`canonical_json` + SHA-256), not a file-byte hash.
- `manifest_set_sha256` is the canonical hash from
  `workers/route_a/worker.py:manifest_set_hash`.
- `mode: "frozen_fixture"` requires byte-identical expected candidate output; a
  mismatch is a hard failure (`hash_mismatch`), never a "new candidate".
- Milestone 2 adds `route_b.mode: "provider_c"`: `replacement.c` is staged,
  `replacement_c_sha256` is set, `expected_candidate_sha256` is `null`, and the
  produced candidate hash is reported.
- The guest recomputes every hash from the staged bytes and fails closed.

## 3. Guest executor contract

The guest executor is a fixed program invoked through a fixed jobwrap operation.
The host never passes an arbitrary command, argv list or path.

```text
jobwrap executor <job_id>
```

Fixed inputs (root-owned config, one line per job):

```text
<job_id>  <staging>/inbox/<job_id>  <staging>/outbox/<job_id>/<run_id>/<attempt_id>  <runner.py>
```

Validation before `exec`:

- `job_id` matches `^[A-Za-z0-9._-]{1,64}$`;
- inbox/outbox paths are under the configured staging root; no `..`;
- runner is the fixed absolute path of `workers/executor/run_job.py`;
- isolation: netns (no default route), uid/gid 1003, caps empty,
  `no_new_privs`, seccomp per baseline, rlimits (CPU 600 s, AS 4 GiB,
  NOFILE 1024, FSIZE 256 MiB), `clearenv` + whitelist
  (`PATH, HOME, TMPDIR, LANG, PYTHON`).

Execution order:

```text
read job.json -> verify staged hashes -> run route steps -> collect evidence
  -> (optional) run the frozen cases against original AND candidate
     and write artifacts/behavior-comparison.json (role behaviour_compare)
  -> (optional) write analysis artifacts (role analysis_*)
  -> write result-bundle.json + artifacts/ + SHA256SUMS in the outbox atomically
  -> exit 0 on success; non-zero on failure (bundle still written)
```

For `purpose: "screening"` the order is: read job.json → verify hashes → run
analysis only → write `screening-result.json` + `artifacts/analysis/*` +
`SHA256SUMS`; no gates, no candidate, no result bundle. Screening must not
execute the original binary against the test cases (no behaviour data yet).

Exit codes: `0` finished; `2` bad package/hash; `3` unsupported fixture/route;
`4` isolation failure; `5` tool failure; `6` timeout. A non-zero exit never
becomes `pass`; the ingest adapter reports `error/tool_failed` when no valid
bundle exists.

Phase progress may be written to `outbox/.../phase.txt` (single ASCII token from
`analyzing|building|validating|packaging`); the host may poll it. It is progress
only, never a verdict.

## 4. Result bundle v1

Canonical JSON (sorted keys, `,`/`:` separators, ASCII). **No `outcome`,
`reason`, `decision` or success label may appear anywhere.**

```json
{
  "schema_version": 1,
  "job_id": "8f1c2e4a-6b7d-4e90-9a1b-2c3d4e5f6a7b",
  "run_id": "0d9e7c55-2f7e-4c55-9f11-2a33a8f1c001",
  "attempt_id": "b0c6f6e0-2d44-4a90-9c2f-7b1a8e3f9d02",
  "route": "route_a",
  "original_sha256": "aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393",
  "contract_sha256": "24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37",
  "manifest_set_sha256": "a564f0397a741b1a4fc386a3149d54550c1bfe7c02958309e021fb6f03333a78",
  "candidate": {
    "relative_path": "artifacts/candidate.elf",
    "sha256": "c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82",
    "size_bytes": 26792
  },
  "artifacts": [
    {"role": "candidate",     "relative_path": "artifacts/candidate.elf",        "sha256": "c4a159...aa82", "size_bytes": 26792, "media_type": "application/x-elf"},
    {"role": "edit_manifest", "relative_path": "artifacts/edit-manifest.json",   "sha256": "<64 hex>", "size_bytes": 1234, "media_type": "application/json"},
    {"role": "audit",         "relative_path": "artifacts/audit.json",           "sha256": "<64 hex>", "size_bytes": 2345, "media_type": "application/json"},
    {"role": "readelf",       "relative_path": "artifacts/readelf-audit.txt",    "sha256": "<64 hex>", "size_bytes": 3456, "media_type": "text/plain"},
    {"role": "behaviour",     "relative_path": "artifacts/manifest-compare.json","sha256": "<64 hex>", "size_bytes": 2345, "media_type": "application/json"},
    {"role": "isolation",     "relative_path": "artifacts/isolation.json",       "sha256": "<64 hex>", "size_bytes": 512,  "media_type": "application/json"},
    {"role": "log",           "relative_path": "artifacts/route_a.log",          "sha256": "<64 hex>", "size_bytes": 512,  "media_type": "text/plain"}
  ],
  "gates": {
    "V0": {"status": "pass",    "detail": "original hash matches staged identity", "evidence": ["artifacts/candidate.elf"]},
    "V1": {"status": "pass",    "detail": "static audit pass",                     "evidence": ["artifacts/audit.json"]},
    "V2": {"status": "pass",    "detail": "loader/interface evidence recorded",    "evidence": ["artifacts/readelf-audit.txt"]},
    "V3": {"status": "pass",    "detail": "six frozen cases 6/6",                  "evidence": ["artifacts/manifest-compare.json"]},
    "V4": {"status": "not_run", "detail": "no symbolic evidence for this candidate hash", "evidence": []},
    "V5": {"status": "not_run", "detail": "no replay record",                      "evidence": []}
  },
  "tool_versions": {"python": "3.11.8", "pyelftools": "0.33", "patcherex2": "0.2.14", "clang": "15.0.7"},
  "isolation": {"uid": 1003, "gid": 1003, "cap_eff": "0", "no_new_privs": 1, "seccomp": 0, "netns": true},
  "started_at": "2026-11-03T10:00:01Z",
  "finished_at": "2026-11-03T10:00:41Z"
}
```

Gate rules:

| Gate | Kind | A `pass` must carry |
|---|---|---|
| V0 | identity | original identity and the candidate hash required by `job.json` |
| V1 | structure | static audit/manifest with before/after headers and change intervals |
| V2 | interface | loader/interface evidence (readelf/relocations/entry) |
| V3 | behaviour | six frozen cases run in the guest under isolation, raw output |
| V4 | symbolic | candidate-specific bounded model record, or `not_run` |
| V5 | reproducibility | double-build byte equality + replay record, or `not_run` |

- `status` enum: `pass | fail | not_run | inconclusive | unsupported`.
- A `pass` lists at least one path from `artifacts`.
- V4/V5 `pass` only with evidence naming this exact `candidate.sha256`;
  evidence for another hash is `not_run` (no pass by association, D8).
- Every artifact listed must exist with the listed hash and size; every file in
  the outbox attempt directory must be listed. Otherwise ingest fails.
- Optional extra roles for the agent UI and the AI step:
  `behaviour_compare`, `analysis_recovered_c`, `analysis_disassembly`,
  `analysis_vulnerability` (section 4a). They are display/AI evidence; they do
  not create a gate pass by themselves.

## 4a. Display artifacts for the agent UI

These artifacts make the new GUI possible without letting it invent anything.
They are optional for acceptance but required before the GUI comparison screen
may claim `available: true`.

### 4a.1 `artifacts/behavior-comparison.json` — role `behaviour_compare`

The guest runs the same frozen cases against the **original** and the
**candidate** inside the same isolation, and records both. The host never runs
either binary. This is the source of the "修复前后对比" screen.

```json
{
  "schema_version": 1,
  "candidate_sha256": "c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82",
  "original_sha256": "aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393",
  "case_set_sha256": "a564f0397a741b1a4fc386a3149d54550c1bfe7c02958309e021fb6f03333a78",
  "cases": [
    {
      "id": "valid-empty",
      "kind": "valid",
      "input_hex": "0a",
      "expected": {"rc": 0, "stdout_hex": "0a", "stderr_hex": ""},
      "original": {"rc": 0, "stdout_hex": "0a", "stderr_hex": "", "ran": true},
      "repaired": {"rc": 0, "stdout_hex": "0a", "stderr_hex": "", "ran": true},
      "verdict": "unchanged",
      "detail": ""
    },
    {
      "id": "invalid-64",
      "kind": "invalid",
      "input_hex": "4141414141414141",
      "expected": {"rc": 1, "stdout_hex": "", "stderr_hex": "ERROR: input exceeds destination capacity\n"},
      "original": {"rc": -11, "stdout_hex": "", "stderr_hex": "", "ran": true},
      "repaired": {"rc": 1, "stdout_hex": "", "stderr_hex": "ERROR: input exceeds destination capacity\n", "ran": true},
      "verdict": "fixed",
      "detail": ""
    }
  ],
  "summary": {
    "total": 6,
    "original_matches": 2,
    "repaired_matches": 6,
    "fixed": 2,
    "regressed": 0,
    "unchanged": 4,
    "not_run": 0
  }
}
```

Rules:

- `verdict` per case is exactly one of `fixed` (original misses expected,
  candidate matches), `regressed` (original matches, candidate misses),
  `unchanged` (both match), `still_broken` (neither matches), `not_run` (case
  was not executed; `ran:false`).
- The UI may display `repaired_matches / total` only as **"样本用例符合率"**
  (sample-case match rate), never as proof of repair and never as the outcome.
  A `not_run` case is not a match.
- `behaviour_compare` is additional display evidence; V3 still requires the raw
  per-case evidence (`manifest-compare.json` or equivalent) and its own pass
  rule. A summary file alone cannot make V3 pass.
- Both runs use the same isolation and the same input bytes; the file records
  `case_set_sha256` so the host can bind it to the staged manifests.

### 4a.2 Analysis artifacts (Milestone 2 and the analysis card)

- `artifacts/analysis/recovered.c`, role `analysis_recovered_c` — recovered C.
- `artifacts/analysis/disassembly.txt`, role `analysis_disassembly` — the
  disassembly excerpt around the target function.
- `artifacts/analysis/vulnerability.json`, role `analysis_vulnerability`:

```json
{
  "schema_version": 1,
  "function": "CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink",
  "address": "0x4012b0",
  "summary": "Unbounded strcpy into a 50-byte stack buffer; input length is not checked.",
  "confidence": "high"
}
```

These are display/AI inputs. They never carry an outcome and never replace the
V0–V5 obligations.

### 4a.3 Diagnostic table derivation

The GUI's diagnostic table is **not a new artifact**; it is a rendering of
persisted rows:

| UI column | Source |
|---|---|
| 义务 | obligation kind (`identity/structure/interface/behaviour/symbolic/reproducibility`) |
| 结果 | persisted obligation `result` (`passed/failed/not_run/unknown/timed_out`) shown verbatim |
| 范围 | route + obligation scope/evidence role |
| 证据 | artifact download link resolved from `evidence_artifact_id` |
| 原因 | persisted `detail` / verdict reason |

The overall outcome on the same screen comes only from
`app/domain/acceptance.py` (via the run verdict). The screen must render
`not_run` verbatim and must not turn a comparison summary into a success label.

### 4b. Screening result (`outbox/screening/<job_id>/<screen_id>/screening-result.json`)

Screening runs analysis only (no candidate, no gates, no outcome):

```json
{
  "schema_version": 1,
  "purpose": "screening",
  "job_id": "8f1c2e4a-6b7d-4e90-9a1b-2c3d4e5f6a7b",
  "screen_id": "0e5b2a10-9f2e-4e31-8a7c-1d2e3f4a5b6c",
  "original_sha256": "aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393",
  "function": "CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink",
  "entry": "0x4012b0",
  "analysis": {
    "vulnerability_summary": "Unbounded strcpy into a 50-byte stack buffer; input length is not checked.",
    "confidence": "high",
    "recovered_c_relative_path": "artifacts/analysis/recovered.c"
  },
  "artifacts": [
    {"role": "analysis_recovered_c",  "relative_path": "artifacts/analysis/recovered.c",     "sha256": "<64 hex>", "size_bytes": 512,  "media_type": "text/plain"},
    {"role": "analysis_disassembly",  "relative_path": "artifacts/analysis/disassembly.txt",  "sha256": "<64 hex>", "size_bytes": 2048, "media_type": "text/plain"},
    {"role": "analysis_vulnerability","relative_path": "artifacts/analysis/vulnerability.json","sha256": "<64 hex>", "size_bytes": 256,  "media_type": "application/json"}
  ],
  "tool_versions": {"python": "3.11.8", "pyelftools": "0.33", "ghidra": "11.0"},
  "started_at": "2026-11-03T10:00:01Z",
  "finished_at": "2026-11-03T10:00:31Z"
}
```

Rules:

- No `gates`, `candidate`, `results`, `outcome` or `reason` keys.
- Artifacts are registered against the **job** (not an attempt) and exposed via
  `GET /api/jobs/{id}/analysis`. They are display/AI evidence only.
- A failed screening writes no `screening-result.json`; the host reports the
  typed reason and the GUI shows "分析未完成（原因）".
- Screening never executes the original binary against the test cases; behaviour
  data is produced only during a repair run (section 4a.1).

## 5. Host ingest adapter

Owner: M5. New module `tools/route_bundle_ingest.py` (plus a small artifact
registry helper if needed). It runs between the outbox and the delivered
`tools/host_importer.py`.

Steps:

1. Read `result-bundle.json` and `SHA256SUMS`; reject unparseable/unknown
   schema versions.
2. Reject path violations before touching any file: absolute paths, `..`,
   backslashes, names outside the pattern, symlinks, non-regular files, missing
   or unlisted files, size overruns.
3. Recompute SHA-256 for every artifact and the candidate; compare with the
   bundle and with `SHA256SUMS`; compare bundle identity with the job/run/
   attempt rows and with the staged `job.json`.
4. Register every artifact in the `artifacts` table (job id, role, sha,
   size, relative path) and collect artifact ids.
5. Map gates: `pass→passed`, `fail→failed`, `not_run→not_run`,
   `inconclusive→unknown`, `unsupported→unknown`. Evidence map = artifact id
   per passed V1–V5; V0 may omit it (worker falls back to the original).
6. Record `attempts.candidate_sha256` (column exists; no code writes it today).
   It is evidence binding, not a pass condition.
7. Hand the mapped bundle to `tools/host_importer.import_bundle(...)`; that keeps
   atomic write, idempotency, conflict rejection and worker trigger.
8. On any failure: write nothing to the controller store; record the reason in
   `outbox/<job>-failed.log` and report `tool_failed`. Never write a partial
   bundle.

The mapped attempt bundle handed to `import_bundle` uses the existing worker
schema (same shape as `docs/run-worker.md`):

```json
{
  "route": "route_a",
  "candidate_sha256": "c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82",
  "results": {"V0": "passed", "V1": "passed", "V2": "passed", "V3": "passed", "V4": "not_run", "V5": "not_run"},
  "evidence": {"V1": "<artifact id>", "V2": "<artifact id>", "V3": "<artifact id>"},
  "details": {"V1": "static audit pass", "V3": "six frozen cases 6/6"}
}
```

Rules for the mapped bundle:

- `evidence` values are database artifact ids for the same job; V0 may be
  omitted (the worker falls back to the original artifact). A passed V1–V5 with
  an unresolvable id is a host bug and the ingest must fail, not write.
- `details` come from the guest `gates.<gate>.detail` strings, trimmed to 500
  ASCII characters.
- `route` must equal the persisted attempt route; the importer re-checks it.

Hardening of the delivered tools (same owner):

- `tools/host_importer.py`: `--bundle`/`bundle_path` must resolve under the
  configured staging root; keep `--no-trigger`; keep identical-bytes
  idempotency and different-bytes rejection.
- `tools/host_broker.py`: strict envelope schema, unknown fields rejected,
  symlink rejection, size cap on envelope and bundle, processed/failed move
  behaviour unchanged, one worker trigger per batch.
- Keep `tests/integration/test_host_broker.py` green; extend it with negative
  cases (traversal, symlink, oversize, extra file, wrong route, conflicting
  existing bundle).

## 6. Lifecycle and failure semantics

```text
PG_queued
  -> host stages inbox package            (stage)
  -> worker spawns executor command       (BINARYREPAIR_ATTEMPT_CMD)
  -> guest runs under jobwrap             (analyze/build/validate/package)
  -> outbox bundle + artifacts            (finished or failed)
  -> host ingest adapter                  (verify/register/map)
  -> host_importer.import_bundle          (atomic attempt bundle + worker)
  -> worker -> acceptance engine          (only outcome writer)
  -> controller snapshot -> GUI           (render only)
```

- The worker spawns the executor once per attempt; if the executor produces no
  bundle, the attempt stays queued and the worker reports it (existing
  behaviour). Infrastructure failures surface as `error/tool_failed`.
- A retry is a new attempt id; the guest must not reuse a previous outbox tree.
- Cancel: the host writes a cancel marker (or kills the executor process); a
  cancelled attempt never becomes success. If termination cannot be confirmed,
  record `error/termination_unconfirmed` and reset the guest snapshot.
- Snapshot reset happens between jobs (VMer); the staging directories are
  cleaned between jobs.

## 7. Reason codes (ingest/executor)

| Code | Applies to | Meaning |
|---|---|---|
| `bad_package` | executor/ingest | malformed job.json/bundle/envelope, unknown field |
| `hash_mismatch` | executor/ingest | original/contract/manifest/candidate/bundle/artifact mismatch |
| `unsupported` | executor/ingest | not the frozen fixture, unknown route/mode |
| `path_violation` | ingest | absolute path, `..`, symlink, non-regular file, unexpected name |
| `too_large` | ingest | file or attempt exceeds the size caps |
| `missing_file` | ingest | listed file absent |
| `unexpected_file` | ingest | unlisted file in the outbox attempt |
| `isolation_failed` | executor | jobwrap/isolation setup failed |
| `timeout` | executor | wall clock exceeded; terminate and report |
| `tool_failed` | host | any failure that leaves no valid bundle |

The worker maps absent/invalid bundles to `error/tool_failed`; missing evidence
is never `passed`.

## 8. Conformance tests

Host-safe (M5 `tests/integration/test_route_bundle_ingest.py`, M3
`workers/executor/self_test.py`, existing `tests/integration/test_host_broker.py`):

1. valid synthetic bundle + artifacts → attempt bundle written once, worker
   triggered, evidence ids resolvable;
2. identical re-ingest → idempotent (`changed=False`); different bytes →
   rejected without overwrite;
3. traversal / absolute / symlink / device file → rejected before read;
4. unexpected extra file or missing listed file → rejected;
5. oversize file/attempt → rejected;
6. tampered artifact/candidate/bundle hash → rejected;
7. gate `passed` without evidence path → rejected;
8. unknown fixture/route/mode/schema version → `unsupported`;
9. no `outcome`/`reason`/`decision` key accepted in a bundle.

Guest-only (M4 records):

10. fixture staged → executor run → outbox bundle with V0–V3 evidence and six
    raw case rows; hashes match;
11. isolation attestation (uid/gid 1003, CapEff 0, NoNewPrivs 1, netns, no
    egress);
12. snapshot reset leaves no inbox/outbox artifacts;
13. host end-to-end: p2 exit 0 with `demo:false` and six persisted obligations
    per attempt.

## 9. Non-goals for v1

- No outcome in the guest bundle; no guest verdict.
- No guest network, no guest API key, no host home mount.
- No arbitrary command/argv/path from the host.
- No arbitrary uploaded ELF (Milestone 3 research).
- No second transport: a pull-over-HTTP guest service is not adopted; if needed
  it becomes a new interface version.
- No client binary or confidential derived content leaves the local scope.

## Changelog

- 2026-11-03 — v1 frozen by Lead decision `docs/handoffs/85` (D1–D9), staged
  inbox/outbox transport; reuses the delivered `tools/host_importer.py` and
  `tools/host_broker.py`.
- 2026-11-03 — added §4a display artifacts (`behavior-comparison.json` with
  before/after rows, analysis roles, diagnostic-table derivation) required by
  the agent-style GUI (`docs/handoffs/86`). Additive; existing rules unchanged.
- 2026-11-03 — added `purpose: screening` (analysis-only job package and
  `screening-result.json`, §4b) for the GUI analysis step; repair flow unchanged.
