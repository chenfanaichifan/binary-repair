"""演示数据（GUI-only 开发模式）。

这里所有内容都是合成的：阶段按“运行开始后的秒数”推进，结论是写死的预设值。
页面必须明确标注“演示数据 / 未执行真实工具”，不能当作修复证据
（对应技术设计 §12：GUI-only development mode using stored or synthetic results,
clearly labeled; it must never emit accepted-patch evidence）。

接真实后端时：把 create_job / snapshot / obligations / artifacts 换成
成员 1 的 controller / API 调用即可，页面与轮询逻辑不用改。
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

# 每个阶段的“演示推进速度”（秒）。仅用于让页面动起来，不是真实耗时。
STAGE_SECONDS = 1.2

# 状态下拉/展示用的中文标签
PHASE_LABELS: dict[str, str] = {
    "draft": "草稿",
    "screening": "输入筛查",
    "analyzing": "二进制分析",
    "roundtrip": "C 往返校验",
    "generating": "候选生成",
    "applying": "写入副本",
    "validating": "共享校验",
    "finished": "已完成",
}

STAGE_LABELS = {name: label for name, label in PHASE_LABELS.items() if name != "finished"}

OUTCOME_LABELS: dict[str, str] = {
    "success_within_scope": "成功（声明范围内）",
    "unsupported": "不支持",
    "rejected": "被拒",
    "inconclusive": "不确定",
    "error": "错误",
    "cancelled": "已取消",
}

STATE_LABELS: dict[str, str] = {
    "pending": "待执行",
    "active": "进行中",
    "done": "已完成",
    "cancelled": "已取消",
}

# 验证/兼容结果的展示文案（页面上不直接露英文枚举）
VALUE_LABELS: dict[str, str] = {
    "not_run": "未运行（not_run）",
    "passed": "通过",
    "failed": "失败",
    "inconclusive": "不确定",
    "unavailable": "不可用",
}

# Route A 没有 roundtrip；Route B 多一步“语义不变往返”
ROUTE_STAGES: dict[str, list[str]] = {
    "A": ["screening", "analyzing", "generating", "applying", "validating"],
    "B": ["screening", "analyzing", "roundtrip", "generating", "applying", "validating"],
}

ROUTE_NAMES = {
    "A": "Route A · 直接指令修复",
    "B": "Route B · 恢复 C 后回填",
}

# 内存里的“数据库”。真实版本是 SQLite（技术设计 §6）。
JOBS: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_job(job_id: str) -> dict[str, Any] | None:
    return JOBS.get(job_id)


def create_job(
    original_sha256: str,
    filename: str,
    defect: str,
    valid_tests: str,
    environment: str,
    valid_domain: str,
    forbidden: str,
    invalid_outcome: str,
    assumptions: str,
) -> dict[str, Any]:
    """登记一个任务（演示版：所有数据在内存里）。"""
    contract_body = {
        "valid_domain": valid_domain.strip() or "输入长度 0–64 字节；不接受越界长度",
        "forbidden": forbidden.strip() or "目标缓冲区越界写（超过 8 字节）",
        "invalid_outcome": invalid_outcome.strip() or "返回错误码 1，不越界、不崩溃",
        "assumptions": [
            line.strip()
            for line in (assumptions or "单进程；Linux x86-64 ELF；未开启栈保护").splitlines()
            if line.strip()
        ],
    }
    contract_sha256 = _sha(json.dumps(contract_body, sort_keys=True, ensure_ascii=False))

    job: dict[str, Any] = {
        "id": "job-" + uuid.uuid4().hex[:8],
        "demo": True,
        "filename": filename,
        "original_sha256": original_sha256,
        "defect": defect.strip() or "（未填写缺陷描述）",
        "valid_tests": [line.strip() for line in valid_tests.splitlines() if line.strip()],
        "environment": environment.strip() or "Ubuntu x86-64 VM（演示：未启用执行）",
        "created_at": _now_iso(),
        "run_started_at": None,
        "cancelled": False,
        "frozen_elapsed": None,
        "phase": "draft",
        "contract": {"revision": 1, "sha256": contract_sha256, **contract_body},
        "routes": {
            "A": _route_state("A"),
            "B": _route_state("B"),
        },
    }
    JOBS[job["id"]] = job
    return job


def _route_state(key: str) -> dict[str, Any]:
    return {
        "name": ROUTE_NAMES[key],
        "phase": "draft",
        "phase_label": PHASE_LABELS["draft"],
        "outcome": None,
        "outcome_label": None,
        "outcome_class": "outcome-none",
        "outcome_reason": "",
        "stages": [],
        "tests": {"passed": 0, "total": 8},
        "verification": "not_run",
        "compatibility": "not_run",
        "changed_regions": [],
        "manual_interventions": 0,
        "ai_usage": "unavailable",
        "elapsed_s": 0.0,
    }


def start(job: dict[str, Any]) -> None:
    """演示用启动：记录开始时间，阶段会随时间推进。真实版本由 controller 负责。"""
    if job["run_started_at"] is None:
        job["run_started_at"] = time.time()
        job["phase"] = "screening"


def cancel(job: dict[str, Any]) -> None:
    """演示用取消：冻结当前进度并标记 cancelled。"""
    if job["run_started_at"] is None:
        return
    job["cancelled"] = True
    job["frozen_elapsed"] = _elapsed(job)


def _elapsed(job: dict[str, Any]) -> float:
    if job["frozen_elapsed"] is not None:
        return job["frozen_elapsed"]
    if job["run_started_at"] is None:
        return 0.0
    return max(0.0, time.time() - job["run_started_at"])


def _obligations_for(route: str) -> list[dict[str, Any]]:
    """演示用的 V0–V5 义务清单（对应技术设计 §9 的验证阶梯）。

    注意：结论是写死的演示值。Route A 在 V3 有效输入回归失败 -> rejected；
    Route B 的 V4 有界符号验证预算用尽 -> inconclusive。
    这样的组合恰好演示“不能把未完成当成功”。
    """
    passed = [
        {"id": "V0", "kind": "身份与前置条件", "description": "输入哈希、契约 revision、测试清单哈希一致"},
        {"id": "V1", "kind": "结构与放置", "description": "指令边界、改动区间、跳转目标可审计"},
        {"id": "V2", "kind": "接口与兼容", "description": "签名、栈/寄存器约定、加载执行检查"},
    ]
    if route == "A":
        return [
            *[
                {**item, "required": True, "result": "passed", "scope": "frozen job inputs", "reason": "演示数据：通过"}
                for item in passed
            ],
            {
                "id": "V3",
                "kind": "具体行为",
                "description": "复现输入、非法输入 oracle、有效输入回归",
                "required": True,
                "result": "failed",
                "scope": "冻结的测试清单（8 个有效输入）",
                "reason": "有效输入回归 case 3 失败：返回值 7 != 3",
            },
            {
                "id": "V4",
                "kind": "有界符号安全",
                "description": "候选自身的模型、输入域、越界访问谓词",
                "required": True,
                "result": "not_run",
                "scope": "—",
                "reason": "V3 已失败，保留诊断证据，不再继续",
            },
            {
                "id": "V5",
                "kind": "可复现性",
                "description": "最终哈希、版本、replay 输入与独立复现",
                "required": True,
                "result": "not_run",
                "scope": "—",
                "reason": "候选未通过前置检查",
            },
        ]
    return [
        *[
            {**item, "required": True, "result": "passed", "scope": "frozen job inputs", "reason": "演示数据：通过"}
            for item in passed
        ],
        {
            "id": "V3",
            "kind": "具体行为",
            "description": "复现输入、非法输入 oracle、有效输入回归",
            "required": True,
            "result": "passed",
            "scope": "冻结的测试清单（8 个有效输入）",
            "reason": "8/8 通过；非法输入走拒绝路径",
        },
        {
            "id": "V4",
            "kind": "有界符号安全",
            "description": "候选自身的模型、输入域、越界访问谓词",
            "required": True,
            "result": "inconclusive",
            "scope": "函数级 · 入口前置条件 · 输入长度 0–64",
            "reason": "探索预算（120 秒）用尽；内存安全义务未解决",
        },
        {
            "id": "V5",
            "kind": "可复现性",
            "description": "最终哈希、版本、replay 输入与独立复现",
            "required": True,
            "result": "not_run",
            "scope": "—",
            "reason": "V4 未完成，不进入复现",
        },
    ]


def _apply_finished(route: dict[str, Any], key: str) -> None:
    """两条路线都结束时，写入演示用的最终数据。"""
    if key == "A":
        route.update(
            {
                "tests": {"passed": 6, "total": 8},
                "verification": "failed",
                "compatibility": "passed",
                "changed_regions": [
                    {
                        "address": "0x0000000000401136",
                        "kind": "原地改写",
                        "before": "e8 75 fe ff ff",
                        "after": "e8 15 ff ff ff",
                    }
                ],
                "manual_interventions": 3,
                "ai_usage": "unavailable",
                "elapsed_s": round(len(ROUTE_STAGES["A"]) * STAGE_SECONDS, 1),
                "outcome": "rejected",
                "outcome_reason": "有效输入回归 case 3 失败（返回值 7 != 3）",
            }
        )
    else:
        route.update(
            {
                "tests": {"passed": 8, "total": 8},
                "verification": "inconclusive",
                "compatibility": "passed",
                "changed_regions": [
                    {
                        "address": "0x00000000004011a0",
                        "kind": "新增代码区",
                        "before": "（原函数 0x1a3 字节）",
                        "after": "（重编译后 0x1f2 字节）",
                    }
                ],
                "manual_interventions": 1,
                "ai_usage": "8.2k 输入 / 1.4k 输出 tokens",
                "elapsed_s": round(len(ROUTE_STAGES["B"]) * STAGE_SECONDS, 1),
                "outcome": "inconclusive",
                "outcome_reason": "有界符号验证：探索预算用尽，内存安全义务未解决",
            }
        )


def snapshot(job: dict[str, Any]) -> dict[str, Any]:
    """生成页面/接口用的只读快照。每次轮询都会调用它来推进演示进度。"""
    elapsed = _elapsed(job)
    cancelled = job["cancelled"]
    started = job["run_started_at"] is not None

    routes: dict[str, dict[str, Any]] = {}
    for key, stage_names in ROUTE_STAGES.items():
        route = job["routes"][key]
        total_seconds = len(stage_names) * STAGE_SECONDS
        route_finished = started and elapsed >= total_seconds
        done_count = min(int(elapsed // STAGE_SECONDS), len(stage_names))

        stages = []
        for index, name in enumerate(stage_names):
            if cancelled:
                state = "done" if index < done_count else ("cancelled" if index == done_count else "pending")
            elif route_finished:
                state = "done"
            elif started and index < done_count:
                state = "done"
            elif started and index == done_count:
                state = "active"
            else:
                state = "pending"
            stages.append(
                {
                    "name": name,
                    "label": STAGE_LABELS[name],
                    "state": state,
                    "state_label": STATE_LABELS[state],
                }
            )

        if cancelled:
            route["phase"] = "finished"
            route["outcome"] = "cancelled"
            route["outcome_reason"] = "操作者取消（演示数据）"
        elif route_finished:
            route["phase"] = "finished"
            if route["outcome"] is None:
                _apply_finished(route, key)
        elif started:
            active_index = min(done_count, len(stage_names) - 1)
            route["phase"] = stage_names[active_index]
        else:
            route["phase"] = "draft"

        route["phase_label"] = PHASE_LABELS[route["phase"]]
        route["verification_label"] = VALUE_LABELS.get(route["verification"], route["verification"])
        route["compatibility_label"] = VALUE_LABELS.get(route["compatibility"], route["compatibility"])
        if route["outcome"]:
            route["outcome_label"] = OUTCOME_LABELS[route["outcome"]]
            route["outcome_class"] = "outcome-" + route["outcome"].replace("_", "-")
        else:
            route["outcome_label"] = None
            route["outcome_class"] = "outcome-none"
        route["stages"] = stages
        routes[key] = route

    # Job 级阶段取“两条路线里更靠后的那个”，两条都结束才算 finished
    if cancelled:
        job_phase = "finished"
    elif not started:
        job_phase = "draft"
    elif routes["A"]["phase"] == "finished" and routes["B"]["phase"] == "finished":
        job_phase = "finished"
    else:
        order = ["screening", "analyzing", "roundtrip", "generating", "applying", "validating"]
        phases = [routes["A"]["phase"], routes["B"]["phase"]]
        job_phase = min(phases, key=lambda p: order.index(p) if p in order else 99)

    snapshot = {
        "id": job["id"],
        "demo": True,
        "filename": job["filename"],
        "original_sha256": job["original_sha256"],
        "defect": job["defect"],
        "valid_tests": job["valid_tests"],
        "environment": job["environment"],
        "created_at": job["created_at"],
        "phase": job_phase,
        "phase_label": PHASE_LABELS[job_phase],
        "cancelled": cancelled,
        "contract": job["contract"],
        "routes": routes,
    }
    return snapshot


def obligations(job: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {"A": _obligations_for("A"), "B": _obligations_for("B")}


def artifacts(job: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """演示用产物清单（真实版本来自 artifacts 表，且下载必须是注册过的文件）。"""
    base = _sha(job["id"] + job["original_sha256"])[:16]
    return {
        "A": [
            {"name": "candidate-A.elf", "role": "候选二进制", "sha256": _sha(base + "A.elf")},
            {"name": "edit-manifest-A.json", "role": "改动清单", "sha256": _sha(base + "A.edit")},
        ],
        "B": [
            {"name": "candidate-B.elf", "role": "候选二进制", "sha256": _sha(base + "B.elf")},
            {"name": "recovered-B.c", "role": "恢复的 C（原始/归一化/修复）", "sha256": _sha(base + "B.c")},
            {"name": "roundtrip-B.json", "role": "语义不变往返报告", "sha256": _sha(base + "B.rt")},
        ],
    }
