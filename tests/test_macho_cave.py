from pathlib import Path

import lief

from app.services.macho_repair import add_macho_rx_section, patch_macho_call_site

ROOT = Path(__file__).resolve().parents[1]
MACHO = ROOT / "fixtures" / "macho" / "3D_Image_Toolkit"


def test_macho_add_rx_section_roundtrips():
    if not MACHO.is_file():
        return
    patched, report = add_macho_rx_section(MACHO.read_bytes(), b"\x90" * 16)
    assert patched is not None, report.limitations
    assert report.status == "written"
    parsed = lief.MachO.parse(list(patched)).at(0)
    assert next((s for s in parsed.sections if s.name == "__brfix"), None) is not None


def test_macho_call_is_redirected():
    if not MACHO.is_file():
        return
    # ARM64 NOP-like ret: ret
    patched, report = patch_macho_call_site(MACHO.read_bytes(), b"\xC0\x03\x5F\xD6")
    assert patched is not None, report.limitations
    assert report.status == "patched"
    assert report.section == "__brfix"
    assert lief.MachO.parse(list(patched)) is not None
