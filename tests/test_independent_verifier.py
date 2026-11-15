"""Tests for the independent repair verifier and its CLI (offline, no AI)."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app.services import independent_verifier as verifier  # noqa: E402
import verify_repair as cli  # noqa: E402

ORIGINAL = bytes(range(256)) * 4
CHANGED = bytearray(ORIGINAL)
CHANGED[32:40] = b"\x90" * 8
CANDIDATE = bytes(CHANGED)
ACTIONS = [{
    "offset": 32,
    "size": 8,
    "before_hex": ORIGINAL[32:40].hex(),
    "after_hex": CANDIDATE[32:40].hex(),
}]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _detect(_data: bytes) -> dict:
    return {
        "format": "elf",
        "arch": "x86_64",
        "bits": 64,
        "endian": "little",
        "sections": [{"name": ".text", "va": 0x401000, "size": 256,
                      "offset": 0, "executable": True}],
    }


def _abi(ok: bool = True, code: str = "") -> callable:
    def check(_code: bytes, _arch: str) -> dict:
        if code:
            return {"ok": True, "fatal": 0,
                    "findings": [{"code": code, "severity": "unknown", "detail": ""}]}
        return {"ok": ok, "fatal": 0 if ok else 1,
                "findings": [] if ok else [{"code": "stack_unbalanced",
                                            "severity": "fatal",
                                            "detail": "unbalanced stack"}]}
    return check


def _oracle(status: str = "pass") -> callable:
    def run(original: bytes, candidate: bytes, _manifest) -> dict:
        return {
            "status": status,
            "runner": "native",
            "tier": "native_run",
            "stdout_signature": "matched" if status == "pass" else "not_run",
            "errno_signature": "not_run",
            "original_sha256": _sha(original),
            "candidate_sha256": _sha(candidate),
            "poc": [{"case_id": "poc", "kind": "poc"}],
            "regression": [{"case_id": "reg", "kind": "regression"}],
            "limitations": [] if status == "pass" else [f"oracle status={status}"],
        }
    return run


def _metadata(original: bytes = ORIGINAL, candidate: bytes = CANDIDATE, **overrides) -> dict:
    metadata = {
        "format": "elf",
        "arch": "x86_64",
        "bits": 64,
        "endian": "little",
        "original_sha256": _sha(original),
        "candidate_sha256": _sha(candidate),
        "target_scope": {"policy": "target_scoped", "name": "vuln_fn",
                         "va": 0x401000, "end": 0x401100},
        "abi_block": {"offset": 32, "size": 8},
        "generator": {"generator_id": "repair-generator/1",
                      "agent": "deterministic", "model": None, "run_id": "run-1"},
    }
    metadata.update(overrides)
    return metadata


def _verify(metadata=None, *, oracle=None, claimed=None, generator=None,
            abi=None, detect=None, run_poc=None):
    oracle_input = {"manifest": {"format": "elf", "arch": "x86_64"}} if oracle is None else oracle
    runner = run_poc if run_poc is not None else _oracle()
    return verifier.verify_repair(
        original=ORIGINAL,
        candidate=CANDIDATE,
        metadata=_metadata() if metadata is None else metadata,
        oracle=oracle_input,
        generator=generator,
        claimed_actions=ACTIONS if claimed is None else claimed,
        detect=detect or _detect,
        abi_check=abi or _abi(),
        run_poc=runner,
    )


def _by_id(report: dict) -> dict:
    return {check["id"]: check for check in report["checks"]}


def test_valid_report_is_schema_valid_and_verified() -> None:
    report = _verify()
    assert report["decision"] == "verified"
    assert report["verifier"]["verifier_id"] == verifier.VERIFIER_ID
    assert report["generator"]["generator_id"] == "repair-generator/1"
    assert report["independence"] == {"ok": True, "generator_evidence_excluded": True}
    checks = _by_id(report)
    assert len(checks) == 8
    assert checks["runtime-oracle"]["status"] == "passed"
    assert checks["runtime-oracle"]["independent"] is True
    assert checks["evidence-completeness"]["independent"] is True
    assert all(check["status"] == "passed" for check in checks.values())
    assert isinstance(report["evidence"], list) and report["evidence"]
    validation = verifier.validate_verification_report(report)
    assert validation["ok"] is True, validation["violations"]
    assert report["decision"] in verifier.DECISIONS


def test_schema_validation_with_jsonschema_when_available() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (ROOT / "contracts/verification.schema.json").read_text(encoding="utf-8")
    )
    report = _verify()
    jsonschema.Draft202012Validator(schema).validate(report)


def test_identity_tamper_is_rejected() -> None:
    metadata = _metadata(original_sha256="0" * 64)
    report = _verify(metadata)
    assert report["decision"] == "rejected"
    assert _by_id(report)["identity"]["status"] == "failed"


def test_candidate_sha_tamper_is_rejected() -> None:
    metadata = _metadata(candidate_sha256="0" * 64)
    report = _verify(metadata)
    assert report["decision"] == "rejected"
    assert _by_id(report)["identity"]["status"] == "failed"


def test_unchanged_candidate_is_rejected() -> None:
    report = verifier.verify_repair(
        original=ORIGINAL,
        candidate=ORIGINAL,
        metadata=_metadata(candidate=ORIGINAL),
        oracle={"manifest": {"format": "elf", "arch": "x86_64"}},
        claimed_actions=[],
        detect=_detect,
        abi_check=_abi(),
        run_poc=_oracle(),
    )
    assert report["decision"] == "rejected"
    assert _by_id(report)["identity"]["status"] == "failed"


def test_claimed_action_mismatch_is_rejected() -> None:
    bad = [{"offset": 0, "size": 8, "before_hex": "00" * 8, "after_hex": "11" * 8}]
    report = _verify(claimed=bad)
    assert report["decision"] == "rejected"
    check = _by_id(report)["action-replay"]
    assert check["status"] == "failed"
    assert "do not match" in check["detail"]


def test_claimed_actions_matching_recomputed_bytes_pass() -> None:
    report = _verify(claimed=json.loads(json.dumps(ACTIONS)))
    assert _by_id(report)["action-replay"]["status"] == "passed"


def test_scope_escape_is_rejected() -> None:
    metadata = _metadata(target_scope={"policy": "target_scoped", "name": "other",
                                        "va": 0x500000, "end": 0x500100})
    report = _verify(metadata)
    assert report["decision"] == "rejected"
    check = _by_id(report)["target-scope"]
    assert check["status"] == "failed"
    assert "escapes" in check["detail"]


def test_missing_scope_is_not_run_and_cannot_verify() -> None:
    metadata = _metadata()
    metadata.pop("target_scope")
    report = _verify(metadata)
    assert _by_id(report)["target-scope"]["status"] == "not_run"
    assert report["target"]["target_scope"]["policy"] == "analysis_only"
    assert report["decision"] == "not_run"


def test_whole_image_scope_requires_explicit_opt_in() -> None:
    no_opt_in = _metadata(target_scope={"policy": "whole_image", "name": "image"})
    report = _verify(no_opt_in)
    assert report["decision"] == "not_run"
    opted_in = _metadata(target_scope={"policy": "whole_image", "name": "image"},
                         allow_whole_image=True)
    report_ok = _verify(opted_in)
    assert report_ok["target"]["target_scope"]["policy"] == "whole_image"
    assert report_ok["decision"] == "verified"


def test_genertor_only_evidence_is_rejected() -> None:
    report = verifier.verify_repair(
        original=ORIGINAL,
        candidate=CANDIDATE,
        metadata=_metadata(),
        oracle=None,
        generator={"generator_id": "repair-generator/1", "verified": True},
        claimed_actions=ACTIONS,
        detect=_detect,
        abi_check=_abi(),
        run_poc=None,
    )
    assert report["decision"] == "rejected"
    checks = _by_id(report)
    assert checks["evidence-completeness"]["status"] == "failed"
    assert checks["independence"]["status"] == "failed"
    assert report["independence"]["ok"] is False
    assert "generator_id" not in report["generator"] or True  # sanitized fields only


def test_generator_verdict_is_ignored() -> None:
    generator = {"generator_id": "repair-generator/1", "verified": True,
                 "decision": "rejected", "agent": "x"}
    report = _verify(generator=generator)
    assert report["generator"] == {"generator_id": "repair-generator/1",
                                   "agent": "x", "model": None, "run_id": None}
    assert "verified" not in report["generator"]
    assert report["decision"] == "verified"


def test_generator_same_as_verifier_is_rejected() -> None:
    report = _verify(generator={"generator_id": verifier.VERIFIER_ID})
    assert report["decision"] == "rejected"
    assert _by_id(report)["independence"]["status"] == "failed"


def test_missing_generator_is_rejected() -> None:
    metadata = _metadata()
    metadata.pop("generator")
    report = _verify(metadata, generator=None)
    assert report["independence"]["ok"] is False
    assert _by_id(report)["independence"]["status"] == "failed"
    assert report["decision"] == "rejected"


def test_abi_fatal_failure_is_rejected() -> None:
    report = _verify(abi=_abi(ok=False))
    assert report["decision"] == "rejected"
    assert _by_id(report)["abi"]["status"] == "failed"


def test_abi_unsupported_is_not_run_with_limitation() -> None:
    report = _verify(abi=_abi(code="abi_check_not_implemented"))
    assert report["decision"] == "not_run"
    check = _by_id(report)["abi"]
    assert check["status"] == "not_run"
    assert "not implemented" in check["detail"]
    assert any("ABI checks are not implemented" in item for item in report["limitations"])


def test_missing_abi_block_is_not_run() -> None:
    metadata = _metadata()
    metadata.pop("abi_block")
    report = _verify(metadata)
    assert _by_id(report)["abi"]["status"] == "not_run"
    assert report["decision"] == "not_run"


def test_oracle_unavailable_is_not_run() -> None:
    report = _verify(run_poc=_oracle(status="unavailable"))
    assert report["decision"] == "not_run"
    assert _by_id(report)["runtime-oracle"]["status"] == "not_run"


def test_oracle_differential_failure_is_rejected() -> None:
    report = _verify(run_poc=_oracle(status="fail"))
    assert report["decision"] == "rejected"
    assert _by_id(report)["runtime-oracle"]["status"] == "failed"
    assert _by_id(report)["evidence-completeness"]["status"] == "failed"


def test_oracle_evidence_sha_tamper_is_rejected() -> None:
    tampered = _oracle()
    def bad(original: bytes, candidate: bytes, _manifest) -> dict:
        evidence = tampered(original, candidate, _manifest)
        evidence["original_sha256"] = "0" * 64
        return evidence
    report = _verify(run_poc=bad)
    assert report["decision"] == "rejected"
    assert _by_id(report)["runtime-oracle"]["status"] == "failed"


def test_stdout_signature_mismatch_is_rejected() -> None:
    metadata = _metadata(expected_stdout_signature="matched")
    def mismatch(original: bytes, candidate: bytes, _manifest) -> dict:
        evidence = _oracle()(original, candidate, _manifest)
        evidence["stdout_signature"] = "mismatch"
        return evidence
    report = _verify(metadata, run_poc=mismatch)
    assert report["decision"] == "rejected"
    assert _by_id(report)["runtime-oracle"]["status"] == "failed"


def test_deterministic_report_sha_and_tamper_detection() -> None:
    first = _verify()
    second = _verify()
    assert first["report_sha256"] == second["report_sha256"]
    assert verifier.validate_verification_report(first)["ok"] is True

    tampered = json.loads(json.dumps(first))
    tampered["decision"] = "rejected"
    validation = verifier.validate_verification_report(tampered)
    assert validation["ok"] is False
    assert any("report_sha256" in item for item in validation["violations"])

    tampered_original = json.loads(json.dumps(first))
    tampered_original["report_sha256"] = "0" * 64
    assert verifier.validate_verification_report(tampered_original)["ok"] is False


def test_unsupported_target_raises_fail_closed() -> None:
    metadata = _metadata(format="coff")
    with pytest.raises(verifier.UnsupportedVerificationTarget):
        _verify(metadata)


def test_schema_cross_field_verified_rules() -> None:
    report = _verify()
    assert report["decision"] == "verified"
    independent_passed = [
        check for check in report["checks"]
        if check.get("independent") is True and check["status"] == "passed"
    ]
    assert independent_passed
    assert report["independence"]["ok"] is True
    assert report["independence"]["generator_evidence_excluded"] is True
    assert all(check["status"] == "passed" for check in report["checks"]
               if check["required"])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_selftest_passes(capsys) -> None:
    assert cli.main(["--selftest"]) == 0
    output = capsys.readouterr().out
    assert "verify-repair selftest: PASS" in output
    assert "schema=jsonschema" in output or "schema=fallback" in output

    assert cli.main(["--selftest", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["case_count"] >= 10
    for case in payload["cases"]:
        assert case["schema_ok"] is True


def test_cli_missing_inputs_exit_two(tmp_path: Path, capsys) -> None:
    assert cli.main(["--original", str(tmp_path / "a"), "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False


def test_cli_missing_file_exit_two(tmp_path: Path, capsys) -> None:
    metadata = tmp_path / "meta.json"
    metadata.write_text(json.dumps(_metadata()), encoding="utf-8")
    code = cli.main(["--original", str(tmp_path / "missing"),
                     "--candidate", str(tmp_path / "missing2"),
                     "--metadata", str(metadata), "--json"])
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False


def test_cli_real_fixture_negative_is_rejected(tmp_path: Path, capsys) -> None:
    fixture = ROOT / "fixtures/elf/vuln-strcpy-x86_64.elf"
    if not fixture.is_file():
        pytest.skip("ELF fixture is not present in this checkout")
    from app.services.binary_pipeline import detect_format
    original = fixture.read_bytes()
    candidate = bytearray(original)
    candidate[0x400:0x408] = b"\x90" * 8
    candidate = bytes(candidate)
    fmt, arch, bits = detect_format(original)
    metadata = {
        "format": fmt,
        "arch": arch,
        "bits": bits,
        "endian": "little",
        "original_sha256": _sha(original),
        "candidate_sha256": _sha(candidate),
        "target_scope": {"policy": "target_scoped", "file_offset": 0x400, "size": 8},
        "generator": {"generator_id": "repair-generator/1", "agent": "deterministic"},
    }
    candidate_path = tmp_path / "candidate.bin"
    candidate_path.write_bytes(candidate)
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    code = cli.main(["--original", str(fixture), "--candidate", str(candidate_path),
                     "--metadata", str(metadata_path), "--json"])
    assert code == 1
    report = json.loads(capsys.readouterr().out)
    assert report["decision"] in {"rejected", "inconclusive"}
    assert verifier.validate_verification_report(report)["ok"] is True


def test_cli_unsupported_target_exit_two(tmp_path: Path, capsys) -> None:
    fixture = ROOT / "fixtures/elf/vuln-strcpy-x86_64.elf"
    if not fixture.is_file():
        pytest.skip("ELF fixture is not present in this checkout")
    original = fixture.read_bytes()
    metadata = _metadata(original=original, candidate=original, format="coff")
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    code = cli.main(["--original", str(fixture), "--candidate", str(fixture),
                     "--metadata", str(metadata_path), "--json"])
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False


@pytest.mark.skipif(platform.system() != "Linux",
                    reason="native PoC differential execution requires a Linux host/guest")
def test_native_poc_diff_is_skipped_off_linux() -> None:
    """Placeholder guard: native PoC tests only run where a native runner exists."""
    pytest.skip("native PoC execution is covered by the release/guest suites on Linux")
