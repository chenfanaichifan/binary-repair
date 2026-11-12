"""Binary assembly repair: real ELF -> trampoline -> ELF, static verification."""
from pathlib import Path

from app.domain.contracts import SecurityContract
from routea.assembly_repair import repair_binary

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "binary-repair"


def test_cave_repair_produces_verified_elf(tmp_path):
    contract = SecurityContract.from_dict(
        __import__("json").loads((ART / "contract.json").read_text(encoding="utf-8"))
    )
    out = tmp_path / "patched.elf"
    report = repair_binary(
        ART / "cave-original.elf",
        target="0x4012b0",
        cave_addr=0x4018E9,
        cave_size=0x71,
        contract=contract,
        out=out,
        report_path=tmp_path / "report.json",
        asm_dir=tmp_path / "asm",
    )
    assert report["passed"] is True
    assert report["changed"] is True
    assert out.is_file()
    assert report["original_sha256"] != report["patched_sha256"]
    assert report["audit"]["pass"] is True
    assert report["elf"]["no_wx"] is True
    assert (tmp_path / "asm" / "before.asm").is_file()
    assert (tmp_path / "asm" / "after.asm").is_file()
    assert len(report["rounds"]) == 3
    assert all(row["pass"] for row in report["rounds"])
