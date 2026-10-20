"""演示数据（GUI-only 开发模式）。

语言规范（2026-10-18，团队决定）：
- 界面可以中文，但**上传 / API / 导出数据一律英文 ASCII**。
- 因此本文件里的所有数据字符串（契约、义务、原因、变更区域、产物角色、
  路线规范名等）都用英文；中文显示文案在 app/i18n.py 里，只给模板用。
- 测试会扫描 /api/jobs/{id} 和导出 JSON，确保没有中日韩字符。

这里所有内容都是合成的：阶段按"运行开始后的秒数"推进，结论是写死的预设值。
页面必须明确标注"演示数据 / 未执行真实工具"，不能当作修复证据
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

# 每个阶段的"演示推进速度"（秒）。仅用于让页面动起来，不是真实耗时。
STAGE_SECONDS = 1.2

# Route A 没有 roundtrip；Route B 多一步"语义不变往返"
ROUTE_STAGES: dict[str, list[str]] = {
    "A": ["screening", "analyzing", "generating", "applying", "validating"],
    "B": ["screening", "analyzing", "roundtrip", "generating", "applying", "validating"],
}

# 规范名（英文，会进入 API/导出；中文显示名在 i18n.py）
ROUTE_NAMES_EN: dict[str, str] = {
    "A": "Route A - Direct instruction repair",
    "B": "Route B - Recovered C reintegration",
}

# 内存里的"数据库"。真实版本是 SQLite（技术设计 §6）。
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
    """登记一个任务（演示版：所有数据在内存里，字段值一律英文）。"""
    contract_body = {
        "valid_domain": valid_domain.strip() or "Input length 0-64 bytes; out-of-range lengths rejected",
        "forbidden": forbidden.strip() or "Out-of-bounds write to the target buffer (more than 8 bytes)",
        "invalid_outcome": invalid_outcome.strip() or "Return error code 1 without out-of-bounds access or crash",
        "assumptions": [
            line.strip()
            for line in (assumptions or "Single process\nLinux x86-64 ELF\nStack protector disabled").splitlines()
            if line.strip()
        ],
    }
    contract_sha256 = _sha(json.dumps(contract_body, sort_keys=True, ensure_ascii=False))

    job: dict[str, Any] = {
        "id": "job-" + uuid.uuid4().hex[:8],
        "demo": True,
        "filename": filename,
        "original_sha256": original_sha256,
        "defect": defect.strip() or "strcpy in stack_buf does not check length; overlong input writes out of bounds",
        "valid_tests": [line.strip() for line in valid_tests.splitlines() if line.strip()],
        "environment": environment.strip() or "Ubuntu x86-64 VM (demo: execution disabled)",
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
        "name": ROUTE_NAMES_EN[key],
        "phase": "draft",
        "outcome": None,
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
    """演示用的 V0-V5 义务清单（对应技术设计 §9 的验证阶梯）。

    注意：结论是写死的演示值。Route A 在 V3 有效输入回归失败 -> rejected；
    Route B 的 V4 有界符号验证预算用尽 -> inconclusive。
    这样的组合恰好演示"不能把未完成当成功"。

    数据字段全部英文 ASCII（会进入证据页与导出 JSON）。
    """
    passed = [
        {
            "id": "V0",
            "kind": "Identity and preconditions",
            "description": "Input hash, contract revision, and test manifest hash match",
        },
        {
            "id": "V1",
            "kind": "Structure and placement",
            "description": "Instruction boundaries, changed intervals, and branch targets are auditable",
        },
        {
            "id": "V2",
            "kind": "Interface and compatibility",
            "description": "Signature, stack/register conventions, and loader execution checks",
        },
    ]
    if route == "A":
        return [
            *[
                {**item, "required": True, "result": "passed", "scope": "frozen job inputs", "reason": "Demo data: passed"}
                for item in passed
            ],
            {
                "id": "V3",
                "kind": "Concrete behavior",
                "description": "Reproducer, invalid-input oracle, valid-input regression",
                "required": True,
                "result": "failed",
                "scope": "Frozen test manifest (8 valid inputs)",
                "reason": "Valid-input regression case 3 failed: return value 7 != 3",
            },
            {
                "id": "V4",
                "kind": "Bounded symbolic security",
                "description": "Candidate-specific model, input domain, out-of-bounds access predicate",
                "required": True,
                "result": "not_run",
                "scope": "n/a",
                "reason": "V3 failed; diagnostic evidence retained and verification not continued",
            },
            {
                "id": "V5",
                "kind": "Reproducibility",
                "description": "Final hashes, versions, replay inputs, independent replay",
                "required": True,
                "result": "not_run",
                "scope": "n/a",
                "reason": "Candidate did not pass prerequisite checks",
            },
        ]
    return [
        *[
            {**item, "required": True, "result": "passed", "scope": "frozen job inputs", "reason": "Demo data: passed"}
            for item in passed
        ],
        {
            "id": "V3",
            "kind": "Concrete behavior",
            "description": "Reproducer, invalid-input oracle, valid-input regression",
            "required": True,
            "result": "passed",
            "scope": "Frozen test manifest (8 valid inputs)",
            "reason": "8/8 passed; invalid input follows the rejection path",
        },
        {
            "id": "V4",
            "kind": "Bounded symbolic security",
            "description": "Candidate-specific model, input domain, out-of-bounds access predicate",
            "required": True,
            "result": "inconclusive",
            "scope": "Function level - entry preconditions - input length 0-64",
            "reason": "Exploration budget (120 s) exhausted; memory-safety obligation unresolved",
        },
        {
            "id": "V5",
            "kind": "Reproducibility",
            "description": "Final hashes, versions, replay inputs, independent replay",
            "required": True,
            "result": "not_run",
            "scope": "n/a",
            "reason": "V4 incomplete; replay not started",
        },
    ]


def _apply_finished(route: dict[str, Any], key: str) -> None:
    """两条路线都结束时，写入演示用的最终数据（字段值英文）。"""
    if key == "A":
        route.update(
            {
                "tests": {"passed": 6, "total": 8},
                "verification": "failed",
                "compatibility": "passed",
                "changed_regions": [
                    {
                        "address": "0x0000000000401136",
                        "kind": "in-place edit",
                        "before": "e8 75 fe ff ff",
                        "after": "e8 15 ff ff ff",
                    }
                ],
                "manual_interventions": 3,
                "ai_usage": "unavailable",
                "elapsed_s": round(len(ROUTE_STAGES["A"]) * STAGE_SECONDS, 1),
                "outcome": "rejected",
                "outcome_reason": "Valid-input regression case 3 failed (return value 7 != 3)",
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
                        "kind": "added code region",
                        "before": "original function 0x1a3 bytes",
                        "after": "recompiled 0x1f2 bytes",
                    }
                ],
                "manual_interventions": 1,
                "ai_usage": "8.2k input / 1.4k output tokens",
                "elapsed_s": round(len(ROUTE_STAGES["B"]) * STAGE_SECONDS, 1),
                "outcome": "inconclusive",
                "outcome_reason": "Bounded symbolic verification: exploration budget exhausted; memory-safety obligation unresolved",
            }
        )


def snapshot(job: dict[str, Any]) -> dict[str, Any]:
    """生成页面/接口用的只读快照（只含英文数据，不含中文显示标签）。"""
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
            stages.append({"name": name, "state": state})

        if cancelled:
            route["phase"] = "finished"
            route["outcome"] = "cancelled"
            route["outcome_reason"] = "Operator cancelled (demo data)"
        elif route_finished:
            route["phase"] = "finished"
            if route["outcome"] is None:
                _apply_finished(route, key)
        elif started:
            active_index = min(done_count, len(stage_names) - 1)
            route["phase"] = stage_names[active_index]
        else:
            route["phase"] = "draft"

        route["stages"] = stages
        routes[key] = route

    # Job 级阶段取"两条路线里更靠后的那个"，两条都结束才算 finished
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
            {"name": "candidate-A.elf", "role": "candidate binary", "sha256": _sha(base + "A.elf")},
            {"name": "edit-manifest-A.json", "role": "edit manifest", "sha256": _sha(base + "A.edit")},
        ],
        "B": [
            {"name": "candidate-B.elf", "role": "candidate binary", "sha256": _sha(base + "B.elf")},
            {"name": "recovered-B.c", "role": "recovered C (raw / normalized / repaired)", "sha256": _sha(base + "B.c")},
            {"name": "roundtrip-B.json", "role": "unchanged round-trip report", "sha256": _sha(base + "B.rt")},
        ],
    }
