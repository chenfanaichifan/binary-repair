"""Gate 3 static evidence bundle for the canonical Route A candidate.

The bundle is written inside the guest (or CI) and contains only static artefacts
plus reproducibility: it never executes the candidate. Items 4-5 (six-case run and
isolation evidence) are separate, explicit steps and are recorded as ``not_run``.

This is the retargeted M4 evidence tooling for main's canonical candidate
``c4a159…`` / contract ``24bfe568…`` (patch review B1/B2). Missing tools or
checks are recorded as ``not_run``, never as a pass.
"""

from __future__ import annotations

import datetime
import json
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from routea.byteaudit import sha256_bytes
from routea.facts import tools_report

REQUIRED_TOOLS = ("readelf", "objdump")


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def run_tool(argv: list[str], *, timeout: int = 120) -> dict[str, Any]:
    executable = shutil.which(argv[0])
    if executable is None:
        return {"command": argv, "available": False, "returncode": None,
                "stdout": "", "stderr": f"{argv[0]} not found on PATH"}
    try:
        proc = subprocess.run([executable, *argv[1:]], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"command": argv, "available": True, "returncode": None,
                "stdout": "", "stderr": f"timeout after {timeout}s"}
    return {"command": argv, "available": True, "returncode": proc.returncode,
            "stdout": proc.stdout.decode("utf-8", "replace"),
            "stderr": proc.stderr.decode("utf-8", "replace")}


def capture_environment() -> dict[str, Any]:
    env: dict[str, Any] = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "kernel": platform.release(),
        "libraries": tools_report(),
        "hostname": platform.node(),
        "utc_now": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    os_release = Path("/etc/os-release")
    if os_release.exists():
        env["os_release"] = os_release.read_text(encoding="utf-8", errors="replace")
    for tool in REQUIRED_TOOLS:
        result = run_tool([tool, "--version"])
        first = (result["stdout"].strip().splitlines() or [""])[0] or \
                (result["stderr"].strip().splitlines() or [""])[0]
        env[f"{tool}_version"] = first or "unavailable"
        env[f"{tool}_available"] = result["available"]
    status = Path("/proc/self/status")
    if status.exists():
        for line in status.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Seccomp:"):
                env["process_seccomp"] = line.split(":", 1)[1].strip()
    return env


def reproducibility_report(original: Path, build_to: Callable[[Path], Path],
                           workdir: Path) -> dict[str, Any]:
    workdir.mkdir(parents=True, exist_ok=True)
    first = build_to(workdir / "candidate-run1.elf")
    second = build_to(workdir / "candidate-run2.elf")
    left, right = first.read_bytes(), second.read_bytes()
    return {
        "original_sha256": sha256_file(original),
        "runs": 2,
        "candidate_sha256": [sha256_bytes(left), sha256_bytes(right)],
        "candidate_sizes": [len(left), len(right)],
        "byte_identical": left == right,
        "pass": left == right,
    }


def capture_independent_views(patched: Path, outdir: Path) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    commands = {
        "readelf-program-headers.txt": ["readelf", "-lW", str(patched)],
        "readelf-section-headers.txt": ["readelf", "-SW", str(patched)],
        "readelf-relocations.txt": ["readelf", "-rW", str(patched)],
        "readelf-header.txt": ["readelf", "-hW", str(patched)],
        "readelf-dynamic.txt": ["readelf", "-dW", str(patched)],
        "readelf-dynsyms.txt": ["readelf", "--dyn-syms", "-W", str(patched)],
        "readelf-notes.txt": ["readelf", "-nW", str(patched)],
        "objdump-disassembly.txt": ["objdump", "-d", "-M", "intel", str(patched)],
    }
    status: dict[str, Any] = {"files": {}, "missing_tools": []}
    unavailable: set[str] = set()
    for name, argv in commands.items():
        if argv[0] in unavailable:
            status["files"][name] = "not_run"
            continue
        result = run_tool(argv)
        if not result["available"]:
            unavailable.add(argv[0])
            status["files"][name] = "not_run"
            status["missing_tools"].append(argv[0])
            continue
        (outdir / name).write_text(
            f"$ {' '.join(argv)}\n\n{result['stdout']}\n--- stderr ---\n{result['stderr']}",
            encoding="utf-8")
        status["files"][name] = "captured"
    program = outdir / "readelf-program-headers.txt"
    status["program_headers_text"] = (
        program.read_text(encoding="utf-8") if program.exists() else None)
    return status


