"""Independent Gate 3 audit + static evidence bundle for the canonical candidate.

Retargeted M4 tooling (patch review B1/B2): it builds the canonical
`routea.cave` plan (candidate `c4a159…`, contract `24bfe568…`) and audits it with
`routea.audit`, then writes the static evidence bundle. It never executes the
candidate; the six-case run and isolation evidence are separate guest steps.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from app.domain.contracts import SecurityContract
from routea.audit import audit_canonical_candidate
from routea.cave import build_cave_patched, plan_route_a_cave
from routea.evidence import (
    capture_environment,
    capture_independent_views,
    reproducibility_report,
    write_evidence_bundle,
)

CALL_SITE = 0x401304
CAVE_ADDR = 0x4018E9
CAVE_SIZE = 1815


def _load_contract(path: Path) -> SecurityContract:
    return SecurityContract.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _build(original: Path, contract: SecurityContract, dest: Path) -> Path:
    plan = plan_route_a_cave(original, contract, cave_addr=CAVE_ADDR, cave_size=CAVE_SIZE)
    build_cave_patched(original, plan, dest, scope_authorized=True)
    return dest


def _plan(original: Path, contract: SecurityContract):
    return plan_route_a_cave(original, contract, cave_addr=CAVE_ADDR, cave_size=CAVE_SIZE)


def audit_command(original: Path, patched: Path, contract_path: Path,
                  readelf: Path | None, out: Path | None) -> dict:
    contract = _load_contract(contract_path)
    plan = _plan(original, contract)
    readelf_text = readelf.read_text(encoding="utf-8", errors="replace") if readelf else None
    result = audit_canonical_candidate(original, patched, plan, readelf_text=readelf_text)
    text = json.dumps(result, indent=2)
    if out:
        out.write_text(text, encoding="utf-8")
    print(text)
    return result


def bundle_command(original: Path, contract_path: Path, outdir: Path) -> dict:
    contract = _load_contract(contract_path)
    outdir.mkdir(parents=True, exist_ok=True)
    candidate = outdir / "candidate.elf"
    plan = _plan(original, contract)
    manifest = build_cave_patched(original, plan, candidate, scope_authorized=True).to_dict()

    views = capture_independent_views(candidate, outdir / "independent-view")
    readelf_text = views.get("program_headers_text")
    audit = audit_canonical_candidate(original, candidate, plan, readelf_text=readelf_text)

    with tempfile.TemporaryDirectory(prefix="routea-gate3-") as tmp:
        report = reproducibility_report(
            original, lambda dest: _build(original, contract, dest), Path(tmp))

    environment = capture_environment()
    payload = dict(manifest)
    payload["audit"] = {"checks": audit["checks"], "pass": audit["pass"],
                        "failed": audit["failed"]}
    info = write_evidence_bundle(
        outdir,
        original=original,
        candidate=candidate,
        manifest=payload,
        audit=audit,
        reproducibility=report,
        environment=environment,
        independent_views=views,
    )
    print(json.dumps(info, indent=2))
    return info


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m routea.gate3")
    sub = ap.add_subparsers(dest="cmd", required=True)

    au = sub.add_parser("audit")
    au.add_argument("--original", type=Path, required=True)
    au.add_argument("--patched", type=Path, required=True)
    au.add_argument("--contract", type=Path, required=True)
    au.add_argument("--readelf", type=Path)
    au.add_argument("--out", type=Path)

    bd = sub.add_parser("bundle")
    bd.add_argument("--original", type=Path, required=True)
    bd.add_argument("--contract", type=Path, required=True)
    bd.add_argument("--out-dir", type=Path, required=True)

    args = ap.parse_args(argv)
    if args.cmd == "audit":
        result = audit_command(args.original, args.patched, args.contract,
                               args.readelf, args.out)
        return 0 if result["pass"] else 1
    info = bundle_command(args.original, args.contract, args.out_dir)
    return 0 if info["sha256sums_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
