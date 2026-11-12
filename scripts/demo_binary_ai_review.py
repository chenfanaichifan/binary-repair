#!/usr/bin/env python3
"""Reproducible direct-ELF AI review experiment.

For each checked-in case this runs:

* the deterministic baseline (no review);
* the same case with the configured reviewer (or a labelled scripted reviewer);
* a scripted ``accept`` control that proves a failed gate cannot be promoted;
* for the passing case, a scripted ``hold`` control that proves a review can veto.

The artifact records whether a real provider was called, which model was used,
token usage, what the reviewer added, and whether the final decision changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import binary_repair_engine as engine  # noqa: E402
from app.services.assistant_llm import client_from_env  # noqa: E402
from app.services.binary_review import run_direct_repair  # noqa: E402

VULN = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"
PE = ROOT / "fixtures" / "pe" / "cli-64.exe"
CASES = (
    {"case_id": "strict_ok", "path": VULN, "evidence_gap": False},
    {"case_id": "unsupported", "path": PE, "evidence_gap": False},
    {"case_id": "missing_evidence", "path": VULN, "evidence_gap": True},
)


class ScriptedReviewer:
    """Local contract control.  It is never presented as an AI call."""

    review_mode = "scripted"
    model = "scripted-reviewer"
    review_provider = "scripted"

    def __init__(self, recommendation: str):
        self.recommendation = recommendation

    def chat_json(self, messages: list[dict[str, str]], **kwargs: Any) -> Any:
        payload = {
            "recommendation": self.recommendation,
            "summary": "Scripted contract control, not an AI call.",
            "concerns": [],
            "missing_evidence": [],
            "further_checks": [],
        }
        return SimpleNamespace(
            content=json.dumps(payload),
            model=self.model,
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            request_id=None,
        )


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def _result(outcome: Any) -> dict[str, Any]:
    return {
        "gate": outcome.verification.packet["gate"],
        "decision": outcome.decision,
        "review": outcome.review.as_dict(),
        "candidate_available": outcome.patched is not None,
        "download_allowed": bool(outcome.decision.get("success")),
        "patched_sha256": outcome.report.patched_sha256,
    }


def _run_case(
    case: dict[str, Any],
    *,
    reviewer: Any,
) -> dict[str, Any]:
    path: Path = case["path"]
    raw = path.read_bytes()
    original = engine._runtime_summary

    def _run(**kwargs: Any) -> Any:
        return run_direct_repair(raw, **kwargs)

    if case["evidence_gap"]:
        engine._runtime_summary = lambda patched, capacity: {
            "available": False,
            "error": "evidence unavailable (simulated for this experiment)",
        }
    try:
        baseline = _run()
        with_review = _run(request_review=True, client=reviewer)
        accept_control = _run(
            request_review=True,
            client=ScriptedReviewer("accept"),
        )
        hold_control = (
            _run(request_review=True, client=ScriptedReviewer("hold"))
            if case["case_id"] == "strict_ok"
            else None
        )
    finally:
        engine._runtime_summary = original

    same_packet = (
        baseline.verification.packet["report_sha256"]
        == with_review.verification.packet["report_sha256"]
    )
    review = with_review.review
    comparison = {
        "gate_outcome": baseline.verification.gate.outcome,
        "gate_outcome_same": same_packet,
        "baseline_success": bool(baseline.decision.get("success")),
        "with_review_success": bool(with_review.decision.get("success")),
        "decision_changed": baseline.decision.get("outcome") != with_review.decision.get("outcome")
        or baseline.decision.get("success") != with_review.decision.get("success"),
        "ai_called": bool(review.called),
        "ai_mode": review.mode,
        "ai_status": review.status,
        "ai_provider": review.provider,
        "ai_model": review.model,
        "recommendation": review.recommendation,
        "ai_effect": review.contribution.get("effect"),
        "new_concerns": review.contribution.get("new_concerns", 0),
        "new_missing_evidence": review.contribution.get("new_missing_evidence", 0),
        "new_further_checks": review.contribution.get("new_further_checks", 0),
        "accept_control_success": bool(accept_control.decision.get("success")),
        "accept_control_reason": accept_control.decision.get("reason"),
        "hold_control_success": (
            bool(hold_control.decision.get("success")) if hold_control is not None else None
        ),
        "hold_control_reason": (
            hold_control.decision.get("reason") if hold_control is not None else None
        ),
    }
    return {
        "case_id": case["case_id"],
        "evidence_gap": bool(case["evidence_gap"]),
        "input": {
            "path": _rel(path),
            "sha256": _sha_bytes(raw),
            "size": len(raw),
        },
        "engine_report": baseline.report.to_dict(),
        "verification": baseline.verification.packet,
        "baseline": _result(baseline),
        "with_review": _result(with_review),
        "accept_control": _result(accept_control),
        "hold_control": _result(hold_control) if hold_control is not None else None,
        "comparison": comparison,
    }


def _table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| case | gate | no AI | with review | AI called | recommendation | changed | new concerns |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        comp = row["comparison"]
        lines.append(
            "| {case} | {gate} | {base} | {with_review} | {called} | {rec} | {changed} | {new} |".format(
                case=row["case_id"],
                gate=comp["gate_outcome"],
                base=row["baseline"]["decision"].get("outcome"),
                with_review=row["with_review"]["decision"].get("outcome"),
                called="yes" if comp["ai_called"] else "no",
                rec=comp["recommendation"] or "—",
                changed="yes" if comp["decision_changed"] else "no",
                new=comp["new_concerns"],
            )
        )
    return "\n".join(lines)


def _write_readme(
    out: Path,
    *,
    payload: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    provider = payload["provider"]
    note = (
        "**AI was called in this run.**"
        if provider["called"]
        else "**AI was not called in this run.** The scripted reviewer is a "
        "contract control, not evidence of model value. Set a provider key and "
        "rerun with `--provider real` to produce an AI comparison."
    )
    text = f"""# Direct ELF AI review experiment — {payload['date']}

