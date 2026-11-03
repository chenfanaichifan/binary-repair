# 83 - Worker executor environment contract (post-final branch)

**Status:** implemented on `post-final/worker-executor-env`; not merged, final tag unchanged.

## Contract

When `BINARYREPAIR_ATTEMPT_CMD` is set, the worker now supplies:

```text
BINARYREPAIR_DATA_DIR
BINARYREPAIR_JOB_ID
BINARYREPAIR_RUN_ID
BINARYREPAIR_ATTEMPT_ID
BINARYREPAIR_ROUTE
BINARYREPAIR_RESULT_PATH
BINARYREPAIR_ORIGINAL
BINARYREPAIR_CONTRACT
```

### Original

`BINARYREPAIR_ORIGINAL = <data>/jobs/<job_id>/original.bin`

Before spawn, the worker checks:

- file exists and is readable;
- SHA-256 equals `jobs.original_sha256`.

### Contract

`BINARYREPAIR_CONTRACT = <data>/jobs/<job_id>/contracts/<contract_id>.json`

The worker:

- reads `contracts.body_json` for `runs.contract_id`;
- refuses an unapproved/missing contract;
- writes the bytes atomically via a temp file + `os.replace`;
- reuses an existing file only when its SHA-256 matches;
- verifies SHA-256 against both `contracts.sha256` and
  `runs.reviewed_scope_sha256`;
- fails closed before spawning the executor on any mismatch.

The contract path includes the contract id, so another revision cannot be
overwritten.

### Compatibility

The original six variables are unchanged. Existing executors that ignore the two
new paths remain compatible.

## Tests

```text
tests/integration/test_worker.py
6 passed, 1 skipped (POSIX-only real-subprocess test on Windows)
```

Covered:

- all 8 env vars present;
- original path readable and hash-bound;
- contract path readable, JSON-parsable, hash-bound to the run;
- executor writes `BINARYREPAIR_RESULT_PATH`, worker consumes the bundle;
- missing original -> executor not spawned;
- unapproved contract -> executor not spawned;
- legacy pre-written bundle path still works;
- POSIX real subprocess test (skipped on Windows).

Full subset:

```text
pytest --ignore=tests/e2e:
269 collected / 265 passed / 3 skipped / 1 failed
```

The single failure is the existing Windows `test_routeb_executor` binutils gap.

## Scope

No gate/record/readme/tag change. M4/Lead decide whether to accept this
post-final head.
