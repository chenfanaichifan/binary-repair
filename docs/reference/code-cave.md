# ELF code cave / new PT_LOAD

`app/services/code_cave.py` adds an **R-X PT_LOAD** and writes machine code
directly into it.  No assembly text is reassembled.

## Implemented wrapper

For a `strcpy(dst, src)` call where `dst` is a stack buffer of known capacity:

```asm
mov rcx, capacity
loop:
  mov al, [rsi]
  test al, al
  jz done
  dec rcx
  jz overflow
  mov [rdi], al
  inc rdi
  inc rsi
  jmp loop
done:
  mov byte [rdi], 0
  ret
overflow:
  write(2, "copy exceeds capacity\n", ...)
  exit(1)
```

The original `call strcpy` is replaced by a `call` to the cave.

## Segment behavior

- Prefer a new `PT_LOAD` at a page-aligned file offset/virtual address;
- extend the last executable `PT_LOAD` when the program-header table has no room;
- patch only the 5-byte `E8 rel32` call;
- no relocations are added (the wrapper is position-independent within the
  existing image);
- RX only; never RWX.

## Reproducible test

`tests/test_code_cave.py` builds a tiny ELF with a stack buffer and a `strcpy`
call, injects the cave, then runs the patched ELF under Unicorn:

```text
strcpy short  -> exit 0, buffer intact
strcpy 32     -> exit 1, "copy exceeds capacity", stack sentinel intact
strcat short  -> exit 0, buffer intact
strcat 32     -> exit 1, "concat exceeds capacity", stack sentinel intact
ET_DYN/PIE style image also passes the cave/runtime test
```

Actual result:

```text
method: new-pt-load
wrapper: strcpy-guard
```

## Limits

- x86-64 ELF only;
- wrappers implemented: `strcpy`, `strcat`; `sprintf` still needs format-aware work;
- call-site capacity must be recoverable from a nearby stack allocation;
- multiple call sites need multiple caves or a dispatcher;
- relocation-aware rewriting for PIE/shared libraries is still future work.


## Engine integration

`binary_repair_engine.repair_elf()` now runs a second pass:
`scan_elf()` finds patchable `strcpy`/`strcat` stack-destination calls, then
`_apply_copy_caves()` injects the wrapper and patches the call.  The returned
report contains `kind=code_cave` findings and a cave-specific mode.
