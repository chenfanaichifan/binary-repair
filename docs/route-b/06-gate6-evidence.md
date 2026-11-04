# Gate 6 concrete crash evidence (2026-10-20)

**Status:** concrete counterexample **accepted partial**; symbolic detection is still
**pending V4**. This page does not claim that gate 6 is complete.

## 1. Identity

| Item | Value |
|---|---|
| Binary | `original.elf`, 26,792 B |
| SHA-256 | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| Guest | Ubuntu 24.04.5 LTS, kernel 6.8.0-147-generic, x86_64 |
| ASLR | `randomize_va_space=2` |
| Raw evidence | `07-gate6-crash-evidence.txt`, SHA-256 `4bab2214e5a17272bb32c20972e3d9ccc422c93e9853cbf89346dbbdf5eb16d9` |
| Summary | `gate6-crash-summary.md`, SHA-256 `cffa8b95ff51774bf55e36fa6e151279c29021215974b14a098241cc21e1801c` |

## 2. Reproduction

```bash
ARG=$(python3 -c "import sys; sys.stdout.write('A'*100)")
./original.elf "$ARG"
echo $?        # 139 (SIGSEGV), consistent 5/5 times
```

## 3. Coverage proof (breakpoint after strcpy returns)

`strcpy` returns at `0x401309`; at that moment:

| Observation | Value |
|---|---|
| `dest` | `0x7fffffffe920` |
| `rbp` | `0x7fffffffe960` |
| `rbp - dest` | **64 bytes** |
| `[rbp]` (saved rbp) | `0x4141414141414141` |
| `[rbp+8]` (return address) | `0x4141414141414141` |

The 50-byte buffer sits 64 bytes away from saved rbp; a 100-byte input (101 including the
NUL) runs past the buffer and exactly overwrites saved rbp and the return address.

## 4. Failure

```text
SIGSEGV at 0x401317 (ret)
rip  0x401317  <..._badSink+103>   ; ret
rsp  0x7fffffffe968                ; return slot
rbp  0x4141414141414141            ; already popped by leave
```

`leave` at `0x401316` has already loaded the attacker bytes into `rbp`; `ret` at `0x401317`
tries to return to `0x4141414141414141`, and the process dies.

## 5. What is proven and what is not

Proven:

- the `0x4012b0` sink has a binary-level OOB write;
- the write reaches saved rbp / the return address;
- a 100-byte input crashes deterministically 5/5 times (exit 139);
- the input is invalid under the frozen oracle (100 > 49).

Does not prove:

- that a repair candidate is safe (V3 is a separate matter);
- symbolic reachability of the OOB path (V4, toolchain missing);
- any conclusion about other inputs/binaries/in general.

## 6. Relationship to V3

- Gate 6 is **detection**: it proves that the original program really has the vulnerability;
- V3 is the **concrete behaviour after repair**: valid stays valid, invalid takes the exact error path;
- the original program's manifest 4/6 is V0 behavioural evidence, not gate 6.

V3's manifest/contract assertions live in `tests/test_fixture_v3_manifest.py`; the concrete
part of gate 6 has been accepted by member 4, and the symbolic part awaits the V4 environment.
