"""P0 safe default: whole-image repair must fail safely unless explicitly allowed.

The default product policy is target-scoped or analysis-only:

* ``repair_any`` without a target and without ``allow_whole_image=True`` is
  analysis-only -- no candidate, no download, no success-readable verification
  packet, ``target_policy="analysis_only"``;
* a declared target keeps today's target-scoped verified path
  (``target_policy="target_scoped"`` + ``patch.target_scope``);
* the historical whole-image engine is only reachable through the explicit
  ``allow_whole_image=True`` opt-in and records ``target_policy="whole_image"``
  (never a target repair);
* a PoC manifest cannot silently opt into whole-image mode;
* review/repair/quick-repair APIs and the CLI inherit the same default, and the
  GUI quick-repair card exposes an optional target input plus an explicit
  default-OFF whole-image checkbox.
"""
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from fastapi.testclient import TestClient

import app.services.poc_runner as poc_runner
from app.main import CSRF_TOKEN, SESSION_TOKEN, app
from app.services.binary_pipeline import repair_any, repair_binary
from app.services.binary_repair_engine import repair_elf
from app.services.binary_review import run_direct_repair
from app.services.binary_verification import build_verification
from app.services.unified_verification import build as build_unified_packet

ROOT = Path(__file__).resolve().parents[1]
VULN = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"
HEAP = ROOT / "fixtures" / "hard-cases" / "vuln-heap-malloc-x86_64.elf"
HEAP_MANIFEST = ROOT / "fixtures" / "poc" / "heap-malloc.json"
PE_VULN = ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe"
MARCX = ROOT / "fixtures" / "elf" / "vuln-capacity-confusion-x86_64.elf"

SAFE_DEFAULT_REASON = "whole-image repair requires an explicit target or allow_whole_image"


def _read(path: Path) -> bytes:
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return path.read_bytes()


def _load_json(path: Path) -> dict:
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _FakePocEvidence:
    """Minimal passing PocEvidence stand-in (run_poc.to_dict shape)."""

    def __init__(self) -> None:
        self._payload = {
            "schema_version": 1,
            "status": "pass",
            "runner": "limactl",
            "tier": "emulated_run",
            "stdout_signature": "matched",
            "no_input": False,
            "original_sha256": "",
            "candidate_sha256": "",
            "poc": [
                self._case("poc", "original", 255, True),
                self._case("poc", "candidate", 0, False),
            ],
            "regression": [
                self._case("regression", "original", 0, False),
                self._case("regression", "candidate", 0, False),
            ],
            "limitations": [],
        }

    @staticmethod
    def _case(kind: str, executable: str, exit_code: int, crashed: bool) -> dict:
        return {
            "case_id": "case",
            "kind": kind,
            "executable": executable,
            "exit_code": exit_code,
            "crashed": crashed,
            "stdout": "",
            "stderr": "",
            "stdout_hex": "",
            "timed_out": False,
            "error": None,
            "expected_ok": True,
        }

    def to_dict(self) -> dict:
        return json.loads(json.dumps(self._payload))


def _fake_passing_runner(monkeypatch) -> None:
    monkeypatch.setattr(poc_runner, "run_poc", lambda *a, **k: _FakePocEvidence())


def _client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    assert client.get("/?token=" + SESSION_TOKEN).status_code == 200
    return client


def _post(client: TestClient, path: str, data: bytes, name: str, **form_fields):
    form = {"csrf": CSRF_TOKEN, **{key: str(value) for key, value in form_fields.items()}}
    return client.post(
        path,
        files={"binary": (name, data, "application/octet-stream")},
        data=form,
    )


def _guest_runner_available() -> bool:
    try:
        from app.services.guest_runner import find_guest_runner

        return find_guest_runner("x86_64") is not None
    except Exception:  # noqa: BLE001 - a missing runner is a skip, not a failure
        return False


# ---------------------------------------------------------------------------
# 1. Pipeline safe default (no target, no opt-in)
# ---------------------------------------------------------------------------


def test_no_target_no_optin_is_analysis_only_without_candidate():
    outcome = repair_any(_read(HEAP), verify=True)
    report = outcome.report
    assert outcome.candidate is None
    assert outcome.verified is False
    assert outcome.download_allowed is False
    assert report.disposition == "analysis_only"
    assert report.supported is False
    assert report.candidate_available is False
    assert report.status == "unsupported"
    assert report.universal["target_policy"] == "analysis_only"
    assert report.universal["target_scope"] is None
    assert report.universal["allow_whole_image"] is False
    assert SAFE_DEFAULT_REASON in (report.error or "")
    assert SAFE_DEFAULT_REASON in " ".join(report.limitations)
    # No verification packet that could be read as a success.
    assert not (report.verification or {}).get("packet")
    # Findings/limitations may still be reported for transparency.
    assert report.patched_sha256 == _sha(_read(HEAP))


