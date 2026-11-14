"""Optional errno side-effect signature comparison.

Runtime extraction is intentionally separate: this module only defines the
conservative comparison used when a runner can supply both values.  ``None``
means the probe did not observe errno; zero means the C convention "unset".
"""
from __future__ import annotations


def set_state(value: int | None) -> str:
    if value is None:
        return "unknown"
    return "set" if value != 0 else "unset"


def compare(original: int | None, candidate: int | None) -> str:
    """Return matched/mismatch/not_run for the errno set/unset signature.

    Exact errno values are intentionally not compared: different libc paths may
    choose different but compatible values; the gate cares whether the repair
    changed whether errno is set at all.
    """
    if original is None or candidate is None:
        return "not_run"
    return "matched" if set_state(original) == set_state(candidate) else "mismatch"
