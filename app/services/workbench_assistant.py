"""Small, maintainable FAQ and workbench-state guidance for the chat assistant.

This module is intentionally deterministic. It does not call a model; the HTTP
chat endpoint may use these facts as retrieved context. Keeping this layer
separate makes the knowledge and state machine testable without an API key.
"""

from __future__ import annotations

from typing import Any

# 20 short, product-specific entries. Keep answers aligned with the current UI;
# update this file when routes or copy change.
FAQ_ENTRIES: tuple[dict[str, Any], ...] = (
    {
        "id": "upload_sample",
        "questions": ["怎么上传样本", "上传文件", "拖入文件", "上传后没反应"],
        "keywords": ["上传", "样本", "拖入", "文件", "upload"],
        "answer": "把 ELF 拖到“上传样本”区域，或点击选择。上传后对话会出现样本消息；如果只看到消息没有表单，刷新页面或点新建任务重新开始。",
        "action": {"type": "new_task", "label": "新建任务", "url": "/agent/new?new=1"},
    },
    {
        "id": "sample_zip",
        "questions": ["上传 zip 行不行", "为什么未检测到 ELF 头", "zip 可以吗"],
        "keywords": ["zip", "elf", "样本", "压缩包", "头"],
        "answer": "zip 不是 ELF，会提示“未检测到 ELF 头”。请解压后上传里面的 ELF 文件。",
    },
    {
        "id": "approval",
        "questions": ["怎么审批", "契约怎么批准", "审批界面在哪", "为什么不能执行"],
        "keywords": ["审批", "批准", "契约", "approve", "contract"],
        "answer": "创建任务成功后会自动进入契约审批区，也可以在任务页点“打开审批界面”。核对契约后点击“批准当前契约”；助手不会替你批准。",
        "action": {"type": "open_approval", "label": "打开审批界面"},
    },
    {
        "id": "postpone_approval",
        "questions": ["等一下再审批", "我累了", "稍后审批", "明天再批"],
        "keywords": ["累了", "休息", "等一下", "等会", "稍后", "晚点", "明天", "再审批"],
        "answer": "可以稍后再批准。契约会保持待批准，不会自动执行；你回来后在任务页打开审批界面即可。",
        "action": {"type": "open_approval", "label": "稍后打开审批界面"},
    },
    {
        "id": "execute_local",
        "questions": ["为什么不能执行", "为什么开始执行没反应", "local 模式能跑吗"],
        "keywords": ["执行", "运行", "local", "run", "启动"],
        "answer": "当前 local 模式只提供真实任务记录、上传和契约审批，不执行二进制修复。要执行需要接 controller + worker/guest。",
    },
    {
        "id": "evidence",
        "questions": ["证据在哪里", "怎么查看证据", "实验数据在哪"],
        "keywords": ["证据", "实验数据", "evidence", "产物"],
        "answer": "打开任务后点击“结果与证据”或“证据与导出”。当前任务可以输入“打开当前任务的证据”，我会跳到证据页。",
        "action": {"type": "open_evidence", "label": "打开证据"},
    },
    {
        "id": "report",
        "questions": ["怎么导出报告", "报告在哪里", "怎么下载证据包"],
        "keywords": ["报告", "导出", "下载", "report", "export"],
        "answer": "任务页和证据页提供 JSON 证据包与 HTML 报告；导出只用于复核，不代表生产批准。",
    },
    {
        "id": "model_key",
        "questions": ["模型未配置怎么办", "怎么配置 key", "api key 在哪填"],
        "keywords": ["key", "api", "模型", "配置", "未配置"],
        "answer": "点工作台顶部“配置模型”，填写用户名和 API Key，保存并测试。Key 不回显；清除需要确认。",
    },
    {
        "id": "next_step",
        "questions": ["下一步做什么", "然后呢", "接下来", "现在做什么"],
        "keywords": ["下一步", "然后", "接下来", "现在", "next"],
        "answer": "我会根据当前任务阶段提示下一步：上传样本、填写任务信息、创建任务、审批契约或查看证据。",
    },
    {
        "id": "status_panel",
        "questions": ["状态面板是什么意思", "为什么状态是待创建任务", "阶段契约怎么看"],
        "keywords": ["状态", "阶段", "契约", "待创建", "面板"],
        "answer": "状态面板显示当前步骤、代码修复、执行状态、阶段和契约。任务创建前显示“待创建任务/草稿/未创建”，不会伪造执行进度。",
    },
    {
        "id": "chat",
        "questions": ["你能聊天吗", "聊天能做什么", "你可以做什么"],
        "keywords": ["聊天", "能做什么", "能力", "chat"],
        "answer": "我可以解释流程、回答常见问题、提示下一步，并根据状态打开审批/证据页面；不会编造 verdict、哈希或执行结果。",
    },
    {
        "id": "memory",
        "questions": ["你有记忆吗", "能记住多少轮", "对话上下文"],
        "keywords": ["记忆", "上下文", "轮", "history", "memory"],
        "answer": "聊天保留最近 10 轮（20 条消息）作为上下文，超过后由服务端截断；更早内容不保证记得。",
    },
    {
        "id": "rename",
        "questions": ["怎么重命名任务", "改任务名", "任务名称怎么改"],
        "keywords": ["重命名", "改名", "名称", "rename"],
        "answer": "当前任务可以输入“把这个任务命名为 X”，我会先显示确认卡；确认后只改本机任务列表记录。",
        "action": {"type": "rename_task", "label": "重命名当前任务"},
    },
    {
        "id": "restore",
        "questions": ["为什么恢复了草稿", "如何开始全新会话", "草稿怎么清空"],
        "keywords": ["恢复", "草稿", "全新", "清空", "draft"],
        "answer": "服务端历史会自动恢复草稿。要开始空白会话，点“新建任务”或地址加 ?new=1。",
        "action": {"type": "new_task", "label": "新建任务", "url": "/agent/new?new=1"},
    },
    {
        "id": "fallback",
        "questions": ["为什么显示助手降级", "llm_plan_schema_invalid", "模型通道未建立"],
        "keywords": ["降级", "fallback", "schema_invalid", "未建立", "模型通道"],
        "answer": "这是助手降级提示：模型计划返回格式不符合 schema 时会回退到确定性引导；不代表任务失败。仍可按页面表单继续。",
    },
    {
        "id": "contract",
        "questions": ["契约是什么", "安全契约填什么", "valid domain 是什么"],
        "keywords": ["契约", "valid", "domain", "forbidden", "假设"],
        "answer": "契约定义合法输入、禁止行为、非法输入期望和假设；它决定验收引擎怎么判。可以先用默认值再逐项修改。",
    },
    {
        "id": "evidence_limits",
        "questions": ["导出代表什么", "证据能证明什么", "not_run 是什么"],
        "keywords": ["导出", "证明", "not_run", "证据", "批准"],
        "answer": "证据只记录实际返回；not_run 表示未执行，不是失败或通过。导出不代表生产批准，verdict 只由验收引擎给出。",
    },
    {
        "id": "n10",
        "questions": ["N-10 是什么", "自定义 key 路径"],
        "keywords": ["n-10", "n10", "自定义", "key 路径", "环境变量"],
        "answer": "N-10 是已接受限制：自定义 key 文件路径只有在 adapter 进程看到相同环境变量时才受保护；默认路径始终受保护。",
    },
    {
        "id": "n11",
        "questions": ["N-11 是什么", "route_bundle_ingest 有 guard 吗"],
        "keywords": ["n-11", "n11", "route_bundle_ingest", "guard", "文档"],
        "answer": "N-11 是 docs-only 修复：route_bundle_ingest 没有被修改，也没有 runtime guard；页面和文档不会声称已有运行时保护。",
    },
    {
        "id": "new_task",
        "questions": ["怎么新建任务", "重新开始", "新建修复内容"],
        "keywords": ["新建", "任务", "开始", "new"],
        "answer": "点左侧或顶部“新建任务”，或打开 /agent/new?new=1 开始空白会话。",
        "action": {"type": "new_task", "label": "新建任务", "url": "/agent/new?new=1"},
    },
    {
        "id": "sample_file",
        "questions": ["有测试样本吗", "想试一个漏洞文件"],
        "keywords": ["测试", "样本", "漏洞文件", "elf", "cwe121"],
        "answer": "当前工作区有 CWE-121 受控样本，可作为 ELF 上传测试；不要在 Windows 主机直接执行，放到 Linux VM/WSL 沙箱。",
    },
)


