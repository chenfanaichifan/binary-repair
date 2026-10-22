#!/usr/bin/env python3
"""Host-side verification of the Gate 3 v2 evidence bundle.

This script only reads a zip and its text/JSON contents. It does **not** parse or
execute any ELF: identity checks are plain SHA-256 of delivered bytes, structural
checks are plain-text/JSON assertions on the delivered `readelf`/`LIEF` outputs.
Run it after copying the v2 bundle to an accessible path:

    python scripts/verify_gate3_v2.py delivery/gate3-bundle-v2-2026-10-22.zip

Exit code 0 means every check passed; 1 means at least one check failed; the
per-check table is printed either way. A missing file or a parse error is a
failure, never a pass.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

EXPECTED = {
    "original_sha256": "aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393",
    "candidate_sha256": "c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82",
    "contract_sha256": "24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37",
    "chain_manifest_sha256": "e53253cf1c3408d832dd4c30b6e75afc4e8c2d621a2c0a3c0959131255878e7c",
    "harness_manifest_sha256": "3bdbc3396fd183ed8563e2d7b0648d02be3a3c55c1a52ccc08890614a97ed678",
}

REQUIRED_FILES = (
    "gate3-summary.json",
    "guest-fingerprint.json",
    "revert.log",
    "v0-original-all.json",
    "candidate-before.txt",
    "candidate-after.txt",
    "isolation.json",
    "lief-diff.json",
    "readelf-original.txt",
    "readelf-candidate.txt",
    "checksec-original.txt",
    "checksec-candidate.txt",
    "tests-raw.txt",
    "cave-probe.txt",
    "harness-v2-manifest.txt",
    "harness-manifest.json",
    "SHA256SUMS",
)

ITEM_KEYWORDS = (
    ("separate candidate copy", 1),
    ("candidate identity", 2),
    ("structural audit", 3),
    ("six-case run", 4),
    ("isolation evidence", 5),
    ("evidence bundle", 6),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main(path: Path) -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    if not path.exists():
        print(f"FAIL bundle not found: {path}")
        return 1

    raw = path.read_bytes()
    check("bundle_sha256_recorded", True, sha256_bytes(raw))
    check("bundle_size", len(raw) > 0, f"{len(raw)} B")

    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        check("zip_entry_count", True, f"{len(names)} entries")
        missing = [n for n in REQUIRED_FILES if n not in names]
        check("required_files_present", not missing, f"missing={missing}")

        def text(name: str) -> str:
            return zf.read(name).decode("utf-8", "replace") if name in names else ""

        # --- G2: inner SHA256SUMS -----------------------------------------
        sums = text("SHA256SUMS")
        bad: list[str] = []
        checked = 0
        for line in sums.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                bad.append(line)
                continue
            digest, rel = parts[0].lower(), parts[1].strip()
            checked += 1
            if rel not in names or sha256_bytes(zf.read(rel)) != digest:
                bad.append(rel)
        check("sha256sums_all_ok", bool(sums) and not bad, f"{checked} entries, bad={bad[:5]}")

        # --- G1: LIEF fields ----------------------------------------------
        try:
            lief = json.loads(text("lief-diff.json"))
        except Exception as exc:  # noqa: BLE001
            lief = {}
            check("lief_json_parses", False, str(exc))
        if lief:
            check("lief_json_parses", True)
        serialized = json.dumps(lief).replace(" ", "")
        check("lief_single_expected_diff",
              "0x8e9" in serialized and "0x1000" in serialized,
              "expected p_filesz/memsz 0x8e9 -> 0x1000")
        check("lief_rx_flags", '"R E"' in serialized or "R E" in json.dumps(lief))
        check("lief_align_1000", "0x1000" in serialized)
        check("lief_interp_not_null", "null" not in json.dumps(lief.get("interp")) if "interp" in lief else False,
              f"interp={lief.get('interp')!r}")
        imports = lief.get("imports") or lief.get("dynamic_symbols") or []
        imports_text = json.dumps(imports)
        check("lief_imports_are_names",
              bool(imports) and not re.fullmatch(r'\[?"\(\d+\)"', imports_text.strip()),
              imports_text[:80])

        # --- G3: summary mapping ------------------------------------------
        try:
            summary = json.loads(text("gate3-summary.json"))
        except Exception as exc:  # noqa: BLE001
            summary = {}
            check("summary_json_parses", False, str(exc))
        if summary:
            check("summary_json_parses", True)
        items = summary.get("items") or []
        item_names = " ".join(str(item.get("name", "")) for item in items).lower()
        mapped = all(keyword in item_names for keyword, _ in ITEM_KEYWORDS)
        check("summary_six_items_mapped", len(items) == 6 and mapped,
              f"items={[i.get('item') for i in items]}")

        # --- G4: revert.log operator --------------------------------------
        revert = text("revert.log")
        check("revert_one_operator",
              "VMer" in revert and "M3" in revert and "operator" in revert.lower()
              and "user did" not in revert.lower() and "VMer did not" not in revert.lower(),
              revert[:160].replace("\n", " "))
        check("revert_manual_snapshot_manager",
              "Snapshot Manager" in revert and ("manual" in revert.lower() or "post hoc" in revert.lower()))

        # --- identity consistency -----------------------------------------
        identity_text = " ".join(
            text(n) for n in (
                "harness-manifest.json", "gate3-summary.json", "candidate-before.txt",
                "candidate-after.txt", "guest-fingerprint.json"))
        for key in ("original_sha256", "candidate_sha256"):
            check(f"{key}_present", EXPECTED[key] in identity_text or EXPECTED[key][:16] in identity_text)
        check("contract_canonical_present", EXPECTED["contract_sha256"] in identity_text)

        # --- six cases -----------------------------------------------------
        case_files = [n for n in names if re.fullmatch(r"case-0[1-6]\.json", n)]
        check("six_case_files", len(case_files) == 6, f"{case_files}")
        cases_ok = 0
        for name in case_files:
            try:
                case = json.loads(text(name))
            except Exception:  # noqa: BLE001
                continue
            if case.get("ok") is True:
                cases_ok += 1
        check("six_cases_ok", cases_ok == 6, f"{cases_ok}/6")

        # --- required non-empty -------------------------------------------
        empty = [n for n in REQUIRED_FILES if n in names and not zf.read(n)]
        check("required_files_nonempty", not empty, f"empty={empty}")

    failed = [name for name, ok, _ in checks if not ok]
    width = max(len(name) for name, _, _ in checks) + 2
    print(f"bundle: {path}")
    for name, ok, detail in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}} {detail}")
    print(f"\nsummary: {len(checks) - len(failed)} passed, {len(failed)} failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/verify_gate3_v2.py <zip>")
    raise SystemExit(main(Path(sys.argv[1])))
