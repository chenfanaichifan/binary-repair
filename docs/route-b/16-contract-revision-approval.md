# Contract revision approval — entry 1 return target

**Status:** M5 corrected; M4 re-review pending; M1/M3 notified.

## Change

Only `authorized_edits[0]` changed: the valid-path branch target is now
**`0x401309`**, the instruction after the 5-byte `call strcpy@plt` at `0x401304`.
The other five entries are untouched. The old branch target is not retained as a
second active hash.

## Canonical hash

`fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json`

```text
1a0ad101097461b207e3ea07e264d8d6eb03bc57d1f54c7b9e41c2955015c10c
```

Recompute only through the canonical helper:

```python
import json
from app.domain.contracts import contract_sha256
data = json.load(open("fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json"))
assert contract_sha256(data) == "1a0ad101097461b207e3ea07e264d8d6eb03bc57d1f54c7b9e41c2955015c10c"
```

## Unchanged

| Item | SHA-256 |
|---|---|
| `original.elf` | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| `tests/valid.json` | `17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76` |
| `tests/invalid.json` | `d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d` |
| oracle/harness | no source change in this revision |
| `dest_capacity_bytes` / `max_valid_input_bytes` / `invalid_*` | unchanged |

The candidate `c4a159…` was generated with a return to `0x401309`; only the
contract text was wrong, so the candidate bytes and hash do not change.
