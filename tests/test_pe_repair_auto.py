from pathlib import Path

from app.services.pe_repair import repair_pe, scan_pe_copy_calls

ROOT = Path(__file__).resolve().parents[1]
PE = ROOT / "fixtures" / "pe" / "cli-64.exe"


def test_pe_auto_is_explicit_when_no_copy_call_exists():
    if not PE.is_file():
        return
    scan = scan_pe_copy_calls(PE.read_bytes())
    if not scan["findings"]:
        patched, report = repair_pe(PE.read_bytes())
        assert patched is None
        assert report.status == "unsupported"
