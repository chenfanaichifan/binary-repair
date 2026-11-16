#!/usr/bin/env python3
"""Export customer-readable reports plus a hashed evidence index.

Reads a product demo run (demo-run.json produced by
scripts/product/demo_repair.py) and writes, into the same directory:

* REPORT.md / report.html          - English report (ASCII, CI-safe default)
* REPORT.zh.md / report.zh.html    - Chinese report (customer locale)
* EVIDENCE-INDEX.json              - hashed index of every evidence file
* SHA256SUMS                       - covers every file except itself

Usage::

    python scripts/product/export_report.py <outdir> [--title TITLE] [--lang en|zh] [--json]

Fail-closed rule: a fixture is presented as verified only when the independent
verifier decision is "verified" AND the disposition is "verified_patch" AND a
candidate digest exists. Any mismatch becomes a fail-closed issue: the report is
still written for audit, the verdict is downgraded, and the CLI exits 2.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUN_FILE = "demo-run.json"
INDEX_FILE = "EVIDENCE-INDEX.json"
SUMS_FILE = "SHA256SUMS"
FILENAMES = {
    "en": ("REPORT.md", "report.html"),
    "zh": ("REPORT.zh.md", "report.zh.html"),
}
VALID_STATUSES = {
    "VERIFIED_WITHIN_SCOPE", "NOT_VERIFIED", "REFUSED", "REJECTED", "ERROR",
}
STATUS_LABELS = {
    "en": {
        "VERIFIED_WITHIN_SCOPE": "verified within scope",
        "NOT_VERIFIED": "not verified",
        "REFUSED": "refused (outside the capability matrix / unrecognised; no bytes produced)",
        "REJECTED": "candidate rejected by the gate",
        "ERROR": "error",
    },
    "zh": {
        "VERIFIED_WITHIN_SCOPE": "在声明范围内已验证",
        "NOT_VERIFIED": "未验证",
        "REFUSED": "拒绝（超出能力矩阵或无法识别，未产出字节）",
        "REJECTED": "候选被 gate 拒绝",
        "ERROR": "运行错误",
    },
}
VERDICT_NOTES = {
    "en": {
        "VERIFIED_WITHIN_SCOPE": (
            "verified scope = one target function/sink + the supplied PoC/regression "
            "cases + the independent verifier checks. It is not a whole-program proof "
            "and does not mean the repaired binary is safe for production use."
        ),
        "NOT_VERIFIED": (
            "no independent verifier 'verified' decision was obtained, so no candidate "
            "bytes are offered for download and no repair success is claimed."
        ),
        "REFUSED": (
            "the input is outside the deterministic repair matrix or unrecognised; the "
            "product fails closed and produces no bytes."
        ),
        "REJECTED": "the candidate was rejected by the deterministic gate and dropped.",
        "ERROR": "the run failed; no repair verdict was produced.",
    },
    "zh": {
        "VERIFIED_WITHIN_SCOPE": (
            "已验证范围 = 一个 target 函数/sink + 给定 PoC/回归用例 + 独立验证器检查；"
            "不是 whole-program 证明，也不代表修复后的二进制可以安全上生产。"
        ),
        "NOT_VERIFIED": (
            "没有获得独立验证器的 verified 结论，因此不产出可下载候选字节、不宣称修复成功。"
        ),
        "REFUSED": "输入超出确定性修复矩阵或无法识别；产品按要求失败关闭，未产出任何字节。",
        "REJECTED": "候选被确定性 gate 拒绝并丢弃；不会以成功或可下载形式出现。",
        "ERROR": "运行过程报错，未形成修复结论。",
    },
}
TEXT = {
    "en": {
        "default_title": "BinaryRepair customer report",
        "generated_at": "Generated at (UTC)",
        "run_time": "Run at",
        "host": "Host",
        "execution": "Execution path",
        "ai": "AI used",
        "network": "Network",
        "api_key": "API key",
        "no": "no",
        "not_required": "not required",
        "verifier": "Independent verifier",
        "boundary": "0. Product boundary (read before any delivery)",
        "item": "Item",
        "statement": "Statement",
        "positioning": "Positioning",
        "public_benchmark": "Public benchmark",
        "hidden_benchmark": "Hidden benchmark",
        "detection": "Detection/localization/root-cause",
        "scope": "Repair scope",
        "verification_scope": "Verification scope",
        "not_claimed": "Not claimed (canonical wording):",
        "summary": "1. Execution summary",
        "summary_cols": ["fixture", "expected", "verdict", "disposition",
                         "independent verification", "oracle", "runtime tier"],
        "details": "2. Per-fixture results",
        "verdict_label": "Verdict",
        "note_label": "Note",
        "reason_label": "Reason",
        "input_label": "Input",
        "scan_label": "Scan",
        "repair_label": "Repair",
        "repair_cols": ["field", "value"],
        "verification_label": "Verification",
        "checks_label": "Verification checks",
        "checks_cols": ["check", "required", "status", "detail"],
        "limitations_label": "Limitations",
        "not_run_label": "Not run / fail-closed",
        "none": "(none)",
        "evidence_dir": "Evidence directory",
        "evidence_dir_note": "original/candidate/patch-plan/verifier-report/scan; SHA256 in section 4",
        "fail_closed": "3. Fail-closed self-check",
        "fail_closed_ok": "Result: passed (no violations)",
        "fail_closed_bad": "Result: FAILED (violations below)",
        "violation": "Violation",
        "evidence_index": "4. Evidence index (SHA256)",
        "evidence_cols": ["file", "bytes", "SHA256"],
        "sums_note": "Full checksum list: {sums}; verify with: shasum -a 256 -c {sums}",
        "not_claimed_heading": "5. Not-claimed list (customer communication wording)",
        "not_claimed_bullets": [
            "public benchmark is only 2/24 verified (8.3%) and hidden is 0/8; do not claim generalisation;",
            "no arbitrary-binary / arbitrary-vulnerability / whole-program repair claim;",
            "no claim that a repaired binary is safe for production use; verification covers only the supplied PoC/regression and one target function;",
            "not_run items are listed explicitly and must not be treated as passed;",
            "AI is only a candidate generator and never owns acceptance; this report used the deterministic path and called no AI.",
        ],
        "repro_note": "Reproduce: tools/product/run-demo.sh <fixture> <outdir>; regenerate reports: python scripts/product/export_report.py <outdir>.",
    },
    "zh": {
        "default_title": "BinaryRepair 修复交付报告",
        "generated_at": "报告生成时间（UTC）",
        "run_time": "运行时间",
        "host": "宿主",
        "execution": "执行路径",
        "ai": "AI 使用",
        "network": "网络",
        "api_key": "API key",
        "no": "否",
        "not_required": "不需要",
        "verifier": "独立验证器",
        "boundary": "0. 产品边界（每次交付必读）",
        "item": "项",
        "statement": "口径",
        "positioning": "定位",
        "public_benchmark": "公开 benchmark",
        "hidden_benchmark": "hidden benchmark",
        "detection": "检测/定位/根因",
        "scope": "修复范围",
        "verification_scope": "验证范围",
        "not_claimed": "不可承诺（原文口径）：",
        "summary": "1. 执行摘要",
        "summary_cols": ["fixture", "期望", "结论", "disposition",
                         "独立验证", "oracle", "运行层级"],
        "details": "2. 逐项结果",
        "verdict_label": "判读",
        "note_label": "说明",
        "reason_label": "原因",
        "input_label": "输入",
        "scan_label": "扫描",
        "repair_label": "修复",
        "repair_cols": ["字段", "值"],
        "verification_label": "验证",
        "checks_label": "验证检查表",
        "checks_cols": ["check", "必选", "状态", "说明"],
        "limitations_label": "限制（limitations）",
        "not_run_label": "未运行 / 失败关闭（not_run）",
        "none": "（无）",
        "evidence_dir": "证据目录",
        "evidence_dir_note": "original/candidate/patch-plan/verifier-report/scan；SHA256 见第 4 节",
        "fail_closed": "3. 失败关闭（fail-closed）自检",
        "fail_closed_ok": "结论：通过（无违规）",
        "fail_closed_bad": "结论：未通过（见下列违规）",
        "violation": "违规",
        "evidence_index": "4. 证据索引（SHA256）",
        "evidence_cols": ["文件", "字节", "SHA256"],
        "sums_note": "完整校验清单见 {sums}；校验命令：shasum -a 256 -c {sums}",
        "not_claimed_heading": "5. 不可承诺清单（客户沟通口径）",
        "not_claimed_bullets": [
            "公开 benchmark 仅 2/24 verified（8.3%）、hidden 0/8，不得据此宣称泛化能力；",
            "不承诺任意二进制 / 任意漏洞 / whole-program 修复；",
            "不承诺修复后的二进制可以安全上生产；验证只覆盖给定 PoC/回归与一个 target 函数；",
            "未运行项以 not_run 显式列出，不得当作已通过；",
            "AI 只作为候选生成器，永远不拥有验收权；本报告使用确定性路径，未调用 AI。",
        ],
        "repro_note": "复现命令：tools/product/run-demo.sh <fixture> <outdir>；报告重新生成：python scripts/product/export_report.py <outdir>。",
    },
}


class ExportError(RuntimeError):
    """The demo run is missing or malformed, or the language is unsupported."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _check_lang(lang: str) -> str:
    if lang not in FILENAMES:
        raise ExportError(f"unsupported report language: {lang!r} (en|zh)")
    return lang


