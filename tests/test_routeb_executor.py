from __future__ import annotations

import hashlib
import json
from pathlib import Path

from routeb.executor import make_bundle

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "fixtures/public/CWE121_src_char_declare_cpy_51b"
ORIGINAL = CASE / "original.elf"
CANDIDATE = ROOT / "routeb/out/gate4/roundtrip.elf"
FUNC = "CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sums_rows(outdir: Path) -> list[tuple[str, str]]:
    rows = []
    for line in (outdir / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        rows.append((digest, name.strip()))
    return rows


def _verify_sums(outdir: Path) -> bool:
    for line in (outdir / "SHA256SUMS").read_text().splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        if _sha(outdir / name.strip()) != digest:
            return False
    return True


def test_static_routeb_bundle(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    result = make_bundle(
        original=ORIGINAL, candidate=CANDIDATE, outdir=out,
        func=FUNC, mode="roundtrip",
    )
    assert result["static_audit"] is True
    assert result["runtime"]["state"] == "not_run"
    assert result["reproducibility"] == "not_run"
    views = sorted((out / "independent-views").glob("*.txt"))
    assert len(views) in (0, 5)

    rows = _sums_rows(out)
    assert result["file_count"] == len(rows)
    assert len(rows) == 7 + len(views)
    assert {p.relative_to(out).as_posix() for p in views} <= {name for _, name in rows}
    manifest = json.loads((out / "edit-manifest.json").read_text())
    assert manifest["schema_version"] == 2
    assert manifest["route"] == "route_b"
    assert manifest["original_sha256"] == "aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393"
    assert manifest["candidate_sha256"] == "decdcdb821bfe4c41a070b0a23a2f6497f46a92f439cb02a1e4139a82cde954b"
    assert manifest["runtime_manifest"]["state"] == "not_run"
    assert manifest["changed_file_intervals"]
    assert (out / "audit.json").exists()
    assert (out / "environment.json").exists()
    assert (out / "bundle-record.md").exists()
    assert not (out / "manifest-compare.json").exists()
    assert _verify_sums(out) is True
    assert (out / "bundle-sha256.txt").read_text().strip() == result["bundle_sha256"]


def test_build_twice_without_c_source_is_not_run(tmp_path: Path) -> None:
    result = make_bundle(
        original=ORIGINAL, candidate=CANDIDATE, outdir=tmp_path / "bundle",
        func=FUNC, mode="roundtrip", build_twice=True,
    )
    assert result["reproducibility"] == "not_run"
