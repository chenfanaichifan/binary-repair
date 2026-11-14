#!/usr/bin/env python3
"""Verify that every CI pytest invocation is serial and xdist stays opt-in.

Release and nightly evidence is produced from a single Lima guest instance and a
single PoC differential; running pytest suites in parallel against them produces
nondeterministic failures.  This checker enforces the repository policy:

* every ``python -m pytest`` / ``pytest`` command in any
  ``.github/workflows/*.yml`` (or ``*.yaml``) workflow must pass
  ``-p no:xdist`` explicitly -- a host with a parallel plugin installed must not
  silently parallelize the suite;
* ``pytest-xdist`` must not be added to ``requirements.txt`` unless the line
  carries a documented release exemption comment
  (``# release-exempt: <reason>``).

The checker is dependency-light: PyYAML is used when available, and a built-in
line scanner over ``run:`` blocks is used otherwise (a clean GitHub runner is
not guaranteed to have PyYAML before dependency installation, and this gate must
still enforce the policy).

Usage::

    python scripts/verify_test_serial.py [--json] [--root PATH]
    python scripts/verify_test_serial.py --list-workflows

The JSON summary has the contract fields ``ok``, ``violations`` and ``checked``
(plus a few explanatory extras); the exit code is 0 when the policy holds and 1
otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

try:  # PyYAML is a test/GUI dependency; keep the import failure explicit.
    import yaml
except ImportError:  # pragma: no cover - exercised only in broken envs
    yaml = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_GLOBS = ("*.yml", "*.yaml")
X_DIST_DISABLE = "-p no:xdist"
#: ``# release-exempt: <reason>`` documents a deliberate pytest-xdist addition.
X_DIST_EXEMPT_RE = re.compile(r"release[-_ ]exempt\s*:\s*(\S.*)", re.IGNORECASE)
#: Tokens that look like a Python executable (``python``, ``python3``,
#: ``python3.11``, ``.venv/bin/python``, ``/usr/bin/python3``).
PYTHON_TOKEN_RE = re.compile(r"(?:^|/)(?:python(?:3(?:\.\d+)?)?)$", re.IGNORECASE)
#: Shell tokens that may precede the command: ``FOO=bar`` env assignments.
ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
#: Shell separators that start a new logical command inside one run block.
SEGMENT_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")


def workflow_files(root: Path) -> list[Path]:
    """Return every GitHub Actions workflow file, sorted for stable output."""
    base = root / ".github" / "workflows"
    files: set[Path] = set()
    for pattern in WORKFLOW_GLOBS:
        files.update(base.glob(pattern))
    return sorted(path for path in files if path.is_file())


def _run_blocks(document: Any) -> Iterator[tuple[str, str, str]]:
    """Yield ``(job_id, step_name, run_script)`` for every runnable step."""
    if not isinstance(document, dict):
        return
    jobs = document.get("jobs")
    if not isinstance(jobs, dict):
        return
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            script = step.get("run")
            if not isinstance(script, str):
                continue
            name = step.get("name") if isinstance(step.get("name"), str) else ""
            yield str(job_id), name or f"steps[{index}]", script


def _run_blocks_without_yaml(text: str) -> list[tuple[str, str, str]]:
    """Minimal ``run:`` block scanner used when PyYAML is unavailable.

    It understands the two GitHub Actions forms this repository uses: an inline
    ``run: <command>`` scalar and a literal/folded block (``run: |`` or
    ``run: >``) whose subsequent lines are more indented than the ``run:`` key.
    Nested job/step context is not reconstructed in this mode; violations still
    carry the workflow file and line number.
    """
    lines = text.splitlines()
    blocks: list[tuple[str, str, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"^(\s*)(?:-\s+)?run:\s*(.*)$", line)
        if not match:
            index += 1
            continue
        indent = len(match.group(1))
        value = match.group(2).strip()
        if value in {"|", ">", "|-", ">-", "|+", ">+"}:
            body: list[str] = []
            cursor = index + 1
            while cursor < len(lines):
                candidate = lines[cursor]
                if not candidate.strip():
                    body.append("")
                    cursor += 1
                    continue
                candidate_indent = len(candidate) - len(candidate.lstrip())
                if candidate_indent <= indent:
                    break
                body.append(candidate)
                cursor += 1
            dedented = [item[indent + 2:] if len(item) > indent + 2 else item.lstrip()
                        for item in body]
            blocks.append(("", "", "\n".join(dedented)))
            index = cursor
            continue
        scalar = value
        if len(scalar) >= 2 and scalar[0] == scalar[-1] and scalar[0] in "\"'":
            scalar = scalar[1:-1]
        blocks.append(("", "", scalar))
        index += 1
    return blocks


def _logical_lines(script: str) -> Iterator[tuple[int, str]]:
    """Yield continuation-joined shell lines with their first source line."""
    buffer = ""
    start = 0
    for number, raw in enumerate(script.splitlines(), start=1):
        line = raw.rstrip()
        if buffer:
            buffer = f"{buffer} {line.lstrip()}"
        else:
            buffer = line
            start = number
        if buffer.endswith("\\"):
            buffer = buffer[:-1].rstrip()
            continue
        yield start, buffer
        buffer = ""
    if buffer:
        yield start, buffer


def _command_segments(line: str) -> list[str]:
    """Split one shell line into logical commands (keeps quoted text intact)."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return []
    # Strip an inline comment only when ``#`` starts a word; quoted strings in
    # CI run blocks are otherwise rare, and this keeps echo/comment text out of
    # the command detection.
    code = re.split(r"(?:^|\s)#", stripped, maxsplit=1)[0].strip()
    if not code:
        return []
    return [part.strip() for part in SEGMENT_SPLIT_RE.split(code) if part.strip()]


