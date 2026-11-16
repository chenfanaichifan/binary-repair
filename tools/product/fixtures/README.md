# Synthetic product-demo fixtures

`unsupported-bigendian-elf64.bin` is a **synthetic 64-byte big-endian ELF64
header only**. It is not a real program and contains no vulnerability. It exists
to demonstrate fail-closed behaviour: the deterministic matrix only rewrites
little-endian thin ELF i386/x86_64/arm64, PE i386/x86_64/arm64 and thin Mach-O
x86_64/arm64, so this input must return `unsupported` with **no candidate
bytes**.

Regenerate deterministically from `binary-repair-gui/` (Python 3.11+):

```bash
.venv/bin/python - <<'PY'
import struct
from pathlib import Path

out = Path("tools/product/fixtures/unsupported-bigendian-elf64.bin")
header = b"\x7fELF" + bytes([2, 2, 1, 0]) + b"\x00" * 8 + struct.pack(
    ">HHIQQQIHHHHHH", 2, 0x3e, 1, 0x400000, 64, 0, 0, 64, 56, 0, 0, 64, 0
)
assert len(header) == 64, len(header)
out.write_bytes(header)
PY
```

Expected SHA256:

```text
edab70b4d85df86a65e9732954db669fd4aad7b2347ec36e042d150aaa5b98c4
```

The demo refuses to run if the file is missing; committed benchmark samples are
SHA256-checked against `benchmark/phase8-v1/manifest.json` before use.
