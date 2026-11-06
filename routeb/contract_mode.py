"""Load a reviewed contract with M5's schema, never with a second copy.

The guest-side Route B scripts and the host-side executor both need the
contract's ``input_mode``. They must reject a contract body that the schema
rejects (for example a no-input body carrying an ``invalid_*`` sentinel), so
they call this adapter instead of reading the JSON field directly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.domain.contracts import SecurityContract  # noqa: E402


def load_contract(path: Path) -> SecurityContract:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("contract must be a JSON object")
    return SecurityContract.from_dict(payload)


def load_contract_mode(path: Path) -> str:
    return load_contract(path).input_mode
