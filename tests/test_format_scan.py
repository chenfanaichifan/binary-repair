"""PE/Mach-O inventory smoke tests using local, non-executed samples."""
from pathlib import Path

from app.services.format_scan import scan_macho, scan_pe

ROOT = Path(__file__).resolve().parents[1]
PE = ROOT / "fixtures" / "pe" / "cli-64.exe"
MACHO = ROOT / "fixtures" / "macho" / "3D_Image_Toolkit"


def test_pe_scan_metadata():
    if not PE.is_file():
        return
    out = scan_pe(PE.read_bytes())
    assert out["format"] == "pe"
    assert "AMD64" in out["arch"]
    assert out["sections"]
    assert out["supported"] is False


def test_macho_scan_metadata():
    if not MACHO.is_file():
        return
    out = scan_macho(MACHO.read_bytes())
    assert out["format"] == "macho"
    assert "ARM64" in out["arch"]
    assert out["segments"]
    assert out["supported"] is False
