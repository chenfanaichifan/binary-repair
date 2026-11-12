# Intentionally vulnerable ELF (local test only)

`vuln.elf` is a minimal **x86-64 Linux** static ELF with one R-X `PT_LOAD`.
It uses raw syscalls and no libc.

## Vulnerability

```asm
sub rsp, 16          ; 16-byte stack buffer
xor eax, eax
xor edi, edi
mov rsi, rsp
mov edx, 256         ; VULNERABLE: 256-byte read into 16-byte buffer
syscall
```

Any input longer than 16 bytes overflows the stack buffer. The program then
writes 256 bytes from the stack, so the overwrite is observable in the output.

## Build

```bash
python3 build_vuln_elf.py
file vuln.elf
sha256sum vuln.elf
```

Current artifact:

```text
ELF 64-bit LSB executable, x86-64, statically linked, stripped
sha256: 363da163094bdb58f4ff43a93868ab03e5c4ea1e1587296fbb64037471639acd
size:   8576 bytes
```

## Test only in an isolated Linux guest

This host is macOS arm64 and cannot execute x86-64 Linux ELF directly.

```bash
# inside a disposable Linux x86-64 VM/container
printf 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA' | ./vuln.elf | xxd | head
```

Do not run this on a shared host. It is deliberately unsafe.

## What it is not

- not a real-world CVE;
- not a network service;
- not a complete exploit;
- not a claim that 16 bytes is a safe capacity (it is intentionally too small).

## Strict fixed variant

`vuln-strict-fixed.elf` fixes both the overflow and the residual
uninitialized-stack disclosure:

```asm
sub rsp, 32
read(0, rsp, 17)       ; one byte of over-read for detection
cmp rax, 16
ja reject
mov rdx, rax           ; write only bytes actually read
write(1, rsp, rdx)
...
reject:
write(2, "input too long...", 30)
exit(1)
```

Behavior:

| stdin | exit | stdout | stderr |
|---|---|---|---|
| 0..16 bytes | 0 | `input> ` + exact input | empty |
| 17+ bytes | 1 | `input> ` | `input too long (max 16 bytes)` |

No uninitialized stack bytes are written. The 17-byte read lands in a 32-byte
stack area, and a sentinel immediately beyond it remains intact.

Verified with Unicorn x86-64 emulation (syscalls modeled):

```text
0, 3, 16 bytes  -> exit 0, exact echo, sentinel intact
17, 32, 256     -> exit 1, exact stderr, sentinel intact
```

See [`strict-runtime-report.json`](strict-runtime-report.json).
The emulator is a test oracle, not a host sandbox.
