from pathlib import Path

import lief

from app.services.pe_repair import patch_pe_call_site

ROOT = Path(__file__).resolve().parents[1]
PE = ROOT / "fixtures" / "pe" / "cli-64.exe"


def test_pe_call_site_is_redirected_and_reparsed():
    if not PE.is_file():
        return
    patched, report = patch_pe_call_site(PE.read_bytes(), b"\xC3")
    assert patched is not None, report.limitations
    assert report.status == "patched"
    assert report.section == ".brfix"
    reparsed = lief.PE.parse(list(patched))
    assert reparsed is not None
    assert reparsed.get_section(".brfix") is not None
    assert report.patched_sha256 != report.original_sha256
