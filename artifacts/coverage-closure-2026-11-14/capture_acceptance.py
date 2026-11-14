#!/usr/bin/env python3
"""Capture the two end-to-end coverage-closure acceptance paths.

1. reviewed capacity-check rewrite (marcx) through the real HTTP review API
   with the PoC/regression manifest executed in the Lima guest;
2. heap-destination guard (malloc+strcpy) through repair_any with its real
   manifest, plus the fail-closed no-manifest control for both.

Writes acceptance.json next to this script.  Run from the repo root with
.venv/bin/python; requires the Lima VM `binaryrepair` for the real guest runs.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from app.services.binary_pipeline import repair_any  # noqa: E402

OUT = Path(__file__).resolve().parent
MARCX = Path("fixtures/elf/vuln-capacity-confusion-x86_64.elf")
MARCX_MANIFEST = Path("fixtures/poc/marcx-capacity.json")
HEAP = Path("fixtures/hard-cases/vuln-heap-malloc-x86_64.elf")
HEAP_MANIFEST = Path("fixtures/poc/heap-malloc.json")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pipeline_case(name: str, binary: Path, manifest_path: Path, *, with_manifest: bool):
    raw = binary.read_bytes()
    manifest = json.loads(manifest_path.read_text()) if with_manifest else None
    out = repair_any(raw, verify=True, poc_manifest=manifest)
    report = out.report
    packet = (report.verification or {}).get("packet") or {}
    checks = {check["id"]: check["status"] for check in packet.get("checks") or []}
    return {
        "case": name,
        "with_manifest": with_manifest,
        "fixture_sha256": sha(raw),
        "disposition": report.disposition,
        "strategy": report.strategy,
        "mode": report.mode,
        "verified": bool(out.verified),
        "download_allowed": bool(out.download_allowed),
        "candidate_sha256": sha(out.candidate) if out.candidate else None,
        "gate_outcome": (report.verification or {}).get("gate", {}).get("outcome"),
        "profile": packet.get("scope", {}).get("profile"),
        "runtime_tier": packet.get("scope", {}).get("runtime_tier"),
        "checks_total": len(checks),
        "checks_failed": sorted(k for k, v in checks.items() if v == "failed"),
        "checks_not_run": sorted(k for k, v in checks.items() if v == "not_run"),
        "poc_status": (report.poc or {}).get("status") if isinstance(report.poc, dict) else None,
    }


def review_api_case() -> dict:
    from fastapi.testclient import TestClient

    from app.main import CSRF_TOKEN, SESSION_TOKEN, app

    client = TestClient(app, base_url="http://127.0.0.1")
    assert client.get("/?token=" + SESSION_TOKEN).status_code == 200
    response = client.post(
        "/api/binary/repair-review",
        data={"csrf": CSRF_TOKEN, "ai_review": "0"},
        files={
            "binary": ("marcx", MARCX.read_bytes(), "application/octet-stream"),
            "poc_manifest": ("marcx-capacity.json", MARCX_MANIFEST.read_bytes(), "application/json"),
        },
    )
    payload = response.json()
    verification = payload.get("verification") or {}
    checks = {check["id"]: check["status"] for check in verification.get("checks") or []}
    patched = payload.get("patched_sha256")
    if not patched and payload.get("patched_base64"):
        import base64

        patched = sha(base64.b64decode(payload["patched_base64"]))
    return {
        "case": "marcx-review-api",
        "http_status": response.status_code,
        "ok": payload.get("ok"),
        "decision": payload.get("decision"),
        "patched_sha256": patched,
        "checks_total": len(checks),
        "checks_failed": sorted(k for k, v in checks.items() if v == "failed"),
        "checks_not_run": sorted(k for k, v in checks.items() if v == "not_run"),
        "profile": (verification.get("scope") or {}).get("profile"),
        "runtime_tier": (verification.get("scope") or {}).get("runtime_tier"),
    }


def main() -> int:
    results = {
        "generated_by": "artifacts/coverage-closure-2026-11-14/capture_acceptance.py",
        "marcx_review_api": review_api_case(),
        "marcx_pipeline_with_manifest": pipeline_case(
            "marcx-pipeline", MARCX, MARCX_MANIFEST, with_manifest=True
        ),
        "marcx_pipeline_without_manifest": pipeline_case(
            "marcx-pipeline", MARCX, MARCX_MANIFEST, with_manifest=False
        ),
        "heap_pipeline_with_manifest": pipeline_case(
            "heap-pipeline", HEAP, HEAP_MANIFEST, with_manifest=True
        ),
        "heap_pipeline_without_manifest": pipeline_case(
            "heap-pipeline", HEAP, HEAP_MANIFEST, with_manifest=False
        ),
    }
    failures = []
    marcx = results["marcx_review_api"]
    if not (marcx["ok"] and marcx["decision"]["success"]):
        failures.append("marcx review API did not succeed")
    if results["marcx_review_api"]["checks_failed"]:
        failures.append("marcx review API has failed checks")
    expected_marcx = "93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2"
    if marcx["patched_sha256"] != expected_marcx:
        failures.append("marcx patched sha mismatch")
    heap = results["heap_pipeline_with_manifest"]
    if not (heap["verified"] and heap["disposition"] == "verified_patch"):
        failures.append("heap pipeline did not verify with manifest")
    expected_heap = "ea22260535efca37dca19404c700ce29e6da1f45b3af24d3903c8d27fdf6fb73"
    if heap["candidate_sha256"] != expected_heap:
        failures.append("heap candidate sha mismatch")
    for key in ("marcx_pipeline_without_manifest", "heap_pipeline_without_manifest"):
        row = results[key]
        if row["verified"] or row["download_allowed"]:
            failures.append(f"{key} must stay fail-closed without evidence")
    results["failures"] = failures
    results["passed"] = not failures
    (OUT / "acceptance.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({k: results[k] for k in (
        "marcx_review_api", "marcx_pipeline_with_manifest",
        "marcx_pipeline_without_manifest", "heap_pipeline_with_manifest",
        "heap_pipeline_without_manifest", "passed", "failures")}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
