# Route A candidate handoff — c4a159…aa82

**Purpose:** resolve the Gate 3 contradiction by delivering both the candidate
ELF and a deterministic regenerator to M3. The candidate was measured on GitHub
Actions (run `39756691896`, 6/6); it has **not** run in the formal VM yet, so
formal Gate 3 remains **CONDITIONALLY FEASIBLE** until M3's isolated run.

## Artifacts

| Item | SHA-256 |
|---|---|
| original.elf | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| candidate.elf | `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` |
| contract.json canonical | `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37` |
| handoff zip | `dist/m5-routea-c4a159-2026-10-22.zip`, SHA-256 `957d73d4…c108e` |

Contents: candidate ELF, original ELF, corrected contract, edit manifest, audit,
6/6 manifest result, readelf audit, standalone `regen_c4a159.py`, SHA256SUMS.

## Determinism

`regen_c4a159.py original.elf out.elf` reproduces `c4a159…` with stdlib only.
It rejects a wrong original or output hash. The contract branch target was
corrected to `0x401309` (text-only; the cave code already returns there), so the
candidate hash does not change.

## Formal VM run

M3 runs `candidate.elf` via the frozen case-id wrapper over `valid.json` /
`invalid.json`; M5 judges the raw outputs; M4 verifies isolation/image. If the
formal run rebuilds the ELF, record the new hash and do not reuse `c4a159…`.

## Contract

Main `8199eca` and this handoff say `0x401309`; canonical hash
`24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37`.
A checkout showing the old branch target is stale; use main `666a5dc` or newer.
