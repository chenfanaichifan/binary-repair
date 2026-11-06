# V3 no-input evidence — synthetic runner fixture

This directory records one **real execution** of the V3 no-input acceptance
path. It is deliberately **not** a CWE416 fixture and does **not** create a
CWE416 contract.

## What was run

`./run.sh` invokes:

```
python routeb/run_manifest_repaired.py \
  --binary ./candidate --tests ./tests \
  --out ./manifest-repaired.json --contract ./contract.json
```

The candidate takes no input; the manifest has exactly one valid case and no
`invalid.json`.

## Result (one execution)

| Field | Value |
|---|---|
| exit code | `0` (`run-exit.txt`) |
| stdout bytes | `4e4f5f494e5055545f4f4b0a` (`NO_INPUT_OK\n`) |
| stderr bytes | empty (`""`) |
| V3 shape | `passed=1`, `total=1`, `valid="1/1"` |
| invalid | `"not_applicable"` |
| `repaired_pass` | `true` |

`manifest-repaired.json` is the full record; `run-output.json` is the runner summary.

## Scope and limitations

- The candidate is a host-native Python executable, not an ELF. This proves the
  runner's 1/1 shape and byte capture; it is **not** a CWE416 V3 gate.
- No CWE416 contract exists and no sentinel `invalid_*` is written. When a real
  no-input CWE416 contract is created, `defect.json#trigger_case` must be
  deleted in the same change.
- The contract here is a synthetic no-input demo contract, not CWE416.
- CWE121 v2 remains 4+2 and its V3 semantics are unchanged.

## Reproduce

```
PYTHON=/path/to/python ./run.sh
```

The paths in `manifest-repaired.json` are relative to this directory, so the
record is portable and hash-checkable.
