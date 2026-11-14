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


def pipeline_case(name: str, binary: Path, manifest_path: Path, *, with_manifest: bool,
                  allow_whole_image: bool = False):
    raw = binary.read_bytes()
    manifest = json.loads(manifest_path.read_text()) if with_manifest else None
    out = repair_any(raw, verify=True, poc_manifest=manifest,
                     allow_whole_image=allow_whole_image)
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
        "target_policy": (report.universal or {}).get("target_policy"),
        "allow_whole_image": allow_whole_image,
    }


def target_scoped_case() -> dict:
    """Heap repair restricted to the declared target function (P0 ownership)."""
    raw = HEAP.read_bytes()
    manifest = json.loads(HEAP_MANIFEST.read_text())
    out = repair_any(raw, verify=True, poc_manifest=manifest, target="heap_bad", require_target=True)
    report = out.report
    packet = (report.verification or {}).get("packet") or {}
    checks = {check["id"]: check["status"] for check in packet.get("checks") or []}
    scope = (packet.get("scope") or {}).get("target")
    return {
        "case": "heap-target-scoped",
        "target": "heap_bad",
        "disposition": report.disposition,
        "verified": bool(out.verified),
        "candidate_sha256": sha(out.candidate) if out.candidate else None,
        "gate_outcome": (report.verification or {}).get("gate", {}).get("outcome"),
        "target_scope_check": checks.get("patch.target_scope"),
        "target_scope": scope,
        "checks_total": len(checks),
        "checks_failed": sorted(k for k, v in checks.items() if v == "failed"),
    }


def wrong_target_case() -> dict:
    """A target with no patchable sink must fail closed (no candidate)."""
    raw = HEAP.read_bytes()
    manifest = json.loads(HEAP_MANIFEST.read_text())
    out = repair_any(raw, verify=True, poc_manifest=manifest, target="main", require_target=True)
    report = out.report
    return {
        "case": "heap-wrong-target",
        "target": "main",
        "disposition": report.disposition,
        "verified": bool(out.verified),
        "download_allowed": bool(out.download_allowed),
        "candidate_present": out.candidate is not None,
        "error": str(report.error or "")[:200],
    }


def review_api_case() -> dict:
    from fastapi.testclient import TestClient

    from app.main import CSRF_TOKEN, SESSION_TOKEN, app

    client = TestClient(app, base_url="http://127.0.0.1")
    assert client.get("/?token=" + SESSION_TOKEN).status_code == 200
    response = client.post(
        "/api/binary/repair-review",
        data={"csrf": CSRF_TOKEN, "ai_review": "0", "allow_whole_image": "1"},
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
        "target_policy": (verification.get("scope") or {}).get("target_policy"),
    }


def main() -> int:
    results = {
        "generated_by": "artifacts/coverage-closure-2026-11-14/capture_acceptance.py",
        "marcx_review_api": review_api_case(),
        "marcx_pipeline_with_manifest": pipeline_case(
            "marcx-pipeline", MARCX, MARCX_MANIFEST, with_manifest=True,
            allow_whole_image=True,
        ),
        "marcx_pipeline_without_manifest": pipeline_case(
            "marcx-pipeline", MARCX, MARCX_MANIFEST, with_manifest=False,
            allow_whole_image=True,
        ),
        "heap_pipeline_with_manifest": pipeline_case(
            "heap-pipeline", HEAP, HEAP_MANIFEST, with_manifest=True,
            allow_whole_image=True,
        ),
        "heap_pipeline_without_manifest": pipeline_case(
            "heap-pipeline", HEAP, HEAP_MANIFEST, with_manifest=False,
            allow_whole_image=True,
        ),
        "marcx_safe_default": pipeline_case(
            "marcx-safe-default", MARCX, MARCX_MANIFEST, with_manifest=True,
            allow_whole_image=False,
        ),
        "heap_safe_default": pipeline_case(
            "heap-safe-default", HEAP, HEAP_MANIFEST, with_manifest=True,
            allow_whole_image=False,
        ),
        "heap_target_scoped": target_scoped_case(),
        "heap_wrong_target": wrong_target_case(),
    }
    failures = []
    marcx = results["marcx_review_api"]
    if not (marcx["ok"] and marcx["decision"]["success"]):
        failures.append("marcx review API did not succeed")
    if results["marcx_review_api"]["checks_failed"]:
        failures.append("marcx review API has failed checks")
    if results["marcx_review_api"].get("target_policy") != "whole_image":
        failures.append("marcx review API opt-in did not record target_policy=whole_image")
    for key in ("marcx_safe_default", "heap_safe_default"):
        row = results[key]
        if row["disposition"] != "analysis_only" or row["verified"] or row["download_allowed"]:
            failures.append(f"{key} must stay analysis_only without target or allow_whole_image")
    for key in ("marcx_pipeline_with_manifest", "heap_pipeline_with_manifest"):
        if results[key].get("target_policy") != "whole_image":
            failures.append(f"{key} did not record whole_image policy")
    expected_marcx = "93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2"
    if marcx["patched_sha256"] != expected_marcx:
        failures.append("marcx patched sha mismatch")
    heap = results["heap_pipeline_with_manifest"]
    if not (heap["verified"] and heap["disposition"] == "verified_patch"):
        failures.append("heap pipeline did not verify with manifest")
    expected_heap = "ea22260535efca37dca19404c700ce29e6da1f45b3af24d3903c8d27fdf6fb73"
    if heap["candidate_sha256"] != expected_heap:
        failures.append("heap candidate sha mismatch")
    scoped = results["heap_target_scoped"]
    if scoped["disposition"] != "verified_patch" or scoped["target_scope_check"] != "passed":
        failures.append("target-scoped heap repair did not verify with patch.target_scope passed")
    if scoped["candidate_sha256"] != expected_heap:
        failures.append("target-scoped heap candidate sha mismatch")
    wrong = results["heap_wrong_target"]
    if wrong["verified"] or wrong["download_allowed"] or wrong["candidate_present"]:
        failures.append("wrong-target repair must fail closed without a candidate")
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
        "heap_pipeline_without_manifest", "heap_target_scoped", "heap_wrong_target",
        "marcx_safe_default", "heap_safe_default", "passed", "failures")}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