def _command_tokens(segment: str) -> list[str]:
    return [token for token in segment.split() if token]


def _pytest_invocation(tokens: list[str]) -> bool:
    """Return True when the token list invokes pytest (``python -m pytest``)."""
    index = 0
    while index < len(tokens) and ENV_ASSIGNMENT_RE.match(tokens[index]):
        index += 1
    if index >= len(tokens):
        return False
    head = tokens[index].strip("\"'")
    if PYTHON_TOKEN_RE.search(head):
        rest = tokens[index + 1:]
        return len(rest) >= 2 and rest[0] == "-m" and rest[1].strip("\"'") == "pytest"
    return head == "pytest"


def _has_serial_flag(segment: str) -> bool:
    return re.search(r"-p\s*no:xdist\b", segment) is not None


def check_workflows(root: Path) -> tuple[list[str], int, int]:
    """Scan every workflow, returning ``(violations, pytest_commands, files)``."""
    files = workflow_files(root)
    violations: list[str] = []
    if not files:
        return (
            [f"no workflow files found under {root / '.github' / 'workflows'}"],
            0,
            0,
        )
    checked = 0
    for path in files:
        relative = path.relative_to(root)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            violations.append(f"{relative}: cannot read workflow: {type(exc).__name__}: {exc}")
            continue
        if yaml is None:
            blocks = _run_blocks_without_yaml(text)
        else:
            try:
                document = yaml.safe_load(text)
            except yaml.YAMLError as exc:
                violations.append(f"{relative}: cannot parse workflow YAML: {type(exc).__name__}: {exc}")
                continue
            blocks = list(_run_blocks(document))
        for job_id, step_name, script in blocks:
            for source_line, line in _logical_lines(script):
                for segment in _command_segments(line):
                    tokens = _command_tokens(segment)
                    if not _pytest_invocation(tokens):
                        continue
                    checked += 1
                    if not _has_serial_flag(segment):
                        violations.append(
                            f"{relative}:{source_line}: job {job_id!r} step {step_name!r}: "
                            f"pytest command lacks {X_DIST_DISABLE!r}: {segment[:200]}"
                        )
    return violations, checked, len(files)


def _split_comment(line: str) -> tuple[str, str]:
    """Split a requirements line into ``(requirement, comment)``."""
    body, marker, comment = line.partition("#")
    return body.strip(), comment.strip() if marker else ""


def _requirement_name(requirement: str) -> str:
    """Extract the canonical package name from a requirements.txt specifier."""
    match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement.strip())
    return match.group(0).lower() if match else ""


def check_requirements(root: Path) -> tuple[list[str], dict[str, Any]]:
    """Fail if pytest-xdist is required without a documented release exemption."""
    path = root / "requirements.txt"
    violations: list[str] = []
    if not path.is_file():
        return (["requirements.txt is missing; cannot verify the xdist policy"], {
            "requirements_checked": False,
            "xdist_present": False,
            "xdist_exempt": False,
            "xdist_exemption": None,
        })
    xdist_present = False
    xdist_exempt = False
    exemption: str | None = None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return ([f"requirements.txt cannot be read: {type(exc).__name__}: {exc}"], {
            "requirements_checked": False,
            "xdist_present": False,
            "xdist_exempt": False,
            "xdist_exemption": None,
        })
    for number, raw in enumerate(lines, start=1):
        requirement, comment = _split_comment(raw)
        if _requirement_name(requirement) != "pytest-xdist":
            continue
        xdist_present = True
        match = X_DIST_EXEMPT_RE.search(comment)
        if match:
            xdist_exempt = True
            exemption = match.group(1).strip()
        else:
            violations.append(
                f"requirements.txt:{number}: pytest-xdist is required without a "
                "documented release exemption; append "
                "'# release-exempt: <reason>' after a deliberate addition or remove it"
            )
    detail = {
        "requirements_checked": True,
        "xdist_present": xdist_present,
        "xdist_exempt": xdist_exempt,
        "xdist_exemption": exemption,
    }
    return violations, detail


def verify(root: Path) -> dict[str, Any]:
    root = root.resolve()
    workflow_violations, checked, files = check_workflows(root)
    requirement_violations, requirement_detail = check_requirements(root)
    violations = workflow_violations + requirement_violations
    return {
        "ok": not violations,
        "violations": violations,
        "checked": checked,
        "workflow_files": files,
        "requirements_checked": requirement_detail,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify CI pytest commands are serial (-p no:xdist) and xdist stays opt-in.",
    )
    parser.add_argument("--json", action="store_true", help="print the structured summary as JSON")
    parser.add_argument("--list-workflows", action="store_true",
                        help="print workflow files that would be checked and exit")
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="repository root to check (for tests/debug only)")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.list_workflows:
        print(json.dumps([str(path.relative_to(root)) for path in workflow_files(root)], indent=2))
        return 0
    summary = verify(root)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            "verify-test-serial: {result} workflows={files} pytest_commands={checked} "
            "violations={violations}".format(
                result="PASS" if summary["ok"] else "FAIL",
                files=summary["workflow_files"],
                checked=summary["checked"],
                violations=len(summary["violations"]),
            )
        )
        for violation in summary["violations"]:
            print(f"  FAIL {violation}")
        if summary["ok"]:
            print(f"  PASS every pytest command includes {X_DIST_DISABLE!r}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
