# Route A strategy C — cave probe result

**Date:** 2026-10-22
**Run:** GitHub Actions `routea-cave-probe`, run `39756078737`
**Result:** **6/6 repaired cases pass** on a disposable Ubuntu 24.04 runner.
This is a **probe**, not a formal Gate 3 pass: the scope ruling for the 5-byte call
replacement, p_filesz extension and exact-stderr data is still required.

## 1. Identity

| Item | Value |
|---|---|
| Original | `original.elf`, 26,792 B, SHA-256 `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| Patched | `routea/out/cave-probe.elf`, 26,792 B, SHA-256 `f3cb9cbb503fb0d47ebebab7053fa2ed37b7876ffe5122157d31fefc783f9fa7` |
| Function | `..._badSink` @ `0x4012b0`, 104 B |
| Call site | `0x401304`, 5-byte `call strcpy@plt 0x4010d0` |
| Cave | `0x4018e9`–`0x401fff`, 1,815 zero bytes already in the file |

## 2. Edits

- redirect the whole 5-byte call: `e8 e0 05 00 00` → cave `0x4018e9`;
- place 72-byte guard + 42-byte exact stderr at `0x4018e9`;
- extend the RX `PT_LOAD` (`0x401000`, offset `0x1000`) `p_filesz`/`p_memsz`
  from `0x8e9` to `0x1000`; no new segment;
- no new relocation, no new PLT (`fprintf@0x401120`, `stderr@0x404080` already there);
- harness `0x401256–0x4012af` unchanged; no W+X segment.

Static audit: all checks true (`rx_extended`, `no_new_segments`, `relocations_unchanged`,
`no_wx`, `redirect_bytes`, `cave_code`, `message_bytes`, `harness_unchanged`).

## 3. Runtime (6/6)

| Case | Input | Result |
|---|---:|---|
| valid-empty | 0 B | exit 0, `\n`, stderr empty |
| valid-smallest | 1 B | exit 0, `A\n` |
| valid-typical | 10 B | exit 0, `A…\n` |
| valid-maximum | 49 B | exit 0, `A…\n` |
| invalid-first | 50 B | **exit 1, stdout empty, exact 42-byte stderr** |
| invalid-longer | 100 B | **exit 1, stdout empty, exact 42-byte stderr** |

`manifest-repaired.json`: `passed=6, total=6, repaired_pass=true`.

## 4. Status

| Item | Status |
|---|---|
| Cave is actually file-loaded after p_filesz extension | **measured yes** |
| 6-case repaired behaviour | **measured PASS** |
| Gate 3 formal | **CONDITIONALLY FEASIBLE → measured PASS; awaiting scope sign-off** |
| Gate 4 formal | **NOT RUN** on member3 VM; supplementary GitHub run PASS |
| Gate 6 symbolic | **NOT RUN** (V4) |

If the scope ruling rejects the 5-byte call replacement, p_filesz extension or
exact-stderr data in the cave, this probe is **UNSUPPORTED**, not a pass.

## 5. Evidence

- `routea/out/cave-probe.elf` — patched binary
- `routea/out/edit-manifest.json` — edits/mappings/header changes
- `routea/out/audit.json` — static checks
- `routea/out/manifest-repaired.json` — 6/6 runtime
- `routea/out/readelf-audit.txt` — independent readelf (LOAD RX size `0x1000`, no W+X)
- `.github/workflows/routea-probe.yml` — reproducible run
