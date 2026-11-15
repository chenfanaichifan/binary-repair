"""Phase-8C C4: private hidden corpus builder + opaque public commitment tests.

All tests operate on ``tmp_path`` fake private roots and fake compilers/guest
validators.  They never read, write or require the Lead-provisioned real hidden
root (``$HOME/.binaryrepair/phase8c-hidden``) and never overwrite the committed
public commitment.  The builder is loaded as a module so its dependency
injection seams (``compile_func``/``validate_func``) can replace Zig and the
Lima guest with deterministic fakes; the schema/semantics checks use the real
C2 contracts and ``scripts/check_contract_schemas.py``.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Mapping

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_phase8c_hidden.py"
PUBLIC_MANIFEST = ROOT / "benchmark" / "phase8c" / "manifest.json"
COMMITMENT_SCHEMA = ROOT / "contracts" / "hidden-benchmark-commitment.schema.json"
SAMPLE_SCHEMA = ROOT / "contracts" / "ground-truth-sample-v2.schema.json"
PYTHON = sys.executable
FORBIDDEN_IMPORTS = (
    "import requests",
    "import urllib",
    "import socket",
    "from openai",
    "import openai",
    "anthropic",
    "import http.client",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


@lru_cache(maxsize=None)
def _hidden():
    spec = importlib.util.spec_from_file_location("_phase8c_hidden", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load scripts/build_phase8c_hidden.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=None)
def _public_manifest() -> dict:
    return json.loads(PUBLIC_MANIFEST.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _public_index() -> dict:
    return _hidden()._public_sample_index(_public_manifest())


def _fake_binary() -> bytes:
    """Unique opaque fake hidden payload (never byte-identical to public data)."""
    return b"FAKE-HIDDEN-ELF-PAYLOAD:" + hashlib.sha256(b"fake-hidden").digest()


def _fake_validation(index: int = 0) -> dict:
    return {
        "status": "fail",
        "runner": "limactl",
        "tier": "emulated_run",
        "executed": True,
        "original_expected_ok": True,
        "regression_expected_ok": True,
        "vulnerable_observed": True,
        "original_poc_case_count": 2,
        "original_regression_case_count": 1,
        "lock_attempt_count": 1,
        "reason": None,
        "evidence_sha256": _sha256(f"fake-validation-{index}".encode()),
    }


def _make_fake_root(
    tmp_path: Path,
    *,
    runtime_sources: list[str] | None = None,
    analysis_count: int = 2,
    commit: bool = True,
) -> dict:
    """Create a well-formed fake private root + public commitment under tmp_path."""
    hidden = _hidden()
    root = tmp_path / "hidden-root"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    hidden._ensure_private_layout(root)
    sources = runtime_sources or list(hidden.SOURCE_SPECS)
    samples: list[dict] = []
    material: dict[str, dict] = {}
    base_payload = _fake_binary()
    for index, source_key in enumerate(sources):
        source = hidden.SOURCE_SPECS[source_key]
        opaque = hidden.opaque_sample_id(f"fake-runtime-{source_key}")
        binary_rel = f"bin/{opaque}.bin"
        (root / binary_rel).write_bytes(
            base_payload + f":{index}:{source_key}".encode())
        binary_sha = _sha256_file(root / binary_rel)
        oracle = hidden.rebind_poc_manifest(
            hidden._source_poc_manifest(source_key), binary_sha)
        oracle_rel = f"poc/{opaque}.json"
        hidden._write_json_atomic(root / oracle_rel, oracle)
        reference_rel = f"reference/{opaque}.c"
        (root / reference_rel).write_text(
            f"/* fake reference fix for variant {index} */\n", encoding="utf-8")
        spec = {
            "target": "x86_64-linux-gnu",
            "optimization": "-O2" if index % 2 else "-O1",
            "static": bool(index % 2),
            "stripped": False,
            "split": "dev" if index < len(sources) // 2 else "validation",
            "compiler_version": "0.17.1",
        }
        samples.append(hidden._runtime_sample(
            spec=spec,
            source_key=source_key,
            public_sample=_public_index()[source["public_sample_id"]],
            opaque_id=opaque,
            binary_sha256=binary_sha,
            oracle_relative=oracle_rel,
            oracle_document=oracle,
            reference_relative=reference_rel,
            reference_sha256=_sha256_file(root / reference_rel),
            target={"kind": "symbol", "symbol": source["symbol"]},
            validation=_fake_validation(index),
        ))
        material[opaque] = {
            "binary_path": binary_rel,
            "oracle_path": oracle_rel,
            "reference_fix_path": reference_rel,
        }
    for index in range(analysis_count):
        source_key = list(hidden.SOURCE_SPECS)[index % len(hidden.SOURCE_SPECS)]
        source = hidden.SOURCE_SPECS[source_key]
        opaque = hidden.opaque_sample_id(f"fake-analysis-{index}")
        binary_rel = f"bin/{opaque}.bin"
        (root / binary_rel).write_bytes(b"MZfake-pe-image-" + bytes([index]))
        binary_sha = _sha256_file(root / binary_rel)
        spec = {
            "format": "pe",
            "arch": "x86_64",
            "bits": 64,
            "target": "x86_64-windows-gnu",
            "optimization": "-O2",
            "split": "dev" if index == 0 else "validation",
            "compiler_version": "0.17.1",
        }
        samples.append(hidden._analysis_sample(
            spec=spec,
            source_key=source_key,
            public_sample=_public_index()[source["public_sample_id"]],
            opaque_id=opaque,
            binary_sha256=binary_sha,
            target_symbol=source["symbol"],
            build_sha256=binary_sha,
        ))
        material[opaque] = {
            "binary_path": binary_rel,
            "oracle_path": None,
            "reference_fix_path": None,
        }
    manifest = hidden.compose_private_manifest(
        public_manifest_sha256=_sha256_file(PUBLIC_MANIFEST),
        samples=samples,
        material=material,
    )
    violations = hidden.validate_private_manifest_document(manifest, root)
    assert not violations, violations
    hidden._write_json_atomic(root / hidden.PRIVATE_MANIFEST_NAME, manifest)
    files = hidden._material_files(root, manifest) + [
        root / hidden.PRIVATE_MANIFEST_NAME]
    hidden._write_bytes_atomic(root / hidden.SUMS_NAME,
                               hidden._sums_payload(root, files))
    commitment = hidden.build_commitment(manifest)
    commitment_path = tmp_path / "hidden-commitment.json"
    if commit:
        hidden._write_json_atomic(commitment_path, commitment)
    return {
        "root": root,
        "manifest": manifest,
        "commitment": commitment,
        "commitment_path": commitment_path,
        "material": material,
        "samples": samples,
    }


def _run_check(fake: dict, *extra: str) -> subprocess.CompletedProcess:
    command = [
        PYTHON, str(SCRIPT), "--check",
        "--root", str(fake["root"]),
        "--commitment", str(fake["commitment_path"]),
        "--public-manifest", str(PUBLIC_MANIFEST),
        "--json", *extra,
    ]
    return subprocess.run(command, cwd=str(ROOT), capture_output=True,
                          text=True, timeout=120)


def test_commitment_is_deterministic_and_opaque(tmp_path: Path):
    fake = _make_fake_root(tmp_path)
    hidden = _hidden()
    first = hidden.build_commitment(fake["manifest"])
    second = hidden.build_commitment(fake["manifest"])
    assert first == second
    assert first["sample_count"] == 8
    assert first["runtime_count"] == 6
    assert first["analysis_only_count"] == 2
    assert first["created_at"] == hidden.FIXED_TIMESTAMP
    assert len(first["samples"]) == 8
    ids = [item["opaque_sample_id"] for item in first["samples"]]
    assert ids == sorted(ids)
    assert all(len(item) == 64 for item in ids)
    assert first["commitment_sha256"] == hidden.commitment_digest(
        hidden._strip_commitment_field(fake["manifest"]))
    text = hidden._canonical(first)
    assert "/" not in text and "\\" not in text


def test_commitment_validates_against_c2_schema_and_semantics(tmp_path: Path):
    jsonschema = pytest.importorskip("jsonschema")
    fake = _make_fake_root(tmp_path)
    commitment = fake["commitment"]
    schema = json.loads(COMMITMENT_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(commitment), key=str)
    assert not errors, [error.message for error in errors]
    hidden = _hidden()
    assert not hidden.validate_commitment_document(commitment)
    # Cross-field semantics from the repository checker agree.
    checker = hidden._checker_module()
    assert not checker._hidden_commitment_semantics(commitment)  # noqa: SLF001


def test_commitment_has_no_private_paths_slugs_or_extra_keys(tmp_path: Path):
    fake = _make_fake_root(tmp_path)
    commitment = fake["commitment"]
    text = json.dumps(commitment, ensure_ascii=True)
    for token in ("bin/", "poc/", "reference/", "reports/",
                  "hidden-manifest.json", str(fake["root"]), "fake-runtime",
                  "fake-analysis", "hidden-cwe"):
        assert token not in text
    allowed = {
        "schema_version", "kind", "benchmark_id", "hidden_version",
        "sample_count", "runtime_count", "analysis_only_count",
        "commitment_sha256", "public_manifest_sha256", "created_at",
        "samples", "limitations",
    }
    assert set(commitment) == allowed
    for item in commitment["samples"]:
        assert set(item) == {"opaque_sample_id", "opaque_binary_sha256"}
    hidden = _hidden()
    assert not hidden._leak_violations(commitment, fake["manifest"],
                                       fake["root"])


def test_private_manifest_matches_lead_hidden_contract(tmp_path: Path):
    fake = _make_fake_root(tmp_path)
    manifest = fake["manifest"]
    hidden = _hidden()
    assert manifest["kind"] == "phase8c_private_hidden_manifest"
    assert manifest["schema_version"] == 1
    assert manifest["benchmark_id"] == "phase8c-hidden"
    assert set(manifest) == set(hidden.PRIVATE_MANIFEST_KEYS)
    assert {sample["sample_id"] for sample in manifest["samples"]} == \
        set(manifest["material"])
    for entry in manifest["material"].values():
        assert set(entry) == {"binary_path", "oracle_path",
                              "reference_fix_path"}
        for relative in entry.values():
            if relative is None:
                continue
            assert not Path(relative).is_absolute()
            assert ".." not in Path(relative).parts
    assert manifest["commitment_sha256"] == \
        fake["commitment"]["commitment_sha256"]


def test_samples_validate_against_c2_sample_contract(tmp_path: Path):
    jsonschema = pytest.importorskip("jsonschema")
    fake = _make_fake_root(tmp_path)
    hidden = _hidden()
    schema = json.loads(SAMPLE_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    for sample in fake["manifest"]["samples"]:
        errors = sorted(validator.iter_errors(sample), key=str)
        assert not errors, [error.message for error in errors]
        assert not hidden.sample_semantics_violations(sample)


def test_analysis_only_samples_never_claim_runtime(tmp_path: Path):
    fake = _make_fake_root(tmp_path)
    analysis = [
        sample for sample in fake["manifest"]["samples"]
        if sample["expected_scope"] == "analysis_only"
    ]
    assert len(analysis) == 2
    for sample in analysis:
        assert sample["oracle"]["kind"] == "analysis_only"
        assert sample["oracle"]["kinds"] == ["analysis_only"]
        assert sample["oracle"]["manifest_path"] is None
        assert sample["reference_fix"] is None
        assert sample["target"]["kind"] == "analysis_only"
        entry = fake["manifest"]["material"][sample["sample_id"]]
        assert entry["oracle_path"] is None
        assert entry["reference_fix_path"] is None


def test_runtime_oracle_manifests_are_rebound(tmp_path: Path):
    fake = _make_fake_root(tmp_path)
    for sample in fake["manifest"]["samples"]:
        if sample["expected_scope"] != "function":
            continue
        entry = fake["manifest"]["material"][sample["sample_id"]]
        oracle = json.loads((fake["root"] / entry["oracle_path"]).read_text(
            encoding="utf-8"))
        assert oracle["fixture_sha256"] == sample["binary_sha256"]
        assert oracle["format"] == "elf"
        assert oracle["arch"] == "x86_64"
        assert oracle["poc"] and oracle["regression"]
        assert sample["oracle"]["manifest_path"] == entry["oracle_path"]
        assert sample["reference_fix"]["path"] == entry["reference_fix_path"]


def test_check_passes_on_well_formed_fake_root(tmp_path: Path):
    fake = _make_fake_root(tmp_path)
    result = _run_check(fake)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["hidden_available"] is True
    assert payload["sample_count"] == 8
    assert payload["runtime_count"] == 6
    assert payload["analysis_only_count"] == 2
    assert payload["mode"] == "check"
    assert payload["violations"] == []
    text = json.dumps(payload)
    assert str(fake["root"]) not in text
    assert "/bin/" not in text and "reference/" not in text


def test_check_detects_binary_tamper(tmp_path: Path):
    fake = _make_fake_root(tmp_path)
    entry = fake["manifest"]["material"][fake["samples"][0]["sample_id"]]
    binary = fake["root"] / entry["binary_path"]
    binary.write_bytes(binary.read_bytes() + b"X")
    result = _run_check(fake)
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "violation"
    assert payload["hidden_available"] is False


def test_check_detects_oracle_manifest_tamper(tmp_path: Path):
    fake = _make_fake_root(tmp_path)
    runtime = [sample for sample in fake["samples"]
               if sample["expected_scope"] == "function"][0]
    entry = fake["manifest"]["material"][runtime["sample_id"]]
    oracle_path = fake["root"] / entry["oracle_path"]
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    oracle["fixture_sha256"] = "0" * 64
    oracle_path.write_text(json.dumps(oracle), encoding="utf-8")
    result = _run_check(fake)
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "violation"


def test_check_detects_private_manifest_tamper(tmp_path: Path):
    fake = _make_fake_root(tmp_path)
    manifest_path = fake["root"] / _hidden().PRIVATE_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["limitations"].append("tampered")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = _run_check(fake)
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "violation"


def test_check_detects_commitment_tamper(tmp_path: Path):
    fake = _make_fake_root(tmp_path)
    commitment_path = fake["commitment_path"]
    commitment = json.loads(commitment_path.read_text(encoding="utf-8"))
    commitment["runtime_count"] = 7
    commitment_path.write_text(json.dumps(commitment), encoding="utf-8")
    result = _run_check(fake)
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "violation"


def test_check_detects_sums_tamper(tmp_path: Path):
    fake = _make_fake_root(tmp_path)
    sums_path = fake["root"] / _hidden().SUMS_NAME
    lines = sums_path.read_text(encoding="utf-8").splitlines()
    lines[0] = "0" * 64 + "  " + lines[0].split("  ", 1)[1]
    sums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = _run_check(fake)
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "violation"


def test_check_rejects_extra_private_file(tmp_path: Path):
    fake = _make_fake_root(tmp_path)
    (fake["root"] / "bin" / "stale-extra.bin").write_bytes(b"stale")
    result = _run_check(fake)
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "violation"


def test_check_missing_root_is_not_run_never_pass(tmp_path: Path):
    fake = _make_fake_root(tmp_path)
    missing = tmp_path / "absent-root"
    command = [
        PYTHON, str(SCRIPT), "--check", "--root", str(missing),
        "--commitment", str(fake["commitment_path"]),
        "--public-manifest", str(PUBLIC_MANIFEST), "--json",
    ]
    result = subprocess.run(command, cwd=str(ROOT), capture_output=True,
                            text=True, timeout=120)
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "not_run"
    assert payload["hidden_available"] is False
    assert payload["violations"]


def test_check_missing_commitment_is_not_run(tmp_path: Path):
    fake = _make_fake_root(tmp_path, commit=False)
    result = _run_check(fake)
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "not_run"
    assert payload["hidden_available"] is False


def test_check_rejects_insecure_root_permissions(tmp_path: Path):
    fake = _make_fake_root(tmp_path)
    os.chmod(fake["root"], 0o755)
    result = _run_check(fake)
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "violation"
    assert payload["hidden_available"] is False


def test_check_binds_the_current_public_manifest(tmp_path: Path):
    fake = _make_fake_root(tmp_path)
    changed = tmp_path / "manifest-changed.json"
    payload = json.loads(PUBLIC_MANIFEST.read_text(encoding="utf-8"))
    payload["limitations"] = list(payload.get("limitations") or []) + ["changed"]
    changed.write_text(json.dumps(payload), encoding="utf-8")
    command = [
        PYTHON, str(SCRIPT), "--check", "--root", str(fake["root"]),
        "--commitment", str(fake["commitment_path"]),
        "--public-manifest", str(changed), "--json",
    ]
    result = subprocess.run(command, cwd=str(ROOT), capture_output=True,
                            text=True, timeout=120)
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "violation"


def _fake_compile_factory(hidden, *, fail_first: bool = False):
    payload = _fake_binary()

    def compile_func(_zig, spec, _source, output_path):
        target = str(spec.get("target") or "")
        marker = f"FAKE-{target}-{spec.get('optimization')}"
        slug = str(spec.get("slug") or "")
        if "windows" in target:
            data = b"MZFAKE-PE:" + marker.encode() + slug.encode()
        elif "macos" in target:
            data = b"\xcf\xfa\xed\xfe" + marker.encode() + slug.encode()
        else:
            data = payload + b":" + slug.encode()
        output_path.write_bytes(data)
        return {
            "status": "compiled",
            "command": ["fake-zig"],
            "output_path": str(output_path),
            "stderr": "",
            "sha256": _sha256(data),
        }

    return compile_func


def _fake_identity(hidden):
    def identity(data: bytes):
        if data.startswith(b"MZ"):
            return {"format": "pe", "arch": "x86_64", "bits": 64,
                    "endian": "little", "limitations": [], "symbols": {}}
        if data.startswith(b"\xcf\xfa\xed\xfe"):
            return {"format": "macho", "arch": "arm64", "bits": 64,
                    "endian": "little", "limitations": [], "symbols": {}}
        return {"format": "elf", "arch": "x86_64", "bits": 64,
                "endian": "little", "limitations": [], "symbols": {}}

    return identity


def _fake_scope(hidden):
    def scope(_data, symbol):
        return {"name": symbol, "va": 0x1000, "end": 0x1040,
                "source": "symbol"}

    return scope


def _fake_validate(hidden, *, fail_sources=()):
    fail_sources = set(fail_sources)

    def validate(binary_path, _oracle_path):
        del binary_path
        return _fake_validation(0)

    def validator(binary_path, oracle_path):
        return validate(binary_path, oracle_path)

    return validator


def _fake_validation_factory(hidden):
    def validate(binary_path, oracle_path):
        data = Path(binary_path).read_bytes()
        manifest = json.loads(Path(oracle_path).read_text(encoding="utf-8"))
        # Fail the first chain entry for the CWE476 source to exercise the
        # fallback/drop path deterministically (the fake compiler is otherwise
        # identical for all runtime variants).
        if b"FAKE-FAIL" in data:
            return {
                "status": "fail", "runner": "fake", "tier": "emulated_run",
                "executed": True, "original_expected_ok": False,
                "regression_expected_ok": True, "vulnerable_observed": True,
                "original_poc_case_count": 1,
                "original_regression_case_count": 1,
                "lock_attempt_count": 0,
                "reason": "variant does not reproduce the expected original "
                          "behavior",
                "evidence_sha256": _sha256(b"failed"),
            }
        if manifest.get("fixture_sha256") != _sha256(data):
            return {
                "status": "not_run", "runner": "", "tier": "",
                "executed": False, "original_expected_ok": False,
                "regression_expected_ok": False,
                "vulnerable_observed": False,
                "original_poc_case_count": 0,
                "original_regression_case_count": 0,
                "lock_attempt_count": 0,
                "reason": "rebound oracle digest mismatch",
                "evidence_sha256": _sha256(b"mismatch"),
            }
        return _fake_validation(0)

    return validate


def _install_fake_build(monkeypatch, hidden, *, fail_476_first: bool = False):
    original_compile = _fake_compile_factory(hidden)
    marker_state = {"first_476": fail_476_first}

    def compile_func(zig, spec, source, output_path):
        record = original_compile(zig, spec, source, output_path)
        slug = str(spec.get("slug") or "")
        if fail_476_first and "cwe476" in slug and "-musl" not in slug:
            output_path.write_bytes(
                output_path.read_bytes() + b"FAKE-FAIL")
            record["sha256"] = _sha256(output_path.read_bytes())
        marker_state["first_476"] = False
        return record

    validator = _fake_validation_factory(hidden)
    monkeypatch.setattr(hidden, "compile_variant", compile_func)
    monkeypatch.setattr(hidden, "container_identity", _fake_identity(hidden))
    monkeypatch.setattr(hidden, "resolve_symbol_scope", _fake_scope(hidden))
    monkeypatch.setattr(hidden, "_same_executable_text", lambda a, b: True)
    monkeypatch.setattr(hidden, "validate_runtime_oracle", validator)


def _build(hidden, tmp_path, *, write_commitment=True):
    tmp_path.mkdir(parents=True, exist_ok=True)
    root = tmp_path / "build-root"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    commitment_path = tmp_path / "built-commitment.json"
    result = hidden.build_hidden_corpus(
        root=root,
        public_manifest_path=PUBLIC_MANIFEST,
        commitment_path=commitment_path,
        validate_oracles=True,
        write_commitment=write_commitment,
        toolchain_probe={"available": True, "version": "0.17.1",
                         "status": "available"},
        zig="/fake/zig",
    )
    return root, commitment_path, result


def test_build_without_zig_reports_not_run(tmp_path: Path, monkeypatch):
    hidden = _hidden()
    root = tmp_path / "no-zig-root"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    monkeypatch.setattr(hidden, "zig_path", lambda: None)
    result = hidden.build_hidden_corpus(
        root=root,
        public_manifest_path=PUBLIC_MANIFEST,
        commitment_path=tmp_path / "commitment.json",
        validate_oracles=True,
        write_commitment=True,
        toolchain_probe={"available": False, "version": None,
                         "status": "not_run"},
        zig=None,
    )
    assert result["status"] == "not_run"
    assert result["summary"]["hidden_available"] is False
    assert not (root / hidden.PRIVATE_MANIFEST_NAME).exists()
    assert not (tmp_path / "commitment.json").exists()


def test_build_without_oracle_validation_blocks(tmp_path: Path):
    hidden = _hidden()
    root = tmp_path / "no-oracle-root"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    result = hidden.build_hidden_corpus(
        root=root,
        public_manifest_path=PUBLIC_MANIFEST,
        commitment_path=tmp_path / "commitment.json",
        validate_oracles=False,
        write_commitment=True,
        toolchain_probe={"available": True, "version": "0.17.1",
                         "status": "available"},
        zig="/fake/zig",
    )
    assert result["status"] == "blocked"
    assert result["summary"]["hidden_available"] is False
    assert not (root / hidden.PRIVATE_MANIFEST_NAME).exists()
    assert not (tmp_path / "commitment.json").exists()


def test_build_refuses_insecure_root(tmp_path: Path):
    hidden = _hidden()
    root = tmp_path / "insecure-root"
    root.mkdir(mode=0o755)
    os.chmod(root, 0o755)
    result = hidden.build_hidden_corpus(
        root=root,
        public_manifest_path=PUBLIC_MANIFEST,
        commitment_path=tmp_path / "commitment.json",
        validate_oracles=True,
        write_commitment=True,
    )
    assert result["status"] == "violation"
    assert result["summary"]["hidden_available"] is False
    assert not (root / hidden.PRIVATE_MANIFEST_NAME).exists()


def test_build_admits_corpus_with_fake_compiler_and_guest(
    tmp_path: Path, monkeypatch
):
    hidden = _hidden()
    _install_fake_build(monkeypatch, hidden)
    root, commitment_path, result = _build(hidden, tmp_path)
    assert result["status"] == "ok", result["summary"]["limitations"]
    summary = result["summary"]
    assert summary["hidden_available"] is True
    assert summary["sample_count"] == 8
    assert summary["runtime_count"] == 6
    assert summary["analysis_only_count"] == 2
    assert commitment_path.is_file()
    manifest = json.loads(
        (root / hidden.PRIVATE_MANIFEST_NAME).read_text(encoding="utf-8"))
    assert len(manifest["samples"]) == 8
    assert manifest["commitment_sha256"] == summary["commitment_sha256"]
    # The freshly built corpus passes the offline check.
    check = hidden.check_private_root(
        root=root,
        commitment_path=commitment_path,
        public_manifest_path=PUBLIC_MANIFEST,
    )
    assert check["ok"] is True, check["summary"]["violations"]
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    # Rebuild determinism: identical private manifest + public commitment.
    first_manifest = (root / hidden.PRIVATE_MANIFEST_NAME).read_bytes()
    first_commitment = commitment_path.read_bytes()
    root2, commitment_path2, result2 = _build(hidden, tmp_path / "again")
    assert result2["status"] == "ok"
    assert (root2 / hidden.PRIVATE_MANIFEST_NAME).read_bytes() == first_manifest
    assert commitment_path2.read_bytes() == first_commitment


def test_build_uses_fallback_when_primary_variant_is_invalid(
    tmp_path: Path, monkeypatch
):
    hidden = _hidden()
    _install_fake_build(monkeypatch, hidden, fail_476_first=True)
    result = hidden.build_hidden_corpus(
        root=tmp_path / "fallback-root",
        public_manifest_path=PUBLIC_MANIFEST,
        commitment_path=tmp_path / "commitment.json",
        validate_oracles=True,
        write_commitment=True,
        toolchain_probe={"available": True, "version": "0.17.1",
                         "status": "available"},
        zig="/fake/zig",
    )
    assert result["status"] == "ok", result["summary"]["limitations"]
    report = json.loads(
        (tmp_path / "fallback-root" / hidden.REPORT_NAME).read_text(
            encoding="utf-8"))
    selected = [
        attempt for attempt in report["selected_attempts"]
        if attempt["source"] == "repair-cwe476"
    ][0]
    assert selected["attempts"][0]["status"] == "compiled"
    assert selected["attempts"][0]["reason"]
    assert selected["attempts"][-1]["status"] == "validated"
    assert report["counts"]["dropped_attempts"] >= 1


def test_build_blocks_when_fewer_than_six_runtime_validate(
    tmp_path: Path, monkeypatch
):
    hidden = _hidden()
    _install_fake_build(monkeypatch, hidden)

    def fail_everything(_binary, _oracle):
        return {
            "status": "not_run", "runner": "", "tier": "", "executed": False,
            "original_expected_ok": False, "regression_expected_ok": False,
            "vulnerable_observed": False, "original_poc_case_count": 0,
            "original_regression_case_count": 0, "lock_attempt_count": 0,
            "reason": "guest unavailable", "evidence_sha256": None,
        }

    monkeypatch.setattr(hidden, "validate_runtime_oracle", fail_everything)
    root = tmp_path / "blocked-root"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    result = hidden.build_hidden_corpus(
        root=root,
        public_manifest_path=PUBLIC_MANIFEST,
        commitment_path=tmp_path / "commitment.json",
        validate_oracles=True,
        write_commitment=True,
        toolchain_probe={"available": True, "version": "0.17.1",
                         "status": "available"},
        zig="/fake/zig",
    )
    assert result["status"] == "blocked"
    assert result["summary"]["hidden_available"] is False
    assert not (root / hidden.PRIVATE_MANIFEST_NAME).exists()
    assert not (tmp_path / "commitment.json").exists()
    assert list((root / "bin").iterdir()) == []
    assert list((root / "poc").iterdir()) == []


def test_build_without_write_commitment_stays_hidden_unavailable(
    tmp_path: Path, monkeypatch
):
    hidden = _hidden()
    _install_fake_build(monkeypatch, hidden)
    root, commitment_path, result = _build(hidden, tmp_path,
                                           write_commitment=False)
    assert result["status"] == "ok"
    assert result["summary"]["hidden_available"] is False
    assert not commitment_path.exists()
    assert (root / hidden.PRIVATE_MANIFEST_NAME).is_file()


def test_build_rejects_hidden_public_duplicate_material(
    tmp_path: Path, monkeypatch
):
    hidden = _hidden()
    public_variant = ROOT / "benchmark" / "phase8c" / "bin" / "variant-cwe122-O2.elf"
    if not public_variant.is_file():
        pytest.skip("public variant artifact missing; duplicate probe unavailable")
    duplicate_bytes = public_variant.read_bytes()
    _install_fake_build(monkeypatch, hidden)

    def compile_duplicate(_zig, spec, _source, output_path):
        output_path.write_bytes(duplicate_bytes)
        return {
            "status": "compiled",
            "command": ["fake-zig"],
            "output_path": str(output_path),
            "stderr": "",
            "sha256": _sha256(duplicate_bytes),
        }

    monkeypatch.setattr(hidden, "compile_variant", compile_duplicate)
    root = tmp_path / "duplicate-root"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    result = hidden.build_hidden_corpus(
        root=root,
        public_manifest_path=PUBLIC_MANIFEST,
        commitment_path=tmp_path / "commitment.json",
        validate_oracles=True,
        write_commitment=True,
        toolchain_probe={"available": True, "version": "0.17.1",
                         "status": "available"},
        zig="/fake/zig",
    )
    assert result["status"] == "blocked"
    assert result["summary"]["hidden_available"] is False
    assert not (root / hidden.PRIVATE_MANIFEST_NAME).exists()
    assert not (tmp_path / "commitment.json").exists()
    assert list((root / "bin").iterdir()) == []
    public_hashes = hidden.public_material_hashes(_public_manifest())["binary"]
    assert _sha256(duplicate_bytes) in public_hashes


def test_private_reference_copies_are_not_byte_identical_to_public(
    tmp_path: Path, monkeypatch
):
    hidden = _hidden()
    _install_fake_build(monkeypatch, hidden)
    root, _commitment_path, result = _build(hidden, tmp_path)
    assert result["status"] == "ok"
    manifest = json.loads(
        (root / hidden.PRIVATE_MANIFEST_NAME).read_text(encoding="utf-8"))
    public = {
        sample["sample_id"]: sample for sample in _public_manifest()["samples"]
    }
    source_for_public = {
        "repair-cwe122": "CWE122_heap_copy",
        "repair-cwe125": "CWE125_oob_read",
        "repair-cwe134": "CWE134_format_string",
        "repair-cwe190": "CWE190_integer_overflow",
        "repair-cwe476": "CWE476_null_deref",
        "repair-cwe787": "CWE787_index_write",
    }
    runtime = [sample for sample in manifest["samples"]
               if sample["expected_scope"] == "function"]
    assert len(runtime) == 6
    public_fix_hashes = {
        str(public[public_id]["reference_fix"]["sha256"])
        for public_id in source_for_public
        if isinstance(public.get(public_id, {}).get("reference_fix"), Mapping)
    }
    for sample in runtime:
        entry = manifest["material"][sample["sample_id"]]
        reference = root / entry["reference_fix_path"]
        digest = _sha256_file(reference)
        assert digest == sample["reference_fix"]["sha256"]
        assert digest not in public_fix_hashes
        text = reference.read_text(encoding="utf-8")
        assert text.startswith("/* Phase-8C private hidden-corpus reference-fix")
        assert "repair" in text.lower() or "ERROR" in text or "if" in text


def test_build_reference_copy_helper_keeps_source_semantics():
    hidden = _hidden()
    source = (ROOT / "fixtures" / "repair-benchmark" / "CWE122_heap_copy"
              / "reference_fix.c").read_bytes()
    copy = hidden._private_reference_bytes(source, "a" * 64)
    assert copy.endswith(source)
    assert _sha256(copy) != _sha256(source)
    assert copy.startswith(b"/* Phase-8C private hidden-corpus reference-fix")


def test_cli_build_blocked_without_validation_writes_nothing(tmp_path: Path):
    root = tmp_path / "cli-root"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    commitment_path = tmp_path / "cli-commitment.json"
    command = [
        PYTHON, str(SCRIPT), "--root", str(root),
        "--commitment", str(commitment_path), "--json",
    ]
    result = subprocess.run(command, cwd=str(ROOT), capture_output=True,
                            text=True, timeout=120)
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["hidden_available"] is False
    assert not commitment_path.exists()
    assert not (root / _hidden().PRIVATE_MANIFEST_NAME).exists()


def test_validate_stable_retries_transient_guest_failures(tmp_path: Path):
    hidden = _hidden()
    calls = {"n": 0}

    def flaky(_binary, _oracle):
        calls["n"] += 1
        if calls["n"] <= 2:
            return {
                "status": "not_run", "runner": "", "tier": "", "executed": False,
                "original_expected_ok": False, "regression_expected_ok": False,
                "vulnerable_observed": False, "original_poc_case_count": 0,
                "original_regression_case_count": 0, "lock_attempt_count": 0,
                "reason": "guest lock timeout", "evidence_sha256": None,
            }
        return _fake_validation(0)

    result = hidden._validate_stable(flaky, tmp_path / "bin", tmp_path / "o.json")
    assert result["executed"] is True
    assert result["reason"] is None
    assert result["validation_stable"] is True
    assert result["validation_repeats"] >= 2


def test_validate_stable_drops_unstable_verdicts(tmp_path: Path):
    hidden = _hidden()
    calls = {"n": 0}

    def unstable(_binary, _oracle):
        calls["n"] += 1
        if calls["n"] == 1:
            return _fake_validation(0)
        return {
            **_fake_validation(1),
            "evidence_sha256": _sha256(b"different-verdict"),
            "reason": "variant does not reproduce the expected behavior",
        }

    result = hidden._validate_stable(unstable, tmp_path / "bin", tmp_path / "o.json")
    assert result["executed"] is False
    assert result["validation_stable"] is False
    assert "not reproducible" in (result["reason"] or "")


def test_validate_stable_drops_when_guest_never_executes(tmp_path: Path):
    hidden = _hidden()

    def never(_binary, _oracle):
        return {
            "status": "not_run", "runner": "", "tier": "", "executed": False,
            "original_expected_ok": False, "regression_expected_ok": False,
            "vulnerable_observed": False, "original_poc_case_count": 0,
            "original_regression_case_count": 0, "lock_attempt_count": 0,
            "reason": "guest unavailable", "evidence_sha256": None,
        }

    result = hidden._validate_stable(never, tmp_path / "bin", tmp_path / "o.json")
    assert result["executed"] is False
    assert result["validation_stable"] is False
    assert "did not execute enough independent rounds" in (result["reason"] or "")


def test_blocked_build_removes_stale_private_manifest(tmp_path: Path):
    hidden = _hidden()
    root = tmp_path / "stale-root"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    hidden._ensure_private_layout(root)
    (root / hidden.PRIVATE_MANIFEST_NAME).write_text("{}", encoding="utf-8")
    hidden._write_bytes_atomic(root / hidden.SUMS_NAME, b"stale\n")
    def failing_compile(_zig, _spec, _source, output):
        output.write_bytes(b"")
        return {"status": "failed", "command": [], "output_path": str(output),
                "stderr": "fake compiler failure", "sha256": None}

    result = hidden.build_hidden_corpus(
        root=root,
        public_manifest_path=PUBLIC_MANIFEST,
        commitment_path=tmp_path / "commitment.json",
        validate_oracles=True,
        write_commitment=True,
        compile_func=failing_compile,
        toolchain_probe={"available": True, "version": "0.17.1",
                         "status": "available"},
        zig="/fake/zig",
    )
    assert result["status"] == "blocked"
    assert not (root / hidden.PRIVATE_MANIFEST_NAME).exists()
    assert not (root / hidden.SUMS_NAME).exists()


def test_validator_binds_deterministic_evidence_only():
    hidden = _hidden()
    first = _fake_validation(0)
    second = dict(first, lock_attempt_count=99)
    # The digest binds status/runner/tier/counts only; lock timing is report-only.
    assert first["evidence_sha256"] == second["evidence_sha256"]


def test_builder_has_no_network_ai_or_git_commands():
    source = SCRIPT.read_text(encoding="utf-8")
    lowered = source.lower()
    for token in FORBIDDEN_IMPORTS:
        assert token not in lowered, token
    for token in ("openai", "anthropic", "siliconflow", "http://",
                  "https://"):
        assert token not in lowered, token
    assert '"git"' not in lowered
    assert "'git'" not in lowered


def test_repo_tree_contains_no_hidden_material():
    hidden = _hidden()
    public_dir = ROOT / "benchmark" / "phase8c"
    allowed_commitment = public_dir / "hidden-commitment.json"
    for candidate in public_dir.rglob("*"):
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(public_dir).as_posix()
        if relative.startswith("bin/") and candidate.name.startswith("hidden-"):
            pytest.fail(f"hidden material committed in the public tree: {relative}")
        if candidate.suffix in {".bin", ".elf"} and "hidden" in candidate.name:
            pytest.fail(f"hidden binary committed in the public tree: {relative}")
    # The only allowed hidden artifact is the opaque commitment document.
    if allowed_commitment.is_file():
        payload = json.loads(allowed_commitment.read_text(encoding="utf-8"))
        assert payload["kind"] == "hidden_benchmark_commitment"
        assert set(payload) == {
            "schema_version", "kind", "benchmark_id", "hidden_version",
            "sample_count", "runtime_count", "analysis_only_count",
            "commitment_sha256", "public_manifest_sha256", "created_at",
            "samples", "limitations",
        }
    for forbidden in ("hidden-manifest.json", "oracle-validation.json",
                      "build-report.json"):
        assert not (ROOT / forbidden).exists()
    assert not (ROOT / hidden.PRIVATE_MANIFEST_NAME).exists()


def test_insecure_root_check_precedes_optional_toolchain(tmp_path: Path, monkeypatch):
    """An insecure root is a violation even when Zig is unavailable (CI host)."""
    hidden = _hidden()
    root = tmp_path / "insecure-root-alone"
    root.mkdir(mode=0o755)
    os.chmod(root, 0o755)
    monkeypatch.setattr(hidden, "zig_path", lambda: None)
    result = hidden.build_hidden_corpus(
        root=root,
        public_manifest_path=PUBLIC_MANIFEST,
        commitment_path=tmp_path / "commitment.json",
        validate_oracles=True,
        write_commitment=True,
    )
    assert result["status"] == "violation"
    assert result["summary"]["hidden_available"] is False


def test_cli_blocked_without_validation_precedes_optional_toolchain(
    tmp_path: Path, monkeypatch
):
    """Omitting --validate-oracles is blocked even when Zig is unavailable."""
    hidden = _hidden()
    monkeypatch.setattr(hidden, "zig_path", lambda: None)
    root = tmp_path / "blocked-root"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    result = hidden.build_hidden_corpus(
        root=root,
        public_manifest_path=PUBLIC_MANIFEST,
        commitment_path=tmp_path / "commitment.json",
        validate_oracles=False,
        write_commitment=True,
    )
    assert result["status"] == "blocked"
    assert result["summary"]["hidden_available"] is False