def load_run(outdir: Path) -> dict[str, Any]:
    path = Path(outdir) / RUN_FILE
    if not path.is_file():
        raise ExportError(f"missing {RUN_FILE} in {outdir}; run demo_repair.py first")
    try:
        run = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExportError(f"unreadable {RUN_FILE}: {exc}") from exc
    if not isinstance(run, dict) or run.get("kind") != "product_demo_run":
        raise ExportError(f"{RUN_FILE} is not a product demo run")
    if not isinstance(run.get("fixtures"), list) or not run["fixtures"]:
        raise ExportError(f"{RUN_FILE} has no fixtures")
    return run


def normalized_status(fixture: dict[str, Any]) -> str:
    """Derive the presented verdict; a verified claim needs full evidence."""
    raw = str(fixture.get("status") or "")
    repair = fixture.get("repair") or {}
    verification = fixture.get("verification") or {}
    disposition = str(repair.get("disposition") or "")
    decision = verification.get("independent_decision")
    if raw == "ERROR":
        return "ERROR"
    if (
        decision == "verified"
        and disposition == "verified_patch"
        and repair.get("candidate_sha256")
    ):
        return "VERIFIED_WITHIN_SCOPE"
    if raw in {"REFUSED", "REJECTED"}:
        return raw
    return "NOT_VERIFIED"


