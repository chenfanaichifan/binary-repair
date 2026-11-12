"""Bounded AI adjudication: AI can veto, never certify an unverified patch.

The deterministic gate is the only source of a positive success. This module
provides the runtime guard and the one-way combination rule recommended in the
v1.2.1 review:

    gate success + AI accept  -> success_within_scope
    gate failure + AI accept  -> gate outcome (never promoted)
    gate success + AI reject  -> rejected (AI veto)
    gate failure + AI reject  -> gate outcome, AI veto recorded

Model payloads carrying verdict/evidence fields are rejected before this
function is called. This keeps model text out of the evidence channel.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

FORBIDDEN_MODEL_KEYS = frozenset(
    {
        "verdict", "outcome", "success_within_scope", "evidence",
        "obligations", "checks", "not_verdict", "gate", "final",
    }
)
AI_ACTIONS = frozenset({"accept", "reject", "repair"})
GATE_OUTCOMES = frozenset(
    {"success_within_scope", "rejected", "inconclusive", "unsupported", "error", "cancelled"}
)


class PolicyViolation(ValueError):
    """The model payload tried to cross the evidence boundary."""


def _walk_keys(value: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            keys.append(str(key))
            keys.extend(_walk_keys(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            keys.extend(_walk_keys(item))
    return keys


def guard_model_payload(payload: Any) -> None:
    """Reject verdict/evidence fields anywhere in a model-produced object."""
    if not isinstance(payload, Mapping):
        raise PolicyViolation("model payload must be an object")
    forbidden = sorted(set(_walk_keys(payload)) & FORBIDDEN_MODEL_KEYS)
    if forbidden:
        raise PolicyViolation(
            "model payload may not carry evidence/verdict fields: " + ", ".join(forbidden)
        )


@dataclass(frozen=True)
class GateResult:
    success: bool
    outcome: str
    reason: str = ""
    required_checks: int = 0
    required_not_run: int = 0
    evidence_sha256: str | None = None

    def validate(self) -> None:
        if self.outcome not in GATE_OUTCOMES:
            raise ValueError(f"unknown gate outcome: {self.outcome}")
        if self.success and self.outcome != "success_within_scope":
            raise ValueError("success gate must use success_within_scope")
        if self.success and (self.required_not_run or not self.evidence_sha256):
            raise ValueError("success gate needs complete required evidence and a hash")
        if self.outcome == "success_within_scope" and not self.success:
            raise ValueError("success_within_scope must be success")


@dataclass(frozen=True)
class FinalDecision:
    outcome: str
    success: bool
    authority: str
    gate_outcome: str
    ai_action: str
    reason: str
    evidence_sha256: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def adjudicate(gate: GateResult, ai_action: str) -> FinalDecision:
    """Combine a deterministic gate with a one-way AI action."""
    gate.validate()
    action = (ai_action or "").strip().lower()
    if action not in AI_ACTIONS:
        raise ValueError("ai_action must be accept, reject or repair")

    if not gate.success:
        # AI acceptance can never promote missing/failed evidence.
        reason = "ai_accept_cannot_promote_gate" if action == "accept" else gate.reason
        if action == "reject":
            reason = "ai_veto_on_non_success"
        return FinalDecision(
            outcome=gate.outcome,
            success=False,
            authority="deterministic_gate",
            gate_outcome=gate.outcome,
            ai_action=action,
            reason=reason or "gate_not_successful",
            evidence_sha256=gate.evidence_sha256,
        )

    if action == "reject":
        return FinalDecision(
            outcome="rejected",
            success=False,
            authority="ai_veto",
            gate_outcome=gate.outcome,
            ai_action=action,
            reason="ai_veto",
            evidence_sha256=gate.evidence_sha256,
        )
    if action == "repair":
        return FinalDecision(
            outcome="inconclusive",
            success=False,
            authority="ai_requested_repair",
            gate_outcome=gate.outcome,
            ai_action=action,
            reason="ai_requested_repair",
            evidence_sha256=gate.evidence_sha256,
        )
    return FinalDecision(
        outcome="success_within_scope",
        success=True,
        authority="deterministic_gate+ai_accept",
        gate_outcome=gate.outcome,
        ai_action=action,
        reason="gate_success_and_ai_accept",
        evidence_sha256=gate.evidence_sha256,
    )


def preflight_key_binding(
    *,
    key_file_configured: bool,
    env_present: bool,
    adapter_reads_same_env: bool,
) -> dict[str, Any]:
    """Fail closed when the custom key source cannot be seen by the adapter.

    N-10 is an environment contract, not a value to guess. This check never
    returns a key; it only reports whether a single source is visible to both
    processes.
    """
    if key_file_configured and not env_present:
        return {"ok": False, "reason": "key_env_not_visible", "source": "custom_key_file"}
    if key_file_configured and not adapter_reads_same_env:
        return {"ok": False, "reason": "adapter_env_mismatch", "source": "custom_key_file"}
    return {"ok": True, "reason": "single_visible_source", "source": "env_or_default"}


def supervisor_step(
    *, gate: GateResult, ai_action: str, attempt: int, max_attempts: int
) -> dict[str, Any]:
    """One bounded autonomous-loop step; never promotes a failed gate."""
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    decision = adjudicate(gate, ai_action)
    if decision.success:
        return {"state": "done", "decision": decision.as_dict()}
    if decision.ai_action == "repair" and attempt < max_attempts:
        return {"state": "retry", "decision": decision.as_dict(), "next_attempt": attempt + 1}
    return {"state": "stopped", "decision": decision.as_dict()}
