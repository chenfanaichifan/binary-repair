"""PE32+ section writeback using a local sample; no execution."""
from pathlib import Path

import lief

from app.services.pe_repair import add_rx_section

ROOT = Path(__file__).resolve().parents[1]
PE = ROOT.parent / "tools/mutagen/.venv/lib/python3.11/site-packages/setuptools/cli-64.exe"


def test_add_rx_section_roundtrips_through_lief():
    if not PE.is_file():
        return
    code = b"\x90" * 16
    patched, report = add_rx_section(PE.read_bytes(), code)
    assert patched is not None, report.limitations
    assert report.status == "written"
    parsed = lief.PE.parse(list(patched))
    sec = parsed.get_section(".brfix")
    assert sec is not None
    assert len(sec.content) >= len(code)
    assert int(parsed.optional_header.sizeof_image) > 0x17000
