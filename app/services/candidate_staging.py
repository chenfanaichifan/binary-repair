"""Host-side staging for provider repair proposals.

A proposal is input, not evidence. Staging records what the provider suggested
and where those bytes live; it deliberately creates no run, no attempt, no
obligation, and no verdict. A proposal only becomes a candidate when a route
produces candidate bytes, and that candidate still has to pass V0-V5 through
``app.domain.acceptance`` like any other candidate.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services import jobs

MAX_PROPOSAL_BYTES = 64 * 1024
STATUS_STAGED = "staged"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def proposals_dir(data_dir: str | Path, job_id: str) -> Path:
    return Path(data_dir) / "jobs" / job_id / "staging" / "proposals"


def _record_path(data_dir: str | Path, job_id: str, proposal_id: str) -> Path:
    # proposal_id is the digest of the proposal text, so it is always a plain
    # hex string. Reject anything else instead of letting it touch the path.
    if not proposal_id or len(proposal_id) != 64 or any(
        character not in "0123456789abcdef" for character in proposal_id
    ):
        raise ValueError("proposal id must be a sha256 hex digest")
    return proposals_dir(data_dir, job_id) / f"{proposal_id}.json"


def stage_proposal(
    job_id: str,
    *,
    data_dir: str | Path,
    text: str,
    source: str = "provider",
    model: str | None = None,
) -> dict[str, Any]:
    """Persist one provider proposal and return its staging record.

    Identical text is deduplicated: the digest is the identity, so restaging the
    same suggestion returns the existing record instead of a second copy.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("proposal text must be a non-empty string")
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_PROPOSAL_BYTES:
        raise ValueError(f"proposal exceeds {MAX_PROPOSAL_BYTES} bytes")
    if jobs.get_job(job_id, data_dir=data_dir) is None:
        raise ValueError("job not found")

    proposal_id = hashlib.sha256(encoded).hexdigest()
    path = _record_path(data_dir, job_id, proposal_id)
    if path.is_file():
        return {**json.loads(path.read_text(encoding="utf-8")), "deduplicated": True}

    record = {
        "id": proposal_id,
        "job_id": job_id,
        "sha256": proposal_id,
        "bytes": len(encoded),
        "source": source,
        "model": model,
        "text": text,
        "status": STATUS_STAGED,
        "created_at": _now(),
        # A staged proposal has no acceptance state at all. These keys are
        # explicit so nobody can read "staged" as "passed".
        "candidate": False,
        "verdict": None,
        "obligations_evaluated": 0,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        prefix=".proposal-", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as temp:
            json.dump(record, temp, indent=2, sort_keys=True)
            temp.write("\n")
        os.replace(temp_name, path)
    except BaseException:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise
    return {**record, "deduplicated": False}


def get_proposal(
    job_id: str, proposal_id: str, *, data_dir: str | Path
) -> dict[str, Any] | None:
    path = _record_path(data_dir, job_id, proposal_id)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_proposals(job_id: str, *, data_dir: str | Path) -> list[dict[str, Any]]:
    directory = proposals_dir(data_dir, job_id)
    if not directory.is_dir():
        return []
    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]
    records.sort(key=lambda record: (str(record.get("created_at") or ""), str(record.get("id") or "")), reverse=True)
    return records


__all__ = [
    "MAX_PROPOSAL_BYTES",
    "STATUS_STAGED",
    "get_proposal",
    "list_proposals",
    "proposals_dir",
    "stage_proposal",
]