{note}

- commit: `{payload.get('commit') or 'unknown'}`
- provider requested: `{provider['requested']}`
- reviewer mode: `{provider['mode']}`
- reviewer model: `{provider.get('model') or '—'}`
- command: `python scripts/demo_binary_ai_review.py --provider {provider['requested']}`

## Result

{_table(rows)}

The deterministic gate is the only source of success. The scripted `accept`
control returns `accept` for every case; the unsupported and missing-evidence
cases stay non-successful with reason `review_accept_cannot_promote_gate`. The
strict case also has a scripted `hold` control to show that a review can veto a
passing gate.

## Files

- `run.json` — complete packet, baseline/with-review/control decisions and reviews.
- `comparison.md` — compact comparison table.
- `SHA256SUMS` — integrity of the three files above.

## Limitations

- One checked-in fixture family; this is not broad ELF coverage.
- Runtime evidence is Unicorn emulation, not a host-kernel run.
- The missing-evidence case deliberately removes runtime evidence to exercise the gate.
- A real model is non-deterministic; a single run is not a general claim about AI value.
"""
    (out / "README.md").write_text(text, encoding="utf-8")


def _write_comparison(out: Path, rows: list[dict[str, Any]]) -> None:
    lines = ["# Baseline vs review", "", _table(rows), ""]
    for row in rows:
        comp = row["comparison"]
        lines.extend(
            [
                f"## {row['case_id']}",
                "",
                f"- gate: `{comp['gate_outcome']}` (same packet: {comp['gate_outcome_same']})",
                f"- baseline: `{row['baseline']['decision'].get('outcome')}`",
                f"- with review: `{row['with_review']['decision'].get('outcome')}`",
                f"- AI called: {comp['ai_called']} ({comp['ai_mode']}, {comp['ai_status']})",
                f"- recommendation: `{comp['recommendation']}`",
                f"- effect: `{comp['ai_effect']}`",
                f"- new concerns / missing evidence / further checks: "
                f"{comp['new_concerns']} / {comp['new_missing_evidence']} / {comp['new_further_checks']}",
                f"- scripted accept control: success={comp['accept_control_success']} "
                f"reason=`{comp['accept_control_reason']}`",
                f"- scripted hold control: success={comp['hold_control_success']} "
                f"reason=`{comp['hold_control_reason']}`",
                "",
            ]
        )
    (out / "comparison.md").write_text("\n".join(lines), encoding="utf-8")


def _write_checksums(out: Path) -> None:
    names = ("README.md", "comparison.md", "run.json")
    lines = [f"{_sha_file(out / name)}  {name}" for name in names]
    (out / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("auto", "real", "scripted"), default="auto")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "artifacts" / f"binary-ai-review-{datetime.now(timezone.utc).date().isoformat()}",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    out = args.out
    if out.exists() and any(out.iterdir()) and not args.force:
        print(f"refusing to overwrite non-empty {out}; pass --force", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)

    real_client = client_from_env() if args.provider in {"auto", "real"} else None
    if args.provider == "real" and real_client is None:
        print("no provider client is configured; set BINARYREPAIR_ASSISTANT_PROVIDER_KEY", file=sys.stderr)
        return 2
    if real_client is not None:
        reviewer: Any = real_client
        reviewer_mode = "llm"
        reviewer_model = getattr(real_client, "model", None)
    else:
        reviewer = ScriptedReviewer("accept")
        reviewer_mode = "scripted"
        reviewer_model = reviewer.model

    rows: list[dict[str, Any]] = []
    for case in CASES:
        rows.append(_run_case(case, reviewer=reviewer))

    provider = {
        "requested": args.provider,
        "mode": reviewer_mode,
        "model": reviewer_model,
        "called": any(row["comparison"]["ai_called"] for row in rows),
        "base_url": getattr(real_client, "base_url", None) if real_client is not None else None,
    }
    payload = {
        "schema_version": 1,
        "date": datetime.now(timezone.utc).date().isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": _commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "provider": provider,
        "cases": rows,
    }
    (out / "run.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_comparison(out, rows)
    _write_readme(out, payload=payload, rows=rows)
    _write_checksums(out)

    print(f"wrote {out}")
    print(_table(rows))
    if not provider["called"]:
        print("AI was NOT called; this artifact is a scripted contract control only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
