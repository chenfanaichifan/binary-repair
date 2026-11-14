"""The deterministic repair matrix is a single source of truth."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.repair_matrix import (
    DISPOSITIONS,
    EVIDENCE_PROFILES,
    FIXTURE_STRATEGY_EVIDENCE,
    REPAIR_CELLS,
    RUNTIME_TIERS,
    SINK_CLASSES,
    STRATEGY_PROFILES,
    is_repairable,
    matrix_payload,
    repair_cell,
    resolve_profile,
    supported_pairs,
)


def _container(fmt: str, arch: str, bits: int | None, endian: str = "little"):
    return SimpleNamespace(format=fmt, arch=arch, bits=bits, endian=endian)


def test_matrix_contains_the_v5_cells():
    pairs = supported_pairs()
    for pair in (
        ("elf", "i386"), ("elf", "x86_64"), ("elf", "arm64"),
        ("pe", "i386"), ("pe", "x86_64"), ("pe", "arm64"),
        ("macho", "x86_64"), ("macho", "arm64"),
    ):
        assert pair in pairs, pair
    assert len(REPAIR_CELLS) == 8


def test_bits_are_part_of_the_matrix():
    assert repair_cell(_container("elf", "i386", 32)) is not None
    assert repair_cell(_container("elf", "i386", 64)) is None
    assert repair_cell(_container("pe", "x86_64", 32)) is None


def test_big_endian_and_unknown_cells_are_outside_the_matrix():
    assert repair_cell(_container("elf", "x86_64", 64, "big")) is None
    assert repair_cell(_container("macho-fat", "arm64", 64)) is None
    assert repair_cell(_container("elf", "arm", 32)) is None
    assert repair_cell(_container("elf", "riscv", 64)) is None
    assert is_repairable(_container("elf", "x86_64", 64)) is True


def test_matrix_payload_is_english_and_complete():
    payload = matrix_payload()
    assert payload["schema_version"] == 1
    assert len(payload["cells"]) == 8
    assert "verified_patch" in payload["dispositions"]
    assert "static_only_patch" in payload["dispositions"]
    assert "not_verified" in payload["dispositions"]
    assert payload["non_goals"]
    assert all(cell["container"] and cell["arch"] for cell in payload["cells"])
    # JSON contract is English ASCII only.
    assert str(payload).isascii()


def test_dispositions_are_declared_once():
    assert "verified_patch" in DISPOSITIONS
    assert len(set(DISPOSITIONS)) == len(DISPOSITIONS)


def _cell(fmt: str, arch: str):
    return repair_cell(_container(fmt, arch, 64 if arch != "i386" else 32))


def test_capacity_check_rewrite_is_scoped_to_elf_x86_64():
    assert SINK_CLASSES["capacity_check_mismatch"]["strategy"] == "capacity"
    assert "capacity" in _cell("elf", "x86_64").strategies
    assert "capacity_check_mismatch" in _cell("elf", "x86_64").sink_classes
    for fmt, arch in (
        ("elf", "i386"), ("elf", "arm64"), ("pe", "i386"),
        ("pe", "x86_64"), ("pe", "arm64"),
        ("macho", "x86_64"), ("macho", "arm64"),
    ):
        cell = _cell(fmt, arch)
        assert "capacity" not in cell.strategies, cell.key
        assert "capacity_check_mismatch" not in cell.sink_classes, cell.key


def test_evidence_profiles_and_strategy_mapping_are_declared():
    assert set(EVIDENCE_PROFILES) == {
        "strict_template", "emulated_instruction", "native_poc",
        "native_poc_rewrite",
    }
    for meta in EVIDENCE_PROFILES.values():
        assert meta["description"]
        assert meta["evidence_sources"]
        assert meta["required_checks"]
        assert isinstance(meta["legacy_required_checks"], tuple)
    assert STRATEGY_PROFILES == {
        "strict-template": "strict_template",
        "immediate": "emulated_instruction",
        "guard": "emulated_instruction",
        "capacity": "native_poc_rewrite",
    }
    payload = matrix_payload()
    assert payload["strategy_profiles"] == STRATEGY_PROFILES
    assert set(payload["evidence_profiles"]) == set(EVIDENCE_PROFILES)
    assert str(payload).isascii()


def test_resolve_profile_never_uses_the_stack_oracle_for_non_stack_sinks():
    assert resolve_profile() == "emulated_instruction"
    assert resolve_profile(destination_kind="heap") == "native_poc"
    assert resolve_profile(destination_kind="global") == "native_poc"
    assert resolve_profile(has_external_poc=True) == "native_poc"
    assert resolve_profile(capacity=True) == "native_poc_rewrite"


def test_no_dead_sink_classes_are_declared():
    # immediate_length was declared historically but no analyzer path emits it
    # (the legacy engine reports read/write length findings separately), so the
    # declaration must not claim an unimplemented capability.
    assert "immediate_length" not in SINK_CLASSES
    assert set(SINK_CLASSES) == {
        "unbounded_copy", "memcpy_length", "syscall_length", "checked_copy",
        "capacity_check_mismatch",
    }


def test_cells_advertise_only_sinks_their_analyzer_can_emit():
    # Measured from the analyzer emission paths (arch dispatch is shared by
    # ELF/PE/Mach-O): x86_64 emits guard/immediate/syscall/checked, i386 emits
    # guard/immediate only, and arm64 emits guard/immediate/checked.
    expected = {
        "i386": {"unbounded_copy", "memcpy_length"},
        "x86_64": {"unbounded_copy", "memcpy_length", "syscall_length", "checked_copy"},
        "arm64": {"unbounded_copy", "memcpy_length", "checked_copy"},
    }
    for cell in REPAIR_CELLS:
        want = set(expected[cell.arch])
        if (cell.container, cell.arch) == ("elf", "x86_64"):
            want = want | {"capacity_check_mismatch"}
        assert set(cell.sink_classes) == want, cell.key


def test_runtime_tier_vocabulary_includes_unavailable():
    # The runtime evidence modules report tier="unavailable"; the matrix must
    # declare that vocabulary instead of silently dropping it.
    assert "unavailable" in RUNTIME_TIERS
    assert "never a verified success" in RUNTIME_TIERS["unavailable"]
    assert set(RUNTIME_TIERS) >= {"native_run", "emulated_run", "static_only"}


def test_matrix_payload_reports_untested_strategies_honestly():
    payload = matrix_payload()
    evidence = payload["fixture_strategy_evidence"]
    assert evidence == {
        key: list(value) for key, value in FIXTURE_STRATEGY_EVIDENCE.items()
    }
    for row in payload["cells"]:
        key = f"{row['container']}/{row['arch']}/{row['bits']}/{row['endian']}"
        exercised = FIXTURE_STRATEGY_EVIDENCE.get(key, ())
        assert set(row["fixture_strategies"]) == {
            strategy for strategy in row["strategies"] if strategy in exercised
        }, key
        assert set(row["untested_strategies"]) == {
            strategy for strategy in row["strategies"] if strategy not in exercised
        }, key
        # Nothing is claimed as tested unless fixture evidence exists for it.
        assert not set(row["fixture_strategies"]) - set(exercised), key
    untested = {
        f"{row['container']}/{row['arch']}": row["untested_strategies"]
        for row in payload["cells"]
    }
    # The immediate strategy has no exercised fixture outside elf/i386.
    assert untested["elf/x86_64"] == ["immediate"]
    assert untested["elf/i386"] == []
    assert untested["pe/x86_64"] == ["immediate"]
