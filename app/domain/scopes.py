"""Evidence scope for each verification gate.

``scope`` says which layer a check actually observes, so the API and the UI do
not have to guess from the obligation kind:

* ``metadata`` - identity and bookkeeping (declared vs recorded hashes);
* ``static``   - offline analysis output (disassembly, recovery) not produced by
  the gates today, reserved for screening artifacts;
* ``binary``   - direct byte/ELF structure inspection of the built artifact;
* ``model``    - a symbolic or model-level conclusion, never machine code;
* ``replay``   - an actual execution of the artifact.

The mapping is deliberately conservative: a check never claims a stronger scope
than the evidence it reads. ``V4 symbolic`` is ``model`` even when it passes,
which is exactly why a passing V4 alone cannot be read as machine-level proof.
"""

from __future__ import annotations

SCOPES: tuple[str, ...] = ("metadata", "static", "binary", "model", "replay")

SCOPE_BY_KIND: dict[str, str] = {
    "identity": "metadata",
    "structure": "binary",
    "interface": "binary",
    "behaviour": "replay",
    "symbolic": "model",
    "reproducibility": "replay",
    # V3's two kinds, when a writer records them directly as obligations.
    "round_trip": "replay",
    "repaired_behaviour": "replay",
}


def scope_for_kind(kind: str) -> str:
    """Scope of an obligation kind; unknown kinds stay at the weakest layer."""
    return SCOPE_BY_KIND.get(kind, "metadata")


__all__ = ["SCOPES", "SCOPE_BY_KIND", "scope_for_kind"]