def fail_closed_issues(run: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    execution = run.get("execution") or {}
    if execution.get("ai_used") is not False:
        issues.append("execution.ai_used is not explicitly false")
    if execution.get("network_used") is not False:
        issues.append("execution.network_used is not explicitly false")
    if execution.get("deterministic_only") is not True:
        issues.append("execution.deterministic_only is not explicitly true")
    for fixture in run.get("fixtures") or []:
        name = fixture.get("fixture")
        raw = str(fixture.get("status") or "")
        repair = fixture.get("repair") or {}
        verification = fixture.get("verification") or {}
        disposition = str(repair.get("disposition") or "")
        decision = verification.get("independent_decision")
        candidate = repair.get("candidate_sha256")
        if raw not in VALID_STATUSES:
            issues.append(f"{name}: unknown status {raw!r}")
        if raw == "VERIFIED_WITHIN_SCOPE":
            if decision != "verified":
                issues.append(
                    f"{name}: claims verified but independent decision is {decision!r}"
                )
            if disposition != "verified_patch":
                issues.append(
                    f"{name}: claims verified but disposition is {disposition!r}"
                )
            if not candidate:
                issues.append(f"{name}: claims verified but has no candidate sha256")
        if decision == "verified" and raw != "VERIFIED_WITHIN_SCOPE":
            issues.append(f"{name}: independent verifier verified but status is {raw!r}")
        if raw in {"REFUSED", "REJECTED"} and repair.get("candidate_produced"):
            issues.append(f"{name}: {raw} but a candidate was produced")
        if repair.get("false_verified") or repair.get("deterministic_claim_withdrawn"):
            issues.append(
                f"{name}: generator claim rejected/withdrawn by the independent verifier"
            )
        if raw != "VERIFIED_WITHIN_SCOPE" and not fixture.get("not_run"):
            issues.append(f"{name}: non-verified result has no explicit not_run reason")
        if not fixture.get("checks"):
            issues.append(f"{name}: no verification check rows were recorded")
    return issues


def evidence_index(outdir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(Path(outdir).rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(outdir).as_posix()
        if relative in {SUMS_FILE, INDEX_FILE}:
            continue
        data = path.read_bytes()
        rows.append({"path": relative, "sha256": _sha256(data), "bytes": len(data)})
    return rows


def build_report(outdir: Path, run: dict[str, Any], title: str) -> dict[str, Any]:
    fixtures = []
    for fixture in run.get("fixtures") or []:
        entry = json.loads(json.dumps(fixture))
        entry["presented_status"] = normalized_status(fixture)
        fixtures.append(entry)
    issues = fail_closed_issues(run)
    return {
        "schema_version": 1,
        "kind": "product_customer_report",
        "title": title,
        "generated_at": _utc_now(),
        "outdir": str(outdir),
        "run_meta": {
            "generated_at": run.get("generated_at"),
            "elapsed_seconds": run.get("elapsed_seconds"),
            "host": run.get("host"),
            "execution": run.get("execution"),
        },
        "boundary": run.get("boundary") or {},
        "fixtures": fixtures,
        "fail_closed": {"ok": not issues, "issues": issues},
    }


def _md_checks(fixture: dict[str, Any], lang: str) -> list[str]:
    cols = TEXT[lang]["checks_cols"]
    lines = [
        "| " + " | ".join(cols) + " |",
        "|" + "|".join(["---"] * len(cols)) + "|",
    ]
    for check in fixture.get("checks") or []:
        detail = str(check.get("detail") or "").replace("\n", " ").replace("|", "/")
        if len(detail) > 220:
            detail = detail[:217] + "..."
        lines.append(
            f"| {check.get('id')} | {check.get('required')} | "
            f"{check.get('status')} | {detail} |"
        )
    return lines


def _md_bullets(title: str, rows: list[str], lang: str) -> list[str]:
    lines = [f"**{title}**", ""]
    if not rows:
        lines.append(f"- {TEXT[lang]['none']}")
    else:
        lines.extend(f"- {str(row).replace('|', '/')}" for row in rows)
    lines.append("")
    return lines


def _md_table(cols: list[str], rows: list[list[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(cols) + " |",
        "|" + "|".join(["---"] * len(cols)) + "|",
    ]
    for row in rows:
        cells = [str(cell if cell is not None else "").replace("|", "/") for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def render_markdown(report: dict[str, Any], index: list[dict[str, Any]], lang: str) -> str:
    T = TEXT[lang]
    labels = STATUS_LABELS[lang]
    notes = VERDICT_NOTES[lang]
    boundary = report.get("boundary") or {}
    run_meta = report.get("run_meta") or {}
    host = run_meta.get("host") or {}
    execution = run_meta.get("execution") or {}
    verifier = execution.get("independent_verifier") or {}
    lines: list[str] = [
        f"# {report['title']}",
        "",
        f"- {T['generated_at']}: {report['generated_at']}",
        f"- {T['run_time']}: {run_meta.get('generated_at')}; "
        f"{run_meta.get('elapsed_seconds')} s",
        f"- {T['host']}: {host.get('platform')}/{host.get('machine')}, "
        f"Python {host.get('python')}",
        f"- {T['execution']}: {execution.get('engine')} | {T['ai']}: {T['no']} | "
        f"{T['network']}: {T['no']} | {T['api_key']}: {T['not_required']}",
        f"- {T['verifier']}: {verifier.get('path')} ({verifier.get('status')})",
        "",
        f"## {T['boundary']}",
        "",
    ]
    lines += _md_table(
        [T["item"], T["statement"]],
        [
            [T["positioning"], boundary.get("positioning")],
            [T["public_benchmark"], boundary.get("public_benchmark")],
            [T["hidden_benchmark"], boundary.get("hidden_benchmark")],
            [T["detection"], boundary.get("detection_localization")],
            [T["scope"], boundary.get("repair_scope")],
            [T["verification_scope"], boundary.get("verification")],
        ],
    )
    lines += ["", f"**{T['not_claimed']}**", ""]
    for item in boundary.get("not_claimed") or []:
        lines.append(f"- {item}")
    lines += ["", f"## {T['summary']}", ""]
    summary_rows = []
    for fixture in report["fixtures"]:
        repair = fixture.get("repair") or {}
        verification = fixture.get("verification") or {}
        summary_rows.append([
            fixture.get("fixture"),
            fixture.get("expected"),
            fixture["presented_status"],
            repair.get("disposition"),
            verification.get("independent_decision"),
            verification.get("oracle_status"),
            repair.get("runtime_tier"),
        ])
    lines += _md_table(T["summary_cols"], summary_rows)
    lines += ["", f"## {T['details']}", ""]
    for position, fixture in enumerate(report["fixtures"], 1):
        repair = fixture.get("repair") or {}
        verification = fixture.get("verification") or {}
        scan = fixture.get("scan") or {}
        input_info = fixture.get("input") or {}
        status = fixture["presented_status"]
        lines += [
            f"### 2.{position} {fixture.get('fixture')} - {status}",
            "",
            f"- {T['verdict_label']}: {labels.get(status, status)}",
            f"- {T['note_label']}: {notes.get(status, '')}",
            f"- {T['reason_label']}: {fixture.get('reason') or T['none']}",
            "",
            f"**{T['input_label']}**: {input_info.get('path')} | "
            f"SHA256 {input_info.get('sha256')}",
            "",
            f"**{T['scan_label']}**: format={scan.get('format')} "
            f"arch={scan.get('arch')} matrix_cell={scan.get('matrix_cell')} "
            f"findings={scan.get('findings_count')} "
            f"repair_supported={scan.get('repair_supported')}",
            "",
            f"**{T['repair_label']}**:",
            "",
        ]
        lines += _md_table(
            T["repair_cols"],
            [
                ["disposition", repair.get("disposition")],
                ["candidate_sha256", repair.get("candidate_sha256")],
                ["patch_plan_sha256", repair.get("patch_plan_sha256")],
                ["integrity", repair.get("integrity")],
                ["gate_outcome", repair.get("gate_outcome")],
                ["poc_status", repair.get("poc_status")],
                ["runtime_tier", repair.get("runtime_tier")],
                ["layout_status", repair.get("layout_status")],
                ["false_verified", repair.get("false_verified")],
            ],
        )
        lines += [
            "",
            f"**{T['verification_label']}**: "
            f"independent_decision={verification.get('independent_decision')} | "
            f"verifier_id={verification.get('verifier_id')} | "
            f"real_verification={verification.get('real_verification')}",
            "",
            f"**{T['checks_label']}**",
            "",
        ]
        lines += _md_checks(fixture, lang)
        lines.append("")
        lines += _md_bullets(T["limitations_label"], list(fixture.get("limitations") or []), lang)
        lines += _md_bullets(T["not_run_label"], list(fixture.get("not_run") or []), lang)
        evidence_root = fixture.get("evidence_root")
        if evidence_root:
            lines += [
                f"**{T['evidence_dir']}**: {evidence_root}/ "
                f"({T['evidence_dir_note']})",
                "",
            ]
    fail_closed = report.get("fail_closed") or {}
    lines += [
        f"## {T['fail_closed']}",
        "",
        f"- {T['fail_closed_ok'] if fail_closed.get('ok') else T['fail_closed_bad']}",
        "",
    ]
    for issue in fail_closed.get("issues") or []:
        lines.append(f"- {T['violation']}: {issue}")
    lines += ["", f"## {T['evidence_index']}", ""]
    lines += _md_table(
        T["evidence_cols"],
        [[row["path"], row["bytes"], row["sha256"]] for row in index],
    )
    lines += [
        "",
        T["sums_note"].format(sums=SUMS_FILE),
        "",
        f"## {T['not_claimed_heading']}",
        "",
    ]
    for item in T["not_claimed_bullets"]:
        lines.append(f"- {item}")
    lines += ["", "---", "", T["repro_note"], ""]
    return "\n".join(lines)


def _html_escape(value: Any) -> str:
    text = str(value if value is not None else "")
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_html(report: dict[str, Any], index: list[dict[str, Any]], lang: str) -> str:
    T = TEXT[lang]
    labels = STATUS_LABELS[lang]
    notes = VERDICT_NOTES[lang]
    boundary = report.get("boundary") or {}
    run_meta = report.get("run_meta") or {}
    summary_rows = []
    for fixture in report["fixtures"]:
        repair = fixture.get("repair") or {}
        verification = fixture.get("verification") or {}
        summary_rows.append(
            "<tr>"
            f"<td><code>{_html_escape(fixture.get('fixture'))}</code></td>"
            f"<td>{_html_escape(fixture.get('expected'))}</td>"
            f'<td class="status">{_html_escape(fixture["presented_status"])}</td>'
            f"<td>{_html_escape(repair.get('disposition'))}</td>"
            f"<td>{_html_escape(verification.get('independent_decision'))}</td>"
            f"<td>{_html_escape(verification.get('oracle_status'))}</td>"
            f"<td>{_html_escape(repair.get('runtime_tier'))}</td>"
            "</tr>"
        )
    sections = []
    for fixture in report["fixtures"]:
        repair = fixture.get("repair") or {}
        verification = fixture.get("verification") or {}
        checks = "".join(
            "<tr>"
            f"<td><code>{_html_escape(check.get('id'))}</code></td>"
            f"<td>{_html_escape(check.get('required'))}</td>"
            f"<td>{_html_escape(check.get('status'))}</td>"
            f"<td>{_html_escape(check.get('detail'))}</td>"
            "</tr>"
            for check in fixture.get("checks") or []
        )
        limitations = "".join(
            f"<li>{_html_escape(item)}</li>" for item in fixture.get("limitations") or []
        ) or f"<li>{_html_escape(T['none'])}</li>"
        not_run = "".join(
            f"<li>{_html_escape(item)}</li>" for item in fixture.get("not_run") or []
        ) or f"<li>{_html_escape(T['none'])}</li>"
        sections.append(
            f"<h2><code>{_html_escape(fixture.get('fixture'))}</code> - "
            f"{_html_escape(fixture['presented_status'])}</h2>"
            f"<p>{_html_escape(labels.get(fixture['presented_status'], ''))}<br>"
            f"{_html_escape(notes.get(fixture['presented_status'], ''))}</p>"
            f"<p><b>{_html_escape(T['reason_label'])}</b>: "
            f"{_html_escape(fixture.get('reason'))}</p>"
            f"<p><b>disposition</b>: {_html_escape(repair.get('disposition'))} &nbsp; "
            f"<b>candidate_sha256</b>: <code>{_html_escape(repair.get('candidate_sha256'))}"
            "</code> &nbsp; "
            f"<b>plan_sha256</b>: <code>{_html_escape(repair.get('patch_plan_sha256'))}"
            "</code> &nbsp; "
            f"<b>gate</b>: {_html_escape(repair.get('gate_outcome'))} &nbsp; "
            f"<b>oracle</b>: {_html_escape(verification.get('oracle_status'))} &nbsp; "
            f"<b>tier</b>: {_html_escape(repair.get('runtime_tier'))}</p>"
            f"<h3>{_html_escape(T['checks_label'])}</h3>"
            "<table><tr>"
            + "".join(f"<th>{_html_escape(col)}</th>" for col in T["checks_cols"])
            + "</tr>"
            f"{checks}</table>"
            f"<h3>{_html_escape(T['limitations_label'])}</h3><ul>{limitations}</ul>"
            f"<h3>{_html_escape(T['not_run_label'])}</h3><ul>{not_run}</ul>"
        )
    evidence_rows = "".join(
        "<tr>"
        f"<td><code>{_html_escape(row['path'])}</code></td>"
        f"<td>{row['bytes']}</td>"
        f"<td><code>{_html_escape(row['sha256'])}</code></td>"
        "</tr>"
        for row in index
    )
    fail_closed = report.get("fail_closed") or {}
    issues = "".join(
        f"<li>{_html_escape(issue)}</li>" for issue in fail_closed.get("issues") or []
    )
    not_claimed = "".join(
        f"<li>{_html_escape(item)}</li>" for item in T["not_claimed_bullets"]
    )
    boundary_rows = "".join(
        "<tr>"
        f"<td>{_html_escape(T[key])}</td>"
        f"<td>{_html_escape(value)}</td>"
        "</tr>"
        for key, value in (
            ("positioning", boundary.get("positioning")),
            ("public_benchmark", boundary.get("public_benchmark")),
            ("hidden_benchmark", boundary.get("hidden_benchmark")),
            ("detection", boundary.get("detection_localization")),
            ("scope", boundary.get("repair_scope")),
            ("verification_scope", boundary.get("verification")),
        )
    )
    style = (
        "body{font:14px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
        "max-width:1080px;margin:32px auto;padding:0 20px;color:#101828}"
        "h1{font-size:24px}"
        "h2{font-size:19px;margin-top:32px;border-top:1px solid #e4e7ec;padding-top:20px}"
        "h3{font-size:15px}"
        "code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}"
        "table{border-collapse:collapse;width:100%;margin:12px 0;font-size:12.5px}"
        "th,td{border:1px solid #e4e7ec;padding:6px 8px;text-align:left;vertical-align:top}"
        "th{background:#f9fafb}.status{font-weight:700}"
        ".banner{background:#fffaeb;border:1px solid #fedf89;padding:12px 14px;"
        "border-radius:8px}"
    )
    html_lang = "en" if lang == "en" else "zh-CN"
    return "\n".join([
        "<!doctype html>",
        f'<html lang="{html_lang}"><head><meta charset="utf-8">',
        f"<title>{_html_escape(report['title'])}</title>",
        f"<style>{style}</style></head><body>",
        f"<h1>{_html_escape(report['title'])}</h1>",
        f"<p>{_html_escape(T['generated_at'])}: "
        f"<code>{_html_escape(report['generated_at'])}</code> | "
        f"{_html_escape(T['host'])}: "
        f"{_html_escape((run_meta.get('host') or {}))}</p>",
        '<div class="banner"><b>' + _html_escape(T["positioning"]) + "</b>: "
        f"{_html_escape(boundary.get('public_benchmark'))}; "
        f"hidden {_html_escape(boundary.get('hidden_benchmark'))}; "
        f"{_html_escape(boundary.get('positioning'))}</div>",
        f"<h2>{_html_escape(T['boundary'])}</h2>",
        "<table>" + boundary_rows + "</table>",
        f"<h2>{_html_escape(T['summary'])}</h2>",
        "<table><tr>"
        + "".join(f"<th>{_html_escape(col)}</th>" for col in T["summary_cols"])
        + "</tr>",
        "".join(summary_rows),
        "</table>",
        f"<h2>{_html_escape(T['details'])}</h2>",
        "".join(sections),
        f"<h2>{_html_escape(T['fail_closed'])}</h2>",
        f"<p>{_html_escape(T['fail_closed_ok'] if fail_closed.get('ok') else T['fail_closed_bad'])}</p>"
        f"<ul>{issues}</ul>",
        f"<h2>{_html_escape(T['evidence_index'])}</h2>",
        "<table><tr>"
        + "".join(f"<th>{_html_escape(col)}</th>" for col in T["evidence_cols"])
        + "</tr>",
        evidence_rows,
        "</table>",
        f"<h2>{_html_escape(T['not_claimed_heading'])}</h2>",
        f"<ul>{not_claimed}</ul>",
        "</body></html>",
        "",
    ])


def write_index(
    outdir: Path, index: list[dict[str, Any]], report: dict[str, Any]
) -> Path:
    target = Path(outdir) / INDEX_FILE
    payload = {
        "schema_version": 1,
        "kind": "product_evidence_index",
        "generated_at": report["generated_at"],
        "file_count": len(index),
        "files": index,
    }
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return target


def write_sha256sums(outdir: Path) -> Path:
    rows = []
    for path in sorted(Path(outdir).rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(outdir).as_posix()
        if relative == SUMS_FILE:
            continue
        rows.append(f"{_sha256(path.read_bytes())}  {relative}")
    target = Path(outdir) / SUMS_FILE
    target.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return target


def export_report(
    outdir: Path, title: str | None = None, lang: str = "en"
) -> dict[str, Any]:
    """Write one report language plus the shared evidence index and checksums."""
    lang = _check_lang(lang)
    outdir = Path(outdir)
    run = load_run(outdir)
    report_title = title or str(
        run.get("title") or TEXT[lang]["default_title"]
    )
    report = build_report(outdir, run, report_title)
    report_md_name, report_html_name = FILENAMES[lang]
    report_md = outdir / report_md_name
    report_html = outdir / report_html_name
    index = evidence_index(outdir)
    report_md.write_text(render_markdown(report, index, lang), encoding="utf-8")
    report_html.write_text(render_html(report, index, lang), encoding="utf-8")
    index = evidence_index(outdir)
    write_index(outdir, index, report)
    sums = write_sha256sums(outdir)
    return {
        "lang": lang,
        "report_md": str(report_md),
        "report_html": str(report_html),
        "evidence_index": str(outdir / INDEX_FILE),
        "sha256sums": str(sums),
        "fail_closed": report["fail_closed"],
        "statuses": {
            fixture["fixture"]: fixture["presented_status"]
            for fixture in report["fixtures"]
        },
        "file_count": len(index),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a customer-readable report + hashed evidence index."
    )
    parser.add_argument(
        "outdir", help="demo output directory (contains demo-run.json)"
    )
    parser.add_argument("--title", default=None, help="report title")
    parser.add_argument("--lang", choices=("en", "zh"), default="en",
                        help="report language (en default, ASCII-safe)")
    parser.add_argument("--json", action="store_true", help="print JSON only")
    args = parser.parse_args(argv)
    outdir = Path(args.outdir).resolve()
    try:
        result = export_report(outdir, title=args.title, lang=args.lang)
    except ExportError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    payload = {"ok": result["fail_closed"]["ok"], **result}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"report: {result['report_md']}")
        print(f"html:   {result['report_html']}")
        print(f"index:  {result['evidence_index']}")
        print(f"sums:   {result['sha256sums']}")
        print(f"fail_closed_ok: {result['fail_closed']['ok']}")
        for fixture, status in result["statuses"].items():
            print(f"  {fixture}: {status}")
        for issue in result["fail_closed"]["issues"]:
            print(f"  VIOLATION: {issue}")
    return 0 if result["fail_closed"]["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