def _norm(value: str) -> str:
    return "".join(ch.lower() for ch in (value or "") if not ch.isspace())


def retrieve_faq(message: str, limit: int = 2) -> list[dict[str, Any]]:
    """Return the best FAQ entries by simple keyword/phrase overlap.

    Deliberately deterministic so the behavior can be evaluated offline. A
    later version may replace this with embeddings without changing the HTTP
    shape.
    """
    text = _norm(message)
    scored: list[tuple[int, dict[str, Any]]] = []
    for entry in FAQ_ENTRIES:
        score = 0
        for keyword in entry["keywords"]:
            if _norm(keyword) and _norm(keyword) in text:
                score += 2
        for question in entry["questions"]:
            q = _norm(question)
            if q and (q in text or text in q):
                score += 3
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[: max(1, limit)]]


def resolve_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Derive one explicit stage and the next safe action from client state."""
    raw = state if isinstance(state, dict) else {}
    job_id = raw.get("job_id") if isinstance(raw.get("job_id"), str) else ""
    has_sample = bool(raw.get("has_sample"))
    context_completed = bool(raw.get("context_completed"))
    contract_approved = bool(raw.get("contract_approved"))
    execution_status = raw.get("execution_status")
    execution_status = execution_status if isinstance(execution_status, str) else ""

    if not job_id:
        if context_completed:
            stage = "context_filled"
            next_action = "review_and_create"
        elif has_sample:
            stage = "sample_selected"
            next_action = "fill_context"
        else:
            stage = "no_task"
            next_action = "upload_sample"
    elif not contract_approved:
        stage = "job_created_contract_pending"
        next_action = "open_approval"
    elif execution_status in {"running", "queued", "pending"}:
        stage = "execution_" + execution_status
        next_action = "view_status"
    elif execution_status in {"success", "succeeded", "verified", "finished"}:
        stage = "evidence_ready"
        next_action = "view_evidence"
    elif execution_status in {"failed", "error", "timed_out"}:
        stage = "failed"
        next_action = "inspect_failure"
    else:
        stage = "contract_approved"
        next_action = "start_or_view"

    action: dict[str, Any] | None = None
    if next_action == "upload_sample":
        action = {"type": "new_task", "label": "新建任务", "url": "/agent/new?new=1"}
    elif next_action == "open_approval" and job_id:
        action = {"type": "open_approval", "job_id": job_id, "label": "打开审批界面"}
    elif next_action in {"view_evidence", "view_status", "inspect_failure"} and job_id:
        action = {"type": "open_evidence", "job_id": job_id, "label": "打开证据" if next_action == "view_evidence" else "查看任务"}

    labels = {
        "upload_sample": "上传样本",
        "fill_context": "填写任务信息",
        "review_and_create": "复核并创建任务",
        "open_approval": "打开契约审批",
        "start_or_view": "启动执行或查看任务",
        "view_status": "查看执行状态",
        "view_evidence": "查看证据",
        "inspect_failure": "查看失败原因",
    }
    return {
        "stage": stage,
        "next_action": next_action,
        "next_label": labels.get(next_action, next_action),
        "action": action,
        "has_sample": has_sample,
        "context_completed": context_completed,
        "job_created": bool(job_id),
        "contract_approved": contract_approved,
        "execution_status": execution_status or None,
    }


def guidance_context(message: str, state: dict[str, Any] | None) -> dict[str, Any]:
    faq = retrieve_faq(message, limit=2)
    resolved = resolve_state(state)
    # A specific FAQ action (rename, approval, evidence) is more useful than the
    # generic no-task "new task" action. Merge the real job id when available.
    for entry in faq:
        action = entry.get("action")
        if not action:
            continue
        merged = dict(action)
        state_action = resolved.get("action") or {}
        if merged.get("type") == state_action.get("type") and state_action.get("job_id"):
            merged["job_id"] = state_action["job_id"]
        resolved["action"] = merged
        break
    return {"faq": faq, "state": resolved}
