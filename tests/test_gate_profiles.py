"""Declared acceptance/evidence-model harmonization (task C).

These tests pin the *declared* gate contract:

* the evidence profiles and the strategy -> profile mapping live in
  ``app.services.repair_matrix`` and are exposed by ``matrix_payload``;
* a wrong/unknown profile or a profile/evidence mismatch fails closed;
* rewrite actions are re-derived from the original and candidate bytes, so a
  tampered action, a missing byte or an empty action list fails;
* the supplied matrix cell and the runtime tier are checked against the matrix;
* a runner that is unavailable keeps the PoC checks ``not_run`` (inconclusive,
  never a mislabelled rejection);
* the declared no-input model (UAF etc.) turns an empty regression list into
  ``not_applicable_no_input``, while an *undeclared* empty regression still
  fails;
* the pipeline selects ``native_poc`` for non-stack destinations without any
  PoC manifest, so a heap/global candidate can never be claimed ``verified``
  through the stack/Unicorn oracle.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.binary_pipeline import _base_report, _evidence_profile, finish_candidate
from app.services.binary_pipeline import repair_any
from app.services.containers import detect_container
from app.services.repair_matrix import (
    EVIDENCE_PROFILES,
    REPAIR_CELLS,
    SINK_CLASSES,
    STRATEGY_PROFILES,
    matrix_payload,
    repair_cell,
    resolve_profile,
)
from app.services.runtime.evidence import RuntimeCase, RuntimeEvidence
from app.services.unified_verification import build

ROOT = Path(__file__).resolve().parents[1]
PE = ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe"

ELF_CELL = repair_cell(
    SimpleNamespace(format="elf", arch="x86_64", bits=64, endian="little")
).to_dict()
ORIGINAL = b"ORIGINAL-BYTES"
CANDIDATE = b"CANDIDATE-BYT"
ORIGINAL_SHA = hashlib.sha256(ORIGINAL).hexdigest()
CANDIDATE_SHA = hashlib.sha256(CANDIDATE).hexdigest()


def _runtime(*, tier: str = "emulated_run", verdict: str = "pass") -> RuntimeEvidence:
    return RuntimeEvidence(
        tier=tier,
        engine="unicorn-test",
        verdict=verdict,
        cases=[RuntimeCase(input_len=16, exit_code=0, canary_intact=True, output_len=16)],
    )


def _external_poc(
    *,
    status: str = "pass",
    no_input: bool | None = None,
    regression: bool = True,
    signature: str = "matched",
    tier: str = "emulated_run",
) -> dict:
    payload: dict = {
        "schema_version": 1,
        "status": status,
        "runner": "limactl",
        "tier": tier if status in {"pass", "fail"} else "",
        "poc": [
            {"case_id": "poc", "kind": "poc", "executable": "original",
             "crashed": True, "stdout_hex": "", "expected_ok": True},
            {"case_id": "poc", "kind": "poc", "executable": "candidate",
             "crashed": False, "stdout_hex": "", "expected_ok": status == "pass"},
        ],
        "regression": (
            [
                {"case_id": "reg", "kind": "regression", "executable": "original",
                 "exit_code": 0, "stdout_hex": "61", "expected_ok": True},
                {"case_id": "reg", "kind": "regression", "executable": "candidate",
                 "exit_code": 0, "stdout_hex": "61", "expected_ok": True},
            ]
            if regression
            else []
        ),
        "limitations": [],
        "stdout_signature": signature,
    }
    if no_input is not None:
        payload["no_input"] = no_input
    return payload


def _build(**overrides):
    kwargs = dict(
        format_name="elf",
        arch="x86_64",
        original=ORIGINAL,
        candidate=CANDIDATE,
        actions=[{"kind": "guard", "offset": 4, "size": 4,
                  "before_hex": "41414141", "after_hex": "42424242"}],
        runtime=_runtime(),
        reparse_ok=True,
        original_sha256=ORIGINAL_SHA,
        patched_sha256=CANDIDATE_SHA,
        profile="emulated_instruction",
        cell=dict(ELF_CELL),
    )
    kwargs.update(overrides)
    return build(**kwargs)


def _statuses(verification) -> dict[str, str]:
    return {str(check["id"]): str(check["status"]) for check in verification.packet["checks"]}


# ---------------------------------------------------------------------------
# Declared registry and matrix payload
# ---------------------------------------------------------------------------

def test_evidence_profiles_are_declared():
    expected = {"strict_template", "emulated_instruction", "native_poc",
                "native_poc_rewrite"}
    assert set(EVIDENCE_PROFILES) == expected
    for name, meta in EVIDENCE_PROFILES.items():
        assert meta["description"], name
        assert meta["evidence_sources"], name
        assert meta["required_checks"], name
        assert all(isinstance(item, str) for item in meta["required_checks"]), name
        assert isinstance(meta["legacy_required_checks"], tuple), name
    assert STRATEGY_PROFILES["capacity"] == "native_poc_rewrite"
    assert STRATEGY_PROFILES["strict-template"] == "strict_template"
    assert STRATEGY_PROFILES["guard"] == "emulated_instruction"
    assert STRATEGY_PROFILES["immediate"] == "emulated_instruction"


def test_matrix_payload_exposes_profiles_and_strategy_mapping():
    payload = matrix_payload()
    assert set(payload["evidence_profiles"]) == set(EVIDENCE_PROFILES)
    assert payload["strategy_profiles"] == STRATEGY_PROFILES
    for name, meta in payload["evidence_profiles"].items():
        assert meta["evidence_sources"] == list(
            EVIDENCE_PROFILES[name]["evidence_sources"]
        )
        assert meta["required_checks"] == list(
            EVIDENCE_PROFILES[name]["required_checks"]
        )
    # The route payload must stay English/ASCII-only.
    assert str(payload).isascii()


def test_capacity_strategy_and_sink_are_scoped_to_elf_x86_64():
    assert SINK_CLASSES["capacity_check_mismatch"]["strategy"] == "capacity"
    elf_x64 = repair_cell(
        SimpleNamespace(format="elf", arch="x86_64", bits=64, endian="little")
    )
    assert "capacity" in elf_x64.strategies
    assert "capacity_check_mismatch" in elf_x64.sink_classes
    for cell in REPAIR_CELLS:
        if (cell.container, cell.arch) == ("elf", "x86_64"):
            continue
        assert "capacity" not in cell.strategies, cell.key
        assert "capacity_check_mismatch" not in cell.sink_classes, cell.key
        assert set(cell.sink_classes) <= set(SINK_CLASSES) - {"capacity_check_mismatch"}


def test_resolve_profile_rules():
    assert resolve_profile() == "emulated_instruction"
    assert resolve_profile(has_runtime=True) == "emulated_instruction"
    assert resolve_profile(destination_kind="heap") == "native_poc"
    assert resolve_profile(destination_kind="global") == "native_poc"
    assert resolve_profile(has_external_poc=True) == "native_poc"
    assert resolve_profile(has_rewrite_actions=True) == "native_poc_rewrite"
    assert resolve_profile(capacity=True) == "native_poc_rewrite"
    assert resolve_profile(has_external_poc=True, destination_kind="heap") == "native_poc"


# ---------------------------------------------------------------------------
# profile.declared / profile.evidence / profile.required_checks
# ---------------------------------------------------------------------------

def test_emulated_instruction_profile_passes_with_runtime_evidence():
    verification = _build()
    assert verification.gate.success is True, verification.gate
    statuses = _statuses(verification)
    assert statuses["profile.declared"] == "passed"
    assert statuses["profile.evidence"] == "passed"
    assert statuses["profile.required_checks"] == "passed"
    assert verification.packet["scope"]["profile"] == "emulated_instruction"
    assert verification.packet["scope"]["profile_declared"] is True


def test_unknown_profile_fails_closed():
    verification = _build(profile="no_such_profile")
    assert verification.gate.success is False
    assert verification.gate.outcome == "rejected"
    statuses = _statuses(verification)
    assert statuses["profile.declared"] == "failed"
    assert statuses["profile.evidence"] == "failed"


def test_profile_evidence_mismatch_fails_closed():
    # A native-PoC profile supplied with only the stack/Unicorn runtime must be
    # rejected: the declared oracle is not the supplied oracle.
    verification = _build(profile="native_poc")
    assert verification.gate.success is False
    assert verification.gate.outcome == "rejected"
    statuses = _statuses(verification)
    assert statuses["profile.declared"] == "passed"
    assert statuses["profile.evidence"] == "failed"
    detail = next(
        check["detail"] for check in verification.packet["checks"]
        if check["id"] == "profile.evidence"
    )
    assert "runtime" in detail

    # And the reverse: an emulated-instruction profile supplied with only an
    # external PoC differential.
    verification = _build(
        runtime=None, profile="emulated_instruction",
        external_poc=_external_poc(),
    )
    assert verification.gate.success is False
    statuses = _statuses(verification)
    assert statuses["profile.evidence"] == "failed"
    assert "external_poc" in next(
        check["detail"] for check in verification.packet["checks"]
        if check["id"] == "profile.evidence"
    )


def test_profile_required_checks_reports_failed_ids():
    verification = _build(runtime=_runtime(verdict="fail"))
    assert verification.gate.success is False
    statuses = _statuses(verification)
    assert statuses["runtime.contract"] == "failed"
    assert statuses["profile.required_checks"] == "failed"
    detail = next(
        check["detail"] for check in verification.packet["checks"]
        if check["id"] == "profile.required_checks"
    )
    assert "runtime.contract" in detail


def test_profile_required_checks_stays_not_run_for_unavailable_evidence():
    # Runtime evidence was requested through the profile but no runner supplied
    # it: the enforcement check must not turn that into a rejection.
    verification = _build(runtime=None)
    assert verification.gate.success is False
    assert verification.gate.outcome == "inconclusive"
    statuses = _statuses(verification)
    assert statuses["profile.evidence"] == "not_run"
    assert statuses["profile.required_checks"] == "not_run"


# ---------------------------------------------------------------------------
# patch.rewrite / patch.capacity
# ---------------------------------------------------------------------------

def _rewrite_action() -> dict:
    return {
        "kind": "capacity_check_rewrite",
        "offset": 0,
        "size": 4,
        "before_hex": ORIGINAL[:4].hex(),
        "after_hex": CANDIDATE[:4].hex(),
        "site_va": 0x1000,
    }


def test_rewrite_actions_are_rederived_from_bytes():
    verification = _build(
        runtime=None,
        profile="native_poc_rewrite",
        rewrite_actions=[_rewrite_action()],
        external_poc=_external_poc(),
    )
    assert verification.gate.success is True, verification.gate
    statuses = _statuses(verification)
    assert statuses["patch.rewrite"] == "passed"
    assert statuses["profile.evidence"] == "passed"


def test_tampered_rewrite_action_fails():
    action = _rewrite_action()
    action["before_hex"] = "ffffffff"
    verification = _build(
        runtime=None,
        profile="native_poc_rewrite",
        rewrite_actions=[action],
        external_poc=_external_poc(),
    )
    assert verification.gate.success is False
    assert verification.gate.outcome == "rejected"
    statuses = _statuses(verification)
    assert statuses["patch.rewrite"] == "failed"
    detail = next(
        check["detail"] for check in verification.packet["checks"]
        if check["id"] == "patch.rewrite"
    )
    assert "before_hex" in detail


def test_rewrite_action_missing_candidate_bytes_fails():
    action = _rewrite_action()
    action["offset"] = len(CANDIDATE)  # slice beyond the candidate
    verification = _build(
        runtime=None,
        profile="native_poc_rewrite",
        rewrite_actions=[action],
        external_poc=_external_poc(),
    )
    assert verification.gate.success is False
    assert _statuses(verification)["patch.rewrite"] == "failed"


def test_zero_rewrite_actions_fails_closed():
    verification = _build(
        runtime=None,
        profile="native_poc_rewrite",
        rewrite_actions=[],
        external_poc=_external_poc(),
    )
    assert verification.gate.success is False
    assert verification.gate.outcome == "rejected"
    assert _statuses(verification)["patch.rewrite"] == "failed"


def test_legacy_capacity_payload_is_rederived_and_kept_for_compat():
    payload = {
        "actions": [_rewrite_action()],
        "sites": [{"site_va": 0x1000, "file_offset": 0, "block_size": 16}],
        "message_actions": [],
        "limitations": [],
    }
    verification = _build(
        runtime=None,
        profile="native_poc_rewrite",
        rewrite_actions=None,
        capacity=payload,
        external_poc=_external_poc(),
    )
    assert verification.gate.success is True, verification.gate
    statuses = _statuses(verification)
    assert statuses["patch.capacity"] == "passed"
    assert statuses["patch.rewrite"] == "passed"
    assert verification.packet["capacity"] == payload


# ---------------------------------------------------------------------------
# container.cell / runtime.cell_tier
# ---------------------------------------------------------------------------

def test_container_cell_mismatch_fails():
    wrong_bits = dict(ELF_CELL)
    wrong_bits["bits"] = 32
    verification = _build(cell=wrong_bits)
    assert verification.gate.success is False
    assert _statuses(verification)["container.cell"] == "failed"

    wrong_container = dict(ELF_CELL)
    wrong_container["container"] = "pe"
    verification = _build(cell=wrong_container)
    assert verification.gate.success is False
    assert _statuses(verification)["container.cell"] == "failed"


def test_runtime_cell_tier_mismatch_fails():
    # The ELF/x86-64 cell only declares emulated_run in this matrix; a native
    # runtime tier claim for it is a matrix mismatch.
    verification = _build(runtime=_runtime(tier="native_run"))
    assert verification.gate.success is False
    statuses = _statuses(verification)
    assert statuses["runtime.cell_tier"] == "failed"
    detail = next(
        check["detail"] for check in verification.packet["checks"]
        if check["id"] == "runtime.cell_tier"
    )
    assert "native_run" in detail


# ---------------------------------------------------------------------------
# External PoC as the runtime evidence model
# ---------------------------------------------------------------------------

def test_external_poc_derives_runtime_evidence_when_no_runtime_engine():
    verification = _build(
        runtime=None,
        profile="native_poc",
        external_poc=_external_poc(),
    )
    assert verification.gate.success is True, verification.gate
    statuses = _statuses(verification)
    assert statuses["runtime.evidence"] == "passed"
    assert statuses["runtime.tier"] == "passed"
    assert statuses["runtime.contract"] == "passed"
    assert verification.packet["runtime"] is None


def test_unavailable_runner_is_not_run_and_inconclusive():
    verification = _build(
        runtime=None,
        profile="native_poc",
        external_poc=_external_poc(status="unavailable"),
    )
    assert verification.gate.success is False
    assert verification.gate.outcome == "inconclusive"
    statuses = _statuses(verification)
    for check_id in (
        "poc.native.available",
        "poc.native.original_failure",
        "poc.native.candidate_pass",
        "poc.native.regression",
        "poc.native.stdout_signature",
        "runtime.evidence",
        "runtime.tier",
        "runtime.contract",
    ):
        assert statuses[check_id] == "not_run", check_id


def test_no_input_declaration_makes_empty_regression_not_applicable():
    verification = _build(
        runtime=None,
        profile="native_poc",
        external_poc=_external_poc(no_input=True, regression=False,
                                   signature="not_applicable"),
    )
    assert verification.gate.success is True, verification.gate
    statuses = _statuses(verification)
    assert statuses["poc.native.regression"] == "passed"
    detail = next(
        check["detail"] for check in verification.packet["checks"]
        if check["id"] == "poc.native.regression"
    )
    assert "not_applicable_no_input" in detail


def test_undeclared_empty_regression_still_fails():
    verification = _build(
        runtime=None,
        profile="native_poc",
        external_poc=_external_poc(regression=False, signature="not_applicable"),
    )
    assert verification.gate.success is False
    assert verification.gate.outcome == "rejected"
    assert _statuses(verification)["poc.native.regression"] == "failed"


# ---------------------------------------------------------------------------
# Pipeline profile selection (heap/global destinations never use the stack
# oracle) and no-manifest fail-closed disposition
# ---------------------------------------------------------------------------

def test_pipeline_profile_selection_rules():
    runtime = _runtime()
    external = _external_poc()
    assert _evidence_profile(
        external_poc=None, runtime=runtime, destination_kind="stack",
        requested_strategy="auto", report_strategy="guard",
    ) == "emulated_instruction"
    assert _evidence_profile(
        external_poc=None, runtime=runtime, destination_kind="heap",
        requested_strategy="auto", report_strategy="guard",
    ) == "native_poc"
    assert _evidence_profile(
        external_poc=external, runtime=runtime, destination_kind="stack",
        requested_strategy="auto", report_strategy="guard",
    ) == "native_poc"
    assert _evidence_profile(
        external_poc=external, runtime=None, destination_kind="stack",
        requested_strategy="capacity", report_strategy="capacity",
    ) == "native_poc_rewrite"
    assert _evidence_profile(
        external_poc=None, runtime=None, destination_kind="stack",
        requested_strategy="capacity", report_strategy="capacity",
        capacity_payload={"actions": []},
    ) == "native_poc_rewrite"


def test_capacity_candidate_without_manifest_is_never_verified():
    fixture = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86_64.elf"
    if not fixture.is_file():
        pytest.skip("ELF fixture missing")
    original = fixture.read_bytes()
    baseline = repair_any(original)
    patched = baseline.candidate
    if patched is None:
        pytest.skip("the host cannot produce a guard candidate")
    container = detect_container(original)
    # Real differing bytes: the gate must be able to re-derive them, the
    # candidate must still not be claimed verified without PoC evidence.
    offset = next(
        index for index, (before, after) in enumerate(zip(original, patched))
        if before != after
    )
    size = min(4, len(original) - offset, len(patched) - offset)
    actions = [{
        "kind": "capacity_check_rewrite", "offset": offset, "size": size,
        "before_hex": original[offset:offset + size].hex(),
        "after_hex": patched[offset:offset + size].hex(),
    }]
    capacity = {
        "capacity": 16,
        "actions": actions,
        "sites": [{"site_va": 0x1000, "file_offset": offset, "block_size": 16}],
        "message_actions": [],
        "limitations": [],
    }
    report = _base_report(original, container)
    outcome = finish_candidate(
        original, container, patched, [], actions,
        report=report, requested_strategy="capacity",
        verify=True, allow_static_only=False,
        poc_manifest=None, rewrite_actions=actions, capacity=capacity,
    )
    assert outcome.verified is False
    assert outcome.candidate is None
    assert outcome.report.disposition == "not_verified"
    assert outcome.report.strategy == "capacity"
    assert outcome.report.mode == "capacity-check"
    assert outcome.report.capacity == 16
    packet = outcome.report.verification["packet"]
    assert packet["scope"]["profile"] == "native_poc_rewrite"
    assert packet["runtime"] is None
    assert outcome.report.verification["gate"]["outcome"] == "inconclusive"


def test_heap_destination_does_not_use_the_stack_oracle(monkeypatch):
    if not PE.is_file():
        pytest.skip("PE fixture missing")
    import app.services.binary_pipeline as pipeline

    data = PE.read_bytes()
    baseline = repair_any(data)
    patched = baseline.candidate
    if patched is None:
        pytest.skip("the host cannot produce a PE guard candidate")
    container = detect_container(data)
    report = _base_report(data, container)
    heap_sink = SimpleNamespace(
        kind="unbounded_copy", capacity=16, destination_kind="heap",
        function_va=0x1000, call_va=0x1010, dest_rel=0, length=64,
        patchable=True, callee="strcpy", confidence="high",
        detail="synthetic heap destination",
    )
    calls = {"count": 0}

    def bomb(*args, **kwargs):
        calls["count"] += 1
        raise AssertionError("the stack/Unicorn oracle must not judge a heap sink")

    monkeypatch.setattr(pipeline, "_select_runtime", bomb)
    outcome = finish_candidate(
        data, container, patched, [heap_sink],
        [{"kind": "guard", "offset": 0, "size": 4,
          "before_hex": "90909090", "after_hex": "cccccccc"}],
        report=report, requested_strategy="guard",
        verify=True, allow_static_only=False,
    )
    assert calls["count"] == 0
    assert outcome.verified is False
    assert outcome.candidate is None
    assert outcome.report.disposition == "not_verified"
    packet = outcome.report.verification["packet"]
    assert packet["scope"]["profile"] == "native_poc"
    assert packet["runtime"] is None
