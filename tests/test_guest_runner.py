from pathlib import Path

from app.services.guest_runner import find_qemu, run_elf

ROOT = Path(__file__).resolve().parents[1]
VULN = ROOT / "artifacts/vuln-elf/vuln.elf"


def test_guest_runner_is_explicit_when_qemu_missing():
    result = run_elf(VULN, arch="x86_64", stdin=b"abc")
    if find_qemu("x86_64") is None:
        assert result.available is False
        assert "qemu" in (result.error or "").lower()
