# Gate 6 — concrete crash evidence on the candidate ELF

**Purpose:** the concrete counterexample half of gate 6 (Member 4). It shows
the original violation at the binary level: a 100-byte input overwrites the
saved frame and return address, and the process dies on `ret`.

**Status:** concrete evidence **passes**; symbolic detection is **pending V4**
(no angr/Z3/LIEF in the guest). This page does not claim gate 6 complete.

## 1. Identity

| Item | Value |
|---|---|
| Binary | `original.elf`, 26,792 bytes |
| SHA-256 | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| Guest | Ubuntu 24.04.5 LTS, kernel 6.8.0-147-generic, x86_64 |
| `randomize_va_space` | `2` (ASLR on for native runs) |
| Raw evidence | `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/07-gate6-crash-evidence.txt` |
| Raw evidence size | **3,750 bytes** (66 lines) |
| Raw evidence SHA-256 | `4bab2214e5a17272bb32c20972e3d9ccc422c93e9853cbf89346dbbdf5eb16d9` |
| GDB command record | `evidence/07-gdb-commands.txt`, 1,241 bytes, SHA-256 `b2fc52f7f5964b13ef2d0375c04b474acd55075b75ae631e8a12402ca3612242` |

## 2. Reproducer

```bash
ARG=$(python3 -c "import sys; sys.stdout.write('A'*100)")
./original.elf "$ARG"
echo $?        # 139 (SIGSEGV)
```

Five consecutive native runs: **5/5 exit 139**.

| Run | Exit code |
|---|---:|
| 1 | 139 |
| 2 | 139 |
| 3 | 139 |
| 4 | 139 |
| 5 | 139 |

The signal is deterministic; the stack addresses vary with ASLR, the overwrite
pattern does not.

### 2.1 GDB commands used

Full record: `evidence/07-gdb-commands.txt`. The core sequence:

```gdb
set pagination off
set confirm off
break *0x401309
run
x/gx $rbp
x/gx $rbp+8
x/8gx $rbp-0x40
continue
bt
info registers rip rsp rbp
x/1i $rip
x/2gx $rsp
```

Invocation: `gdb -batch -q -x /tmp/g6.gdb --args ./original.elf "$ARG"`.

### 2.2 Causal chain

1. `dest[50]` sits at `rbp-64` (`0x7fffffffe920` vs `0x7fffffffe960`).
2. `strcpy(dest, data)` with 100 × `A` writes 101 bytes, through `dest` and
   past its end to `[rbp]` and `[rbp+8]`.
3. Breakpoint at `0x401309` (immediately after `strcpy`, before `printLine`)
   shows `[rbp] = [rbp+8] = 0x4141414141414141`.
4. `printLine` runs; `leave` at `0x401316` loads `rbp = 0x4141...`; `ret` at
   `0x401317` loads `0x4141...` as the return address → SIGSEGV.

That is the chain M4 asked to verify: overwrite → corrupted saved frame →
`ret` to `0x4141414141414141`.

## 3. Overwrite proof (breakpoint immediately after `strcpy`)

`strcpy` returns at `0x401309`. At that point, before `printLine`:

| Observation | Value |
|---|---|
| destination buffer `dest` | `0x7fffffffe920` |
| frame pointer `rbp` | `0x7fffffffe960` |
| distance `rbp - dest` | **64 bytes** |
| saved `rbp` slot at `[rbp]` | `0x4141414141414141` |
| return-address slot at `[rbp+8]` | `0x4141414141414141` |
| first 64 bytes at `dest` | all `0x4141414141414141` |

The buffer is 50 bytes but the frame slot is 64 bytes away; a 100-byte input
(101 bytes including NUL) passes `dest` and lands exactly on the saved frame
pointer and return address. This is not a crash in `strcpy`; it is a
controlled overwrite of the return path.

## 4. Fault

```text
Program received signal SIGSEGV, Segmentation fault.
0x0000000000401317 in ..._badSink (...):33
#0  0x0000000000401317 in ..._badSink ...
#1  0x4141414141414141 in ??
rip  0x401317  <..._badSink+103>   ; ret
rsp  0x7fffffffe968                ; return slot
rbp  0x4141414141414141            ; already popped by leave
```

The faulting instruction is `ret` at `0x401317`; `leave` at `0x401316` has
already loaded the attacker bytes into `rbp`. Backtrace frame #1 is
`0x4141414141414141`, i.e. the overwritten return address. The process cannot
return to `main`.

## 5. What this proves and what it does not

Proves:

- a binary-level out-of-bounds write exists in the `0x4012b0` sink;
- the write reaches the saved frame pointer and return address;
- the crash is deterministic for a 100-byte input (5/5, exit 139);
- the input is `invalid` under the frozen oracle (100 > 49).

Does not prove:

- that a repair candidate is safe (V3 is separate);
- symbolic reachability of the OOB path (V4, blocked on the missing toolchain);
- any claim about other inputs, other binaries, or a population.

## 6. Gate 6 status

| Component | Status |
|---|---|
| concrete counterexample + crash record | **accepted partial** (Member 4) |
| symbolic detection on the original | **pending V4** — angr/Claripy/Z3 absent |
| gate 6 complete | **no** |

The manifest run against the original (4/6) is V0 behaviour evidence; it is
not gate 6 and is not counted as such.
