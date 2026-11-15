"""Build a bounded, non-rewriting feedback packet for assembly repair."""
from __future__ import annotations

from typing import Any


def build_assembly_feedback(raw_assembly: str,
                            diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "raw_assembly": raw_assembly,
        "diagnostics": diagnostics,
        "instructions": [
            "Do not change the meaning by deleting or rewriting the reported line.",
            "Replace absolute branch targets with local labels inside the replacement block.",
            "Keep the complete function and the calling convention; return corrected assembly.",
            "Do not use ud2/int3/traps/privileged instructions or unlisted calls.",
        ],
    }
