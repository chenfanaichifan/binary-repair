"""Deterministic offline provider used by unit tests and preflight."""
from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Callable, Iterable

from ..base import GenerationRequest, GenerationResult


class MockProvider:
    name = "mock"

    def __init__(
        self,
        responses: Iterable[Any] | None = None,
        *,
        responder: Callable[[GenerationRequest], Any] | None = None,
        model: str = "mock-model",
        name: str = "mock",
    ) -> None:
        self.name = name
        self.responses = list(responses or [])
        self.responder = responder
        self.model = model
        self.requests: list[GenerationRequest] = []

    def __repr__(self) -> str:
        return f"MockProvider(name={self.name!r}, responses={len(self.responses)})"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.requests.append(request)
        if self.responder is not None:
            value = self.responder(request)
        elif self.responses:
            value = self.responses.pop(0)
        else:
            value = {"ok": True}
        if isinstance(value, Exception):
            raise value
        if isinstance(value, GenerationResult):
            return replace(value, provider=self.name)
        if isinstance(value, str):
            content = value
            model = request.model or self.model
            usage: dict[str, int] = {}
        else:
            content = json.dumps(value, ensure_ascii=False)
            model = request.model or self.model
            usage = {}
        return GenerationResult(content=content, provider=self.name,
                                model=model, model_requested=request.model,
                                usage=usage)


__all__ = ["MockProvider"]
