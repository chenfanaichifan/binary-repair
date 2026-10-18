# 04 — Instruction inspection

Work item 4. Status: ☐ not started

## Purpose

Read real disassembly of the sample and be able to say what each instruction
does at the vulnerable site, before proposing any patch.

## Workflow

1. Locate the vulnerable function symbol:
   ```bash
   nm -C samples/<sample>.elf | grep -i <name>
   ```
2. Disassemble only that function:
   ```bash
   objdump -d --no-show-raw-insn samples/<sample>.elf \
     | sed -n '/<function>:/,/^$/p'
   ```
3. Disassemble with bytes, to keep instruction encodings visible:
   ```bash
   objdump -d samples/<sample>.elf | sed -n '/<function>:/,/^$/p'
   ```
4. Note the call to the copying function (`strcpy`/`memcpy`/`sprintf`/...), the
   destination buffer address, and how far the buffer is from the saved return
   address / saved frame pointer.

## Things to record while reading

- [ ] Function prologue: how much stack is reserved (`sub $0x..,%rsp`).
- [ ] Caller-provided arguments: which register holds the destination, which the
      source, in the SysV x86-64 convention (`%rdi`, `%rsi`, ...).
- [ ] The copy itself: call target, or inlined loop.
- [ ] Buffer-to-return-address distance (bytes).
- [ ] Any length check before the copy — or the absence of one.
- [ ] Instruction boundaries of the candidate patch site (must not split an
      instruction).
- [ ] Branch reach: are the nearby branch targets inside the same function?

## Notes on reading disassembly

- `endbr64` at function start is expected with modern toolchains; it is not the
  vulnerable instruction.
- Position-independent code uses `%rip`-relative operands; a copied or moved
  instruction with a `%rip` operand changes meaning if relocated.
- Always keep the raw bytes for instructions you intend to modify.

## Evidence to save under `reports/`

- `reports/04-nm-function.txt`
- `reports/04-objdump-function.txt`
- `reports/04-annotated-function.md` — the disassembly with your line-by-line notes
