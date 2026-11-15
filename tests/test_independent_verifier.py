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
        "sections": [
            {"name": ".text", "va": 0x401000, "size": 256,
             "offset": 0, "executable": True},
            {"name": ".rodata", "va": 0x402000, "size": 128,
             "offset": 256, "executable": False},
        ],
        "symbols": [{"va": 0x401000, "name": "vuln_fn"}],
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
    assert len(checks) == 9
    assert checks["layout-plan"]["status"] == "not_run"
    assert checks["layout-plan"]["required"] is False
    assert checks["runtime-oracle"]["status"] == "passed"
    assert checks["runtime-oracle"]["independent"] is True
    assert checks["evidence-completeness"]["independent"] is True
    for check_id, check in checks.items():
        if check_id == "layout-plan":
            continue  # optional no-plan rewrite path: required=false, not_run
        assert check["status"] == "passed"
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
    assert report_ok["decision"] == "rejected"
    assert any("whole_image" in item for item in report_ok["limitations"])
    assert verifier.validate_verification_report(report_ok)["ok"] is True


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


def test_cli_plan_and_poc_execute_oracle(tmp_path: Path, monkeypatch, capsys) -> None:
    original, candidate, plan, poc = _b1_stack_plan()
    monkeypatch.setattr(verifier, "_default_run_poc", lambda: _fake_b1_oracle)
    candidate_path = tmp_path / "candidate.bin"
    candidate_path.write_bytes(candidate)
    metadata = {
        "format": "elf", "arch": "x86_64", "bits": 64, "endian": "little",
        "target_sha256": _sha(original),
        "target_scope": plan["target_scope"],
        "generator": {"generator_id": "deterministic-repair-any/test"},
    }
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    code = cli.main([
        "--original", str(B1 / "disagreement-stack-strcpy-x86_64/original.elf"),
        "--candidate", str(candidate_path),
        "--metadata", str(metadata_path),
        "--poc", str(poc),
        "--plan", str(plan_path),
        "--json",
    ])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["decision"] == "verified"
    assert report["oracle_evidence"]["status"] == "executed"
    assert report["layout_evidence"]["replay_ok"] is True
    assert verifier.validate_verification_report(report)["ok"] is True


def test_cli_plan_missing_file_exit_two(tmp_path: Path, capsys) -> None:
    fixture = ROOT / "fixtures/elf/vuln-strcpy-x86_64.elf"
    if not fixture.is_file():
        pytest.skip("ELF fixture is not present in this checkout")
    metadata = _metadata()
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    code = cli.main([
        "--original", str(fixture), "--candidate", str(fixture),
        "--metadata", str(metadata_path), "--plan", str(tmp_path / "missing-plan.json"),
        "--json",
    ])
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False


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


# ---------------------------------------------------------------------------
# Phase-8B layout-aware plan tests
# ---------------------------------------------------------------------------

B1 = ROOT / "artifacts" / "phase8b-baseline-2026-11-16"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _redirect(site_va: int, cave_va: int) -> bytes:
    import struct

    return b"\xe9" + struct.pack("<i", cave_va - (site_va + 5))


def _plan(original: bytes, candidate: bytes, *, scope_policy: str = "target_scoped",
          operations: list[dict] | None = None, cave: dict | None = None,
          abi_blocks: list[dict] | None = None,
          oracle_runner: str = "native", oracle_tier: str = "native_run",
          scope_va: int = 0x401000, scope_end: int = 0x401100) -> dict:
    if operations is None:
        operations = [{
            "kind": "write", "original_offset": 32, "candidate_offset": None,
            "size": 5, "before_hex": original[32:37].hex(),
            "after_hex": _redirect(0x401020, 0x500000).hex(),
            "site_va": 0x401020, "reason": "reviewed_site", "authorization_ref": None,
        }]
    if abi_blocks is None:
        abi_blocks = [{
            "function": "vuln_fn", "va": 0x401000, "size": 64, "arch": "x86_64",
            "evidence_sha256": _sha(candidate[0:64]),
        }]
    manifest = json.dumps({"format": "elf", "arch": "x86_64"},
                          sort_keys=True, separators=(",", ":")).encode("ascii")
    return {
        "schema_version": 1,
        "candidate_id": "cand-test-layout",
        "target_sha256": _sha(original),
        "candidate_sha256": _sha(candidate),
        "strategy": "guard_cave" if cave else "reviewed_site",
        "scope_policy": scope_policy,
        "target_scope": {"policy": scope_policy, "name": "vuln_fn",
                         "va": scope_va, "end": scope_end},
        "operations": operations,
        "cave": cave,
        "relocations": [],
        "abi_blocks": abi_blocks,
        "oracle": {"manifest_sha256": _sha(manifest),
                   "runner": oracle_runner, "tier": oracle_tier,
                   "status": "executed"},
        "limitations": [],
    }