def test_manifest_without_target_stays_analysis_only(monkeypatch):
    # The PoC runner must not even be consulted by the safe default.
    def _must_not_run(*_args, **_kwargs):
        raise AssertionError("PoC manifest must not be executed by the safe default")

    monkeypatch.setattr(poc_runner, "run_poc", _must_not_run)
    outcome = repair_any(
        _read(HEAP), verify=True, poc_manifest=_load_json(HEAP_MANIFEST),
    )
    report = outcome.report
    assert outcome.candidate is None
    assert report.disposition == "analysis_only"
    assert report.universal["target_policy"] == "analysis_only"
    assert report.poc == {}
    assert not (report.verification or {}).get("packet")


def test_repair_binary_wrapper_defaults_to_safe_policy():
    patched, report = repair_binary(_read(PE_VULN), verify=True)
    assert patched is None
    assert report.disposition == "analysis_only"
    assert report.universal["target_policy"] == "analysis_only"


def test_explicit_whole_image_optin_restores_previous_behaviour():
    data = _read(VULN)
    outcome = repair_any(data, verify=True, allow_whole_image=True)
    report = outcome.report
    assert outcome.verified is True
    assert outcome.candidate is not None
    assert report.disposition == "verified_patch"
    assert report.strategy == "strict-template"
    assert report.universal["target_policy"] == "whole_image"
    assert report.universal["target_scope"] is None
    assert report.universal["allow_whole_image"] is True
    packet = report.verification["packet"]
    assert packet["scope"]["target_policy"] == "whole_image"
    assert report.verification["gate"]["success"] is True
    # Whole-image evidence is never claimed as a target repair.
    assert "target" not in packet["scope"]


def test_explicit_whole_image_optin_with_manifest_uses_native_poc(monkeypatch):
    _fake_passing_runner(monkeypatch)
    outcome = repair_any(
        _read(HEAP), verify=True,
        poc_manifest=_load_json(HEAP_MANIFEST),
        allow_whole_image=True,
    )
    report = outcome.report
    assert outcome.verified is True
    assert report.disposition == "verified_patch"
    assert report.universal["target_policy"] == "whole_image"
    packet = report.verification["packet"]
    assert packet["scope"]["target_policy"] == "whole_image"
    assert packet["scope"]["profile"] == "native_poc"


# ---------------------------------------------------------------------------
# 2. Target-scoped mode is unchanged and wins over the default
# ---------------------------------------------------------------------------


def test_target_mode_is_target_scoped_verified(monkeypatch):
    _fake_passing_runner(monkeypatch)
    outcome = repair_any(
        _read(HEAP), target="heap_bad", require_target=True,
        poc_manifest=_load_json(HEAP_MANIFEST),
    )
    report = outcome.report
    assert outcome.verified is True
    assert report.universal["target_policy"] == "target_scoped"
    assert report.universal["target_scope"]["name"] == "heap_bad"
    packet = report.verification["packet"]
    assert packet["scope"]["target_policy"] == "target_scoped"
    statuses = {check["id"]: check["status"] for check in packet["checks"]}
    assert statuses["patch.target_scope"] == "passed"


def test_require_target_without_target_fails_closed():
    outcome = repair_any(_read(HEAP), require_target=True)
    report = outcome.report
    assert outcome.candidate is None
    assert report.disposition == "unsupported"
    assert "requires an explicit target" in (report.error or "")


# ---------------------------------------------------------------------------
# 3. Review path / serialized payloads
# ---------------------------------------------------------------------------


def test_run_direct_repair_default_has_no_download_and_analysis_only_policy():
    outcome = run_direct_repair(_read(HEAP))
    assert outcome.patched is None
    assert outcome.decision["success"] is False
    assert outcome.report.universal["target_policy"] == "analysis_only"
    packet = outcome.verification.packet
    assert packet["scope"].get("target_policy") == "analysis_only"
    assert packet.get("checks") == []
    payload = outcome.to_payload(filename="heap-fixed.elf")
    assert payload["download_allowed"] is False
    assert payload["target_policy"] == "analysis_only"
    assert "patched_base64" not in payload


