# 84 - M4 verification of post-final head `1da22ff` (incoming-AI run)

**Date:** 2026-11-05
**Verifier:** incoming AI operator (not an independent human reviewer)
**Head verified:** `1da22ff01ecfe99da5f235c210959dc2e272750b` (`post-final/host-importer-broker`)
**Final tag state:** unchanged - `mvp-2026-10-31` -> `472aa94`

> This record is a verification line for review. It is **not** a Gate pass
> signature by a second person. The recorded limitation "M4 and Lead are the
> same operator" still stands, and it now also covers this run.

---

## 1. Tree identity

| Item | Expected | Observed |
| --- | --- | --- |
| `main` head | `472aa94` | `472aa94b8d931e03a2b20a8e4f671ba64f832230` |
| `mvp-2026-10-31` | annotated tag object `b6135c7`, commit `472aa94` | tag object `b6135c7370a453a802fb6ab58f6a23e86fe4607b` -> commit `472aa94` |
| `post-final/worker-executor-env` | `63b6eb8` (base `472aa94`) | `63b6eb81649e4c25cce5118d07f3d9681f465a7c`, parent `472aa94` |
| `post-final/m5-adapter-env` | `a9196d9` | `a9196d9efdc148563fbbb8888fcc8b262b6abfcb`, parent `84af51b`, grandparent `63b6eb8` |
| `post-final/host-importer-broker` | `1da22ff` | `1da22ff01ecfe99da5f235c210959dc2e272750b`, parent `a9196d9` |

The tag message still carries the recorded limitations (Gate4 strict, Gate5 A/B
split-chain, V4 model-level bounded 64, frozen fixture, same-person M4/Lead,
full-suite environment gaps).

## 2. Delta scope (main -> 1da22ff)

Whole-tree SHA-256 comparison, no other file touched:

```text
added     docs/handoffs/83-worker-executor-env-contract.md
added     docs/host-importer-broker.md
added     tests/integration/test_host_broker.py
added     tools/host_broker.py
added     tools/host_importer.py
modified  app/services/worker.py
modified  docs/run-worker.md
modified  routeb/attempt_writer.py
modified  tests/integration/test_worker.py
modified  tests/test_routeb_attempt_writer.py
removed   (none)
```

No change to `app/domain/acceptance.py`, `app/services/orchestration.py`,
`app/domain/outcomes.py`, the DB schema, or any GUI template. The acceptance
engine and the verdict ownership rule are untouched by this delta.

## 3. Test results

Environment: Windows, Python 3.14.6, pytest 9.2.0, fastapi 0.162.0,
pydantic 2.14.2, jsonschema 4.26.0, httpx 0.28.1, pyelftools 0.33,
capstone 5.0.9, lief 1.0.0. No binutils (`readelf`/`objdump`) and no clang.

```text
main 472aa94      : 265 collected / 262 passed / 2 skipped / 1 failed
1da22ff           : 273 collected / 269 passed / 3 skipped / 1 failed
```

Both match the numbers already recorded for those heads.

Targeted:

```text
tests/integration/test_worker.py            6 passed, 1 skipped
tests/integration/test_host_broker.py       2 passed
tests/test_routeb_attempt_writer.py         3 passed
```

### The single failure

```text
tests/test_routeb_executor.py::test_static_routeb_bundle
assert result["file_count"] >= 8   ->   7
```

Root cause confirmed by generating the bundle directly: `file_count` counts
every produced file except `SHA256SUMS` and `bundle-sha256.txt`. The seven
counted files are the two ELFs plus the four JSON/Markdown outputs plus
`bundle-record.md`. The five `independent-views/*.txt` files are only written
when `readelf` and `objdump` exist, and neither exists on this host, so the
count stops at 7. This is the recorded Windows binutils gap, not a code defect
and not a regression.

### New environment finding: deep `TMPDIR` breaks the suite

`TMPDIR` is inherited as
`C:\Users\<user>\AppData\Roaming\...\managed-opencode-workdir\tmp`. With
`LongPathsEnabled = 0` and a 266-character `tmp_path`, six tests fail with
`WinError 3` when they `mkdir` the attempt directory:

```text
test_orchestration.py::test_verdict_is_persisted_field_by_field
test_attempt_writer.py::test_generic_writer_writes_worker_bundle
test_attempt_writer.py::test_routeb_bundle_maps_static_audit_without_runtime_pass
test_attempt_writer.py::test_routea_bundle_maps_gates_and_registers_evidence
test_attempt_writer.py::test_routeb_identity_passes_only_with_matching_original
test_attempt_writer.py::test_routeb_identity_fails_on_original_mismatch
```