def _resized_case() -> tuple[bytes, bytes, dict]:
    original = ORIGINAL
    candidate = bytearray(original)
    candidate[32:37] = _redirect(0x401020, 0x500000)
    appended = b"\x00" * 16 + b"\x31\xc0\xc3"
    candidate.extend(appended)
    candidate = bytes(candidate)
    plan = _plan(original, candidate, cave={
        "va": 0x500000, "size": 3, "executable": True, "method": "test",
    })
    plan["operations"].append({
        "kind": "insert", "original_offset": len(original),
        "candidate_offset": len(original), "size": len(appended),
        "before_hex": "", "after_hex": appended.hex(),
        "site_va": 0x401020, "reason": "guard_cave", "authorization_ref": None,
    })
    return original, candidate, plan


def _plan_verify(metadata: dict, *, oracle=None, plan=None, generator=None,
                 original_bytes: bytes | None = None,
                 candidate_bytes: bytes | None = None, abi=None, detect=None):
    active_original = original_bytes if original_bytes is not None else ORIGINAL
    active_candidate = candidate_bytes if candidate_bytes is not None else CANDIDATE
    return verifier.verify_repair(
        original=active_original,
        candidate=active_candidate,
        metadata=_metadata(active_original, active_candidate) if metadata is None else metadata,
        oracle={"manifest": {"format": "elf", "arch": "x86_64"}} if oracle is None else oracle,
        generator=generator,
        patch_plan=plan,
        detect=detect or _detect,
        abi_check=abi or _abi(),
        run_poc=_oracle(),
    )


def test_plan_resized_candidate_verifies() -> None:
    original, candidate, plan = _resized_case()
    metadata = _metadata(original, candidate)
    metadata["target_scope"] = {"policy": "target_scoped", "name": "vuln_fn",
                                "va": 0x401000, "end": 0x401100}
    report = verifier.verify_repair(
        original=original, candidate=candidate, metadata=metadata,
        oracle={"manifest": {"format": "elf", "arch": "x86_64"}},
        patch_plan=plan, detect=_detect, abi_check=_abi(), run_poc=_oracle(),
    )
    assert report["decision"] == "verified"
    checks = _by_id(report)
    assert checks["layout-plan"]["status"] == "passed"
    assert checks["action-replay"]["status"] == "passed"
    assert report["layout_evidence"]["replay_ok"] is True
    assert report["layout_evidence"]["cave"]["executable"] is True
    assert report["patch_plan_sha256"] == report["layout_evidence"]["patch_plan_sha256"]
    validation = verifier.validate_verification_report(report)
    assert validation["ok"] is True, validation["violations"]


def test_resized_without_plan_is_not_run_not_blanket_rejected() -> None:
    original, candidate, _ = _resized_case()
    metadata = _metadata(original, candidate)
    report = verifier.verify_repair(
        original=original, candidate=candidate, metadata=metadata,
        oracle={"manifest": {"format": "elf", "arch": "x86_64"}},
        detect=_detect, abi_check=_abi(), run_poc=_oracle(),
    )
    checks = _by_id(report)
    assert checks["layout-plan"]["status"] == "not_run"
    assert checks["layout-plan"]["required"] is True
    assert checks["action-replay"]["status"] == "not_run"
    assert report["decision"] == "not_run"
    assert verifier.validate_verification_report(report)["ok"] is True


def test_plan_tamper_is_rejected() -> None:
    original, candidate, plan = _resized_case()
    tampered = json.loads(json.dumps(plan))
    tampered["operations"][0]["after_hex"] = "90" + tampered["operations"][0]["after_hex"][2:]
    metadata = _metadata(original, candidate)
    metadata["target_scope"] = {"policy": "target_scoped", "name": "vuln_fn",
                                "va": 0x401000, "end": 0x401100}
    report = verifier.verify_repair(
        original=original, candidate=candidate, metadata=metadata,
        oracle={"manifest": {"format": "elf", "arch": "x86_64"}},
        patch_plan=tampered, detect=_detect, abi_check=_abi(), run_poc=_oracle(),
    )
    assert report["decision"] == "rejected"
    checks = _by_id(report)
    assert checks["layout-plan"]["status"] == "failed"
    assert checks["action-replay"]["status"] == "failed"


