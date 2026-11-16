#!/usr/bin/env python3
"""Build a portable delivery package zip from a product demo run.

The package contains reports, textual/JSON evidence, the canonical limitation
text, usage notes, a manifest with per-file SHA256 and a SHA256SUMS file.
**Candidate and original binary bytes are intentionally excluded**: they are
regenerable with the documented command and would bloat the delivery.

Usage::

    python scripts/product/build_delivery_package.py <outdir> [--out PATH] [--json]

Exit codes: 0 package built and verified, 1 build/verification error,
2 usage/missing demo run.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PACKAGE_DIR = "delivery-package"
MAX_INCLUDED_BYTES = 2 * 1024 * 1024
BINARY_SUFFIXES = {
    ".bin", ".elf", ".exe", ".o", ".so", ".dylib", ".macho", ".out",
}
TEXT_SUFFIXES = {".md", ".html", ".json", ".txt", ".csv", ".log"}
SKIP_DIRS = {PACKAGE_DIR, "__pycache__"}


class PackageError(RuntimeError):
    """The demo run is unusable or the package failed verification."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_export_module() -> Any:
    path = ROOT / "scripts" / "product" / "export_report.py"
    spec = importlib.util.spec_from_file_location("delivery_export_report", path)
    if spec is None or spec.loader is None:
        raise PackageError("cannot load scripts/product/export_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def collect_files(outdir: Path) -> tuple[list[Path], list[dict[str, Any]]]:
    """Return (included, excluded) files under the demo output directory."""
    included: list[Path] = []
    excluded: list[dict[str, Any]] = []
    for path in sorted(outdir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(outdir)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        size = path.stat().st_size
        suffix = path.suffix.lower()
        if suffix in BINARY_SUFFIXES:
            excluded.append({"path": relative.as_posix(), "bytes": size,
                             "reason": "binary bytes are regenerable and excluded"})
            continue
        if suffix not in TEXT_SUFFIXES:
            excluded.append({"path": relative.as_posix(), "bytes": size,
                             "reason": "not a text/JSON evidence file"})
            continue
        if size > MAX_INCLUDED_BYTES:
            excluded.append({"path": relative.as_posix(), "bytes": size,
                             "reason": "exceeds the text evidence size limit"})
            continue
        included.append(path)
    return included, excluded


def _report_names(outdir: Path) -> list[str]:
    names = []
    for name in ("REPORT.md", "report.html", "REPORT.zh.md", "report.zh.html"):
        if (outdir / name).is_file():
            names.append(name)
    return names


def _package_readme(run: dict[str, Any], outdir: Path) -> str:
    boundary = run.get("boundary") or {}
    execution = run.get("execution") or {}
    host = run.get("host") or {}
    return "\n".join([
        "# BinaryRepair delivery package (demo)",
        "",
        "This package is a portable snapshot of a product demo run. It contains",
        "the customer reports, the textual/JSON evidence, the canonical limitation",
        "text and an independent SHA256 index.",
        "",
        "## What is included",
        "",
        "- English and Chinese reports (REPORT.md / report.html / REPORT.zh.md / report.zh.html);",
        "- EVIDENCE-INDEX.json (hash of every evidence file in the source run);",
        "- per-fixture scan/outcome/metadata/plan/verifier-report JSON;",
        "- 05-limitations/ (NOT-RUN.md, NOT-CLAIMED.md, LIMITATIONS.md);",
        "- manifest.json and SHA256SUMS.",
        "",
        "## What is NOT included",
        "",
        "- original and candidate binary bytes (regenerable; excluded on purpose);",
        "- any customer binary or credential.",
        "",
        "## Regenerate the full run (including binaries)",
        "",
        "From the repository root:",
        "",
        "    tools/product/run-demo.sh all <outdir>",
        "",
        "The command is deterministic, needs no API key and no external network.",
        "",
        "## Verify this package",
        "",
        "    shasum -a 256 -c SHA256SUMS",
        "",
        "## Boundary (read before use)",
        "",
        f"- positioning: {boundary.get('positioning')}",
        f"- public benchmark: {boundary.get('public_benchmark')}",
        f"- hidden benchmark: {boundary.get('hidden_benchmark')}",
        f"- verification scope: {boundary.get('verification')}",
        f"- execution path: {execution.get('engine')} (AI used: {execution.get('ai_used')}, "
        f"network used: {execution.get('network_used')})",
        f"- host: {host.get('platform')}/{host.get('machine')}",
        "",
        "Not-claimed items and not_run rows are listed in 05-limitations/ and in the",
        "reports. Never present this package as an arbitrary-binary or whole-program",
        "repair proof.",
        "",
    ])


def _command_notes(run: dict[str, Any], outdir: Path) -> str:
    host = run.get("host") or {}
    execution = run.get("execution") or {}
    verifier = execution.get("independent_verifier") or {}
    return "\n".join([
        "# Commands used for this package",
        "",
        "## Run",
        "",
        "    tools/product/run-demo.sh all <outdir>",
        "",
        f"- generated at: {run.get('generated_at')}",
        f"- elapsed seconds: {run.get('elapsed_seconds')}",
        f"- host: {host.get('platform')}/{host.get('machine')} python {host.get('python')}",
        f"- engine: {execution.get('engine')}",
        f"- AI used: {execution.get('ai_used')}",
        f"- network used: {execution.get('network_used')}",
        f"- independent verifier: {verifier.get('path')} ({verifier.get('status')})",
        f"- report languages: {execution.get('report_langs')}",
        "",
        "## Re-export reports only",
        "",
        "    .venv/bin/python scripts/product/export_report.py <outdir> --lang en",
        "    .venv/bin/python scripts/product/export_report.py <outdir> --lang zh",
        "",
        "## Rebuild this package",
        "",
        "    .venv/bin/python scripts/product/build_delivery_package.py <outdir>",
        "",
        "## Verify evidence",
        "",
        "    cd <outdir> && shasum -a 256 -c SHA256SUMS",
        "",
    ])


def _not_run_markdown(run: dict[str, Any]) -> str:
    lines = ["# Not run / fail-closed items", ""]
    any_items = False
    for fixture in run.get("fixtures") or []:
        rows = fixture.get("not_run") or []
        if not rows:
            continue
        any_items = True
        lines.append(f"## {fixture.get('fixture')} ({fixture.get('status')})")
        lines.append("")
        lines.extend(f"- {row}" for row in rows)
        lines.append("")
    if not any_items:
        lines.append("- (no not_run rows; every fixture produced a verified or refused"
                     " disposition with explicit reasons)")
        lines.append("")
    lines.append("Platform and program-level not_run items (from the canonical claims/"
                 "limitations) are listed in LIMITATIONS.md and the reports.")
    lines.append("")
    return "\n".join(lines)


def _not_claimed_markdown(run: dict[str, Any]) -> str:
    boundary = run.get("boundary") or {}
    lines = ["# Not claimed (canonical wording)", ""]
    for item in boundary.get("not_claimed") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _write_zip(
    outdir: Path,
    zip_path: Path,
    included: list[Path],
    generated: dict[str, bytes],
    manifest: dict[str, Any],
    sums: bytes,
) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in included:
            archive.write(path, arcname=path.relative_to(outdir).as_posix())
        for name in sorted(generated):
            archive.writestr(name, generated[name])
        archive.writestr("manifest.json",
                         json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        archive.writestr("SHA256SUMS", sums.decode("utf-8"))


def build_package(outdir: Path, out_path: Path | None = None) -> dict[str, Any]:
    """Build and verify the delivery package zip."""
    outdir = Path(outdir)
    exporter = _load_export_module()
    try:
        run = exporter.load_run(outdir)
    except exporter.ExportError as exc:
        raise PackageError(str(exc)) from exc
    included, excluded = collect_files(outdir)
    report_names = _report_names(outdir)
    if not report_names:
        raise PackageError(
            "no report files found; run scripts/product/export_report.py first"
        )
    limitations = ROOT / "docs" / "acceptance" / "LIMITATIONS.md"
    generated: dict[str, bytes] = {
        "README.md": _package_readme(run, outdir).encode("utf-8"),
        "COMMANDS.md": _command_notes(run, outdir).encode("utf-8"),
        "05-limitations/NOT-RUN.md": _not_run_markdown(run).encode("utf-8"),
        "05-limitations/NOT-CLAIMED.md": _not_claimed_markdown(run).encode("utf-8"),
    }
    if limitations.is_file():
        generated["05-limitations/LIMITATIONS.md"] = limitations.read_bytes()
    files: list[dict[str, Any]] = []
    payloads: dict[str, bytes] = {}
    for path in included:
        data = path.read_bytes()
        relative = path.relative_to(outdir).as_posix()
        payloads[relative] = data
        files.append({"path": relative, "sha256": _sha256(data), "bytes": len(data)})
    for name, data in generated.items():
        payloads[name] = data
        files.append({"path": name, "sha256": _sha256(data), "bytes": len(data)})
    files.sort(key=lambda item: item["path"])
    manifest = {
        "schema_version": 1,
        "kind": "delivery_package_manifest",
        "generated_at": _utc_now(),
        "source_outdir": str(outdir),
        "run_generated_at": run.get("generated_at"),
        "boundary": run.get("boundary") or {},
        "file_count": len(files),
        "files": files,
        "excluded_binaries": [row for row in excluded
                              if row["reason"].startswith("binary bytes")],
        "excluded_other": [row for row in excluded
                           if not row["reason"].startswith("binary bytes")],
        "note": (
            "candidate and original binary bytes are excluded on purpose; "
            "regenerate with tools/product/run-demo.sh"
        ),
    }
    sums_lines = [f"{row['sha256']}  {row['path']}" for row in files]
    sums = ("\n".join(sums_lines) + "\n").encode("utf-8")
    if out_path is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        out_path = outdir / PACKAGE_DIR / f"binaryrepair-demo-{stamp}.zip"
    out_path = Path(out_path)
    _write_zip(outdir, out_path, included, generated, manifest, sums)
    # Verify the written archive against the manifest and checksums.
    problems: list[str] = []
    with zipfile.ZipFile(out_path) as archive:
        names = set(archive.namelist())
        for row in files:
            if row["path"] not in names:
                problems.append(f"missing in zip: {row['path']}")
                continue
            digest = _sha256(archive.read(row["path"]))
            if digest != row["sha256"]:
                problems.append(f"sha256 mismatch: {row['path']}")
        if "SHA256SUMS" not in names:
            problems.append("missing SHA256SUMS in zip")
        binary_names = [name for name in names if Path(name).suffix.lower() in BINARY_SUFFIXES]
        if binary_names:
            problems.append(f"binary files leaked into zip: {binary_names[:5]}")
    if problems:
        raise PackageError("; ".join(problems[:8]))
    package_bytes = out_path.read_bytes()
    return {
        "ok": True,
        "package": str(out_path),
        "package_sha256": _sha256(package_bytes),
        "package_bytes": len(package_bytes),
        "file_count": len(files),
        "excluded_binary_count": len(manifest["excluded_binaries"]),
        "excluded_binary_bytes": sum(
            row["bytes"] for row in manifest["excluded_binaries"]
        ),
        "report_files": report_names,
        "boundary": {
            "public_benchmark": (run.get("boundary") or {}).get("public_benchmark"),
            "hidden_benchmark": (run.get("boundary") or {}).get("hidden_benchmark"),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a portable delivery package zip from a product demo run "
            "(reports + textual evidence + limitations + SHA256, no binaries)."
        )
    )
    parser.add_argument("outdir", help="demo output directory (contains demo-run.json)")
    parser.add_argument("--out", default=None, help="output zip path")
    parser.add_argument("--json", action="store_true", help="print JSON only")
    args = parser.parse_args(argv)
    outdir = Path(args.outdir).resolve()
    out_path = Path(args.out).resolve() if args.out else None
    try:
        result = build_package(outdir, out_path)
    except PackageError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    except OSError as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False))
        return 1
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"package: {result['package']}")
        print(f"sha256:  {result['package_sha256']}")
        print(f"bytes:   {result['package_bytes']}")
        print(f"files:   {result['file_count']} "
              f"(excluded binaries: {result['excluded_binary_count']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
