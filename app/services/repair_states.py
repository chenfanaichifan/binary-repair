"""Canonical repair/capability states: the single source of truth.

Every module that reasons about repair progress must use the states and
transitions declared here instead of inventing its own vocabulary. The state
machine is deliberately small and fail-closed:

* a repair attempt starts at ``candidate`` (a target/attempt exists but no
  analysis has been accepted yet);
* ``analysis_only`` means the attempt was analysed without a verified patch;
* ``patch_candidate`` means candidate bytes exist but the deterministic gate has
  not accepted them yet;
* ``verified`` means the deterministic gate returned ``success_within_scope``;
* ``release_eligible`` is a *separate* terminal state: it requires both
  ``evidence_ok`` and ``independence_ok`` on top of ``verified``. Documentation
  or a model recommendation can never make that transition by itself.

Failure outcomes are explicit states (``not_run``, ``unavailable``,
``unsupported``, ``rejected``, ``inconclusive``, ``regression_failed``,
``identity_mismatch``) instead of a boolean. Illegal transitions return a
non-empty reason so callers never have to guess.

This module imports nothing from the pipeline at import time. The read-only
mapping to ``app.services.acceptance_invariants`` is resolved lazily inside
:func:`acceptance_invariants_state` (that module is not modified here).
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA_VERSION = 1

#: Capability-universe states (a capability claim, not a repair attempt).
CAPABILITY_STATES: tuple[str, ...] = (
    "not_started",
    "partial",
    "covered",
    "non_goal",
    "unavailable",
)

#: Non-terminal + terminal states of one repair attempt, in forward order.
REPAIR_STATES: tuple[str, ...] = (
    "candidate",
    "analysis_only",
    "patch_candidate",
    "verified",
    "release_eligible",
)

#: Explicit failure states. A failure is never "just false".
FAILURE_STATES: tuple[str, ...] = (
    "not_run",
    "unavailable",
    "unsupported",
    "rejected",
    "inconclusive",
    "regression_failed",
    "identity_mismatch",
)

#: Terminal repair states: no further transition is legal from here.
TERMINAL_STATES: tuple[str, ...] = (
    "release_eligible",
    "unsupported",
    "rejected",
    "regression_failed",
    "identity_mismatch",
)

#: Every repair state (forward states plus failure states).
ALL_REPAIR_STATES: tuple[str, ...] = REPAIR_STATES + FAILURE_STATES

#: The pseudo-state used when an attempt has not been started yet.
START_STATE = "start"

#: Accepted start aliases (a transition may start from "nothing yet").
_START_ALIASES = frozenset({"", "start", "initial", "new", "none"})

#: Allowed transitions. Targets are declared repair states; the transition is
#: otherwise rejected with an explicit reason.
ALLOWED_TRANSITIONS: Mapping[str, tuple[str, ...]] = {
    START_STATE: (
        "candidate",
        "analysis_only",
        "not_run",
        "unsupported",
        "unavailable",
    ),
    "candidate": (
        "analysis_only",
        "patch_candidate",
        "not_run",
        "inconclusive",
        "unsupported",
        "rejected",
        "identity_mismatch",
    ),
    "analysis_only": (
        "patch_candidate",
        "not_run",
        "unsupported",
        "rejected",
    ),
    "patch_candidate": (
        "verified",
        "inconclusive",
        "rejected",
        "regression_failed",
        "identity_mismatch",
    ),
    "verified": (
        "release_eligible",
        "rejected",
        "identity_mismatch",
    ),
    "release_eligible": (),
    "not_run": (
        "candidate",
        "analysis_only",
        "unavailable",
    ),
    "inconclusive": (
        "candidate",
        "analysis_only",
        "not_run",
        "rejected",
    ),
    "unavailable": (
        "candidate",
        "not_run",
        "analysis_only",
    ),
    "unsupported": (),
    "rejected": (),
    "regression_failed": (),
    "identity_mismatch": (),
}

#: Raw status/disposition vocabulary (old pipeline and invariants) mapped to
#: canonical repair states. Unknown tokens map to ``"unknown"``.
STATUS_ALIASES: Mapping[str, str] = {
    # verified family (acceptance_invariants.VERIFIED_DISPOSITIONS)
    "verified": "verified",
    "verified_patch": "verified",
    "patched": "verified",
    "success_within_scope": "verified",
    # candidate / pre-verification family
    "candidate": "candidate",
    "patch_candidate": "patch_candidate",
    "static_only_patch": "patch_candidate",
    # analysis-only family (acceptance_invariants.NON_DOWNLOAD_DISPOSITIONS)
    "analysis_only": "analysis_only",
    "not_verified": "analysis_only",
    "invalid": "unsupported",
    # explicit failure states
    "not_run": "not_run",
    "inconclusive": "inconclusive",
    "unsupported": "unsupported",
    "unavailable": "unavailable",
    "rejected": "rejected",
    "regression_failed": "regression_failed",
    "identity_mismatch": "identity_mismatch",
    # capability-universe tokens are accepted by capability_state_of, not here
    "release_eligible": "release_eligible",
}

#: Raw tokens that only make sense for a capability claim.
CAPABILITY_STATUS_ALIASES: Mapping[str, str] = {
    "not_started": "not_started",
    "partial": "partial",
    "covered": "covered",
    "supported": "covered",
    "non_goal": "non_goal",
    "unavailable": "unavailable",
    "unknown": "not_started",
}

#: Token used when a status cannot be normalized.
UNKNOWN_STATE = "unknown"

#: Keys inspected by :func:`state_of` when a mapping/object is supplied.
_STATE_KEYS: tuple[str, ...] = (
    "canonical_state",
    "state",
    "disposition",
    "status",
    "gate_outcome",
    "outcome",
)

#: Fallback copies of the read-only acceptance-invariants vocabulary. They are
#: only used if the invariants module cannot be imported; the mapping is
#: cross-checked by tests when the module is importable.
_FALLBACK_VERIFIED_DISPOSITIONS: tuple[str, ...] = (
    "verified_patch",
    "verified",
    "patched",
)
_FALLBACK_NON_DOWNLOAD_DISPOSITIONS: tuple[str, ...] = (
    "analysis_only",
    "not_verified",
    "unsupported",
    "invalid",
    "rejected",
)
_FALLBACK_TARGET_POLICIES: tuple[str, ...] = (
    "target_scoped",
    "whole_image",
    "analysis_only",
)
_FALLBACK_GATE_OUTCOMES: tuple[str, ...] = (
    "success_within_scope",
    "rejected",
    "inconclusive",
    "unsupported",
)


def _acceptance_vocabulary() -> dict[str, tuple[str, ...]]:
    """Read-only view of the acceptance-invariants vocabulary (lazy import)."""
    try:
        from app.services import acceptance_invariants as invariants
    except Exception:  # noqa: BLE001 - optional read-only dependency
        return {
            "verified_dispositions": _FALLBACK_VERIFIED_DISPOSITIONS,
            "non_download_dispositions": _FALLBACK_NON_DOWNLOAD_DISPOSITIONS,
            "target_policies": _FALLBACK_TARGET_POLICIES,
            "gate_outcomes": _FALLBACK_GATE_OUTCOMES,
        }
    return {
        "verified_dispositions": tuple(
            str(item) for item in getattr(invariants, "VERIFIED_DISPOSITIONS", ())
        ) or _FALLBACK_VERIFIED_DISPOSITIONS,
        "non_download_dispositions": tuple(
            str(item) for item in getattr(
                invariants, "NON_DOWNLOAD_DISPOSITIONS", ())
        ) or _FALLBACK_NON_DOWNLOAD_DISPOSITIONS,
        "target_policies": tuple(
            str(item) for item in getattr(invariants, "TARGET_POLICIES", ())
        ) or _FALLBACK_TARGET_POLICIES,
        "gate_outcomes": _FALLBACK_GATE_OUTCOMES,
    }


def canonical_status(value: Any) -> str:
    """Normalize one status token to a canonical repair state.

    ``value`` may be a string or a string-valued enum. Unknown values return
    ``"unknown"`` instead of raising, so callers can fail closed explicitly.
    """
    if isinstance(value, str):
        token = value.strip().lower()
    else:
        token = str(getattr(value, "value", value) or "").strip().lower()
    if token in REPAIR_STATES or token in FAILURE_STATES:
        return token
    return STATUS_ALIASES.get(token, UNKNOWN_STATE)


def capability_state_of(value: Any) -> str:
    """Normalize one capability-universe status token (D01-D20 registry)."""
    if isinstance(value, str):
        token = value.strip().lower()
    else:
        token = str(getattr(value, "value", value) or "").strip().lower()
    if token in CAPABILITY_STATES:
        return token
    return CAPABILITY_STATUS_ALIASES.get(token, UNKNOWN_STATE)


def _value_of(container: Any, key: str) -> Any:
    if isinstance(container, Mapping):
        return container.get(key)
    return getattr(container, key, None)


def _container_view(value: Any) -> Mapping[str, Any] | None:
    """Best-effort mapping view of a report/packet/record object."""
    if isinstance(value, Mapping):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            result = to_dict()
        except Exception:  # noqa: BLE001 - target object is untrusted
            result = None
        if isinstance(result, Mapping):
            return result
    view = getattr(value, "__dict__", None)
    if isinstance(view, Mapping):
        return {
            key: item for key, item in view.items() if not key.startswith("_")
        }
    return None


def state_of(value: Any) -> str:
    """Extract and normalize the canonical repair state of a report/record/str.

    Mapping/objects are inspected through ``canonical_state``, ``state``,
    ``disposition``, ``status``, ``gate_outcome`` and ``outcome`` in order.
    Nested ``verification.gate`` / ``gate`` views are also supported when the
    top-level object only carries a verification packet. Returns ``"unknown"``
    when no state can be established (never guesses ``verified``).
    """
    if isinstance(value, str):
        return canonical_status(value)
    view = _container_view(value)
    if view is not None:
        for key in _STATE_KEYS:
            candidate = view.get(key)
            if candidate:
                state = canonical_status(candidate)
                if state != UNKNOWN_STATE:
                    return state
        for nested_key in ("verification", "gate", "decision", "report"):
            nested = view.get(nested_key)
            if nested is None:
                continue
            if isinstance(nested, Mapping):
                for key in _STATE_KEYS:
                    candidate = nested.get(key)
                    if candidate:
                        state = canonical_status(candidate)
                        if state != UNKNOWN_STATE:
                            return state
                candidate = nested.get("gate")
                if isinstance(candidate, Mapping):
                    state = canonical_status(candidate.get("outcome"))
                    if state != UNKNOWN_STATE:
                        return state
        success = view.get("success")
        if isinstance(success, bool):
            return "verified" if success else "analysis_only"
        verified = view.get("verified")
        if isinstance(verified, bool):
            return "verified" if verified else "analysis_only"
    if value is None:
        return UNKNOWN_STATE
    return canonical_status(value)


def is_failure_state(value: Any) -> bool:
    return canonical_status(value) in FAILURE_STATES


def is_terminal_state(value: Any) -> bool:
    return canonical_status(value) in TERMINAL_STATES


def allowed_transitions(from_state: Any) -> tuple[str, ...]:
    """Allowed target states for ``from_state`` (empty for terminal states)."""
    if from_state is None or str(from_state).strip().lower() in _START_ALIASES:
        return ALLOWED_TRANSITIONS[START_STATE]
    state = canonical_status(from_state)
    if state == UNKNOWN_STATE:
        return ()
    return ALLOWED_TRANSITIONS.get(state, ())


def _normalize_from(from_state: Any) -> str:
    if from_state is None:
        return START_STATE
    token = str(from_state).strip().lower()
    if token in _START_ALIASES:
        return START_STATE
    return canonical_status(from_state)


def validate_transition(
    from_state: Any,
    to_state: Any,
    evidence_ok: bool = False,
    independence_ok: bool = False,
) -> tuple[bool, str]:
    """Validate one repair-state transition; returns ``(allowed, reason)``.

    ``reason`` is an empty string for an allowed transition and a concrete
    explanation for every rejection. The ``verified`` -> ``release_eligible``
    transition additionally requires ``evidence_ok=True`` and
    ``independence_ok=True``; missing either gate rejects the transition even
    though the edge is otherwise legal.
    """
    origin = _normalize_from(from_state)
    if origin == UNKNOWN_STATE:
        return False, f"unknown source state: {from_state!r}"
    target = canonical_status(to_state)
    if target == UNKNOWN_STATE:
        return False, f"unknown target state: {to_state!r}"
    if origin == target:
        return False, (
            f"self-transition {origin!r} is not a state change"
        )
    allowed_targets = ALLOWED_TRANSITIONS.get(origin, ())
    if target not in allowed_targets:
        return False, (
            f"illegal transition {origin!r} -> {target!r}; "
            f"allowed targets: {list(allowed_targets)}"
        )
    if origin == "verified" and target == "release_eligible":
        missing: list[str] = []
        if not evidence_ok:
            missing.append("evidence_ok=True (evidence gate not satisfied)")
        if not independence_ok:
            missing.append("independence_ok=True (independence gate not satisfied)")
        if missing:
            return False, (
                "verified -> release_eligible requires " + " and ".join(missing)
            )
    return True, ""


def acceptance_invariants_state(value: Any) -> str:
    """Map an old acceptance-invariants value to a canonical repair state.

    Covers every value in the invariants module's verified dispositions,
    non-download dispositions, target policies and gate outcomes. The mapping is
    read-only: the invariants module is imported lazily and never modified.
    """
    vocabulary = _acceptance_vocabulary()
    if isinstance(value, str):
        token = value.strip().lower()
    else:
        token = str(getattr(value, "value", value) or "").strip().lower()
    if token in {item.lower() for item in vocabulary["verified_dispositions"]}:
        return "verified"
    if token in {
        item.lower() for item in vocabulary["non_download_dispositions"]
    }:
        mapped = canonical_status(token)
        return mapped if mapped != UNKNOWN_STATE else "analysis_only"
    if token in {item.lower() for item in vocabulary["gate_outcomes"]}:
        mapped = canonical_status(token)
        return mapped if mapped != UNKNOWN_STATE else "analysis_only"
    if token in {item.lower() for item in vocabulary["target_policies"]}:
        return "analysis_only" if token == "analysis_only" else "candidate"
    return canonical_status(token)


def validate_state_machine() -> list[str]:
    """Structural self-check of the declared state machine (empty means valid)."""
    violations: list[str] = []
    if set(REPAIR_STATES) & set(FAILURE_STATES):
        violations.append("REPAIR_STATES and FAILURE_STATES overlap")
    if len(set(ALL_REPAIR_STATES)) != len(ALL_REPAIR_STATES):
        violations.append("ALL_REPAIR_STATES contains duplicates")
    if not set(TERMINAL_STATES) <= set(ALL_REPAIR_STATES):
        violations.append("TERMINAL_STATES contains undeclared states")
    for state in ALL_REPAIR_STATES:
        if state not in ALLOWED_TRANSITIONS:
            violations.append(f"missing ALLOWED_TRANSITIONS entry for {state!r}")
            continue
        for target in ALLOWED_TRANSITIONS[state]:
            if target not in ALL_REPAIR_STATES:
                violations.append(
                    f"transition {state!r} -> {target!r} targets an unknown state")
    for state in TERMINAL_STATES:
        outgoing = ALLOWED_TRANSITIONS.get(state, ())
        if outgoing:
            violations.append(
                f"terminal state {state!r} has outgoing transitions {list(outgoing)}")
    return violations


__all__ = [
    "ALLOWED_TRANSITIONS",
    "ALL_REPAIR_STATES",
    "CAPABILITY_STATES",
    "FAILURE_STATES",
    "REPAIR_STATES",
    "SCHEMA_VERSION",
    "START_STATE",
    "STATUS_ALIASES",
    "TERMINAL_STATES",
    "UNKNOWN_STATE",
    "acceptance_invariants_state",
    "allowed_transitions",
    "canonical_status",
    "capability_state_of",
    "is_failure_state",
    "is_terminal_state",
    "state_of",
    "validate_state_machine",
    "validate_transition",
]