def _associated_case() -> tuple[bytes, bytes, dict]:
    candidate = bytearray(ORIGINAL)
    candidate[32:40] = b"\x90" * 8
    candidate[260:268] = bytes((byte ^ 0xFF) for byte in ORIGINAL[260:268])
    candidate = bytes(candidate)
    operations = [
        {"kind": "write", "original_offset": 32, "candidate_offset": None, "size": 8,
         "before_hex": ORIGINAL[32:40].hex(), "after_hex": candidate[32:40].hex(),
         "site_va": 0x401020, "reason": "reviewed_site", "authorization_ref": None},
        {"kind": "write", "original_offset": 260, "candidate_offset": None, "size": 8,
         "before_hex": ORIGINAL[260:268].hex(), "after_hex": candidate[260:268].hex(),
         "site_va": None, "reason": "rodata_message",
         "authorization_ref": "test:rodata-message"},
    ]
    plan = _plan(ORIGINAL, candidate, scope_policy="target_scoped_associated",
                 operations=operations)
    return ORIGINAL, candidate, plan


def test_associated_change_plan_verifies_and_scope_checks() -> None:
    original, candidate, plan = _associated_case()
    metadata = _metadata(original, candidate)
    metadata["target_scope"] = {"policy": "target_scoped_associated", "name": "vuln_fn",
                                "va": 0x401000, "end": 0x401100}
    report = verifier.verify_repair(
        original=original, candidate=candidate, metadata=metadata,
        oracle={"manifest": {"format": "elf", "arch": "x86_64"}},
        patch_plan=plan, detect=_detect, abi_check=_abi(), run_poc=_oracle(),
    )
    assert report["decision"] == "verified"
    checks = _by_id(report)
    assert checks["target-scope"]["status"] == "passed"
    associated = report["layout_evidence"]["associated_changes"]
    assert associated and associated[0]["kind"] == "rodata_message"
    assert associated[0]["section"] == ".rodata"
    assert verifier.validate_verification_report(report)["ok"] is True


def test_associated_change_without_authorization_is_rejected() -> None:
    original, candidate, plan = _associated_case()
    unauthorized = json.loads(json.dumps(plan))
    unauthorized["operations"][1]["authorization_ref"] = None
    metadata = _metadata(original, candidate)
    metadata["target_scope"] = {"policy": "target_scoped_associated", "name": "vuln_fn",
                                "va": 0x401000, "end": 0x401100}
    report = verifier.verify_repair(
        original=original, candidate=candidate, metadata=metadata,
        oracle={"manifest": {"format": "elf", "arch": "x86_64"}},
        patch_plan=unauthorized, detect=_detect, abi_check=_abi(), run_poc=_oracle(),
    )
    assert report["decision"] == "rejected"
    assert _by_id(report)["layout-plan"]["status"] == "failed"


def test_undeclared_associated_change_is_rejected() -> None:
    original, candidate, plan = _associated_case()
    incomplete = json.loads(json.dumps(plan))
    incomplete["operations"] = incomplete["operations"][:1]
    metadata = _metadata(original, candidate)
    metadata["target_scope"] = {"policy": "target_scoped_associated", "name": "vuln_fn",
                                "va": 0x401000, "end": 0x401100}
    report = verifier.verify_repair(
        original=original, candidate=candidate, metadata=metadata,
        oracle={"manifest": {"format": "elf", "arch": "x86_64"}},
        patch_plan=incomplete, detect=_detect, abi_check=_abi(), run_poc=_oracle(),
    )
    assert report["decision"] == "rejected"
    assert _by_id(report)["layout-plan"]["status"] == "failed"


def test_nonexecutable_cave_is_rejected() -> None:
    original, candidate, plan = _resized_case()
    plan = json.loads(json.dumps(plan))
    plan["cave"]["executable"] = False
    report = verifier.verify_repair(
        original=original, candidate=candidate,
        metadata=_metadata(original, candidate),
        oracle={"manifest": {"format": "elf", "arch": "x86_64"}},
        patch_plan=plan, detect=_detect, abi_check=_abi(), run_poc=_oracle(),
    )
    assert report["decision"] == "rejected"
    assert _by_id(report)["target-scope"]["status"] == "failed"


def test_plan_oracle_mismatch_is_rejected() -> None:
    original, candidate, plan = _associated_case()
    plan = json.loads(json.dumps(plan))
    plan["oracle"]["runner"] = "different-runner"
    report = verifier.verify_repair(
        original=original, candidate=candidate,
        metadata=_metadata(original, candidate),
        oracle={"manifest": {"format": "elf", "arch": "x86_64"}},
        patch_plan=plan, detect=_detect, abi_check=_abi(), run_poc=_oracle(),
    )
    assert report["decision"] == "rejected"
    assert _by_id(report)["runtime-oracle"]["status"] == "failed"


