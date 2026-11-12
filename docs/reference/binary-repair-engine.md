# Direct binary repair engine

## What it does

`app/services/binary_repair_engine.py` repairs an ELF **without converting it
to assembly text and reassembling it**:

```text
ELF bytes
  -> capstone decodes instructions for analysis only
  -> locate immediate read/write lengths and nearest sub rsp, N
  -> patch the imm32 in the original file bytes
  -> re-decode and verify the patched instruction
  -> emit patched ELF + JSON report
```

The original `.text` bytes are not regenerated.  No instruction is assembled
from text.

## CLI

```bash
.venv/bin/python scripts/repair_binary.py \
  artifacts/vuln-elf/vuln.elf \
  /tmp/vuln-patched.elf \
  --report /tmp/vuln-patched.json
```

For the known fixture it returns the reviewed **strict** binary.  For a modified
ELF with the same immediate pattern it returns a **bounds-only** patch.

Scan without writing:

```bash
.venv/bin/python scripts/repair_binary.py artifacts/vuln-elf/vuln.elf --scan-only
```

## API / GUI

`POST /api/binary/quick-repair` accepts an ELF and returns:

```json
{
  "ok": true,
  "patched_base64": "...",
  "report": {
    "mode": "strict" | "bounds-only" | "unsupported",
    "capacity": 16,
    "findings": [...],
    "limitations": [...]
  }
}
```

## Supported

- little-endian **ELF64 x86-64**;
- `.text` section;
- `sub rsp, N` followed by a syscall whose `edx` is an **immediate** larger than
  `N` (read/write);
- `call memcpy` with an immediate `edx` and a stack destination derived from
  `rdi = rsp` / `lea rdi, [rsp+off]`;
- ELF64 x86-64 format detection; PE/Mach-O are reported as unsupported rather
  than patched.

It patches the immediate in place.  That is a genuine binary-level fix for the
buffer length; it does **not** rewrite the whole control flow.

## Strict fixture

For the generated `vuln.elf` digest, the engine returns a separately reviewed
strict template:

```text
read loop up to EOF / 17
cmp total, 16
ja reject
write only total
exit 1 on >16
```

This closes the short-read disclosure and truncation semantics.

## Fail-closed

The engine returns `unsupported` and no output when:

- input is not ELF64 x86-64;
- `.text` cannot be parsed;
- read/write length is not an immediate;
- no `sub rsp` capacity is found;
- a patch would need a new segment, relocation, or code cave.

No arbitrary machine code is guessed.

## Why "any binary" is not one algorithm

Arbitrary binary repair needs:

- relocation/GOT/PLT rewriting;
- PIE and shared-library awareness;
- data/code separation and function boundaries;
- calling-convention and stack-frame recovery;
- code caves or new loadable segments;
- PE/Mach-O support;
- isolated runtime regression.

This engine covers a deliberately safe subset and keeps expanding by adding
verified patterns.  It does not claim universal automatic repair.

## Runtime verification

`app/services/x86_runtime.py` uses Unicorn to execute the ELF's own x86-64
instructions with modeled `read`/`write`/`exit` syscalls.  It checks:

- valid/boundary input echo;
- over-limit rejection;
- exit status;
- stack sentinel beyond the buffer;
- partial reads.

It is a test oracle, not a host sandbox.  Final acceptance still belongs in a
disposable x86-64 Linux guest.
