#!/usr/bin/env python3
"""Generate CAP1 archives for fixtures/hard-cases/vuln-capacity-param-x86_64.elf.

The synthetic fixture mirrors the reviewed defect class: a renderer with three
inlined destination range checks where the ``span`` branch uses the payload-pool
size instead of the output buffer size.  With ``out_size < data_size`` the
oversized ``span`` copy passes every check and overflows the output allocation;
the fixture has a guard word after the allocation and exits 1 with
``output guard corrupt``.

Usage: python3 fixtures/hard-cases/gen_capacity_archives.py <output-dir>
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

MAGIC = b"CAP1"
FLAG_SPARSE = 1


def write_archive(
    path: Path,
    *,
    flags: int,
    out_size: int,
    data_size: int,
    ops: list[tuple[int, int, int, int, int]],
    payload: bytes,
) -> None:
    assert len(payload) >= data_size
    body = b"".join(struct.pack("<IIIII", *op) for op in ops)
    path.write_bytes(
        MAGIC
        + struct.pack("<IIII", flags, out_size, data_size, len(ops))
        + body
        + payload[:data_size]
    )


def main(output_dir: str | Path) -> int:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = bytes(range(256)) * 8  # 2048 deterministic bytes

    # Valid archives: the repaired binary must behave exactly like the original.
    write_archive(out / "benign.marc", flags=0, out_size=32, data_size=32,
                  ops=[(0, 0, 0, 32, 0)], payload=payload)
    write_archive(out / "benign_sparse.marc", flags=FLAG_SPARSE, out_size=64,
                  data_size=1024, ops=[(1, 0, 0, 64, 0)], payload=payload)
    write_archive(out / "benign_fill.marc", flags=FLAG_SPARSE, out_size=64,
                  data_size=64, ops=[(2, 0, 0, 64, 0x5A)], payload=payload)
    write_archive(out / "ctrl_span_equal_sizes.marc", flags=FLAG_SPARSE,
                  out_size=16, data_size=16, ops=[(1, 0, 0, 16, 0)], payload=payload)

    # Differential controls: already rejected before the defect can trigger.
    write_archive(out / "ctrl_literal_dst_oob.marc", flags=FLAG_SPARSE,
                  out_size=16, data_size=64, ops=[(0, 8, 0, 32, 0)], payload=payload)
    write_archive(out / "ctrl_span_src_oob.marc", flags=FLAG_SPARSE,
                  out_size=16, data_size=64, ops=[(1, 0, 48, 32, 0)], payload=payload)
    write_archive(out / "ctrl_span_no_sparse.marc", flags=0, out_size=16,
                  data_size=16, ops=[(1, 0, 0, 8, 0)], payload=payload)

    # The PoC: dst+len (16+768=784) fits data_size (1024) but not out_size (64).
    write_archive(out / "poc_overflow.marc", flags=FLAG_SPARSE, out_size=64,
                  data_size=1024, ops=[(1, 16, 0, 768, 0)], payload=payload)

    for name in sorted(path.name for path in out.iterdir()):
        print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "capacity-archives"))