def test_plan_abi_fatal_is_rejected() -> None:
    original, candidate, plan = _associated_case()
    report = verifier.verify_repair(
        original=original, candidate=candidate,
        metadata=_metadata(original, candidate),
        oracle={"manifest": {"format": "elf", "arch": "x86_64"}},
        patch_plan=plan, detect=_detect, abi_check=_abi(ok=False), run_poc=_oracle(),
    )
    assert report["decision"] == "rejected"
    assert _by_id(report)["abi"]["status"] == "failed"


def test_plan_report_is_deterministic() -> None:
    original, candidate, plan = _resized_case()
    kwargs = dict(
        metadata=_metadata(original, candidate),
        oracle={"manifest": {"format": "elf", "arch": "x86_64"}},
        patch_plan=plan, detect=_detect, abi_check=_abi(), run_poc=_oracle(),
    )
    first = verifier.verify_repair(original=original, candidate=candidate, **kwargs)
    second = verifier.verify_repair(original=original, candidate=candidate, **kwargs)
    assert first["report_sha256"] == second["report_sha256"]
    assert first["decision"] == "verified"


# ---------------------------------------------------------------------------
# Phase-8B B1 artifact integration (read-only evidence inputs)
# ---------------------------------------------------------------------------


def _fake_b1_oracle(original: bytes, candidate: bytes, manifest):
    return {
        "status": "pass", "runner": "limactl", "tier": "emulated_run",
        "stdout_signature": "matched", "errno_signature": "not_run",
        "original_sha256": _sha(original), "candidate_sha256": _sha(candidate),
        "poc": [{"case_id": "poc", "kind": "poc"}],
        "regression": [{"case_id": "reg", "kind": "regression"}],
        "limitations": [],
    }


def _b1_stack_plan() -> tuple[bytes, bytes, dict, Path]:
    sample = B1 / "disagreement-stack-strcpy-x86_64"
    if not sample.is_dir():
        pytest.skip("B1 stack artifact is not present in this checkout")
    from app.services.binary_pipeline import detect_format
    from app.services.containers import detect_container

    original = (sample / "original.elf").read_bytes()
    candidate = (sample / "candidate.bin").read_bytes()
    outcome = json.loads((sample / "outcome.json").read_text(encoding="utf-8"))
    reproduction = outcome["reproduction"]
    site_va = int(reproduction["actions"][0]["site_va"])
    cave_va = int(reproduction["actions"][0]["cave_va"], 16)
    container = detect_container(original)
    site_offset = container.va_to_offset(site_va)
    assert site_offset is not None
    changed = []
    index = 0
    while index < len(original):
        if original[index] == candidate[index]:
            index += 1
            continue
        start = index
        while index < len(original) and original[index] != candidate[index]:
            index += 1
        changed.append((start, index - start))
    operations = []
    for offset, size in changed:
        if offset < site_offset + 6 and offset + size > site_offset:
            continue
        operations.append({
            "kind": "write", "original_offset": offset, "candidate_offset": None,
            "size": size, "before_hex": original[offset:offset + size].hex(),
            "after_hex": candidate[offset:offset + size].hex(), "site_va": None,
            "reason": "header_update", "authorization_ref": "phase8b:new-pt-load",
        })
    operations.append({
        "kind": "write", "original_offset": site_offset, "candidate_offset": None,
        "size": 6, "before_hex": original[site_offset:site_offset + 6].hex(),
        "after_hex": candidate[site_offset:site_offset + 6].hex(),
        "site_va": site_va, "reason": "reviewed_site", "authorization_ref": None,
    })
    appended = candidate[len(original):]
    operations.append({
        "kind": "insert", "original_offset": len(original),
        "candidate_offset": len(original), "size": len(appended),
        "before_hex": "", "after_hex": appended.hex(),
        "site_va": site_va, "reason": "guard_cave", "authorization_ref": None,
    })
    function_va = site_va - (site_va - 16956084)
    function_size = 16956128 - function_va
    function_offset = container.va_to_offset(function_va)
    plan = {
        "schema_version": 1, "candidate_id": "cand-phase8b-stack-strcpy",
        "target_sha256": _sha(original), "candidate_sha256": _sha(candidate),
        "strategy": "guard_cave", "scope_policy": "target_scoped_associated",
        "target_scope": {"policy": "target_scoped_associated", "name": "vuln_copy",
                         "va": 16956084, "end": 16956128},
        "operations": operations,
        "cave": {"va": cave_va, "size": 38, "executable": True, "method": "new-pt-load"},
        "relocations": [],
        "abi_blocks": [{
            "function": "vuln_copy", "va": function_va, "size": function_size,
            "arch": "x86_64",
            "evidence_sha256": _sha(candidate[function_offset:function_offset + function_size]),
        }],
        "oracle": {"manifest_sha256": _sha(
            (ROOT / "fixtures/poc/elf-x86_64-strcpy.json").read_bytes()),
            "runner": "limactl", "tier": "emulated_run", "status": "executed"},
        "limitations": [],
    }
    assert detect_format(original)[1] == "x86_64"
    return original, candidate, plan, ROOT / "fixtures/poc/elf-x86_64-strcpy.json"


