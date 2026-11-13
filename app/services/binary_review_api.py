"""HTTP surface for the read-only direct-ELF review path.

This router is registered by ``app.main`` after the FastAPI app exists, which
keeps the legacy quick-repair route untouched and makes the new path easy to
test without duplicating the session/host middleware.
"""
from __future__ import annotations

import hmac
import os
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.services.binary_review import run_direct_repair

router = APIRouter()
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _require_csrf(token: str) -> None:
    # Late import: this router is imported while app.main is still defining the
    # app, so importing CSRF_TOKEN at module scope would be circular.  Requests
    # only arrive after app.main has finished loading.
    from app.main import CSRF_TOKEN

    if not token or not hmac.compare_digest(str(token), CSRF_TOKEN):
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid.")


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _filename(name: str | None, fmt: str = "elf") -> str:
    base = Path(name or "sample.elf").name
    stem = Path(base).stem or "sample"
    suffix = {"elf": ".elf", "pe": ".exe", "macho": ".macho"}.get(fmt, ".bin")
    return f"{stem}-fixed{suffix}"


@router.post("/api/binary/repair-review")
async def binary_repair_review(
    binary: UploadFile = File(...),
    csrf: str = Form(...),
    ai_review: str = Form("0"),
) -> JSONResponse:
    """Verify a direct ELF repair and optionally request a read-only review.

    The HTTP status is 200 for every valid upload, even when the deterministic
    gate is non-successful: the body's ``ok``/``decision`` carry the outcome and
    there is no candidate download unless the gate succeeded.
    """
    _require_csrf(csrf)
    raw = await binary.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds the 20 MiB limit.")

    # Late import so tests and operators can monkeypatch ``app.main``'s client
    # factory; this also keeps the router independent of the app module's import
    # order.
    from app.main import client_from_env

    requested = _truthy(ai_review)
    client = client_from_env() if requested else None
    data_dir = os.environ.get("BINARYREPAIR_DATA_DIR") or "var"
    try:
        outcome = run_direct_repair(
            raw,
            request_review=requested,
            client=client,
            data_dir=data_dir,
        )
    except Exception:  # noqa: BLE001 - no stack/secret text leaves the process
        return JSONResponse(
            {"ok": False, "detail": "direct repair review failed"},
            status_code=500,
            headers={"Cache-Control": "no-store"},
        )

    payload = outcome.to_payload(
        filename=_filename(binary.filename, getattr(outcome.report, "format", "elf")),
        include_candidate=True,
    )
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


@router.get("/api/binary/review-contract")
async def binary_review_contract() -> JSONResponse:
    """Describe the review-only boundary without exposing provider details."""
    return JSONResponse(
        {
            "schema_version": 1,
            "authority": "deterministic_gate",
            "review_only": True,
            "endpoint": "/api/binary/repair-review",
            "recommendations": ["accept", "hold", "needs_more_checks"],
            "ai_may": ["accept", "hold", "needs_more_checks"],
            "ai_may_not": [
                "promote_gate_failure",
                "emit_verdict",
                "emit_evidence",
                "change_gate_evidence",
            ],
            "success_requires": (
                "success_within_scope gate with every required check passed and "
                "a complete evidence hash"
            ),
            "hold_effect": "veto_gate_success",
            "accept_effect": "cannot_promote_failed_gate",
            "review_unavailable_effect": "gate_outcome_unchanged",
            "review_can_only_tighten": True,
            "download_requires": "decision.success",
            "patched_bytes_requires": "decision.success",
            "gate_evidence_immutable": True,
            "scripted_control": (
                "scripted reviewers use the same rule but report called=false "
                "and an authority prefixed scripted_"
            ),
            "not_verdict": True,
        },
        headers={"Cache-Control": "no-store"},
    )