def test_run_direct_repair_whole_image_optin_records_policy():
    outcome = run_direct_repair(_read(VULN), allow_whole_image=True)
    assert outcome.decision["success"] is True
    payload = outcome.to_payload(filename="vuln-fixed.elf")
    assert payload["ok"] is True
    assert payload["target_policy"] == "whole_image"
    assert payload["manifest_routing"] == "legacy_readonly"
    assert payload["verification"]["scope"]["target_policy"] == "whole_image"
    assert base64.b64decode(payload["patched_base64"])[:4] == b"\x7fELF"


def test_run_direct_repair_target_scope_wins(monkeypatch):
    _fake_passing_runner(monkeypatch)
    outcome = run_direct_repair(
        _read(HEAP), target="heap_bad", require_target=True,
        poc_manifest=_load_json(HEAP_MANIFEST),
    )
    assert outcome.decision["success"] is True
    payload = outcome.to_payload(filename="heap-fixed.elf")
    assert payload["target_policy"] == "target_scoped"
    assert payload["verification"]["scope"]["target"]["name"] == "heap_bad"
    assert payload["verification"]["scope"]["target_policy"] == "target_scoped"
    assert "patched_base64" in payload


# ---------------------------------------------------------------------------
# 4. HTTP surfaces: review / repair / quick-repair
# ---------------------------------------------------------------------------


