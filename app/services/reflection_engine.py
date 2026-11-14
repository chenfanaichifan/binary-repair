"""Reflection engine: a fail-closed 12-question contract for failure analysis.

Phase-7 foundation.  The engine turns observed failures into a *reviewable*
reflection record.  It never repairs anything, never promotes a capability and
never claims verification: ``verified`` is always ``False`` and the only allowed
``capability_decision`` values are ``analysis_only``, ``candidate`` and
``not_run``.

Hard rules enforced by :func:`validate_record` (and by construction):

1. exactly the 12 contract questions are present, in order, each with
   ``q`` / ``answer`` / ``evidence`` / ``status``; ``status`` is
   ``answered`` or ``unknown`` and an ``unknown`` answer carries its reason in
   the answer text (a question is never omitted);
2. ``verified`` is always ``False``;
3. ``capability_decision`` is one of ``analysis_only`` / ``candidate`` /
   ``not_run``;
4. without evidence (or with infrastructure/unknown evidence) a record can
   never be a ``candidate``; no evidence means ``not_run``;
5. an infrastructure failure is classified as ``infrastructure`` and is never
   turned into a capability gap (its decision is ``not_run``);
6. the experiment plan always has ``samples``, ``acceptance_criteria``,
   ``independent_verification`` and ``regression_checks``; it is ``planned``
   only for a capability hypothesis with evidence and concrete samples, and
   ``cannot_plan`` otherwise;
7. all output ordering is deterministic (observations, evidence, refs, questions,
   plan lists), so the ``reflection_id`` is stable for identical input.

The engine is offline and pure: no network, no LLM, no clock, no global state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

SCHEMA_VERSION = 1

CAPABILITY_DECISIONS = ("analysis_only", "candidate", "not_run")
FAILURE_TYPES = ("capability", "evaluation", "infrastructure", "knowledge", "unknown")
QUESTION_STATUSES = ("answered", "unknown")
PLAN_STATUSES = ("planned", "cannot_plan")

#: The 12-question contract, in canonical order.  The ids are part of the
#: machine-readable record; tests and reviewers assert the complete list.
QUESTION_CONTRACT: tuple[dict[str, str], ...] = (
    {"q": "Q01", "title": "What was expected?"},
    {"q": "Q02", "title": "What was observed?"},
    {"q": "Q03", "title": "What evidence supports the observation?"},
    {"q": "Q04", "title": "Is the evidence sufficient to classify the failure?"},
    {"q": "Q05", "title": "Is this an infrastructure/environment failure?"},
    {"q": "Q06", "title": "Is the observed miss explained by a capability gap?"},
    {"q": "Q07", "title": "Which capability, cell or strategy is implicated?"},
    {"q": "Q08", "title": "What is the root-cause hypothesis?"},
    {"q": "Q09", "title": "What is the smallest falsifiable experiment?"},
    {"q": "Q10", "title": "What acceptance criteria and independent verification apply?"},
    {"q": "Q11", "title": "What regression checks protect existing evidence?"},
    {"q": "Q12", "title": "What is the safe capability decision and review owner?"},
)
QUESTION_IDS: tuple[str, ...] = tuple(question["q"] for question in QUESTION_CONTRACT)

#: Ordered, deterministic classification markers.  Infrastructure is checked
#: first so an environment failure can never be relabelled as a capability gap.
INFRASTRUCTURE_MARKERS: tuple[str, ...] = (
    "timeout",
    "timed out",
    "subprocess",
    "no such file or directory",
    "connection refused",
    "connection reset",
    "network",
    "runner unavailable",
    "guest runner",
    "limactl",
    "qemu",
    "os error",
    "permission denied",
    "disk full",
    "infrastructure",
)
EVALUATION_MARKERS: tuple[str, ...] = (
    "evaluation",
    "acceptance model",
    "matcher",
    "mismatch",
    "expected vs observed",
    "disposition",
    "model identity",
    "oracle",
    "gate mismatch",
    "claim mismatch",
)
KNOWLEDGE_MARKERS: tuple[str, ...] = (
    "unknown",
    "not_run",
    "no corpus",
    "missing documentation",
    "knowledge",
    "undiscovered",
)
EVIDENCE_KINDS_FOR_CAPABILITY = frozenset({"cell", "gap", "contract", "artifact", "fixture"})

DEFAULT_REVIEW_OWNER = "autonomous-audit"
DEFAULT_REGRESSION_CHECKS = (
    "python scripts/verify_coverage_gate.py --static-only --json",
    "python scripts/meta_audit.py --json",
    "python -m pytest -q -p no:xdist tests/test_capability_audit.py tests/test_coverage_gate.py",
)
DEFAULT_INDEPENDENT_VERIFICATION = (
    "re-derive the result from a fresh artifact copy in a separate process",
    "have a second reviewer check the recorded evidence sha256 values",
    "confirm the capability decision with scripts/autonomous_repair_audit.py --mode static",
)


@dataclass(frozen=True)
class EvidenceRef:
    """One machine-readable evidence pointer (artifact, cell, contract, log...)."""

    kind: str
    ref: str
    sha256: str | None = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "ref": self.ref,
            "sha256": self.sha256,
            "note": self.note,
        }


@dataclass
class FailureObservation:
    """One observed failure/unknown outcome fed to the reflection engine."""

    source: str
    expected: str
    observed: str
    evidence: list[EvidenceRef] = field(default_factory=list)
    refs: list[str] = field(default_factory=list)
    observation_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "source": self.source,
            "expected": self.expected,
            "observed": self.observed,
            "evidence": [item.to_dict() for item in _sorted_evidence(self.evidence)],
            "refs": sorted(str(ref) for ref in self.refs),
            "metadata": _sorted_metadata(self.metadata),
        }


def _sorted_evidence(evidence: Iterable[EvidenceRef]) -> list[EvidenceRef]:
    return sorted(
        evidence,
        key=lambda item: (item.kind, item.ref, item.sha256 or "", item.note),
    )


def _sorted_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: metadata[key] for key in sorted(metadata)}


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_observation(observation: FailureObservation) -> FailureObservation:
    """Return a deterministic copy with sorted evidence/refs and a stable id."""
    evidence = _sorted_evidence(observation.evidence)
    refs = sorted(str(ref) for ref in observation.refs)
    metadata = _sorted_metadata(dict(observation.metadata))
    observation_id = _as_text(observation.observation_id)
    if not observation_id:
        seed = {
            "source": _as_text(observation.source),
            "expected": _as_text(observation.expected),
            "observed": _as_text(observation.observed),
            "evidence": [item.to_dict() for item in evidence],
            "refs": refs,
        }
        observation_id = "obs-" + hashlib.sha256(
            _canonical(seed).encode("ascii")
        ).hexdigest()[:16]
    return FailureObservation(
        source=_as_text(observation.source),
        expected=_as_text(observation.expected),
        observed=_as_text(observation.observed),
        evidence=evidence,
        refs=refs,
        observation_id=observation_id,
        metadata=metadata,
    )


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _failure_text(observation: FailureObservation) -> str:
    parts = [observation.source, observation.expected, observation.observed]
    for item in observation.evidence:
        parts.extend((item.kind, item.ref, item.note))
    parts.extend(str(value) for value in observation.metadata.values())
    return " ".join(parts).lower()


def classify_failure(observation: FailureObservation) -> str:
    """Classify one observation; returns ``unknown`` rather than guessing.

    Order is fixed and fail-closed: infrastructure first (an environment
    failure must never become a capability gap), then explicit hints that are
    *not* capability, then evaluation/knowledge markers, and only last a
    capability classification that requires both an explicit capability hint
    and concrete evidence with refs.  Everything else is ``unknown``.
    """
    text = _failure_text(observation)
    hint = _as_text(observation.metadata.get("failure_type")).lower()
    if hint and hint not in FAILURE_TYPES:
        hint = ""
    evidence_kinds = {item.kind for item in observation.evidence}
    if "infrastructure" in evidence_kinds or any(
        marker in text for marker in INFRASTRUCTURE_MARKERS
    ):
        return "infrastructure"
    if hint in {"evaluation", "knowledge"}:
        return hint
    if hint == "capability":
        has_capability_pointer = bool(
            _as_text(observation.metadata.get("capability_id"))
            or _as_text(observation.metadata.get("cell"))
            or any(item.kind == "gap" for item in observation.evidence)
        )
        if (
            observation.evidence
            and has_capability_pointer
            and evidence_kinds & EVIDENCE_KINDS_FOR_CAPABILITY
        ):
            return "capability"
        return "unknown"
    if any(marker in text for marker in EVALUATION_MARKERS):
        return "evaluation"
    if any(marker in text for marker in KNOWLEDGE_MARKERS):
        return "knowledge"
    return "unknown"


def _aggregate_failure_type(observations: Sequence[FailureObservation]) -> str:
    if not observations:
        return "unknown"
    types = {classify_failure(observation) for observation in observations}
    if len(types) == 1:
        return next(iter(types))
    if "infrastructure" in types:
        return "infrastructure"
    # A mixed reflection cannot safely be promoted: it stays unknown.
    return "unknown"


def _samples(observation: FailureObservation) -> list[str]:
    """Concrete sample identifiers available in the observation (never invented)."""
    samples: set[str] = set()
    declared = observation.metadata.get("samples")
    if isinstance(declared, (list, tuple)):
        samples.update(_as_text(item) for item in declared if _as_text(item))
    for ref in observation.refs:
        if any(
            marker in ref
            for marker in ("/", "::", "fixtures/", ".elf", ".json", "case")
        ):
            samples.add(ref)
    for item in observation.evidence:
        if item.kind in {"cell", "fixture", "case", "artifact"} and item.ref:
            samples.add(item.ref)
    return sorted(sample for sample in samples if sample)


def build_experiment_plan(
    observations: Sequence[FailureObservation],
    failure_type: str,
) -> dict[str, Any]:
    """Build the experiment plan; ``cannot_plan`` never hides its reason."""
    evidence_ok = bool(observations) and all(
        observation.evidence for observation in observations
    )
    samples: list[str] = []
    for observation in observations:
        samples.extend(_samples(observation))
    samples = sorted(set(samples))
    can_plan = (
        failure_type == "capability"
        and evidence_ok
        and bool(samples)
    )
    plan: dict[str, Any] = {
        "hypothesis": (
            "the implicated capability is missing or mis-modelled; a bounded, "
            "evidence-backed experiment can confirm or refute it"
            if can_plan
            else "cannot be planned from the available evidence; collect more "
                 "evidence before proposing an experiment"
        ),
        "samples": samples if can_plan else [],
        "acceptance_criteria": (
            [
                "every declared sample reproduces the expected disposition on the frozen tree",
                "the independent verifier re-derives the same result from a fresh artifact copy",
                "no previously verified disposition or evidence record regresses",
            ]
            if can_plan
            else []
        ),
        "independent_verification": list(DEFAULT_INDEPENDENT_VERIFICATION) if can_plan else [],
        "regression_checks": list(DEFAULT_REGRESSION_CHECKS) if can_plan else [],
        "status": "planned" if can_plan else "cannot_plan",
        "reason": "" if can_plan else _plan_blocker(failure_type, evidence_ok, samples),
    }
    return plan


def _plan_blocker(failure_type: str, evidence_ok: bool, samples: Sequence[str]) -> str:
    if failure_type == "infrastructure":
        return "infrastructure failure: fix the environment first; no repair experiment is justified"
    if failure_type == "evaluation":
        return "evaluation mismatch: correct the acceptance/evaluation model before proposing a capability experiment"
    if failure_type == "knowledge":
        return "knowledge gap: the missing knowledge must be gathered first; this is not a capability experiment"
    if failure_type == "unknown":
        return "failure type is unknown: evidence is insufficient to plan an experiment"
    if not evidence_ok:
        return "no machine-readable evidence: a candidate/experiment is forbidden until evidence exists"
    if not samples:
        return "no concrete sample identifiers: the experiment cannot be falsified"
    return "preconditions for a capability experiment are not met"


def decide_capability(
    failure_type: str,
    observations: Sequence[FailureObservation],
    plan: dict[str, Any],
) -> str:
    """Only three decisions exist; no evidence or infrastructure means not_run."""
    evidence_ok = bool(observations) and all(
        observation.evidence for observation in observations
    )
    if failure_type in {"infrastructure", "unknown"} or not evidence_ok:
        return "not_run"
    if (
        failure_type == "capability"
        and plan.get("status") == "planned"
        and plan.get("samples")
    ):
        return "candidate"
    return "analysis_only"


def _observation_evidence_dicts(observations: Sequence[FailureObservation]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    for observation in observations:
        collected.extend(item.to_dict() for item in observation.evidence)
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in collected:
        key = _canonical(item)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return sorted(unique, key=lambda item: (item["kind"], item["ref"], item["sha256"] or ""))


def _question(
    q: str,
    answer: str,
    evidence: list[dict[str, Any]],
    status: str,
) -> dict[str, Any]:
    if status not in QUESTION_STATUSES:
        raise ValueError(f"invalid question status: {status!r}")
    if status == "unknown" and not answer.startswith("unknown:"):
        raise ValueError(f"unknown question {q} must explain itself in the answer")
    if not answer:
        raise ValueError(f"question {q} has an empty answer")
    return {
        "q": q,
        "answer": answer,
        "evidence": evidence,
        "status": status,
    }



def _capability_question_answer(failure_type: str, evidence_ok: bool) -> str:
    """Q06 answer; an ``unknown`` status always starts with ``unknown:``."""
    if failure_type == "capability":
        if evidence_ok:
            return (
                "yes: a capability gap hypothesis is supported, but it must be "
                "falsified by the planned experiment before any candidate exists"
            )
        return (
            "unknown: a capability failure was hinted but no machine-readable "
            "evidence supports it"
        )
    if failure_type in {"evaluation", "knowledge", "infrastructure"}:
        if evidence_ok:
            return (
                "no: the failure is classified as "
                f"{failure_type!r}, not a capability gap"
            )
        return (
            "unknown: the failure type is "
            f"{failure_type!r} but there is no machine-readable evidence"
        )
    return "unknown: the available evidence does not distinguish a capability gap"


def build_questions(
    observations: Sequence[FailureObservation],
    failure_type: str,
    plan: dict[str, Any],
    decision: str,
) -> list[dict[str, Any]]:
    """Build exactly the 12 contract questions (never fewer, never more)."""
    evidence = _observation_evidence_dicts(observations)
    evidence_ok = bool(evidence)
    expected = "; ".join(
        sorted({observation.expected for observation in observations if observation.expected})
    )
    observed = "; ".join(
        sorted({observation.observed for observation in observations if observation.observed})
    )
    refs = sorted({ref for observation in observations for ref in observation.refs})
    capability_refs = [
        ref for ref in refs
        if "::" in ref or "/" in ref or ref.startswith(("cell:", "capability:", "gap:"))
    ]
    infra_evidence = [item for item in evidence if item["kind"] == "infrastructure"]
    capability_evidence = [item for item in evidence if item["kind"] in EVIDENCE_KINDS_FOR_CAPABILITY]
    questions = [
        _question(
            "Q01",
            expected if expected else "unknown: expected behavior was not recorded",
            evidence,
            "answered" if expected else "unknown",
        ),
        _question(
            "Q02",
            observed if observed else "unknown: observed behavior was not recorded",
            evidence,
            "answered" if observed else "unknown",
        ),
        _question(
            "Q03",
            (
                f"{len(evidence)} machine-readable evidence item(s): "
                + ", ".join(f"{item['kind']}:{item['ref']}" for item in evidence[:6])
            )
            if evidence
            else "unknown: no machine-readable evidence was supplied",
            evidence,
            "answered" if evidence else "unknown",
        ),
        _question(
            "Q04",
            (
                f"evidence present ({len(evidence)} item(s)); classification is "
                f"{failure_type!r} but the capability decision remains {decision!r}"
            )
            if evidence
            else "unknown: without evidence the failure cannot be classified",
            evidence,
            "answered" if evidence else "unknown",
        ),
        _question(
            "Q05",
            (
                "yes: the observation is consistent with an infrastructure/environment failure"
                if failure_type == "infrastructure"
                else "no: no infrastructure marker is present"
                if evidence_ok
                else "unknown: cannot rule out infrastructure without evidence"
            ),
            infra_evidence or evidence,
            "answered" if evidence_ok else "unknown",
        ),
        _question(
            "Q06",
            _capability_question_answer(failure_type, evidence_ok),
            capability_evidence or evidence,
            "answered"
            if failure_type in {"capability", "evaluation", "knowledge", "infrastructure"}
            and evidence_ok
            else "unknown",
        ),
        _question(
            "Q07",
            (
                "implicated capability/cell refs: " + ", ".join(capability_refs[:8])
                if capability_refs
                else "unknown: no capability/cell/strategy pointer is recorded"
            ),
            [item for item in evidence if item["ref"] in set(capability_refs)] or evidence,
            "answered" if capability_refs else "unknown",
        ),
        _question(
            "Q08",
            _root_cause_hypothesis(observations, failure_type, evidence_ok),
            evidence,
            "answered" if failure_type != "unknown" else "unknown",
        ),
        _question(
            "Q09",
            (
                "smallest falsifiable experiment: " + str(plan.get("hypothesis"))
                if plan.get("status") == "planned"
                else "unknown: no experiment can be planned yet ("
                     + str(plan.get("reason") or "preconditions not met") + ")"
            ),
            evidence if plan.get("status") == "planned" else [],
            "answered" if plan.get("status") == "planned" else "unknown",
        ),
        _question(
            "Q10",
            (
                "acceptance criteria: " + "; ".join(plan.get("acceptance_criteria") or [])
                if plan.get("status") == "planned"
                else "unknown: no acceptance criteria are justified without a planned experiment"
            ),
            evidence if plan.get("status") == "planned" else [],
            "answered" if plan.get("status") == "planned" else "unknown",
        ),
        _question(
            "Q11",
            (
                "regression checks: " + "; ".join(plan.get("regression_checks") or [])
                if plan.get("status") == "planned"
                else "unknown: no regression plan is justified without an experiment"
            ),
            evidence if plan.get("status") == "planned" else [],
            "answered" if plan.get("status") == "planned" else "unknown",
        ),
        _question(
            "Q12",
            f"capability_decision={decision!r}; review owner="
            f"{_owner(observations) or DEFAULT_REVIEW_OWNER!r}; verified is always false",
            evidence,
            "answered",
        ),
    ]
    return questions


def _root_cause_hypothesis(
    observations: Sequence[FailureObservation],
    failure_type: str,
    evidence_ok: bool,
) -> str:
    if failure_type == "infrastructure":
        return (
            "hypothesis: an environment/tooling failure (runner, guest, network, "
            "timeout or filesystem) interrupted the observation; no capability "
            "conclusion is justified until the infrastructure issue is fixed"
        )
    if failure_type == "evaluation":
        return (
            "hypothesis: the acceptance/evaluation model or the recorded "
            "expectation is wrong or incomplete; the capability is not implicated "
            "until the evaluation mismatch is resolved"
        )
    if failure_type == "knowledge":
        return (
            "hypothesis: a knowledge/documentation gap prevents a capability "
            "judgement; gather the missing knowledge before planning repairs"
        )
    if failure_type == "capability" and evidence_ok:
        return (
            "hypothesis: the declared capability record does not cover the "
            "observed case; a bounded experiment can falsify this before any "
            "candidate is proposed"
        )
    return "unknown: evidence is insufficient to state a root-cause hypothesis"


def _owner(observations: Sequence[FailureObservation]) -> str:
    for observation in observations:
        owner = _as_text(observation.metadata.get("review_owner"))
        if owner:
            return owner
    return ""


def reflect(
    observations: FailureObservation | Sequence[FailureObservation],
    *,
    review_owner: str = DEFAULT_REVIEW_OWNER,
) -> dict[str, Any]:
    """Build one deterministic :class:`ReflectionRecord`-shaped dict."""
    if isinstance(observations, FailureObservation):
        sequence = [observations]
    else:
        sequence = list(observations)
    normalized = sorted(
        (_normalize_observation(item) for item in sequence),
        key=lambda item: (item.source, item.observation_id),
    )
    failure_type = _aggregate_failure_type(normalized)
    plan = build_experiment_plan(normalized, failure_type)
    decision = decide_capability(failure_type, normalized, plan)
    questions = build_questions(normalized, failure_type, plan, decision)
    observations_payload = [item.to_dict() for item in normalized]
    diagnosis = (
        f"{failure_type} classification over {len(normalized)} observation(s); "
        f"capability decision {decision}; verified is always false"
    )
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "reflection_id": "",
        "observations": observations_payload,
        "diagnosis": diagnosis,
        "failure_type": failure_type,
        "root_cause_hypothesis": _root_cause_hypothesis(
            normalized, failure_type, all(item.evidence for item in normalized)
        ),
        "12_questions": questions,
        "experiment_plan": plan,
        "capability_decision": decision,
        "verified": False,
        "review_owner": _assigned_owner(normalized, review_owner),
    }
    seed = {key: value for key, value in record.items() if key != "reflection_id"}
    record["reflection_id"] = "ref-" + hashlib.sha256(
        _canonical(seed).encode("ascii")
    ).hexdigest()[:24]
    violations = validate_record(record)
    if violations:
        raise ValueError("reflection record violates the contract: " + "; ".join(violations))
    return record


def _assigned_owner(
    observations: Sequence[FailureObservation],
    fallback: str,
) -> str:
    return _owner(observations) or _as_text(fallback) or DEFAULT_REVIEW_OWNER


def validate_record(record: dict[str, Any]) -> list[str]:
    """Return every contract violation in one record (empty list means valid)."""
    violations: list[str] = []
    if not isinstance(record, dict):
        return ["record is not a JSON object"]
    if record.get("schema_version") != SCHEMA_VERSION:
        violations.append("schema_version must be 1")
    if not _as_text(record.get("reflection_id")):
        violations.append("reflection_id must be a non-empty string")
    if record.get("failure_type") not in FAILURE_TYPES:
        violations.append(f"failure_type must be one of {FAILURE_TYPES}")
    if record.get("capability_decision") not in CAPABILITY_DECISIONS:
        violations.append(f"capability_decision must be one of {CAPABILITY_DECISIONS}")
    if record.get("verified") is not False:
        violations.append("verified must be exactly False")
    observations = record.get("observations")
    if not isinstance(observations, list) or not observations:
        violations.append("observations must be a non-empty list")
        observations = []
    for index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            violations.append(f"observations[{index}] is not an object")
            continue
        if not isinstance(observation.get("evidence"), list):
            violations.append(f"observations[{index}].evidence must be a list")
    questions = record.get("12_questions")
    if not isinstance(questions, list):
        violations.append("12_questions must be a list")
        questions = []
    ids = [item.get("q") if isinstance(item, dict) else None for item in questions]
    if ids != list(QUESTION_IDS):
        violations.append(
            f"12_questions must be exactly {list(QUESTION_IDS)} in order; got {ids}"
        )
    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            violations.append(f"12_questions[{index}] is not an object")
            continue
        if set(question) != {"q", "answer", "evidence", "status"}:
            violations.append(
                f"12_questions[{index}] must contain q/answer/evidence/status"
            )
        if not _as_text(question.get("answer")):
            violations.append(f"12_questions[{index}] has an empty answer")
        if not isinstance(question.get("evidence"), list):
            violations.append(f"12_questions[{index}].evidence must be a list")
        if question.get("status") not in QUESTION_STATUSES:
            violations.append(f"12_questions[{index}] has invalid status")
    plan = record.get("experiment_plan")
    if not isinstance(plan, dict):
        violations.append("experiment_plan must be an object")
        plan = {}
    for key in ("hypothesis", "samples", "acceptance_criteria",
                "independent_verification", "regression_checks", "status"):
        if key not in plan:
            violations.append(f"experiment_plan is missing {key!r}")
    if plan.get("status") not in PLAN_STATUSES:
        violations.append("experiment_plan.status must be planned|cannot_plan")
    if plan.get("status") == "planned":
        for key in ("samples", "acceptance_criteria", "independent_verification",
                    "regression_checks"):
            if not plan.get(key):
                violations.append(
                    f"planned experiment_plan requires non-empty {key!r}"
                )
        if not _as_text(plan.get("hypothesis")):
            violations.append("planned experiment_plan requires a hypothesis")
    decision = record.get("capability_decision")
    failure_type = record.get("failure_type")
    evidence_present = any(
        isinstance(observation, dict) and observation.get("evidence")
        for observation in observations
    )
    if decision == "candidate":
        if failure_type != "capability":
            violations.append("candidate requires failure_type == 'capability'")
        if not evidence_present:
            violations.append("candidate requires machine-readable evidence")
        if plan.get("status") != "planned":
            violations.append("candidate requires a planned experiment")
    if failure_type == "infrastructure" and decision == "candidate":
        violations.append("infrastructure failure must never become a capability candidate")
    if not evidence_present and decision != "not_run":
        violations.append("without evidence capability_decision must be 'not_run'")
    if _as_text(record.get("root_cause_hypothesis")) == "":
        violations.append("root_cause_hypothesis must be a non-empty string")
    if _as_text(record.get("review_owner")) == "":
        violations.append("review_owner must be a non-empty string")
    return violations
