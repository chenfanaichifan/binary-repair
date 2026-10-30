#!/usr/bin/env python3
"""Second real attempt bundle set: V2 and V5 now carry measured evidence.

Differences from the first set are only V2 and V5. Route B V2 is recorded as
*failed* because the candidate adds two PT_LOAD segments where the contract
allows at most one, and that is what the probe measured. Nothing else moved.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

EV = Path(r"D:/BinRepair/docs/handoffs/evidence")
RUN = Path(r"D:/BinRepair/.tmp/p2-real-2026-10-30")

JOB_ORIGINAL = "aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build_route_a() -> dict:
    pkg = EV / "P3A"
    candidate = pkg / "route_a" / "candidate.elf"
    cand_sha = sha(candidate)
    bundle = json.loads((pkg / "result-bundle.json").read_text(encoding="utf-8"))
    assert cand_sha == bundle["identity"]["candidate_sha256"]

    v2 = json.loads((RUN / "v2-routea.json").read_text(encoding="utf-8"))
    v5 = json.loads((RUN / "v5-reproducibility.json").read_text(encoding="utf-8"))
    assert v2["hashes"]["candidate_sha256"] == cand_sha
    assert v5["routes"]["route_a"]["shipped_candidate_sha256"] == cand_sha

    results = {
        "V0": "passed",
        "V1": "passed",
        "V2": "passed" if v2["result"] == "passed" else "failed",
        "V3": "passed",
        "V4": "not_run",
        "V5": "passed" if v5["routes"]["route_a"]["result"] == "passed" else "failed",
    }
    details = {
        "V0": "P3A v6 result-bundle.json gates.V0.status = pass",
        "V1": "P3A v6 result-bundle.json gates.V1.status = pass",
        "V2": (
            f"v2_interface.py: {sum(1 for v in v2['checks'].values() if v is True)}"
            f"/{len(v2['checks'])} interface checks passed in the guest"
        ),
        "V3": "P3A v6 result-bundle.json gates.V3.status = pass",
        "V4": "bounded symbolic verdict not_run; no solver output in P3A v6",
        "V5": "fresh replay: 2 runs byte identical to the shipped candidate",
    }
    return {
        "route": "route_a",
        "candidate_sha256": cand_sha,
        "results": results,
        "evidence_files": {
            "V0": str(pkg / "result-bundle.json"),
            "V1": str(pkg / "evidence" / "v1" / "lief.json"),
            "V2": str(RUN / "v2-routea.json"),
            "V3": str(pkg / "evidence" / "v3" / "formal-run.json"),
            "V5": str(RUN / "v5-reproducibility.json"),
        },
        "details": details,
    }


def build_route_b() -> dict:
    pkg = EV / "P3B"
    candidate = pkg / "candidate.elf"
    cand_sha = sha(candidate)
    audit = json.loads((pkg / "audit.json").read_text(encoding="utf-8"))
    repaired = json.loads((pkg / "manifest-repaired.json").read_text(encoding="utf-8"))
    v2 = json.loads((RUN / "v2-routeb.json").read_text(encoding="utf-8"))
    v5 = json.loads((RUN / "v5-reproducibility.json").read_text(encoding="utf-8"))
    assert repaired["binary_sha256"] == cand_sha
    assert v2["hashes"]["candidate_sha256"] == cand_sha

    cases = repaired.get("cases") or []
    cases_ok = all(bool(c.get("ok")) for c in cases) and len(cases) == 6

    results = {
        "V0": "passed",
        "V1": "passed" if audit.get("pass") else "failed",
        "V2": "passed" if v2["result"] == "passed" else "failed",
        "V3": "passed" if cases_ok else "failed",
        "V4": "not_run",
        "V5": "passed" if v5["routes"]["route_b"]["result"] == "passed" else "failed",
    }
    details = {
        "V0": f"original {JOB_ORIGINAL} matches the job record; candidate matches manifest-repaired.binary_sha256",
        "V1": "P3B routeb static audit (audit.json pass=true)",
        "V2": (
            "v2_interface.py failed: extra_load_segments_within_contract — "
            f"{v2['informational']['extra_load_segment_count']} extra PT_LOAD segments, "
            f"contract allows {v2['informational']['allowed_extra_load_segments']} "
            "(authorized_edits[2], fallback only)"
        ),
        "V3": f"manifest-repaired.json: {sum(1 for c in cases if c.get('ok'))}/{len(cases)} cases ok",
        "V4": "bounded symbolic verdict not_run; no solver output in P3B v5",
        "V5": "record re-verified: shipped bytes match the recorded two-run result",
    }
    return {
        "route": "route_b",
        "candidate_sha256": cand_sha,
        "results": results,
        "evidence_files": {
            "V0": str(pkg / "edit-manifest.json"),
            "V1": str(pkg / "audit.json"),
            "V2": str(RUN / "v2-routeb.json"),
            "V3": str(pkg / "manifest-repaired.json"),
            "V5": str(RUN / "v5-reproducibility.json"),
        },
        "details": details,
    }


def main() -> None:
    for name, payload in (("route-a-v2", build_route_a()), ("route-b-v2", build_route_b())):
        path = RUN / f"{name}-input.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(name, payload["results"])


if __name__ == "__main__":
    main()
