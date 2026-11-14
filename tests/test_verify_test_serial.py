"""Tests for scripts/verify_test_serial.py (offline, tmp-dir fixtures)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_test_serial as serial  # noqa: E402


def _write_workflow(root: Path, name: str, text: str) -> Path:
    path = root / ".github" / "workflows" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_requirements(root: Path, text: str) -> Path:
    path = root / "requirements.txt"
    path.write_text(text, encoding="utf-8")
    return path


GREEN_WORKFLOW = """
name: green
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Serial suite
        run: python -m pytest -q -p no:xdist --ignore=tests/e2e
      - name: Serial subset
        run: |
          python -m pytest -q -p no:xdist \\
            tests/test_alpha.py \\
            tests/test_beta.py
"""

SINGLE_LINE_BAD_WORKFLOW = """
name: bad
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Parallel accidentally
        run: python -m pytest -q tests/
"""


def test_green_workflow_passes_and_counts_commands(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "ci.yml", GREEN_WORKFLOW)
    _write_requirements(tmp_path, "pytest>=9\n")
    summary = serial.verify(tmp_path)
    assert summary["ok"] is True
    assert summary["violations"] == []
    assert summary["checked"] == 2
    assert summary["workflow_files"] == 1


def test_missing_serial_flag_is_a_violation(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "ci.yml", SINGLE_LINE_BAD_WORKFLOW)
    _write_requirements(tmp_path, "pytest>=9\n")
    summary = serial.verify(tmp_path)
    assert summary["ok"] is False
    assert summary["checked"] == 1
    assert len(summary["violations"]) == 1
    violation = summary["violations"][0]
    assert "lacks '-p no:xdist'" in violation
    assert "Parallel accidentally" in violation


def test_bare_pytest_command_is_detected(tmp_path: Path) -> None:
    _write_workflow(
        tmp_path,
        "ci.yml",
        """
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: pytest -q tests/test_one.py
""",
    )
    _write_requirements(tmp_path, "pytest>=9\n")
    summary = serial.verify(tmp_path)
    assert summary["ok"] is False
    assert summary["checked"] == 1
    assert "lacks '-p no:xdist'" in summary["violations"][0]


def test_python3_and_env_prefix_are_detected(tmp_path: Path) -> None:
    _write_workflow(
        tmp_path,
        "ci.yml",
        """
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: |
          PYTHONPATH=src python3 -m pytest -q tests/test_one.py
          PYTHONPATH=src python3 -m pytest -q -p no:xdist tests/test_two.py
""",
    )
    _write_requirements(tmp_path, "pytest>=9\n")
    summary = serial.verify(tmp_path)
    assert summary["checked"] == 2
    assert summary["ok"] is False
    assert len(summary["violations"]) == 1


def test_compound_commands_require_flag_in_each_pytest_segment(tmp_path: Path) -> None:
    _write_workflow(
        tmp_path,
        "ci.yml",
        """
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: |
          mkdir -p out && python -m pytest -q -p no:xdist tests/a.py
          python -m pytest -q -p no:xdist tests/b.py || echo "suite failed"
""",
    )
    _write_requirements(tmp_path, "pytest>=9\n")
    summary = serial.verify(tmp_path)
    assert summary["ok"] is True
    assert summary["checked"] == 2


def test_multiple_workflows_are_all_parsed(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "ci.yml", GREEN_WORKFLOW)
    _write_workflow(
        tmp_path,
        "ubuntu-verify.yaml",
        """
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - run: python -m pytest -q tests/test_a.py
""",
    )
    _write_requirements(tmp_path, "pytest>=9\n")
    summary = serial.verify(tmp_path)
    assert summary["workflow_files"] == 2
    assert summary["checked"] == 3
    assert summary["ok"] is False
    assert any("ubuntu-verify.yaml" in item for item in summary["violations"])


def test_non_pytest_commands_are_ignored(tmp_path: Path) -> None:
    _write_workflow(
        tmp_path,
        "ci.yml",
        """
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo "pytest runs are covered by a script"
      - run: python scripts/check_language_policy.py
      - run: python -m pip install -r requirements.txt
