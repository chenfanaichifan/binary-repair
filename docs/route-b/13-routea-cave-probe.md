# Route A strategy C — cave probe result (six-entry contract)

**Date:** 2026-10-22
**Run:** GitHub Actions `routea-cave-probe`, run `39756691896`
**Result:** **6/6 repaired cases pass** on disposable Ubuntu 24.04.
**Gate 3 status:** all three technical items exist (cave runtime probe, six-case run,
edit manifest); formal status is still **CONDITIONALLY FEASIBLE** until handoff-10
isolation evidence and scope sign-off. Gate 4 remains formal **NOT RUN**.

## 1. Identity

| Item | Value |
|---|---|
| Original | 26,792 B, SHA-256 `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| Patched | 26,792 B, SHA-256 `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` |
| Contract | `fixtures/.../contract.json`, six `authorized_edits`, SHA-256 `363f3575…8889` |
| Function | `..._badSink` @ `0x4012b0`, 104 B |
| Call site | `0x401304`, `e8 c7 fd ff ff` → `strcpy@plt 0x4010d0` |
| Cave | `0x4018e9`–`0x401fff`, 1,815 zero bytes |

## 2. Edits

- whole 5-byte call redirect: `e8 e0 05 00 00` → `0x4018e9`;
- 71-byte guard + 42-byte exact stderr at `0x4018e9` (message at `0x401930`);
- RX `PT_LOAD` at `0x401000`: `p_filesz`/`p_memsz` **0x8e9 → 0x1000**; same
  segment/page, no new `PT_LOAD`, no overlap;
- no new import/PLT/GOT/relocation; invalid path uses `write(2, msg, 42)` syscall
  and `exit_group(1)`; `allowed_calls` stays `("strcpy", "printLine")`;
- harness `0x401256–0x4012af` unchanged; no W+X.

Static audit: all true (`rx_extended`, `no_new_segments`, `relocations_unchanged`,
`no_wx`, `redirect_bytes`, `cave_code`, `message_bytes`, `harness_unchanged`).
`readelf -lW`: `LOAD 0x401000 filesz=0x1000 memsz=0x1000 R E`.

## 3. Runtime (6/6)

| Case | Input | Result |
|---|---:|---|
| valid-empty | 0 B | exit 0, `\n` |
| valid-smallest | 1 B | exit 0, `A\n` |
| valid-typical | 10 B | exit 0, `A…\n` |
| valid-maximum | 49 B | exit 0, `A…\n` |
| invalid-first | 50 B | exit 1, stdout empty, exact 42-byte stderr |
| invalid-longer | 100 B | exit 1, stdout empty, exact 42-byte stderr |

`manifest-repaired.json`: `passed=6, total=6, repaired_pass=true`.

## 4. Gate status

| Item | Status |
|---|---|
| cave mapped/executed | yes, measured |
| six-case repaired behavior | pass, measured |
| edit manifest | present (`routea/out/edit-manifest.json`) |
| Gate 3 formal | **CONDITIONALLY FEASIBLE** until isolation + scope sign-off |
| Gate 4 formal | **NOT RUN** on member3 VM; supplementary GitHub PASS |
| Gate 6 symbolic | **NOT RUN** (V4) |

The six-case run is gate-3 feasibility evidence, not V3 acceptance or repair proof.
`fprintf`/`stderr` are not used by the final cave; `write` syscall keeps
`allowed_calls` unchanged.

## 5. Evidence

- `routea/out/cave-probe.elf`
- `routea/out/edit-manifest.json`
- `routea/out/audit.json`
- `routea/out/manifest-repaired.json`
- `routea/out/readelf-audit.txt`
- `.github/workflows/routea-probe.yml`
