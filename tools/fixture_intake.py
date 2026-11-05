#!/usr/bin/env python3
"""Validate a public fixture before anyone treats it as evidence.

A fixture is usable only when its source, its build recipe, its defect
classification and its test manifest are present and mutually consistent.
Without that, a second defect class cannot be repaired generically: the
planner would be tuned to one sample and nobody could reproduce the build.

This checker reads text and hashes bytes.  It never runs ``build.sh``, never
executes ``original.elf`` and never touches the network.

Required layout::

    fixtures/public/<name>/
      src.c
      original.elf
      build.sh
      build.json
      defect.json
      contract.json
      tests/valid.json
      tests/invalid.json
      tests/SHA256SUMS

``tests/SHA256SUMS`` lists every file in the fixture by its path relative to
the fixture root, so editing ``original.elf`` without updating the sums fails
instead of rotting silently.

Usage::

    python tools/fixture_intake.py --check fixtures/public/<name>
    python tools/fixture_intake.py --list fixtures/public
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_FILES = (
    "src.c",
    "original.elf",
    "build.sh",
    "build.json",
    "defect.json",
    "contract.json",
    "tests/valid.json",
    "tests/invalid.json",
    "tests/SHA256SUMS",
)

REQUIRED_OBLIGATIONS = {
    "behaviour",
    "identity",
    "interface",
    "reproducibility",
    "structure",
    "symbolic",
}

CWE_PATTERN = re.compile(r"^CWE-\d+$")

# A build script that can reach the network cannot be reproduced offline, which
# is the point of a guest build path.
NETWORK_MARKERS = (
    "curl",
    "wget",
    "apt-get",
    "apt ",
    "pip ",
    "pip3 ",
    "npm ",
    "git clone",
    "http://",
    "https://",
    "ftp://",
)

MIN_VALID_CASES = 4
MIN_INVALID_CASES = 2


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    detail: str
    severity: str = "error"

    @property
    def is_error(self) -> bool:
        return self.severity == "error"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, findings: list[Finding]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as error:
        findings.append(
            Finding("invalid_json", str(path), f"not valid JSON: {error}")
        )
        return None


def _require_keys(
    data: dict[str, Any], keys: tuple[str, ...], path: str, findings: list[Finding]
) -> None:
    for key in keys:
        if key not in data:
            findings.append(Finding("missing_field", path, f"missing {key!r}"))


def _check_build_script(root: Path, findings: list[Finding]) -> None:
    text = (root / "build.sh").read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        findings.append(Finding("empty_file", "build.sh", "build script is empty"))
    lowered = text.lower()
    for marker in NETWORK_MARKERS:
        if marker in lowered:
            findings.append(
                Finding(
                    "build_script_network",
                    "build.sh",
                    f"contains {marker.strip()!r}; the guest build must not reach the network",
                )
            )


def _check_source(root: Path, findings: list[Finding]) -> None:
    if (root / "src.c").stat().st_size == 0:
        findings.append(Finding("empty_file", "src.c", "source is empty"))


def _check_elf(root: Path, findings: list[Finding]) -> str | None:
    with (root / "original.elf").open("rb") as handle:
        magic = handle.read(4)
    if magic != b"\x7fELF":
        findings.append(
            Finding("not_elf", "original.elf", f"magic is {magic!r}, expected b'\\x7fELF'")
        )
        return None
    return _sha256(root / "original.elf")


def _check_build_json(
    root: Path, artifact_sha256: str | None, findings: list[Finding]
) -> None:
    data = _load_json(root / "build.json", findings)
    if data is None:
        return
    if not isinstance(data, dict):
        findings.append(Finding("invalid_shape", "build.json", "expected an object"))
        return
    _require_keys(
        data,
        ("schema_version", "compiler", "flags", "argv", "source", "output", "network"),
        "build.json",
        findings,
    )
    if data.get("network") is not False:
        findings.append(
            Finding(
                "build_json_network",
                "build.json",
                "network must be false; the guest build cannot fetch anything",
            )
        )

    compiler = data.get("compiler")
    if isinstance(compiler, dict):
        _require_keys(compiler, ("name", "version"), "build.json#compiler", findings)
    elif "compiler" in data:
        findings.append(
            Finding("invalid_shape", "build.json#compiler", "expected an object")
        )

    source = data.get("source")
    if isinstance(source, dict):
        _require_keys(source, ("url", "commit", "license"), "build.json#source", findings)
        for key in ("url", "commit", "license"):
            value = source.get(key)
            if key in source and (not isinstance(value, str) or not value.strip()):
                findings.append(
                    Finding(
                        "empty_provenance",
                        f"build.json#source.{key}",
                        "provenance must be a non-empty string",
                    )
                )
    elif "source" in data:
        findings.append(
            Finding("invalid_shape", "build.json#source", "expected an object")
        )

    reproduction = data.get("reproduction")
    if reproduction is not None:
        if not isinstance(reproduction, dict):
            findings.append(
                Finding("invalid_shape", "build.json#reproduction", "expected an object")
            )
        else:
            _require_keys(
                reproduction, ("status", "reason"), "build.json#reproduction", findings
            )
            status = reproduction.get("status")
            if status not in {"verified", "unverified"}:
                findings.append(
                    Finding(
                        "invalid_shape",
                        "build.json#reproduction.status",
                        f"expected 'verified' or 'unverified', got {status!r}",
                    )
                )
            elif status == "unverified":
                # The fixture may be complete while its build is unproven. That
                # is a warning: it must not fail the intake, and it must not be
                # printed as a pass either.
                findings.append(
                    Finding(
                        "reproduction_unverified",
                        "build.json#reproduction",
                        str(reproduction.get("reason") or "no reason given"),
                        severity="warning",
                    )
                )

    output = data.get("output")
    if isinstance(output, dict):
        _require_keys(output, ("path", "sha256"), "build.json#output", findings)
        if output.get("path") != "original.elf":
            findings.append(
                Finding(
                    "build_output_path",
                    "build.json#output.path",
                    f"expected 'original.elf', got {output.get('path')!r}",
                )
            )
        claimed = output.get("sha256")
        if artifact_sha256 is not None and claimed != artifact_sha256:
            findings.append(
                Finding(
                    "build_output_hash",
                    "build.json#output.sha256",
                    "does not match the committed original.elf; the committed binary "
                    "is not what this recipe produced",
                )
            )
    elif "output" in data:
        findings.append(
            Finding("invalid_shape", "build.json#output", "expected an object")
        )


def _check_defect(
    root: Path, invalid_ids: set[str], findings: list[Finding]
) -> tuple[str | None, str | None]:
    data = _load_json(root / "defect.json", findings)
    if data is None:
        return None, None
    if not isinstance(data, dict):
        findings.append(Finding("invalid_shape", "defect.json", "expected an object"))
        return None, None
    _require_keys(
        data,
        ("schema_version", "cwe", "title", "mechanism", "trigger_case"),
        "defect.json",
        findings,
    )

    cwe = data.get("cwe")
    if not isinstance(cwe, str) or not CWE_PATTERN.match(cwe):
        findings.append(
            Finding(
                "defect_cwe_format",
                "defect.json#cwe",
                f"expected 'CWE-<number>', got {cwe!r}",
            )
        )
        cwe = None

    mechanism = data.get("mechanism")
    if not isinstance(mechanism, str) or not mechanism.strip():
        findings.append(
            Finding(
                "defect_mechanism_missing",
                "defect.json#mechanism",
                "the repair mechanism is the axis T8.3 differs on; it must be stated",
            )
        )
        mechanism = None

    baseline = data.get("baseline_mechanism")
    if baseline is not None:
        if not isinstance(baseline, str) or not baseline.strip():
            findings.append(
                Finding(
                    "invalid_shape",
                    "defect.json#baseline_mechanism",
                    "expected a non-empty string",
                )
            )
        elif mechanism is not None and baseline == mechanism:
            findings.append(
                Finding(
                    "not_a_distinct_class",
                    "defect.json#baseline_mechanism",
                    f"mechanism equals the baseline mechanism {baseline!r}; a second "
                    "class cannot repair the same way as the first",
                )
            )

    trigger = data.get("trigger_case")
    if trigger not in invalid_ids:
        findings.append(
            Finding(
                "defect_trigger_unknown",
                "defect.json#trigger_case",
                f"{trigger!r} is not an invalid case in tests/invalid.json",
            )
        )
    return cwe, mechanism


def _check_contract(root: Path, findings: list[Finding]) -> None:
    data = _load_json(root / "contract.json", findings)
    if data is None:
        return
    if not isinstance(data, dict):
        findings.append(Finding("invalid_shape", "contract.json", "expected an object"))
        return
    _require_keys(
        data,
        ("schema_version", "required_obligations", "forbidden_behavior", "valid_domain"),
        "contract.json",
        findings,
    )
    obligations = data.get("required_obligations")
    if isinstance(obligations, list):
        missing = REQUIRED_OBLIGATIONS - set(obligations)
        if missing:
            findings.append(
                Finding(
                    "contract_obligations",
                    "contract.json#required_obligations",
                    f"missing {sorted(missing)}",
                )
            )
    elif "required_obligations" in data:
        findings.append(
            Finding("invalid_shape", "contract.json#required_obligations", "expected a list")
        )
    for key in ("forbidden_behavior", "valid_domain"):
        value = data.get(key)
        if key in data and (not isinstance(value, str) or not value.strip()):
            findings.append(
                Finding("empty_contract_field", f"contract.json#{key}", "must not be empty")
            )


def _load_cases(
    root: Path, name: str, expected_kind: str, findings: list[Finding]
) -> tuple[list[str], str | None]:
    data = _load_json(root / "tests" / name, findings)
    if data is None:
        return [], None
    if not isinstance(data, dict):
        findings.append(Finding("invalid_shape", f"tests/{name}", "expected an object"))
        return [], None
    _require_keys(data, ("schema_version", "case_id", "original_sha256", "tests"), f"tests/{name}", findings)

    tests = data.get("tests")
    if not isinstance(tests, list) or not tests:
        findings.append(Finding("empty_cases", f"tests/{name}", "no test cases"))
        return [], data.get("original_sha256")

    ids: list[str] = []
    for index, case in enumerate(tests):
        where = f"tests/{name}#tests[{index}]"
        if not isinstance(case, dict):
            findings.append(Finding("invalid_shape", where, "expected an object"))
            continue
        _require_keys(case, ("id", "kind", "argv", "expected"), where, findings)
        case_id = case.get("id")
        if isinstance(case_id, str) and case_id:
            ids.append(case_id)
        else:
            findings.append(Finding("missing_case_id", where, "id must be a non-empty string"))
        if case.get("kind") != expected_kind:
            findings.append(
                Finding(
                    "case_kind_mismatch",
                    where,
                    f"expected kind {expected_kind!r}, got {case.get('kind')!r}",
                )
            )
        expected = case.get("expected")
        if isinstance(expected, dict):
            _require_keys(
                expected, ("return_code", "stdout", "stderr"), f"{where}.expected", findings
            )
        elif "expected" in case:
            findings.append(Finding("invalid_shape", f"{where}.expected", "expected an object"))

    return ids, data.get("original_sha256")


def _check_sums(root: Path, findings: list[Finding]) -> None:
    sums_path = root / "tests" / "SHA256SUMS"
    text = sums_path.read_text(encoding="utf-8", errors="replace")

    listed: dict[str, str] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            findings.append(
                Finding(
                    "sums_format",
                    f"tests/SHA256SUMS:{number}",
                    "expected '<64 hex>  <path>'",
                )
            )
            continue
        digest, relative = parts[0], parts[1].strip()
        if relative in listed:
            findings.append(
                Finding("sums_duplicate", f"tests/SHA256SUMS:{number}", f"duplicate {relative!r}")
            )
            continue
        listed[relative] = digest

    for relative, digest in listed.items():
        target = root / relative
        if not target.is_file():
            findings.append(
                Finding("sums_missing_file", relative, "listed but not present")
            )
            continue
        actual = _sha256(target)
        if actual != digest:
            findings.append(
                Finding("sums_hash_mismatch", relative, f"listed {digest}, actual {actual}")
            )

    on_disk = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != sums_path
    }
    unlisted = sorted(on_disk - set(listed))
    if unlisted:
        findings.append(
            Finding(
                "sums_incomplete",
                "tests/SHA256SUMS",
                f"does not cover {unlisted}; provenance must cover every file",
            )
        )


def check_fixture(
    root: Path,
    *,
    siblings: dict[str, str] | None = None,
    allow_same_cwe: bool = False,
    baseline_cwe: str | None = None,
) -> list[Finding]:
    findings: list[Finding] = []

    if not root.is_dir():
        return [Finding("not_a_directory", str(root), "fixture path is not a directory")]

    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            findings.append(Finding("missing_file", relative, "required for intake"))

    if any(f.code == "missing_file" for f in findings):
        # Later checks would only restate the absence.
        return findings

    _check_source(root, findings)
    _check_build_script(root, findings)
    artifact_sha256 = _check_elf(root, findings)
    _check_build_json(root, artifact_sha256, findings)
    _check_contract(root, findings)

    valid_ids, valid_sha = _load_cases(root, "valid.json", "valid", findings)
    invalid_ids, invalid_sha = _load_cases(root, "invalid.json", "invalid", findings)

    if len(valid_ids) < MIN_VALID_CASES:
        findings.append(
            Finding(
                "too_few_valid",
                "tests/valid.json",
                f"{len(valid_ids)} cases, need at least {MIN_VALID_CASES}",
            )
        )
    if len(invalid_ids) < MIN_INVALID_CASES:
        findings.append(
            Finding(
                "too_few_invalid",
                "tests/invalid.json",
                f"{len(invalid_ids)} cases, need at least {MIN_INVALID_CASES}",
            )
        )

    overlap = set(valid_ids) & set(invalid_ids)
    if overlap:
        findings.append(
            Finding("duplicate_case_id", "tests", f"used in both files: {sorted(overlap)}")
        )

    _check_defect(root, set(invalid_ids), findings)

    declared = {value for value in (valid_sha, invalid_sha) if value is not None}
    if len(declared) > 1:
        findings.append(
            Finding(
                "case_sha_disagree",
                "tests",
                "valid.json and invalid.json declare different original_sha256",
            )
        )
    for name, value in (("tests/valid.json", valid_sha), ("tests/invalid.json", invalid_sha)):
        if isinstance(value, str) and artifact_sha256 is not None and value != artifact_sha256:
            findings.append(
                Finding(
                    "case_sha_mismatch",
                    name,
                    "original_sha256 does not match the committed original.elf",
                )
            )

    _check_sums(root, findings)

    if not allow_same_cwe:
        defect = _load_json(root / "defect.json", [])
        cwe = defect.get("cwe") if isinstance(defect, dict) else None
        if isinstance(cwe, str) and baseline_cwe and cwe == baseline_cwe:
            findings.append(
                Finding(
                    "not_a_distinct_class",
                    "defect.json#cwe",
                    f"{cwe} is the baseline class; T8.3 needs a different defect class, "
                    "or pass --allow-same-cwe if the axis is the repair mechanism",
                )
            )
        for other, other_cwe in (siblings or {}).items():
            if other_cwe == cwe and Path(other).name != root.name:
                findings.append(
                    Finding(
                        "not_a_distinct_class",
                        "defect.json#cwe",
                        f"{cwe} is already used by {other}; T8.3 needs a different defect "
                        "class, or pass --allow-same-cwe if the axis is the repair mechanism",
                    )
                )

    return findings


def _siblings(fixtures_root: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    for child in sorted(fixtures_root.iterdir()):
        defect = child / "defect.json"
        if not defect.is_file():
            continue
        try:
            data = json.loads(defect.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and isinstance(data.get("cwe"), str):
            found[str(child)] = data["cwe"]
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/fixture_intake.py")
    parser.add_argument("--check", type=Path, help="validate one fixture directory")
    parser.add_argument("--list", type=Path, help="summarise every fixture under this directory")
    parser.add_argument(
        "--allow-same-cwe",
        action="store_true",
        help="allow a CWE already used by a sibling fixture or the baseline",
    )
    parser.add_argument(
        "--baseline-cwe",
        default=None,
        help="CWE the new fixture must differ from, e.g. CWE-121",
    )
    args = parser.parse_args(argv)

    if bool(args.check) == bool(args.list):
        parser.error("pass exactly one of --check or --list")

    if args.check:
        root = args.check
        siblings = _siblings(root.parent) if root.parent.is_dir() else {}
        findings = check_fixture(
            root,
            siblings=siblings,
            allow_same_cwe=args.allow_same_cwe,
            baseline_cwe=args.baseline_cwe,
        )
        for finding in findings:
            print(f"{finding.severity}\t{finding.code}\t{finding.path}\t{finding.detail}")
        errors = [f for f in findings if f.is_error]
        warnings = [f for f in findings if not f.is_error]
        if errors:
            print(f"FAILED ({len(errors)} error(s), {len(warnings)} warning(s))")
            return 1
        if warnings:
            print(f"OK ({len(warnings)} warning(s))")
            return 0
        print("OK")
        return 0

    root = args.list
    siblings = _siblings(root)
    status = 0
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        findings = check_fixture(
            child,
            siblings=siblings,
            allow_same_cwe=args.allow_same_cwe,
            baseline_cwe=args.baseline_cwe,
        )
        errors = [f for f in findings if f.is_error]
        warnings = [f for f in findings if not f.is_error]
        if errors:
            state = f"FAILED ({len(errors)})"
        elif warnings:
            state = f"OK ({len(warnings)} warning(s))"
        else:
            state = "OK"
        print(f"{child.name}\t{state}")
        for finding in findings:
            print(f"  {finding.severity}\t{finding.code}\t{finding.path}\t{finding.detail}")
        status = status or (1 if errors else 0)
    return status


if __name__ == "__main__":
    sys.exit(main())
