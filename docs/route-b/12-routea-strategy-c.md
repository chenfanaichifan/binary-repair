# Route A strategy C — cave + 5-byte call redirect

**Status (2026-10-22):** plan/code implemented in `routea/cave.py`; candidate
**not built**. Pending rulings: exact stderr data placement and whether replacing
the 5-byte `strcpy` call as a unit is allowed. Gate 3 is still **not pass**.

## 1. Why C

A pure 5-byte call swap to `strlen`/`strncpy` is not available: the binary has no
such PLT entry. Strategy C keeps the 5-byte instruction boundary and redirects the
existing `call strcpy@plt` at `0x401304` to a code cave. The cave owns the guard.

## 2. Layout

| Item | Value |
|---|---|
| call site | `0x401304`, 5 bytes `e8 c7 fd ff ff` → `strcpy@plt 0x4010d0` |
| redirect | `e8 rel32` → cave |
| cave | must be inside the R-X `PT_LOAD` (`0x401000`–`0x4018e9`); 1815 bytes reported by member3 |
| cave code | 72 bytes for the fixture (inline NUL scan, compare 49, `fprintf`, `exit_group`) |
| message | 42 bytes immediately after the code in the cave |
| new segment | none (strategy C) |
| new relocation | none |
| new PLT | **none needed**: `fprintf@0x401120` and `stderr@0x404080` already exist |

Cave entry state: `rdi = dest`, `rsi = data` (set by the original sequence at
`0x4012f6`–`0x401304`). The cave uses `r8`/`rcx` for the scan and preserves
`rdi`/`rsi` for the valid path.

## 3. Control flow

```text
0x401304: call cave
cave:
  mov r8, rsi
  xor ecx, ecx
  cmp byte [r8+rcx], 0
  je done
  inc rcx
  jmp scan
done:
  cmp rcx, 49
  jbe valid
  sub rsp, 8                 ; align before call (cave entry rsp%16=8)
  mov rdi, [stderr]
  lea rsi, [msg]
  xor eax, eax
  call fprintf@plt
  mov eax, 231; mov edi, 1; syscall   ; exit_group(1)
valid:
  jmp strcpy@plt             ; rsp%16=8 at entry, strcpy returns to 0x401309
```

No return address is rewritten; the original return address on the stack is
`0x401309`, so `jmp strcpy@plt` returns to the instruction after the call.

## 4. What is still undecided

1. **Cave start address / exact range.** "1815 bytes" is a size, not an address;
   the worker needs `--cave 0x...` and `--cave-size 1815`. Without the start it
   cannot check overlap or emit the redirect.
2. **Exact stderr data.** The cave places the 42-byte string in the same R-X
   region. If data-in-executable-region is not allowed, it needs an R-- segment
   (layout change), or Route A is unsupported.
3. **Call replacement.** Earlier constraint said `strcpy@0x401304–0x401308`
   "不得切開". Strategy C replaces the 5-byte call **as a whole** (not split).
   This must be explicitly allowed; otherwise C is not valid.
4. **New PLT.** Not needed for this binary; `fprintf` and `stderr` are already
   imported. If a future fixture lacks them, that is a new scope item.

## 5. Commands

```bash
python -m routea.cave plan \
  --elf fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf \
  --contract contract.json \
  --cave 0x... --cave-size 1815 --out cave-plan.json
```

`plan` does not write the candidate. A build is intentionally absent until the
three rulings above exist; `build_cave_patched(..., scope_authorized=True)` is
implemented and gated.

Tests: `tests/test_routea_cave.py` (redirect bytes, cave code, `jmp strcpy@plt`,
scope gate, audit rejects unpatched).