def test_review_api_default_is_safe_and_optin_verified():
    client = _client()
    response = _post(client, "/api/binary/repair-review", _read(VULN), "vuln.elf")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["download_allowed"] is False
    assert payload["candidate_available"] is False
    assert payload["target_policy"] == "analysis_only"
    assert payload["verification"]["scope"]["target_policy"] == "analysis_only"
    assert "patched_base64" not in payload
    assert SAFE_DEFAULT_REASON in (payload.get("detail") or "")

    response = _post(
        client, "/api/binary/repair-review", _read(VULN), "vuln.elf",
        allow_whole_image="1",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["target_policy"] == "whole_image"
    assert payload["verification"]["scope"]["target_policy"] == "whole_image"
    assert base64.b64decode(payload["patched_base64"])[:4] == b"\x7fELF"


def test_review_api_target_scoped_with_manifest(monkeypatch):
    _fake_passing_runner(monkeypatch)
    client = _client()
    response = client.post(
        "/api/binary/repair-review",
        files={
            "binary": ("heap.elf", _read(HEAP), "application/octet-stream"),
            "poc_manifest": (
                "heap-malloc.json",
                HEAP_MANIFEST.read_bytes(),
                "application/json",
            ),
        },
        data={
            "csrf": CSRF_TOKEN,
            "target": "heap_bad",
            "require_target": "1",
            "allow_whole_image": "0",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["target_policy"] == "target_scoped"
    assert payload["verification"]["scope"]["target"]["name"] == "heap_bad"
    assert base64.b64decode(payload["patched_base64"])[:4] == b"\x7fELF"


def test_review_api_require_target_validation():
    client = _client()
    response = _post(
        client, "/api/binary/repair-review", _read(VULN), "vuln.elf",
        require_target="1",
    )
    assert response.status_code == 422
    assert "target" in response.json()["detail"]
    response = _post(
        client, "/api/binary/repair-review", _read(VULN), "vuln.elf",
        target="x" * 257,
    )
    assert response.status_code == 422


def test_repair_and_quick_repair_endpoints_default_safe():
    client = _client()
    for path in ("/api/binary/repair", "/api/binary/quick-repair"):
        response = _post(client, path, _read(PE_VULN), "vuln.exe")
        assert response.status_code == 422, path
        payload = response.json()
        assert payload["ok"] is False
        assert payload["target_policy"] == "analysis_only"
        assert "patched_base64" not in payload
        assert SAFE_DEFAULT_REASON in (payload.get("detail") or "")

        response = _post(
            client, path, _read(PE_VULN), "vuln.exe", allow_whole_image="1",
        )
        assert response.status_code == 200, path
        payload = response.json()
        assert payload["ok"] is True
        assert payload["target_policy"] == "whole_image"
        assert payload["report"]["universal"]["target_policy"] == "whole_image"
        assert base64.b64decode(payload["patched_base64"])


# ---------------------------------------------------------------------------
# 5. Gate builders: policy metadata only, hashes commit to it
# ---------------------------------------------------------------------------


def _unified_build(**overrides):
    original = b"ORIGINAL-BYTES"
    candidate = b"CANDIDATE-BYT"
    kwargs = dict(
        format_name="elf",
        arch="x86_64",
        original=original,
        candidate=candidate,
        actions=[{"kind": "guard", "site_va": 0x1000}],
        runtime=None,
        reparse_ok=True,
        original_sha256=_sha(original),
        patched_sha256=_sha(candidate),
    )
    kwargs.update(overrides)
    return build_unified_packet(**kwargs)


def test_unified_builder_records_target_policy_without_changing_checks():
    baseline = _unified_build()
    policy = _unified_build(target_policy="whole_image")
    assert "target_policy" not in baseline.packet["scope"]
    assert policy.packet["scope"]["target_policy"] == "whole_image"
    checks = lambda packet: [(c["id"], c["status"]) for c in packet["checks"]]
    assert checks(baseline.packet) == checks(policy.packet)
    assert baseline.gate.outcome == policy.gate.outcome
    assert baseline.packet["report_sha256"] != policy.packet["report_sha256"]


def test_legacy_builder_policy_is_opt_in_and_hash_committed():
    raw = _read(VULN)
    patched, report = repair_elf(raw)
    assert patched is not None
    default = build_verification(report, original=raw, patched=patched)
    repeated = build_verification(report, original=raw, patched=patched)
    assert default.packet["report_sha256"] == repeated.packet["report_sha256"]
    assert "target_policy" not in default.packet["scope"]

    policy = build_verification(
        report, original=raw, patched=patched, target_policy="whole_image",
    )
    assert policy.packet["scope"]["target_policy"] == "whole_image"
    assert policy.packet["report_sha256"] != default.packet["report_sha256"]
    checks = lambda packet: [(c["id"], c["status"]) for c in packet["checks"]]
    assert checks(policy.packet) == checks(default.packet)
    assert policy.gate.success == default.gate.success
    assert policy.packet["report_sha256"] == policy.gate.evidence_sha256


# ---------------------------------------------------------------------------
# 6. GUI quick-repair card safe controls
# ---------------------------------------------------------------------------


def test_agent_quick_repair_card_exposes_safe_target_controls():
    client = _client()
    assert client.get("/agent/new").status_code == 200
    js = client.get("/static/js/agent.js")
    assert js.status_code == 200
    for marker in (
        "agent-repair-target",
        "目标函数（可选，声明补丁归属）",
        'form.append("target"',
        'form.append("require_target", "1")',
        "agent-allow-whole-image",
        "allowToggle.checked = false",
        'form.append("allow_whole_image"',
        "允许全镜像修复（不声明目标归属）",
        "agent-target-policy-chip",
        "target_policy",
    ):
        assert marker in js.text, marker


# ---------------------------------------------------------------------------
# 7. CLI: safe default vs explicit opt-in (one real target-scoped run)
# ---------------------------------------------------------------------------


def test_cli_default_is_analysis_only_and_optin_verifies(tmp_path):
    default = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "repair_binary.py"),
         str(VULN), str(tmp_path / "out.elf"), "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert default.returncode == 2, default.stderr
    payload = json.loads(default.stdout)
    assert payload["disposition"] == "analysis_only"
    assert payload["verified"] is False
    assert payload["target_policy"] == "analysis_only"
    assert "output" not in payload

    opt_in = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "repair_binary.py"),
         str(VULN), str(tmp_path / "out-whole.elf"), "--allow-whole-image", "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert opt_in.returncode == 0, opt_in.stderr
    payload = json.loads(opt_in.stdout)
    assert payload["verified"] is True
    assert payload["target_policy"] == "whole_image"
    assert (tmp_path / "out-whole.elf").read_bytes()[:4] == b"\x7fELF"


@pytest.mark.skipif(
    not _guest_runner_available(),
    reason="no native/qemu/Lima runner for x86_64 ELF on this host",
)
def test_cli_target_scoped_run_is_verified(tmp_path):
    out = tmp_path / "heap-fixed.elf"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "repair_binary.py"),
         str(HEAP), str(out), "--target", "heap_bad", "--require-target",
         "--poc", str(HEAP_MANIFEST), "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=240,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["verified"] is True
    assert payload["target_policy"] == "target_scoped"
    assert payload["target_scope_check"] == "passed"
    assert payload["target_scope"]["name"] == "heap_bad"
    assert out.read_bytes()[:4] == b"\x7fELF"