They all pass once `TMPDIR`/`TEMP`/`TMP` point at a short directory. These are
spurious host failures, not regressions; do not record them as product failures.
Anyone re-running on this host must shorten the temp root first.

## 4. Fixed-fixture scenario (worker -> adapter, composed)

Both post-final features were exercised together on the frozen Route B fixture,
without executing any uploaded or repaired binary.

Setup: real `fixtures/public/CWE121_.../original.elf`, approved contract,
`start_run`, a real `routeb/executor.make_bundle` bundle, and then the bundle's
own `original.elf` was **deleted** before the run.

`BINARYREPAIR_ATTEMPT_CMD` pointed at a wrapper that calls
`python -m routeb.attempt_writer --from-env` for route B.

Observed:

```text
worker_processed                          2
contract file created                     jobs/<job>/contracts/<contract_id>.json
contract SHA-256 == runs.reviewed_scope   true
bundle still missing original.elf         true
route_b V0 / V1                           passed / passed
route_b outcome                           inconclusive (required_check_not_run)
route_a outcome                           inconclusive (required_check_not_run)
```

`V0 passed` while the bundle has no `original.elf` is the proof that the adapter
really consumed `BINARYREPAIR_ORIGINAL`: the identity check hashed the
worker-supplied original against `edit-manifest.json`.

Negative case: the stored `jobs/<job>/original.bin` was overwritten after
approval, then the worker ran again.

```text
route_a outcome   error / tool_failed
route_b outcome   error / tool_failed
executor bundles written by the executor: none
worker log        "original input hash does not match the job record"
```

Fail closed, no fabricated verdict, both attempts persisted as errors.

## 5. Generic adapter question

`app/services/attempt_writer.py --routeb-bundle` still reads only
`BINARYREPAIR_DATA_DIR` / `JOB_ID` / `RUN_ID` / `ATTEMPT_ID` / `ROUTE` /
`RESULT_PATH`. It never reads `BINARYREPAIR_ORIGINAL` or `BINARYREPAIR_CONTRACT`.

Probed directly: with the generic writer wired to the worker and a bundle whose
`original.elf` was deleted, route B still reached `V0 = passed` from the
manifest's declared hash and the job record.

**Conclusion: the generic adapter needs no change to keep working.** It is
weaker only at the adapter level (declared-hash comparison instead of hashing
the real original bytes), but the worker now verifies the real original bytes
and the contract hash *before spawn* for every route, so the deployment keeps
the same top-level guarantee. A change to the generic adapter would be
defense-in-depth, not a defect fix.

## 6. Gaps this run found

1. **`--from-env` depends on an undocumented variable.** The adapter requires
   `BINARYREPAIR_ROUTEB_BUNDLE`, and the worker never sets it. The deployment
   wrapper must export it for each attempt, which is not stated in
   `docs/handoffs/83` or `docs/host-importer-broker.md`. Without it the adapter
   exits non-zero and the attempt becomes `error / tool_failed`.
2. **The real-subprocess 8-variable test is skipped on Windows.** On this host
   the full env set is only proven through a monkeypatched `subprocess.run`,
   not a real second process.
3. **No guest execution.** V2-V5 remain `not_run`; nothing here claims a Gate 4
   or Gate 5 pass for the post-final head.
4. **`lief` installed is 1.0.0.** `requirements.txt` says `lief>=0.15`, which
   admits 1.x, but the Route A build path is untested on this host because
   clang is absent.
5. **Legacy runs without `runs.reviewed_scope_sha256`** would now fail closed
   at spawn (the empty string never equals the contract hash). Fine for
   fail-closed policy, worth knowing before a migration.

## 7. Recommendation

The delta is in scope, matches its own documentation, fails closed on the two
bad inputs tested, and does not touch the acceptance engine. Test numbers
reproduce exactly.

It should still not change `main` or `mvp-2026-10-31` on the strength of this
record alone, because:

- this verification is the same-operator limitation again;
- item 1 above is a real wiring requirement that must be written down before a
  deployment relies on `--from-env`.

Suggested next step: document `BINARYREPAIR_ROUTEB_BUNDLE`, add the real
subprocess test to a POSIX job, then decide a merge strategy that preserves the
frozen tag (for example a new tag on top of `1da22ff` rather than moving
`mvp-2026-10-31`).