""",
    )
    _write_requirements(tmp_path, "pytest>=9\n")
    summary = serial.verify(tmp_path)
    assert summary["ok"] is True
    assert summary["checked"] == 0


def test_no_workflow_files_is_a_violation(tmp_path: Path) -> None:
    _write_requirements(tmp_path, "pytest>=9\n")
    summary = serial.verify(tmp_path)
    assert summary["ok"] is False
    assert any("no workflow files" in item for item in summary["violations"])


def test_stdlib_fallback_scanner_when_pyyaml_is_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    """A clean runner may not have PyYAML before dependency installation."""
    _write_workflow(tmp_path, "ci.yml", GREEN_WORKFLOW)
    _write_requirements(tmp_path, "pytest>=9\n")
    monkeypatch.setattr(serial, "yaml", None)
    summary = serial.verify(tmp_path)
    assert summary["ok"] is True, summary["violations"]
    assert summary["checked"] == 2


def test_stdlib_fallback_scanner_still_flags_missing_flag(
    tmp_path: Path, monkeypatch
) -> None:
    _write_workflow(tmp_path, "ci.yml", SINGLE_LINE_BAD_WORKFLOW)
    _write_requirements(tmp_path, "pytest>=9\n")
    monkeypatch.setattr(serial, "yaml", None)
    summary = serial.verify(tmp_path)
    assert summary["ok"] is False
    assert summary["checked"] == 1
    assert "lacks '-p no:xdist'" in summary["violations"][0]


def test_unparseable_workflow_is_a_violation_not_a_crash(tmp_path: Path) -> None:
    pytest.importorskip("yaml", reason="malformed-YAML detection requires PyYAML")
    _write_workflow(tmp_path, "broken.yml", "jobs: [unclosed\n")
    _write_requirements(tmp_path, "pytest>=9\n")
    summary = serial.verify(tmp_path)
    assert summary["ok"] is False
    assert any("cannot parse workflow YAML" in item for item in summary["violations"])


def test_xdist_in_requirements_without_exemption_is_a_violation(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "ci.yml", GREEN_WORKFLOW)
    _write_requirements(tmp_path, "pytest>=9\npytest-xdist>=3\n")
    summary = serial.verify(tmp_path)
    assert summary["ok"] is False
    assert any("pytest-xdist" in item and "release-exempt" in item
               for item in summary["violations"])
    assert summary["requirements_checked"]["xdist_present"] is True
    assert summary["requirements_checked"]["xdist_exempt"] is False


def test_xdist_with_documented_release_exemption_passes(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "ci.yml", GREEN_WORKFLOW)
    _write_requirements(
        tmp_path,
        "pytest>=9\npytest-xdist>=3  # release-exempt: measured serial fallback retained\n",
    )
    summary = serial.verify(tmp_path)
    assert summary["ok"] is True
    assert summary["requirements_checked"]["xdist_exempt"] is True
    assert "measured serial fallback" in summary["requirements_checked"]["xdist_exemption"]


def test_xdist_mentioned_only_in_comment_is_fine(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "ci.yml", GREEN_WORKFLOW)
    _write_requirements(tmp_path, "pytest>=9\n# pytest-xdist stays out on purpose\n")
    summary = serial.verify(tmp_path)
    assert summary["ok"] is True
    assert summary["requirements_checked"]["xdist_present"] is False


def test_missing_requirements_is_a_violation(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "ci.yml", GREEN_WORKFLOW)
    summary = serial.verify(tmp_path)
    assert summary["ok"] is False
    assert any("requirements.txt is missing" in item for item in summary["violations"])


def test_json_cli_shape_and_exit_codes(tmp_path: Path, capsys) -> None:
    _write_workflow(tmp_path, "ci.yml", GREEN_WORKFLOW)
    _write_requirements(tmp_path, "pytest>=9\n")
    assert serial.main(["--json", "--root", str(tmp_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) >= {"ok", "violations", "checked", "workflow_files"}
    assert payload["ok"] is True

    _write_workflow(tmp_path, "bad.yml", SINGLE_LINE_BAD_WORKFLOW)
    assert serial.main(["--json", "--root", str(tmp_path)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["violations"]


def test_human_cli_and_list_workflows(tmp_path: Path, capsys) -> None:
    _write_workflow(tmp_path, "ci.yml", GREEN_WORKFLOW)
    _write_requirements(tmp_path, "pytest>=9\n")
    assert serial.main(["--root", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "verify-test-serial: PASS" in output
    assert serial.main(["--list-workflows", "--root", str(tmp_path)]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed == [".github/workflows/ci.yml"]


@pytest.mark.parametrize(
    "segment",
    [
        "python -m pytest -q -p no:xdist tests/",
        "python -m pytest -pno:xdist -q tests/",
        "python3 -m pytest -q -p no:xdist tests/",
    ],
)
def test_serial_flag_spellings_are_recognized(segment: str) -> None:
    assert serial._has_serial_flag(segment) is True


def test_repository_workflows_follow_the_policy() -> None:
    """The repository itself must satisfy the serial policy (CI runs this check)."""
    summary = serial.verify(ROOT)
    assert summary["ok"] is True, summary["violations"]
    assert summary["checked"] >= 4
    assert summary["workflow_files"] >= 2
