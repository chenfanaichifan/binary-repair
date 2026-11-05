# Test manifest — CWE121_src_char_declare_cpy_51b

Frozen 2026-10-20. Two files:

| File | SHA-256 |
|---|---|
| `valid.json` | `17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76` |
| `invalid.json` | `d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d` |

Both bind `original_sha256 =
aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`.

## What the oracle means

The two kinds are **not** measured the same way, and that difference is
deliberate:

- **valid** expectations are the **measured behaviour of the original
  `original.elf`**. A repair must preserve them byte for byte.
- **invalid** expectations are the **required post-repair behaviour**, frozen
  in the reviewed contract. The original has no rejection path, so it fails
  these cases; that failure is the vulnerability evidence, not a manifest bug.

Running these cases against the original is therefore a V0-style check:
valid cases pass, invalid cases fail. Running them against a candidate is V3:
all six must pass.

Be precise about the exit-code difference when reading evidence:

- the original on an invalid input returns **SIGSEGV / 139**, or **0** for the
  silent 50-byte overflow — it never returns 1;
- the manifest's `return_code = 1` is the **required post-repair** behaviour;
- **4/6 against the original is the expected V0 shape, not gate 6.** Gate 6 is
  a verification mechanism that detects the original violation; the manifest
  run alone does not satisfy it.

## Capacity rule

`DEST_CAPACITY = 50` bytes (`char dest[50]`, case file line 28).
`strcpy` also writes the terminating NUL, so:

```text
valid   iff len(data) + 1 <= 50   ->  len(data) <= 49
invalid iff len(data) + 1 >  50   ->  len(data) >= 50
```

Length 50 is the first invalid input, not the largest valid one.

## Cases

| id | kind | input | expected exit | expected stdout | expected stderr |
|---|---|---|---:|---|---|
| `valid-empty` | valid | `""` | 0 | `"\n"` | `""` |
| `valid-smallest` | valid | `"A"` | 0 | `"A\n"` | `""` |
| `valid-typical` | valid | 10 × `A` | 0 | 10 × `A` + `\n` | `""` |
| `valid-maximum` | valid | 49 × `A` | 0 | 49 × `A` + `\n` | `""` |
| `invalid-first` | invalid | 50 × `A` | 1 | `""` | `ERROR: input exceeds destination capacity\n` |
| `invalid-longer` | invalid | 100 × `A` | 1 | `""` | `ERROR: input exceeds destination capacity\n` |

`stderr` is matched exactly, including the trailing newline and the colon and
spaces. Route A and Route B must emit the same bytes; two different messages
would give the two routes different oracles, which this manifest forbids.

There are no allowed output files and no stdin input: `stdin_literal` and
`stdin_artifact` are both `null` for every case. The only input channel is
`argv[1]`, passed directly to the Juliet sink by the harness (see
`../provenance.md` §4).

## Measured original behaviour (for contrast)

| Length | exit | stdout | stderr |
|---:|---:|---|---|
| 0 | 0 | `\n` | empty |
| 1 | 0 | `A\n` | empty |
| 10 | 0 | `AAAAAAAAAA\n` | empty |
| 49 | 0 | 49 × `A` + `\n` | empty |
| 50 | 0 | 50 × `A` + `\n` | empty — silent 1-byte overflow |
| 100 | 139 | empty | empty — SIGSEGV, saved `rbp` = `0x4141414141414141` |

Raw evidence: `../evidence/03-run-boundary.txt`, `../evidence/04-gdb-crash-100.txt`.

Two details worth keeping:

- At length 100 the process dies before flushing stdio, so the captured
  stdout is empty even though `printLine` was reached. Empty stdout there is
  not evidence that the copy did not run.
- At length 50 the extra byte lands in stack padding and does not crash. The
  violation is still real (51 bytes written into a 50-byte object) and the
  contract still rejects it. "It did not crash" is not "it is valid".

## How to run

The runner must invoke the binary with exactly the argument array in `argv`,
with no shell interpolation and no added environment. For example:

```bash
./original ""
./original "A"
./original "$(printf 'A%.0s' $(seq 1 49))"
./original "$(printf 'A%.0s' $(seq 1 50))"
./original "$(printf 'A%.0s' $(seq 1 100))"
```

Compare exit code, stdout and stderr as byte strings. Do not normalise
whitespace.

## Runner and original-binary result

`../build/run_manifest.py` loads both files and compares return code, stdout
and stderr as bytes. Run it from the fixture root (`./original.elf` plus
`tests/`) inside the guest.

Against the original it reports **4/6 passed**: all four valid cases pass, both
invalid cases fail. That is the expected result for a vulnerable binary, not a
manifest defect. Note that Python's `subprocess` reports the SIGSEGV as
`rc=-11`; a POSIX shell reports 139. Raw output:
`../evidence/06-manifest-vs-original.txt`.

## V3 assertions (`v3_oracle.py`)

`v3_oracle.py` is the judging layer for V3: it turns (manifest, observed
behaviour) into `passed` / `failed` / `not_run`. It **executes nothing**, which
is deliberate:

- the host and CI may run it, because no binary is executed;
- Route A and Route B are judged by the same code, so F5 compares like with
  like;
- the acceptance engine gets an ordinary obligation instead of a second verdict
  path.

`run_manifest.py` executes the binary and produces the numbers; `v3_oracle.py`
decides whether those numbers satisfy the contract. Keep the two apart so a
result can be re-judged from recorded output without running anything again.

### Interface

```python
from v3_oracle import Observation, evaluate_files, load_manifest, check_manifest_pair

check_manifest_pair(valid, invalid, dest_capacity=50, max_valid_len=49)  # oracle self-check

suite = evaluate_files(
    ["tests/valid.json", "tests/invalid.json"],
    {
        "valid-empty":    Observation(return_code=0, stdout=b"\n", stderr=b""),
        "invalid-first":  Observation(return_code=1, stdout=b"",
                                      stderr=b"ERROR: input exceeds destination capacity\n"),
        # ...
    },
)
suite.result          # "passed" | "failed" | "not_run"
suite.obligation()    # {"kind": "behaviour", "required": True,
                      #  "result": ..., "detail": "6 passed, 0 failed, 0 not run"}
suite.as_dict()       # full per-case record for the evidence bundle
```

Rules the code enforces, all of them load-bearing:

- comparison is **byte-exact** on `return_code`, `stdout` and `stderr`; a
  missing trailing newline is a failure, not a rounding error;
- a case with **no observation** is `not_run` and can never become `passed`;
- a definite failure outranks missing evidence (`failed`, not `not_run`);
- an unexpected output file fails the case;
- the manifest cannot be weakened: a `valid` case longer than
  `DEST_CAPACITY - 1`, an `invalid` case that fits, a duplicated id, a
  mismatched `case_id`/`original_sha256` pair, or a `max_valid_len` that
  contradicts `DEST_CAPACITY` all raise `ManifestError` before any candidate is
  judged.

### Tests

`test_v3_oracle.py` covers the layer with synthetic observations — no binary, no
network, standard library only:

```bash
cd fixtures/public/CWE121_src_char_declare_cpy_51b/tests
python -m unittest test_v3_oracle -v      # 24 tests
```

Notable cases: a conforming candidate scores 6/6 `passed`; the measured
original scores 4/6 `failed` (V0 evidence, never a passing V3); a missing
`stderr` newline fails; missing observations produce `not_run`.

## Freeze rule

Changing a case, the capacity rule, the expected stderr, or
`original_sha256` creates a new manifest and invalidates prior approvals. Tell
Member 4 before changing any hash. Rationale for each case is in the JSON
`rationale` field.
