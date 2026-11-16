"""Product demo tests: CLI structure and fail-closed behaviour only.

These tests do not assert repair quality and never run the runtime oracle
(no Lima/guest execution, no network, no model). They cover:

* the demo fixture registry and its expectations;
* the synthetic unsupported negative control: refused, no candidate bytes;
* the export fail-closed downgrade: a "verified" claim without independent
  verification is presented as NOT_VERIFIED and reported as a violation;
* the deterministic-only promise by source inspection (no AI client import,
  no environment/API-key access) plus the run-demo.sh entry point.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_DIR = ROOT / "scripts" / "product"
DEMO = PRODUCT_DIR / "demo_repair.py"
EXPORT = PRODUCT_DIR / "export_report.py"
RUN_DEMO = ROOT / "tools" / "product" / "run-demo.sh"
BUILDER = PRODUCT_DIR / "build_delivery_package.py"
NEGATIVE_FIXTURE = (
    ROOT / "tools" / "product" / "fixtures" / "unsupported-bigendian-elf64.bin"
)
FIXTURE_IDS = {"strcpy-stack-x86_64", "marcx-capacity", "unsupported-bigendian"}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(*args: str, cwd: Path = ROOT, timeout: int = 240) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_fixture_registry_shape() -> None:
    module = _load(DEMO, "demo_repair_registry")
    assert set(module.FIXTURES) == FIXTURE_IDS
    assert module.FIXTURES["strcpy-stack-x86_64"]["expected"] == "verified"
    assert module.FIXTURES["marcx-capacity"]["expected"] == "verified"
    assert module.FIXTURES["unsupported-bigendian"]["expected"] == "refused"
    assert NEGATIVE_FIXTURE.is_file()
    assert NEGATIVE_FIXTURE.stat().st_size == 64


def test_cli_lists_fixtures() -> None:
    result = _run(str(DEMO), "--list")
    assert result.returncode == 0, result.stderr
    for fixture in FIXTURE_IDS:
        assert fixture in result.stdout


def test_unknown_fixture_is_usage_error() -> None:
    result = _run(str(DEMO), "not-a-fixture", "--out", "unused")
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "unknown fixture" in payload["error"]


def test_negative_control_is_refused_and_writes_evidence(tmp_path: Path) -> None:
    outdir = tmp_path / "demo"
    result = _run(str(DEMO), "unsupported-bigendian", "--out", str(outdir))
    assert result.returncode == 0, result.stderr
    run = json.loads((outdir / "demo-run.json").read_text(encoding="utf-8"))
    assert run["execution"]["ai_used"] is False
    assert run["execution"]["network_used"] is False
    assert run["execution"]["deterministic_only"] is True
    assert len(run["fixtures"]) == 1
    fixture = run["fixtures"][0]
    assert fixture["status"] == "REFUSED"
    assert fixture["repair"]["disposition"] == "unsupported"
    assert fixture["repair"]["candidate_produced"] is False
    assert fixture["repair"]["candidate_sha256"] is None
    assert fixture["verification"]["independent_decision"] == "not_run"
    assert fixture["not_run"], "a refused result must carry explicit not_run reasons"

    report = (outdir / "REPORT.md").read_text(encoding="utf-8")
    assert "REFUSED" in report
    assert "2/24" in report and "0/8" in report
    assert "SHA256" in report
    assert "Fail-closed self-check" in report
    # The Chinese report is produced next to the English one (customer locale).
    zh_report = (outdir / "REPORT.zh.md").read_text(encoding="utf-8")
    assert "未验证" in zh_report or "拒绝" in zh_report
    assert "2/24" in zh_report and "0/8" in zh_report

    # Fail-closed: no candidate bytes anywhere in the evidence tree.
    assert not list(outdir.rglob("candidate.bin"))

    # Evidence index and checksums are internally consistent.
    index = json.loads((outdir / "EVIDENCE-INDEX.json").read_text(encoding="utf-8"))
    assert index["file_count"] >= 4
    for row in index["files"]:
        assert _sha256(outdir / row["path"]) == row["sha256"]
    sums = (outdir / "SHA256SUMS").read_text(encoding="utf-8").strip().splitlines()
    assert sums
    for line in sums:
        digest, relative = line.split("  ", 1)
        assert _sha256(outdir / relative) == digest


def _fake_run(status: str, decision: str, *, candidate: bool) -> dict:
    return {
        "schema_version": 1,
        "kind": "product_demo_run",
        "title": "fail-closed fixture",
        "generated_at": "2026-11-17T00:00:00Z",
        "elapsed_seconds": 0.1,
        "host": {"platform": "test", "machine": "test", "python": "test"},
        "execution": {
            "deterministic_only": True,
            "ai_used": False,
            "api_key_required": False,
            "network_used": False,
            "engine": "test-engine",
            "independent_verifier": {"status": "available", "path": "test-verifier"},
        },
        "fixtures": [
            {
                "fixture": "fake",
                "label": "fake",
                "expected": "verified",
                "status": status,
                "reason": "test",
                "input": {"path": "fake.bin", "sha256": "0" * 64},
                "scan": {},
                "repair": {
                    "disposition": "verified_patch",
                    "candidate_produced": candidate,
                    "candidate_sha256": ("1" * 64) if candidate else None,
                    "false_verified": False,
                    "deterministic_claim_withdrawn": False,
                },
                "verification": {
                    "independent_decision": decision,
                    "oracle_status": "not_run",
                },
                "checks": [
                    {"id": "independent_verification", "required": True,
                     "status": "not_run", "detail": "test"}
                ],
                "limitations": ["test limitation"],
                "not_run": ["independent verification not_run: test"],
                "evidence_root": "evidence/fake",
            }
        ],
        "boundary": {
            "public_benchmark": "2/24 verified (8.3%)",
            "hidden_benchmark": "0/8 verified",
            "not_claimed": ["arbitrary binary repair"],
        },
    }


def test_export_downgrades_unverified_verified_claim(tmp_path: Path) -> None:
    (tmp_path / "demo-run.json").write_text(
        json.dumps(_fake_run("VERIFIED_WITHIN_SCOPE", "not_run", candidate=True)),
        encoding="utf-8",
    )
    result = _run(str(EXPORT), str(tmp_path), "--json")
    assert result.returncode == 2, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["statuses"]["fake"] == "NOT_VERIFIED"
    assert payload["fail_closed"]["issues"], "a false verified claim must be reported"
    report = (tmp_path / "REPORT.md").read_text(encoding="utf-8")
    assert "FAILED" in report
    assert "claims verified but independent decision is 'not_run'" in report


def test_export_reports_explicitly_failed_fixture(tmp_path: Path) -> None:
    # An ERROR fixture is not a fail-closed violation (no false claim is made):
    # the report must present it as ERROR and still write the evidence index.
    run = _fake_run("ERROR", "not_run", candidate=False)
    run["fixtures"][0]["repair"]["disposition"] = "unsupported"
    run["fixtures"][0]["status"] = "ERROR"
    (tmp_path / "demo-run.json").write_text(json.dumps(run), encoding="utf-8")
    result = _run(str(EXPORT), str(tmp_path), "--json")
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["statuses"]["fake"] == "ERROR"
    assert (tmp_path / "REPORT.md").is_file()
    assert (tmp_path / "EVIDENCE-INDEX.json").is_file()


def test_export_language_option(tmp_path: Path) -> None:
    (tmp_path / "demo-run.json").write_text(
        json.dumps(_fake_run("REFUSED", "not_run", candidate=False)),
        encoding="utf-8",
    )
    result = _run(str(EXPORT), str(tmp_path), "--lang", "zh", "--json")
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["lang"] == "zh"
    assert (tmp_path / "REPORT.zh.md").is_file()
    assert (tmp_path / "report.zh.html").is_file()
    assert not (tmp_path / "REPORT.md").exists()
    zh = (tmp_path / "REPORT.zh.md").read_text(encoding="utf-8")
    assert "失败关闭" in zh
    bad = _run(str(EXPORT), str(tmp_path), "--lang", "fr")
    assert bad.returncode == 2
    assert "invalid choice" in bad.stderr or "unsupported report language" in bad.stdout


def test_deterministic_only_by_source_inspection() -> None:
    source = DEMO.read_text(encoding="utf-8") + EXPORT.read_text(encoding="utf-8")
    for forbidden in (
        "assistant_llm",
        "os.environ",
        "getenv",
        "requests.",
        "urllib.request",
        "http_client",
    ):
        assert forbidden not in source, f"product scripts must not use {forbidden!r}"
    assert '"ai_used": False' in DEMO.read_text(encoding="utf-8")
    assert '"network_used": False' in DEMO.read_text(encoding="utf-8")


@pytest.mark.skipif(sys.platform == "win32", reason="run-demo.sh is a POSIX shell tool")
def test_run_demo_shell_entry_point() -> None:
    assert RUN_DEMO.is_file()
    assert RUN_DEMO.stat().st_mode & 0o111, "run-demo.sh must be executable"
    syntax = subprocess.run(
        ["bash", "-n", str(RUN_DEMO)], capture_output=True, text=True, timeout=60
    )
    assert syntax.returncode == 0, syntax.stderr
    listed = subprocess.run(
        ["bash", str(RUN_DEMO), "--list"], capture_output=True, text=True, timeout=120
    )
    assert listed.returncode == 0, listed.stderr
    for fixture in FIXTURE_IDS:
        assert fixture in listed.stdout


def test_delivery_package_builder(tmp_path: Path) -> None:
    outdir = tmp_path / "demo"
    outdir.mkdir()
    run = _fake_run("REFUSED", "not_run", candidate=False)
    (outdir / "demo-run.json").write_text(json.dumps(run), encoding="utf-8")
    (outdir / "REPORT.md").write_text("# report\n", encoding="utf-8")
    (outdir / "EVIDENCE-INDEX.json").write_text("{}\n", encoding="utf-8")
    (outdir / "evidence").mkdir()
    (outdir / "evidence" / "outcome.json").write_text("{}\n", encoding="utf-8")
    (outdir / "evidence" / "original.bin").write_bytes(b"0" * (1024 * 1024))
    result = _run(str(BUILDER), str(outdir), "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    package = Path(payload["package"])
    assert package.is_file() and package.stat().st_size > 0
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
        for expected in ("REPORT.md", "manifest.json", "SHA256SUMS", "README.md", "COMMANDS.md"):
            assert expected in names
        assert "05-limitations/LIMITATIONS.md" in names
        assert not any(name.endswith(".bin") for name in names)
        manifest = json.loads(archive.read("manifest.json"))
        for row in manifest["files"]:
            assert _sha256_bytes(archive.read(row["path"])) == row["sha256"]
        assert manifest["excluded_binaries"], "the excluded binary must be recorded"


def test_delivery_package_requires_demo_run(tmp_path: Path) -> None:
    result = _run(str(BUILDER), str(tmp_path), "--json")
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