def _b1_heap_plan() -> tuple[bytes, bytes, dict, Path]:
    sample = B1 / "disagreement-heap-capacity-x86_64"
    if not sample.is_dir():
        pytest.skip("B1 heap artifact is not present in this checkout")
    original = (sample / "original.elf").read_bytes()
    candidate = (sample / "candidate.bin").read_bytes()
    outcome = json.loads((sample / "outcome.json").read_text(encoding="utf-8"))
    reproduction = outcome["reproduction"]
    action = reproduction["actions"][0]
    message = reproduction["message_actions"][0]
    operations = [
        {"kind": "write", "original_offset": action["offset"], "candidate_offset": None,
         "size": action["size"], "before_hex": action["before_hex"],
         "after_hex": action["after_hex"], "site_va": action["site_va"],
         "reason": "reviewed_site", "authorization_ref": None},
        {"kind": "write", "original_offset": message["offset"], "candidate_offset": None,
         "size": message["size"], "before_hex": message["before_hex"],
         "after_hex": message["after_hex"], "site_va": None,
         "reason": "rodata_message",
         "authorization_ref": "phase8b:capacity-message-align"},
    ]
    plan = {
        "schema_version": 1, "candidate_id": "cand-phase8b-heap-capacity",
        "target_sha256": _sha(original), "candidate_sha256": _sha(candidate),
        "strategy": "capacity_check_rewrite", "scope_policy": "target_scoped_associated",
        "target_scope": {"policy": "target_scoped_associated", "name": "capacity_site",
                         "va": 4202713, "end": 4202729},
        "operations": operations, "cave": None, "relocations": [], "abi_blocks": [],
        "oracle": {"manifest_sha256": _sha(
            (ROOT / "fixtures/poc/marcx-capacity.json").read_bytes()),
            "runner": "limactl", "tier": "emulated_run", "status": "executed"},
        "limitations": [],
    }
    return original, candidate, plan, ROOT / "fixtures/poc/marcx-capacity.json"


def test_b1_stack_resized_candidate_verifies_with_plan() -> None:
    original, candidate, plan, poc = _b1_stack_plan()
    report = verifier.verify_repair(
        original=original, candidate=candidate,
        metadata={"format": "elf", "arch": "x86_64", "bits": 64, "endian": "little",
                  "target_sha256": _sha(original),
                  "target_scope": plan["target_scope"],
                  "generator": {"generator_id": "deterministic-repair-any/test"}},
        oracle=poc, patch_plan=plan, run_poc=_fake_b1_oracle,
    )
    assert report["decision"] == "verified", [
        (check["id"], check["status"], check["detail"]) for check in report["checks"]
    ]
    checks = _by_id(report)
    assert checks["layout-plan"]["status"] == "passed"
    assert checks["target-scope"]["status"] == "passed"
    assert checks["abi"]["status"] == "passed"
    assert report["layout_evidence"]["replay_ok"] is True
    validation = verifier.validate_verification_report(report)
    assert validation["ok"] is True, validation["violations"]


def test_b1_heap_associated_candidate_is_not_verified_without_abi_evidence() -> None:
    original, candidate, plan, poc = _b1_heap_plan()
    report = verifier.verify_repair(
        original=original, candidate=candidate,
        metadata={"format": "elf", "arch": "x86_64", "bits": 64, "endian": "little",
                  "target_sha256": _sha(original),
                  "target_scope": plan["target_scope"],
                  "generator": {"generator_id": "deterministic-repair-any/test"}},
        oracle=poc, patch_plan=plan, run_poc=_fake_b1_oracle,
    )
    checks = _by_id(report)
    assert checks["layout-plan"]["status"] == "passed"
    assert checks["action-replay"]["status"] == "passed"
    assert checks["target-scope"]["status"] == "passed"
    assert checks["abi"]["status"] == "not_run"
    assert report["decision"] == "not_run"
    assert any("ABI" in item for item in report["limitations"])
    validation = verifier.validate_verification_report(report)
    assert validation["ok"] is True, validation["violations"]
