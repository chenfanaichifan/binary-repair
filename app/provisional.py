"""Provisional evidence status for the GUI.

A route attempt is provisional until the P3A checker and the M5 worker JSON are
accepted. Provisional evidence is display-only and must never be presented as a
success or as a replacement for a Gate 3 approval.
"""

from __future__ import annotations

from typing import Any

SUPERSEDED_SOURCES = {
    "8256c8501afd95c02b371a99a507c436e5e431f49bdc5e4641b9a3bab2cbe64f": (
        "gate3-bundle-v2-2026-10-22"
    ),
    "0ef655464459dd0597f8259b3784ee15389884c9a75b26afa1299af7f54bf8d5": (
        "gate3-bundle-2026-10-22"
    ),
}
DEFAULT_SOURCE = "8256c8501afd95c02b371a99a507c436e5e431f49bdc5e4641b9a3bab2cbe64f"


def provisional_notice(snapshot: dict[str, Any]) -> dict[str, str] | None:
    """Return a provisional warning when evidence is not P3A/Gate-3 approved."""
    if snapshot.get("demo"):
        return None
    if snapshot.get("p3a_checker") == "passed" or snapshot.get("gate3_approved"):
        return None
    route_a = (snapshot.get("routes") or {}).get("A") or {}
    if not route_a.get("outcome"):
        return None
    source = (
        snapshot.get("source_sha256")
        or route_a.get("source_sha256")
        or snapshot.get("provisional_source")
        or DEFAULT_SOURCE
    )
    return {
        "source_sha256": str(source),
        "label": SUPERSEDED_SOURCES.get(str(source), "old attempt / superseded source"),
    }
