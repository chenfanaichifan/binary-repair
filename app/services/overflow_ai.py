"""Runtime candidate memory for C overflow shapes.

The shipped model is a small logistic regression over structural features
trained offline by ``scripts/train_overflow_knowledge.py``. It is deliberately a
*candidate* classifier: deterministic rules remain authoritative, and the
model cannot claim that a patch is verified.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from app.services.overflow_features import vector

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE = ROOT / "knowledge"


class OverflowMemory:
    def __init__(self, root: Path = KNOWLEDGE) -> None:
        self.root = root
        self.kb: dict[str, Any] = {}
        self.model: dict[str, Any] = {}
        self.error = ""
        try:
            self.kb = json.loads((root / "overflow_kb.json").read_text(encoding="utf-8"))
            self.model = json.loads((root / "overflow_model.json").read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - optional memory must not break the app
            self.error = str(exc)

    @property
    def available(self) -> bool:
        return bool(self.model.get("features"))

    def status(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "error": self.error,
            "name": self.kb.get("name", "overflow-candidate-memory"),
            "generated_at": self.kb.get("generated_at"),
            "corpus": self.kb.get("corpus", {}),
            "metrics": self.kb.get("metrics", {}),
            "classes": self.kb.get("classes", []),
            "limits": self.kb.get("limits", []),
        }

    def classify(self, code: str) -> dict[str, Any]:
        if not self.available:
            return {"available": False, "error": self.error or "overflow memory is not installed"}
        raw = vector(code)
        if not any(raw):
            return {
                "available": True, "cwe": None, "confidence": 0.0,
                "alternatives": [], "novelty": True, "candidate_only": True,
                "model": self.model.get("family", ""),
                "note": "No known overflow surface features; this is not evidence of safety or vulnerability.",
            }
        mean = self.model["mean"]
        scale = self.model["scale"]
        normalized = [(value - mean[i]) / (scale[i] or 1.0) for i, value in enumerate(raw)]
        classes = list(self.model["classes"])
        logits = []
        for offset, cls in enumerate(classes):
            coef = self.model["coef"][offset]
            logits.append(float(self.model["intercept"][offset]) + sum(a * b for a, b in zip(coef, normalized)))
        top = max(logits)
        exps = [math.exp(value - top) for value in logits]
        total = sum(exps) or 1.0
        ranked = sorted(
            ({"cwe": cls, "probability": round(exp / total, 4)} for cls, exp in zip(classes, exps)),
            key=lambda item: item["probability"], reverse=True,
        )
        best = ranked[0]
        return {
            "available": True,
            "cwe": best["cwe"],
            "confidence": best["probability"],
            "alternatives": ranked[1:4],
            "novelty": best["probability"] < 0.55,
            "candidate_only": True,
            "model": self.model.get("family", ""),
            "note": "Candidate ranking from synthetic structural training; confirm with rules, review and runtime tests.",
        }


_memory: OverflowMemory | None = None


def memory() -> OverflowMemory:
    global _memory
    if _memory is None:
        _memory = OverflowMemory()
    return _memory
