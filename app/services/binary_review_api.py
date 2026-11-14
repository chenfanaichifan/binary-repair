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


def _validate_target(target: str | None, require_target: str | None) -> str | None:
    """Validate the optional declared-target form field.

    The target is a symbol name, unique symbol substring, or an explicit VA
    range accepted by the container-neutral resolver.  It is bounded to keep
    hostile uploads from turning into unbounded resolver work; a required but
    missing target is an explicit 422 (the pipeline would also fail closed,
    but a parameter error is clearer for API clients).
    """
    name = str(target or "").strip()
    if len(name) > 256:
        raise HTTPException(
            status_code=422,
            detail="target exceeds the 256 character limit.",
        )
    if _truthy(require_target) and not name:
        raise HTTPException(
            status_code=422,
            detail="require_target requires a non-empty target.",
        )
    return name or None


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
    target: str = Form(""),
    require_target: str = Form("0"),
    allow_whole_image: str = Form("0"),
    poc_manifest: UploadFile | None = File(None),
) -> JSONResponse:
    """Verify a direct ELF repair and optionally request a read-only review.

    The HTTP status is 200 for every valid upload, even when the deterministic
    gate is non-successful: the body's ``ok``/``decision`` carry the outcome and
    there is no candidate download unless the gate succeeded.

    An optional ``poc_manifest`` form field supplies the PoC/regression manifest
    used as runtime evidence by the reviewed capacity-check repair class.  It
    is validated here (<= 64 KiB, UTF-8 JSON object) and never bypasses the
    deterministic gate.

    Safe default: without ``target`` and without ``allow_whole_image=1`` the
    request is analysis-only (no candidate, no download) with
    ``target_policy="analysis_only"``.  ``target`` declares the function whose
    repair is claimed; ``require_target=1`` fails closed when it is missing;
    ``allow_whole_image=1`` is the explicit whole-image opt-in
    (``target_policy="whole_image"``, never a target repair).
    """
    _require_csrf(csrf)
    target_name = _validate_target(target, require_target)
    require = _truthy(require_target)
    allow_whole = _truthy(allow_whole_image)
    raw = await binary.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds the 20 MiB limit.")

    # Late import so tests and operators can monkeypatch ``app.main``'s client
    # factory; this also keeps the router independent of the app module's import
    # order.
    from app.main import _read_poc_manifest, client_from_env

    parsed_poc, poc_error = await _read_poc_manifest(poc_manifest)
    if poc_error:
        raise HTTPException(status_code=422, detail=poc_error)

    requested = _truthy(ai_review)
    client = client_from_env() if requested else None
    data_dir = os.environ.get("BINARYREPAIR_DATA_DIR") or "var"
    try:
        outcome = run_direct_repair(
            raw,
            request_review=requested,
            client=client,
            data_dir=data_dir,
            poc_manifest=parsed_poc,
            target=target_name,
            require_target=require,
            allow_whole_image=allow_whole,
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
