# Build recipe and tool versions — no competing gate-3 evidence

## Sole candidate

Only `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82`
is gate-3 evidence. M4's earlier `f3cb9cbb…` (fprintf writer) is **superseded**
and is not accepted as a second candidate. The `member-4-routea-gate3` branch is
not fetchable in this workspace, so its `routea/` changes are **not reviewed or
merged**; no second evidence bundle will be pushed by M5.

## Primary recipe (stdlib-only)

```bash
python3 regen_c4a159.py original.elf candidate.elf
sha256sum candidate.elf
# c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82
```

Inputs: `original.elf` (`aa428157…8393`) and `contract.json`
(canonical `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37`).
The script fails closed on either hash.

## Secondary recipe (routea CLI)

```bash
PYTHON=/opt/angr-venv/bin/python   # any Python 3.11+
"$PYTHON" -m routea.cave build \
  --elf fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf \
  --contract fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json \
  --cave 0x4018e9 --cave-size 1815 \
  --out candidate.elf --manifest edit-manifest.json --scope-authorized
```

Host versions used for the schema-2 manifest and candidate check:

| Tool | Version |
|---|---|
| Python | 3.11.8 |
| pyelftools | 0.33 |
| capstone | 5.0.9 |
| pydantic | 2.14.1 |
| network | not used |
| compiler / LIEF | not used by the primary recipe |

The `routea` CLI uses pyelftools + capstone only; LIEF is not required for the
cave build. LIEF 1.0.0 is still required for the independent Gate 3 structural
view (item 3), which is not part of this build recipe.

## Schema-2 edit manifest

`routea/out/edit-manifest.json` now contains:

- `displaced`: call-site `original_hex` `e8c7fdffff`, `new_hex` `e8e0050000`;
- `added`: code/data intervals with file offsets, sizes, SHA-256;
- `intervals.changed` / `intervals.added`;
- `header_changes.rx_load`: program-header file offset, `p_offset`, old/new
  `filesz`/`memsz`, align, page congruence, overlap check, beyond-original check;
- `writer`: `write(2, msg, 42)` syscall;
- `termination`: `exit_group(1)`;
- `tool_versions` and `edits`/`mappings`/`audit`.

The manifest does not change the candidate bytes; `c4a159…` is unchanged.
