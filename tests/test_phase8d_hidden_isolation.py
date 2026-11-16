"""Phase-8D hidden isolation audit tests (fake roots only; never touch real hidden bytes)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
import audit_hidden_isolation as audit_mod  # noqa: E402


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fake_repo(tmp_path: Path) -> tuple[Path, Path, dict]:
    repo = tmp_path / "repo"
    private = tmp_path / "private-root"
    (repo / "benchmark/phase8c").mkdir(parents=True)
    (repo / "artifacts/phase8c-hidden-2026-11-16").mkdir(parents=True)
    (private / "bin").mkdir(parents=True)
    (private / "poc").mkdir()
    (private / "reference").mkdir()

    manifest_path = repo / "benchmark/phase8c/manifest.json"
    manifest_path.write_text(json.dumps({"kind": "benchmark_manifest_v2", "samples": []}),
                             encoding="utf-8")
    public_sha = _sha(manifest_path.read_bytes())
    commitment_sha = _sha(b"fake-commitment")
    ids = [hashlib.sha256(f"hidden-sample-{i}".encode()).hexdigest() for i in range(8)]
    samples = []
    material = {}
    commitment_samples = []
    for i, sample_id in enumerate(ids):
        binary = f"binary-{i}-unique".encode()
        path = private / "bin" / f"{sample_id}.bin"
        path.write_bytes(binary)
        binary_sha = _sha(binary)
        scope = "analysis_only" if i >= 6 else "runtime"
        samples.append({
            "sample_id": sample_id,
            "binary_sha256": binary_sha,
            "expected_scope": scope,
            "oracle": {"kinds": ["external_poc"] if scope == "runtime" else []},
        })
        material[sample_id] = {"binary_path": f"bin/{sample_id}.bin",
                               "oracle_path": None, "reference_fix_path": None}
        commitment_samples.append({"opaque_sample_id": sample_id,
                                   "opaque_binary_sha256": binary_sha})
    commitment = {
        "kind": "hidden_benchmark_commitment", "benchmark_id": "phase8c-hidden",
        "schema_version": 1, "sample_count": 8, "runtime_count": 6,
        "analysis_only_count": 2, "commitment_sha256": commitment_sha,
        "public_manifest_sha256": public_sha, "samples": commitment_samples,
    }
    (repo / "benchmark/phase8c/hidden-commitment.json").write_text(
        json.dumps(commitment), encoding="utf-8")
    private_manifest = {
        "kind": "phase8c_private_hidden_manifest", "schema_version": 1,
        "commitment_sha256": commitment_sha, "public_manifest_sha256": public_sha,
        "samples": samples, "material": material,
    }
    (private / "hidden-manifest.json").write_text(json.dumps(private_manifest), encoding="utf-8")
    aggregate = {
        "aggregate": {
            "sample_count": 8,
            "denominator": {"samples": 8, "executed": 8, "verification_attempted": 0},
            "verified_count": 0, "false_verified_count": 0,
            "rejected_count": 0, "status_counts": {"executed": 8},
        },
        "analysis_only": {"sample_count": 2},
    }
    (repo / "artifacts/phase8c-hidden-2026-11-16/aggregate.json").write_text(
        json.dumps(aggregate), encoding="utf-8")
    (repo / "benchmark/phase8c/results.json").write_text(json.dumps({
        "hidden_aggregate": aggregate["aggregate"],
    }), encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs/clean.md").write_text("no hidden material here\n", encoding="utf-8")
    os.chmod(private, 0o700)
    return repo, private, {"ids": ids, "commitment": commitment, "manifest": private_manifest}


def _audit(repo: Path, private: Path, monkeypatch, tracked=None):
    monkeypatch.setattr(audit_mod, "_git_tracked",
                        lambda _root: list(tracked or ["docs/clean.md"]))
    return audit_mod.audit(root=private, repo_root=repo)


def test_clean_private_root_passes_and_does_not_publish_hidden_identity(
    tmp_path, monkeypatch
):
    repo, private, fixture = _fake_repo(tmp_path)
    result = _audit(repo, private, monkeypatch)
    assert result["status"] == "ok", result["checks"]
    assert result["ok"] is True
    assert result["counts"] == {"sample_count": 8, "runtime_count": 6,
                                "analysis_only_count": 2, "material_entries": 8}
    encoded = json.dumps(result)
    assert str(private) not in encoded
    assert not any(sample_id in encoded for sample_id in fixture["ids"])
    assert result["cryptographic_isolation"] is False
    assert result["operational_isolation"] is True
    assert result["capability_promotion"] is False


def test_group_or_world_writable_root_fails_closed(tmp_path, monkeypatch):
    repo, private, _fixture = _fake_repo(tmp_path)
    os.chmod(private, 0o755)
    result = _audit(repo, private, monkeypatch)
    assert result["status"] == "fail"
    assert result["ok"] is False
    assert any(c["id"] == "root-owner-only-0700" and c["status"] == "failed"
               for c in result["checks"])


def test_symlink_root_is_rejected(tmp_path, monkeypatch):
    repo, private, _fixture = _fake_repo(tmp_path)
    link = tmp_path / "link-root"
    link.symlink_to(private, target_is_directory=True)
    result = _audit(repo, link, monkeypatch)
    assert result["status"] == "fail"
    assert any(c["id"] == "root-not-symlink" and c["status"] == "failed"
               for c in result["checks"])


def test_commitment_mismatch_fails_closed(tmp_path, monkeypatch):
    repo, private, _fixture = _fake_repo(tmp_path)
    manifest = json.loads((private / "hidden-manifest.json").read_text(encoding="utf-8"))
    manifest["commitment_sha256"] = "0" * 64
    (private / "hidden-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = _audit(repo, private, monkeypatch)
    assert result["status"] == "fail"
    assert any(c["id"] == "private-manifest-commitment" and c["status"] == "failed"
               for c in result["checks"])


def test_hidden_opaque_id_leak_in_public_file_fails(tmp_path, monkeypatch):
    repo, private, fixture = _fake_repo(tmp_path)
    (repo / "docs/leak.md").write_text("leaked " + fixture["ids"][0], encoding="utf-8")
    result = _audit(repo, private, monkeypatch,
                    tracked=["docs/clean.md", "docs/leak.md"])
    assert result["status"] == "fail"
    check = next(c for c in result["checks"]
                 if c["id"] == "no-hidden-id-or-material-in-public-files")
    assert check["status"] == "failed"
    assert result["public_leak_scan"]["findings"]
    # The audit output names the public file, never the hidden sample id.
    assert "docs/leak.md" in json.dumps(result["public_leak_scan"])
    assert fixture["ids"][0] not in json.dumps(result["public_leak_scan"])


def test_exact_hidden_binary_copied_to_public_file_fails(tmp_path, monkeypatch):
    repo, private, fixture = _fake_repo(tmp_path)
    source = next((private / "bin").glob("*.bin"))
    copied = repo / "docs/copied.bin"
    copied.write_bytes(source.read_bytes())
    result = _audit(repo, private, monkeypatch,
                    tracked=["docs/clean.md", "docs/copied.bin"])
    assert result["status"] == "fail"
    check = next(c for c in result["checks"]
                 if c["id"] == "no-hidden-binary-material-in-public-files")
    assert check["status"] == "failed"
    assert "docs/copied.bin" in json.dumps(result["public_leak_scan"])
    assert fixture["ids"][0] not in json.dumps(result["public_leak_scan"])


def test_aggregate_with_per_sample_fields_fails(tmp_path, monkeypatch):
    repo, private, _fixture = _fake_repo(tmp_path)
    path = repo / "artifacts/phase8c-hidden-2026-11-16/aggregate.json"
    aggregate = json.loads(path.read_text(encoding="utf-8"))
    aggregate["sample_id"] = "opaque"
    path.write_text(json.dumps(aggregate), encoding="utf-8")
    result = _audit(repo, private, monkeypatch)
    assert result["status"] == "fail"
    assert any(c["id"] == "aggregate-no-per-sample-fields" and c["status"] == "failed"
               for c in result["checks"])


def test_missing_private_root_is_fail_not_ok(tmp_path, monkeypatch):
    repo, _private, _fixture = _fake_repo(tmp_path)
    result = _audit(repo, tmp_path / "does-not-exist", monkeypatch)
    assert result["status"] == "fail"
    assert result["ok"] is False


def test_written_artifact_is_deterministic_and_checkable(tmp_path, monkeypatch):
    repo, private, _fixture = _fake_repo(tmp_path)
    result = _audit(repo, private, monkeypatch)
    out = tmp_path / "out"
    audit_mod.write_artifact(result, out)
    first = {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}
    audit_mod.write_artifact(result, out)
    second = {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}
    assert first == second
    assert audit_mod.check_artifact(out) == []
    data = json.loads((out / "isolation.json").read_text(encoding="utf-8"))
    assert data["status"] == "ok"
    assert data["no_hidden_content_published"] is True
    (out / "isolation.json").write_text("{}\n", encoding="utf-8")
    assert audit_mod.check_artifact(out)


def test_real_committed_isolation_artifact_checks():
    proc = __import__("subprocess").run(
        [sys.executable, str(ROOT / "scripts/audit_hidden_isolation.py"), "--check", "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["ok"] is True
