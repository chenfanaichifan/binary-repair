# M5 Route A candidate handoff — c4a159…aa82

This directory is the option-1 delivery: the patched ELF **and** a standalone
deterministic regenerator with its input and contract.

| Item | Value |
|---|---|
| Original | `original.elf`, 26,792 B, SHA-256 `aa428157…8393` |
| Candidate | `candidate.elf`, 26,792 B, SHA-256 `c4a15921…aa82` |
| Contract | `contract.json`, canonical SHA-256 `24bfe568…4e37`; entry 1 says **0x401309**; refined CET/seccomp assumptions |
| Provenance | GitHub Actions run `39756691896` (supplementary; not formal VM) |
| Formal Gate 3 | still **CONDITIONALLY FEASIBLE** until M3 reruns in isolation |

## Regenerate

```bash
python3 regen_c4a159.py original.elf /tmp/candidate-c4a159.elf
sha256sum /tmp/candidate-c4a159.elf
# c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82
```

The script is stdlib-only and fails closed on either hash. It patches:
`0x401304` call → `0x4018e9`; 71 B guard + 42 B exact stderr; RX `p_filesz/memsz`
`0x8e9 -> 0x1000`; no new segment/relocation.

## Run in the formal VM

M3 can run `candidate.elf` directly (schema-2 edit manifest included) (chmod +x if needed) through the frozen
`valid.json` / `invalid.json` case-id wrapper. Expected: valid 4 cases preserved;
invalid 50/100 exit 1, empty stdout, exact 42-byte stderr; 6/6.

## Contract note

If your checkout still says `0x401308`, it is stale. Main `8199eca` and this
handoff both say `0x401309`; canonical hash is
`24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37`.
