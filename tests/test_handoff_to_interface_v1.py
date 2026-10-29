from __future__ import annotations

from pathlib import Path

from scripts.handoff_to_interface_v1 import main as converter_main


def test_published_converter_entrypoint(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.txt").write_text("a\n", encoding="utf-8")
    (pkg / "handoff.json").write_text(
        '{"package_id":"P4","from":"M3","to":"M5","route":"gate4",'
        '"created_at":"2026-10-29T00:00:00+08:00","files":["a.txt"]}',
        encoding="utf-8",
    )
    (pkg / "SHA256SUMS").write_text("0" * 64 + "  a.txt\n", encoding="utf-8")
    out = tmp_path / "out"
    assert converter_main([str(pkg), "--out", str(out)]) == 0
    assert (out / "handoff.json").exists()