def write_evidence_bundle(
    outdir: Path,
    *,
    original: Path,
    candidate: Path,
    manifest: dict[str, Any],
    audit: dict[str, Any],
    reproducibility: dict[str, Any],
    environment: dict[str, Any],
    independent_views: dict[str, Any],
) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "candidate.elf").write_bytes(candidate.read_bytes())
    (outdir / "original.elf").write_bytes(original.read_bytes())
    (outdir / "edit-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (outdir / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    (outdir / "reproducibility.json").write_text(json.dumps(reproducibility, indent=2),
                                                 encoding="utf-8")
    (outdir / "environment.json").write_text(json.dumps(environment, indent=2), encoding="utf-8")
    (outdir / "independent-views.json").write_text(
        json.dumps({k: v for k, v in independent_views.items() if k != "program_headers_text"},
                   indent=2), encoding="utf-8")
    item_states = gate3_item_states(manifest, audit, reproducibility, independent_views)
    (outdir / "gate3-record.md").write_text(
        render_record(item_states, environment, manifest), encoding="utf-8")

    hashes = []
    for path in sorted(p for p in outdir.rglob("*") if p.is_file()):
        rel = path.relative_to(outdir).as_posix()
        if rel in ("SHA256SUMS", "bundle-sha256.txt"):
            continue
        hashes.append(f"{sha256_file(path)}  {rel}")
    sums_text = "\n".join(hashes) + "\n"
    (outdir / "SHA256SUMS").write_text(sums_text, encoding="utf-8")
    bundle_hash = sha256_bytes(sums_text.encode("utf-8"))
    (outdir / "bundle-sha256.txt").write_text(bundle_hash + "\n", encoding="utf-8")
    return {"outdir": str(outdir), "bundle_sha256": bundle_hash,
            "file_count": len(hashes), "item_states": item_states,
            "sha256sums_ok": verify_sha256sums(outdir)}


def verify_sha256sums(bundle_dir: Path) -> bool:
    sums = bundle_dir / "SHA256SUMS"
    if not sums.exists():
        return False
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        path = bundle_dir / name.strip()
        if not path.exists() or sha256_file(path) != digest:
            return False
    return True


def gate3_item_states(manifest: dict[str, Any], audit: dict[str, Any],
                      reproducibility: dict[str, Any],
                      independent_views: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Map handoff 11 §3 items to what this static bundle measured."""
    static = "measured" if audit.get("pass") else "fail"
    repro = "measured" if reproducibility.get("pass") else "fail"
    readelf = "measured" if independent_views.get("program_headers_text") else "not_run"
    manifest_complete = bool(
        manifest.get("displaced") and manifest.get("added")
        and manifest.get("header_changes") and manifest.get("writer")
        and manifest.get("termination"))
    return {
        "1_separate_copy_and_hashes": {
            "state": "measured",
            "evidence": "original.elf, candidate.elf, SHA256SUMS; guest-side hashes still required",
        },
        "2_reproducibility_and_manifest": {
            "state": repro if manifest_complete else "fail",
            "evidence": "reproducibility.json, edit-manifest.json",
        },
        "3_structural_audit": {
            "state": static if readelf == "measured" else "partial",
            "evidence": "audit.json, environment.json, readelf-*.txt",
        },
        "4_six_case_run": {
            "state": "not_run",
            "evidence": "run routeb/run_manifest_repaired.py in the guest under isolation",
        },
        "5_isolation_evidence": {
            "state": "not_run",
            "evidence": "snapshot revert + egress block + uid 1003 wrapper attestation",
        },
        "6_evidence_bundle": {
            "state": "measured",
            "evidence": "SHA256SUMS, bundle-sha256.txt",
        },
    }


def render_record(item_states: dict[str, dict[str, str]], environment: dict[str, Any],
                  manifest: dict[str, Any]) -> str:
    patched_size = (manifest.get("header_changes") or {}).get("patched_size")
    lines = [
        "# Gate 3 static evidence record - canonical Route A candidate",
        "",
        "**Status:** generated by `python -m routea.gate3 bundle`. Static evidence only:",
        "items 4-5 (six-case run, isolation) are `not_run` until the guest run is",
        "recorded separately. Do not upgrade this to a gate pass from this file.",
        "",
        "## Candidate identity",
        "",
        f"- original SHA-256: `{manifest.get('original_sha256')}`",
        f"- candidate SHA-256: `{manifest.get('patched_sha256')}`",
        f"- candidate size: {patched_size} bytes",
        f"- kernel: {environment.get('kernel')} / {environment.get('platform')}",
        f"- python: {environment.get('python')}",
        "",
        "## Six required items (handoff 11 §3)",
        "",
        "| # | Item | State | Evidence |",
        "|---|---|---|---|",
    ]
    for key, value in item_states.items():
        lines.append(f"| {key.split('_', 1)[0]} | {key.split('_', 1)[1].replace('_', ' ')} "
                     f"| `{value['state']}` | {value['evidence']} |")
    lines += ["", "`measured` is not a gate label; `fail` means a concrete check failed; "
                  "`not_run` means execution/isolation evidence does not exist yet.", ""]
    return "\n".join(lines)
