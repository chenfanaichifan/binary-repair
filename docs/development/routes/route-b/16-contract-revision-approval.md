# Contract revision approval — reviewed scope v2

**Status:** M5 amended; M4 review pending; M1/M3 notified.

## M4 proposal disposition

M4's proposal (`ba33b4d0…`) was reviewed but **not adopted verbatim**. M5 amends it
to match the sole final candidate `c4a159…` and to make the environmental
assumptions explicit. The six `authorized_edits` and oracle constants are
unchanged; only `allowed_calls` and `environment_assumptions` are revised.

This is the canonical persisted value; there is no second active contract hash.

## Canonical hash

`fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json`

```text
24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37
```

Recompute only through the canonical helper:

```python
import json
from app.domain.contracts import contract_sha256
data = json.load(open("fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json"))
assert contract_sha256(data) == "24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37"
```

## Reviewed scope change

| Field | Value | Why |
|---|---|---|
| `authorized_edits[0]` | branch back to `0x401309` | 5-byte call at `0x401304`; the next instruction is `0x401309` |
| `allowed_calls` | `("fprintf", "printLine", "strcpy")` | M4 proposal keeps the existing `fprintf` PLT option; final candidate may use the `write` syscall instead |
| `environment_assumptions` | CET compile-time only; runtime IBT/shadow-stack unverified; guest seccomp for `write`/`exit_group` unrecorded | prevents "CET enabled" from being read as runtime proof |
| oracle constants | unchanged (`50/49`, exit `1`, exact stdout/stderr) | frozen |
| six `authorized_edits` | unchanged from handoff 09 §4.1 | reviewed |

`c4a159…` uses `write(2)` and does not call `fprintf`; keeping `fprintf` in
`allowed_calls` is a scope allowance, not a second candidate. Only `c4a159…` is
accepted as gate-3 evidence.

## Unchanged

| Item | SHA-256 |
|---|---|
| `original.elf` | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| `tests/valid.json` | `17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76` |
| `tests/invalid.json` | `d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d` |

The candidate bytes and hash do not change: `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82`.
