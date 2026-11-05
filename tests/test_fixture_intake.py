"""The fixture intake checker: a fixture is evidence only when it is whole.

Every case here builds a fixture in ``tmp_path``.  Nothing is written under
``fixtures/public``: a synthetic sample must never be mistaken for a real
second-class corpus entry by M3 or M4.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.fixture_intake import check_fixture

CASE = {
    "schema_version": 1,
    "case_id": "second_class_demo",
    "original_sha256": "0" * 64,
    "tests": [],
}


def _case(case_id: str, kind: str, argv: list[str]) -> dict:
    return {
        "id": case_id,
        "kind": kind,
        "argv": argv,
        "expected": {"return_code": 0, "stdout": "", "stderr": ""},
    }


def _contract(*, input_mode: str | None = None) -> dict:
    """A complete SecurityContract body; the schema is M5's, not the test's."""
    data = {
        "schema_version": 2,
        "target_entry": "demo",
        "target_signature": "void demo(void)",
        "valid_domain": "inputs of length 0..16 bytes",
        "valid_behavior": "exit 0 and print the input",
        "forbidden_behavior": "write past the end of the allocation",
        "dest_capacity_bytes": 50,
        "capacity_includes_terminator": True,
        "authorized_edits": [],
        "allowed_calls": [],
        "environment_assumptions": [],
        "required_obligations": [
            "behaviour",
            "identity",
            "interface",
            "reproducibility",
            "structure",
            "symbolic",
        ],
    }
    rejection = {
        "invalid_input_response": "exit 1 with an error",
        "max_valid_input_bytes": 16,
        "invalid_exit_code": 1,
        "invalid_stdout": "",
        "invalid_stderr": "error\n",
    }
    if input_mode is None:
        data.update(rejection)
    else:
        data["schema_version"] = 3
        data["input_mode"] = input_mode
        if input_mode == "none":
            data["valid_domain"] = "no program input"
        else:
            data.update(rejection)
    return data


def build_fixture(
    root: Path,
    *,
    cwe: str = "CWE-787",
    trigger: str | None = "invalid-first",
    valid_count: int = 4,
    invalid_count: int = 2,
    input_mode: str | None = None,
    include_invalid: bool = True,
) -> str:
    root.mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(exist_ok=True)

    elf = b"\x7fELF" + bytes(range(64))
    (root / "original.elf").write_bytes(elf)
    sha = hashlib.sha256(elf).hexdigest()

    (root / "src.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    (root / "build.sh").write_text(
        "#!/bin/sh\nset -eu\ngcc -O0 -o original.elf src.c\n", encoding="utf-8"
    )

    (root / "build.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "compiler": {"name": "gcc", "version": "13.2.0"},
                "flags": ["-O0", "-fno-pie", "-no-pie"],
                "argv": ["gcc", "-O0", "-fno-pie", "-no-pie", "-o", "original.elf", "src.c"],
                "source": {
                    "url": "https://example.test/sample",
                    "commit": "0" * 40,
                    "license": "MIT",
                },
                "output": {"path": "original.elf", "sha256": sha},
                "network": False,
            }
        ),
        encoding="utf-8",
    )

    defect = {
        "schema_version": 1,
        "cwe": cwe,
        "title": "out-of-bounds write past the end of a heap buffer",
        "mechanism": "bounds-check",
    }
    if trigger is not None:
        defect["trigger_case"] = trigger
    (root / "defect.json").write_text(json.dumps(defect), encoding="utf-8")

    (root / "contract.json").write_text(
        json.dumps(_contract(input_mode=input_mode)), encoding="utf-8"
    )

    valid = dict(CASE)
    valid["tests"] = [
        _case(f"valid-{index}", "valid", ["./original", "x" * index])
        for index in range(valid_count)
    ]
    valid["original_sha256"] = sha
    (root / "tests" / "valid.json").write_text(json.dumps(valid), encoding="utf-8")

    if include_invalid:
        invalid = dict(CASE)
        cases = [
            _case("invalid-first", "invalid", ["./original", "x" * 20]),
            _case("invalid-longer", "invalid", ["./original", "x" * 40]),
        ]
        for index in range(2, invalid_count):
            cases.append(
                _case(f"invalid-{index}", "invalid", ["./original", "x" * (20 + index * 10)])
            )
        invalid["tests"] = cases[:invalid_count]
        invalid["original_sha256"] = sha
        (root / "tests" / "invalid.json").write_text(
            json.dumps(invalid), encoding="utf-8"
        )

    write_sums(root)
    return sha


def write_sums(root: Path, *, omit: set[str] | None = None) -> None:
    omit = omit or set()
    lines = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS":
            continue
        relative = path.relative_to(root).as_posix()
        if relative in omit:
            continue
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}")
    (root / "tests" / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def codes(findings) -> set[str]:
    return {finding.code for finding in findings}


def test_a_complete_fixture_passes(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root)
    assert check_fixture(root) == []


def test_the_committed_elf_must_be_what_the_recipe_produced(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root)
    (root / "original.elf").write_bytes(b"\x7fELF" + b"tampered")
    write_sums(root)

    # The sums are self-consistent again, but the recipe no longer describes
    # the binary and the test manifest still cites the old hash.
    findings = check_fixture(root)
    assert {"build_output_hash", "case_sha_mismatch"} <= codes(findings)


def test_build_json_must_not_claim_network(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root)
    data = json.loads((root / "build.json").read_text(encoding="utf-8"))
    data["network"] = True
    (root / "build.json").write_text(json.dumps(data), encoding="utf-8")
    write_sums(root)

    assert "build_json_network" in codes(check_fixture(root))


def test_build_script_may_not_reach_the_network(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root)
    (root / "build.sh").write_text(
        "#!/bin/sh\nset -eu\ncurl -O https://example.test/src.c\ngcc -o original.elf src.c\n",
        encoding="utf-8",
    )
    write_sums(root)

    assert "build_script_network" in codes(check_fixture(root))


def test_the_sums_must_cover_every_file(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root)
    write_sums(root, omit={"original.elf"})

    # A sums file that skips the binary lets the binary change unnoticed.
    assert "sums_incomplete" in codes(check_fixture(root))


def test_a_stale_sums_entry_fails(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root)
    (root / "src.c").write_text("int main(void) { return 1; }\n", encoding="utf-8")

    assert "sums_hash_mismatch" in codes(check_fixture(root))


@pytest.mark.parametrize("count", [0, 1, 2, 3])
def test_fewer_than_four_valid_cases_fails(tmp_path: Path, count: int) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root, valid_count=count)
    assert "too_few_valid" in codes(check_fixture(root))


def test_fewer_than_two_invalid_cases_fails(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root, invalid_count=1)
    assert "too_few_invalid" in codes(check_fixture(root))


def test_the_trigger_case_must_exist_and_be_invalid(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root, trigger="invalid-typo")

    # A prose claim that the class is covered is not enough; the pointer must
    # resolve to an invalid case.
    assert "defect_trigger_unknown" in codes(check_fixture(root))


def test_a_case_id_cannot_be_reused_across_files(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root)
    invalid = json.loads((root / "tests" / "invalid.json").read_text(encoding="utf-8"))
    invalid["tests"][0]["id"] = "valid-0"
    (root / "tests" / "invalid.json").write_text(json.dumps(invalid), encoding="utf-8")
    write_sums(root)

    assert "duplicate_case_id" in codes(check_fixture(root))


def test_a_non_elf_artifact_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root)
    (root / "tests").mkdir(exist_ok=True)
    (root / "original.elf").write_bytes(b"not an elf")
    write_sums(root)

    assert "not_elf" in codes(check_fixture(root))


def test_a_missing_required_file_stops_the_check(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root)
    (root / "build.json").unlink()

    # Missing files short-circuit the rest: reporting "sums incomplete" here
    # would only restate the absence.
    assert codes(check_fixture(root)) == {"missing_file"}


def test_a_second_fixture_must_not_reuse_the_first_cwe(tmp_path: Path) -> None:
    first = tmp_path / "fixtures" / "second_class_demo"
    second = tmp_path / "fixtures" / "another_sample"
    build_fixture(first, cwe="CWE-787")
    build_fixture(second, cwe="CWE-787")

    siblings = {str(first): "CWE-787", str(second): "CWE-787"}

    findings = check_fixture(second, siblings=siblings)
    assert "not_a_distinct_class" in codes(findings)

    # If the team decides the axis is the repair mechanism, this becomes legal.
    assert check_fixture(second, siblings=siblings, allow_same_cwe=True) == []


def test_a_fixture_matching_the_baseline_class_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root, cwe="CWE-121")

    # The baseline CWE may be passed explicitly, so the check does not depend
    # on the first-class fixture already having a defect.json.
    findings = check_fixture(root, baseline_cwe="CWE-121")
    assert "not_a_distinct_class" in codes(findings)
    assert check_fixture(root, baseline_cwe="CWE-121", allow_same_cwe=True) == []


def test_a_defect_without_a_mechanism_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root)
    data = json.loads((root / "defect.json").read_text(encoding="utf-8"))
    del data["mechanism"]
    (root / "defect.json").write_text(json.dumps(data), encoding="utf-8")
    write_sums(root)

    # The mechanism is the axis a second class differs on; it cannot be implied
    # by the CWE number alone.
    assert "defect_mechanism_missing" in codes(check_fixture(root))


def test_a_second_class_cannot_reuse_the_baseline_mechanism(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root, cwe="CWE-416")
    data = json.loads((root / "defect.json").read_text(encoding="utf-8"))
    data["mechanism"] = "bounds-check"
    data["baseline_mechanism"] = "bounds-check"
    (root / "defect.json").write_text(json.dumps(data), encoding="utf-8")
    write_sums(root)

    assert "not_a_distinct_class" in codes(check_fixture(root))


def test_an_unverified_build_is_a_warning_not_a_pass(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root)
    data = json.loads((root / "build.json").read_text(encoding="utf-8"))
    data["reproduction"] = {
        "status": "unverified",
        "reason": "no toolchain on the authoring host",
    }
    (root / "build.json").write_text(json.dumps(data), encoding="utf-8")
    write_sums(root)

    findings = check_fixture(root)
    warnings = [f for f in findings if not f.is_error]
    assert codes(warnings) == {"reproduction_unverified"}
    assert not [f for f in findings if f.is_error]


def test_the_first_class_fixture_is_complete_but_not_reproduced() -> None:
    root = Path(__file__).resolve().parents[1] / "fixtures" / "public" / "CWE121_src_char_declare_cpy_51b"
    if not root.is_dir():
        pytest.skip("first-class fixture not present")

    findings = check_fixture(root)
    missing = {finding.path for finding in findings if finding.code == "missing_file"}
    assert not missing, f"the baseline fixture still lacks {sorted(missing)}"

    # Provenance and sums are complete now, but the recipe has never been run:
    # there is no compiler on the host. The intake says so instead of passing
    # silently.
    assert not [finding for finding in findings if finding.is_error]
    assert "reproduction_unverified" in codes(findings)


# -- no-input contracts (CWE416 / T30, M5 option A) -------------------------
#
# The schema itself is M5's. This checker only reads ``input_mode`` as data:
# absent means the historical argv contract, ``"none"`` changes the layout.


def build_no_input(root: Path, **overrides) -> str:
    options = dict(
        cwe="CWE-416",
        input_mode="none",
        valid_count=1,
        include_invalid=False,
        trigger=None,
    )
    options.update(overrides)
    return build_fixture(root, **options)


def test_a_no_input_fixture_passes(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_no_input(root)

    # One valid case, no invalid cases, no rejection fields: this is the shape
    # the CWE416 contract needs when it takes no program input.
    assert check_fixture(root) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("invalid_input_response", "not applicable"),
        ("invalid_exit_code", 0),
        ("invalid_stdout", ""),
        ("invalid_stderr", ""),
    ],
)
def test_no_input_rejects_any_rejection_field(
    tmp_path: Path, field: str, value
) -> None:
    root = tmp_path / "second_class_demo"
    build_no_input(root)
    data = json.loads((root / "contract.json").read_text(encoding="utf-8"))
    data[field] = value
    (root / "contract.json").write_text(json.dumps(data), encoding="utf-8")
    write_sums(root)

    # A sentinel value is still a fabricated rejection path. M5's schema
    # rejects the field; the intake reports that as a schema failure.
    findings = check_fixture(root)
    assert "contract_schema_invalid" in codes(findings)
    assert any(
        field in finding.detail
        for finding in findings
        if finding.code == "contract_schema_invalid"
    )


def test_no_input_rejects_an_invalid_manifest(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_no_input(root, include_invalid=True, invalid_count=1)

    assert "no_input_invalid_manifest_present" in codes(check_fixture(root))


@pytest.mark.parametrize("count", [0, 2])
def test_no_input_requires_exactly_one_valid_case(
    tmp_path: Path, count: int
) -> None:
    root = tmp_path / "second_class_demo"
    build_no_input(root, valid_count=count)

    assert "no_input_valid_case_count_mismatch" in codes(check_fixture(root))


def test_no_input_rejects_an_empty_invalid_manifest(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    sha = build_no_input(root)
    empty = dict(CASE)
    empty["tests"] = []
    empty["original_sha256"] = sha
    (root / "tests" / "invalid.json").write_text(json.dumps(empty), encoding="utf-8")
    write_sums(root)

    # The invalid manifest must be absent, not an empty placeholder.
    assert "no_input_invalid_manifest_present" in codes(check_fixture(root))


def test_no_input_rejects_a_trigger_case_pointer(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_no_input(root, trigger="invalid-first")

    # There is no invalid case for the pointer to resolve to; a leftover
    # CWE121-shaped trigger is a fabricated invalid path, not evidence.
    assert "no_input_trigger_case_present" in codes(check_fixture(root))


def test_an_unknown_input_mode_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root, input_mode="environment")

    findings = check_fixture(root)
    assert "contract_schema_invalid" in codes(findings)
    assert any(
        "input_mode" in finding.detail
        for finding in findings
        if finding.code == "contract_schema_invalid"
    )


def test_a_v2_contract_must_not_carry_input_mode(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root)
    data = json.loads((root / "contract.json").read_text(encoding="utf-8"))
    data["input_mode"] = "none"
    (root / "contract.json").write_text(json.dumps(data), encoding="utf-8")
    write_sums(root)

    findings = check_fixture(root)
    assert "contract_schema_invalid" in codes(findings)
    assert any(
        "input_mode" in finding.detail
        for finding in findings
        if finding.code == "contract_schema_invalid"
    )


def test_no_input_rejects_max_valid_input_bytes(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_no_input(root)
    data = json.loads((root / "contract.json").read_text(encoding="utf-8"))
    data["max_valid_input_bytes"] = 0
    (root / "contract.json").write_text(json.dumps(data), encoding="utf-8")
    write_sums(root)

    findings = check_fixture(root)
    assert "contract_schema_invalid" in codes(findings)
    assert any(
        "max_valid_input_bytes" in finding.detail
        for finding in findings
        if finding.code == "contract_schema_invalid"
    )


def test_more_than_four_valid_cases_fails(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root, valid_count=5)

    assert "too_many_valid" in codes(check_fixture(root))


def test_more_than_two_invalid_cases_fails(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root, invalid_count=3)

    assert "too_many_invalid" in codes(check_fixture(root))


def test_the_argv_default_keeps_the_four_and_two_matrix(tmp_path: Path) -> None:
    root = tmp_path / "second_class_demo"
    build_fixture(root)

    findings = check_fixture(root)
    assert findings == []
    assert not [f for f in findings if f.code.startswith("no_input_")]


@pytest.mark.parametrize("mode", ["argv", "stdin"])
def test_v3_input_modes_keep_the_four_and_two_matrix(
    tmp_path: Path, mode: str
) -> None:
    root = tmp_path / f"second_class_{mode}"
    build_fixture(root, input_mode=mode)

    # Only "none" changes the layout; the input-bearing modes keep 4+2 and a
    # resolvable trigger case.
    assert check_fixture(root) == []
