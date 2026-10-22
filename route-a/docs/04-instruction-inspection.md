# 04 — Instruction inspection

Work item 4. Status: **done** (2026-10-20). Function under test:
`CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink`
at `0x4012b0`, 104 bytes.

The annotated listing lives in this page. The old template asked for a separate
`reports/04-annotated-function.md`; `route-a/reports/` is retired
(`route-a/reports/README.md`) and evidence now lives with the fixture, so the
annotation is kept next to the reasoning it supports instead of in a second
file.

## Purpose

Read real disassembly of the sample and be able to say what each instruction
does at the vulnerable site, before proposing any patch.

## Commands

```bash
nm -S -C original.elf | grep -E "badSink| main$|printLine"
objdump -d --disassemble=CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink original.elf
objdump -d --disassemble=main original.elf
gdb -batch -q -ex "run $(printf "A%.0s" {1..100})" -ex bt \
    -ex "info registers rip rbp rsp" ./original.elf
```

## Annotated disassembly

Raw output: `evidence/02-objdump-badsink.txt`. Frame: `sub $0x50,%rsp`, so the
frame is 80 bytes.

| Address | Bytes | Instruction | What it does |
|---|---|---|---|
| `0x4012b0` | `f3 0f 1e fa` | `endbr64` | IBT landing pad; required because CET/IBT is enabled. Not the vulnerable instruction |
| `0x4012b4` | `55` | `push %rbp` | saves the caller's frame pointer at `rbp` (after the `push`) |
| `0x4012b5` | `48 89 e5` | `mov %rsp,%rbp` | frame base; saved `rbp` is at `[rbp]`, return address at `[rbp+8]` |
| `0x4012b8` | `48 83 ec 50` | `sub $0x50,%rsp` | reserves 80 bytes of frame (50 for `dest`, 14 of alignment/padding, 8 for the argument slot, 8 more for the saved area below `rbp`) |
| `0x4012bc` | `48 89 7d b8` | `mov %rdi,-0x48(%rbp)` | spills the `data` argument |
| `0x4012c0`–`0x4012f0` | — | seven zero-stores | initialise `dest`: 6 × `movq` (48 B) + 1 × `movw` (2 B) = **50 bytes at `rbp-0x40`**, which is exactly `char dest[50]` |
| `0x4012f6` | `48 8b 55 b8` | `mov -0x48(%rbp),%rdx` | `rdx = data` |
| `0x4012fa` | `48 8d 45 c0` | `lea -0x40(%rbp),%rax` | `rax = &dest` |
| `0x4012fe` | `48 89 d6` | `mov %rdx,%rsi` | 2nd SysV argument = source pointer |
| `0x401301` | `48 89 c7` | `mov %rax,%rdi` | 1st SysV argument = destination pointer |
| `0x401304` | `e8 c7 fd ff ff` | `call 4010d0 <strcpy@plt>` | **the unbounded copy**; 5 bytes, ends at `0x401308`. No length check precedes it |
| `0x401309` | `48 8b 45 b8` | `mov -0x48(%rbp),%rax` | reloads **`data`**, not `dest` |
| `0x40130d` | `48 89 c7` | `mov %rax,%rdi` | argument for `printLine` |
| `0x401310` | `e8 6b 00 00 00` | `call 401380 <printLine>` | prints the **source string**, so the overflow is invisible in stdout |
| `0x401315` | `90` | `nop` | padding before the epilogue |
| `0x401316` | `c9` | `leave` | `mov %rbp,%rsp; pop %rbp` — restores the **corrupted** saved `rbp` |
| `0x401317` | `c3` | `ret` | pops the **corrupted** return address; this is where the 100-byte run dies (`rip = 0x401317` in `04-gdb-crash-100.txt`) |

## Frame map

```text
rbp+0x08   saved return address      <- reached by a write of length >= 72
rbp+0x00   saved rbp                 <- reached by a write of length >= 64
rbp-0x0e   end of dest (50 bytes)    <- byte 50 of the write lands here
rbp-0x40   dest[0]
rbp-0x48   spilled `data` pointer
```

Two distances matter and are easy to conflate:

- `&dest` → saved `rbp` = `0x40` = **64 bytes**. A 50–63 byte input overruns
  `dest` into the padding but does **not** reach the saved frame pointer, so
  it produces **no crash** — measured: length 50 exits 0 with a silent
  one-byte-over-capacity write.
- `&dest` → saved return address = **72 bytes**. Length 100 reaches it and
  segfaults.

This is why the contract boundary (50) and the crash boundary (64+) differ: the
contract protects the object, the crash protects the frame.

## Things recorded while reading

- [x] Prologue reserves `0x50` bytes.
- [x] `%rdi` carries the destination, `%rsi` the source, per SysV x86-64.
- [x] The copy is a real call to `strcpy@plt` at `0x4010d0`, not an inlined
      loop.
- [x] Buffer-to-saved-frame distance is 64 bytes; buffer-to-return is 72.
- [x] There is **no length check** before the copy — the vulnerability.
- [x] Candidate patch site boundaries: the `call` spans `0x401304`–`0x401308`;
      the next instruction starts at `0x401309`. A patch must not split those
      five bytes.
- [x] Branch reach: the only transfers inside the function are the calls to
      `strcpy@plt` (`0x401304`) and `printLine` (`0x401310`); no conditional
      branches, so a guard inserted at the site only needs to jump to a new
      block and back, or to the epilogue at `0x401316`.
- [x] Live registers at `0x401304`: `rdi = &dest`, `rsi = data`, `rdx = data`,
      `rax = &dest`; `rcx`, `r8`–`r11` are caller-saved and unconstrained by
      this function, so a guard may clobber them but must preserve nothing
      here.

## Notes on reading disassembly

- `endbr64` at the function start is expected with CET and is not the
  vulnerable instruction.
- The binary is non-PIE (`ET_EXEC`), so every address above is absolute and
  reproducible; no `%rip`-relative relocation arithmetic is needed for this
  function.
- Always keep the raw bytes for instructions you intend to modify.

## Gaps

- The 50–63 byte range is inferred from the frame layout, and length 50 was
  measured to exit 0; lengths 51–63 were **not** run one by one. The stated
  "no crash before 64" is a layout argument plus the measured endpoints, not a
  full sweep.
- The crash boundary (64) was not measured directly either; the measured crash
  is at length 100 and the measured non-crash at 50.

## Evidence

- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/02-objdump-badsink.txt`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/02-objdump-main.txt`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/02-symbols.txt`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/04-gdb-crash-100.txt`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/03-run-boundary.txt`
