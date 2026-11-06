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


def build_fixture(
    root: Path,
    *,
    cwe: str = "CWE-787",
    trigger: str = "invalid-first",
    bug_site: str | None = "heap",
    baseline_bug_site: str | None = None,
    valid_count: int = 4,
    invalid_count: int = 2,
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

    (root / "defect.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cwe": cwe,
                "title": "out-of-bounds write past the end of a heap buffer",
                "bug_site": bug_site,
                "baseline_bug_site": baseline_bug_site,
                "trigger_case": trigger,
            }
        ),
        encoding="utf-8",
    )

    (root / "contract.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "required_obligations": [
                    "behaviour",
                    "identity",
                    "interface",
                    "reproducibility",
                    "structure",
                    "symbolic",
                ],
                "forbidden_behavior": "write past the end of the allocation",
                "valid_domain": "inputs of length 0..16 bytes",
            }
        ),
        encoding="utf-8",
    )

    valid = dict(CASE)
    valid["tests"] = [
        _case(f"valid-{index}", "valid", ["./original", "x" * index])
        for index in range(valid_count)
    ]
    valid["original_sha256"] = sha
    (root / "tests" / "valid.json").write_text(json.dumps(valid), encoding="utf-8")

    invalid = dict(CASE)
    invalid["tests"] = [
        _case("invalid-first", "invalid", ["./original", "x" * 20]),
        _case("invalid-longer", "invalid", ["./original", "x" * 40]),
    ][:invalid_count]
    invalid["original_sha256"] = sha
    (root / "tests" / "invalid.json").write_text(json.dumps(invalid), encoding="utf-8")

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


def test_the_existing_first_class_fixture_is_incomplete() -> None:
    root = Path(__file__).resolve().parents[1] / "fixtures" / "public" / "CWE121_src_char_declare_cpy_51b"
    if not root.is_dir():
        pytest.skip("first-class fixture not present")

    findings = check_fixture(root)
    missing = {finding.path for finding in findings if finding.code == "missing_file"}

    # This is the real gap M4 would hit: the sample cannot be rebuilt and its
    # sums do not cover the binary.  A second-class fixture must not copy it.
    # The source may be named original.c (upstream) or src.c (authored here);
    # this one has neither.
    assert {"original.c", "build.sh", "build.json", "defect.json"} <= missing


def test_a_bug_site_must_be_a_known_place(tmp_path: Path) -> None:
    build_fixture(tmp_path / "f", bug_site="somewhere")
    findings = check_fixture(tmp_path / "f")
    assert any(f.code == "defect_bug_site" for f in findings)


def test_a_second_class_cannot_reuse_the_baseline_site(tmp_path: Path) -> None:
    build_fixture(tmp_path / "f", bug_site="stack", baseline_bug_site="stack")
    findings = check_fixture(tmp_path / "f")
    assert any(f.code == "not_a_distinct_class" for f in findings)


def test_declaring_a_baseline_site_requires_the_new_site(tmp_path: Path) -> None:
    build_fixture(tmp_path / "f", bug_site=None, baseline_bug_site="stack")
    findings = check_fixture(tmp_path / "f")
    assert any(f.code == "defect_bug_site_missing" for f in findings)


def test_a_heap_site_after_a_stack_baseline_is_accepted(tmp_path: Path) -> None:
    build_fixture(tmp_path / "f", bug_site="heap", baseline_bug_site="stack")
    findings = check_fixture(tmp_path / "f")
    assert not [f for f in findings if f.code == "not_a_distinct_class"]
