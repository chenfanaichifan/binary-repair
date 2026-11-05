"""T8.2 LLM planner seam (M2)。

范围（Lead 决定，T8.2 由 M2 承接）：

* ``BINARYREPAIR_ASSISTANT_MODE=llm`` 时的 prompt 构造；
* 模型返回的 ``AssistantPlan`` 结构校验；
* 任何失败都回退到确定性引导，并给出可展示的 ``fallback_reason``；
* 调用 usage 记录（写入 ``model_calls`` 形状的 dict，交给调用方落库）；
* 供 UI 使用的 mode / fallback 状态。

边界：

* 不实现 M5 的 deterministic planner，不改 ``app/domain/assistant.py`` /
  ``004_assistant.sql`` / ``app/services/assistant.py`` 的持久化部分。
* 不读环境里的 API key，不建 HTTP 连接。传输层通过 ``client`` 注入，具体走
  哪条 trusted provider 路径待 M1 确认；未注入 client 时直接回退，不伪造计划。
* 不把 prompt、模型原文或 key 写进日志/返回值。``PlanOutcome`` 只暴露长度、
  模型名、token 计数与稳定的失败码。

LLM 调用若在本进程内完成，key 只应存在于注入的 client 里；本模块从不接触它。
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

__all__ = [
    "ASSISTANT_MODE_ENV",
    "DEFAULT_MODEL",
    "FallbackReason",
    "PlanClient",
    "PlanOutcome",
    "assistant_status",
    "build_messages",
    "generate_plan",
    "resolve_mode",
    "validate_plan",
]

ASSISTANT_MODE_ENV = "BINARYREPAIR_ASSISTANT_MODE"
ASSISTANT_MODEL_ENV = "BINARYREPAIR_ASSISTANT_MODEL"
DEFAULT_MODEL = "deepseek-chat"

MODES = ("llm", "deterministic", "fixture")


class FallbackReason:
    """稳定的回退原因码；展示层只翻译，不推断。"""

    NO_CLIENT = "llm_client_not_configured"
    DISABLED = "assistant_mode_not_llm"
    TIMEOUT = "llm_timeout"
    NETWORK = "llm_network_error"
    EMPTY = "llm_empty_content"
    MALFORMED = "llm_invalid_json"
    SCHEMA = "llm_plan_schema_invalid"
    UNKNOWN = "llm_unknown_error"


#: 计划步骤允许的交互类型。未知 kind 一律按 schema 失败处理，避免前端猜渲染方式。
STEP_KINDS = ("upload", "question", "review")


class PlanClient(Protocol):
    """注入的传输层。

    实现方负责鉴权与网络；本模块只消费返回值。返回值形如::

        {"content": "<json string>", "model": "deepseek-chat",
         "usage": {"prompt_tokens": 10, "completion_tokens": 20,
                   "total_tokens": 30}, "request_id": "..."}

    ``content`` 必须是 JSON 文本；也可以直接返回已解析的 dict。
    """

    def complete(self, messages: Sequence[Mapping[str, str]], *, model: str) -> Mapping[str, Any]:
        ...


@dataclass(frozen=True)
class PlanOutcome:
    """一次规划尝试的结果。``plan`` 只在 llm 成功时非空。"""

    mode: str
    plan: dict[str, Any] | None
    fallback: bool
    fallback_reason: str | None
    model_requested: str
    model_returned: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    #: 仅用于排障的长度/指纹，绝不含原文。
    prompt_chars: int = 0
    prompt_sha256_prefix: str = ""

    def as_agent_view(self) -> dict[str, Any]:
        """给控制台徽章/侧栏用的最小视图（不含计划正文）。"""
        return {
            "mode": self.mode,
            "fallback": self.fallback,
            "fallback_reason": self.fallback_reason,
            "model": self.model_returned or self.model_requested,
            "tokens": {
                "prompt": self.usage.get("prompt_tokens"),
                "completion": self.usage.get("completion_tokens"),
            },
        }

    def as_model_call_row(self, *, call_id: str, created_at: str) -> dict[str, Any]:
        """映射成 ``model_calls`` 表的一行；调用方负责写库。

        ``status`` 只有 ``ok`` / ``fallback``，不把失败伪装成成功。
        """
        row: dict[str, Any] = {
            "id": call_id,
            "model_requested": self.model_requested,
            "model_returned": self.model_returned,
            "status": "ok" if not self.fallback else "fallback",
            "prompt_tokens": self.usage.get("prompt_tokens"),
            "completion_tokens": self.usage.get("completion_tokens"),
            "total_tokens": self.usage.get("total_tokens"),
            "estimated_cost_usd": None,
            "latency_ms": self.usage.get("latency_ms"),
            "request_id": self.request_id,
            "usage_json": json.dumps(
                {
                    "fallback_reason": self.fallback_reason,
                    "prompt_chars": self.prompt_chars,
                    "prompt_sha256_prefix": self.prompt_sha256_prefix,
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            "created_at": created_at,
        }
        return row


def resolve_mode(value: str | None = None) -> str:
    """读取助手模式；未知取值一律视为 deterministic，不静默当成 llm。"""
    raw = (value if value is not None else os.environ.get(ASSISTANT_MODE_ENV, "")).strip().lower()
    return raw if raw in MODES else "deterministic"


def resolve_model(value: str | None = None) -> str:
    return (value or os.environ.get(ASSISTANT_MODEL_ENV, "")).strip() or DEFAULT_MODEL


def assistant_status(*, mode: str | None = None, client_configured: bool | None = None) -> dict[str, Any]:
    """UI 用的模式状态。

    ``available`` 只有在 llm 模式且确实注入了 client 时才为真。未接线时页面必须
    显示“未接线”，不能显示成“已启用”。
    """
    resolved = resolve_mode(mode)
    if client_configured is None:
        # 没有显式告知时按“未接线”处理：宁可显示未接线，也不冒充已启用。
        client_configured = False
    return {
        "mode": resolved,
        "model": resolve_model() if resolved == "llm" else None,
        "available": resolved == "llm" and bool(client_configured),
        "fallback_reason": None if resolved != "llm" or client_configured else FallbackReason.NO_CLIENT,
    }


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def build_messages(description: str, *, context: Mapping[str, Any] | None = None) -> list[dict[str, str]]:
    """构造规划用的对话消息。

    prompt 只含用户描述与结构化上下文；不含任何凭据。输出要求严格 JSON，
    便于校验失败时明确回退，而不是把半截文本当计划。
    """
    system = (
        "You are the planning assistant of a binary-repair workbench.\n"
        "Return ONLY a JSON object matching this shape:\n"
        '{"mode":"llm","steps":[{"id":"string","title":"string",'
        '"kind":"upload|question|review","prompt":"string","questions":'
        '[{"key":"string","label":"string","required":true,"ascii":true,'
        '"input":"text|textarea","default":"string"}], '
        '"default":"string"}]}\n'
        "Rules:\n"
        "- You guide the user; you never create jobs, never start runs, never judge repairs.\n"
        "- Do not invent hashes, verdicts, or evidence.\n"
        "- Steps must be concrete and ordered; keep the number small (<= 6).\n"
        "- Output ASCII English only for values that will be submitted to the backend.\n"
        "- No markdown fences, no commentary."
    )
    payload: dict[str, Any] = {"description": description}
    if context:
        payload["context"] = dict(context)
    user = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def validate_plan(plan: Any) -> list[str]:
    """按前端消费契约校验计划；返回错误列表，空列表表示可渲染。"""
    errors: list[str] = []
    if not isinstance(plan, dict):
        return ["plan is not an object"]
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        return ["steps must be a non-empty list"]
    if len(steps) > 6:
        errors.append("steps must contain at most 6 entries")

    seen_ids: set[str] = set()
    for index, step in enumerate(steps):
        where = f"steps[{index}]"
        if not isinstance(step, dict):
            errors.append(f"{where} is not an object")
            continue
        step_id = step.get("id")
        if not isinstance(step_id, str) or not step_id.strip():
            errors.append(f"{where}.id must be a non-empty string")
        elif step_id in seen_ids:
            errors.append(f"{where}.id is duplicated")
        else:
            seen_ids.add(step_id)
        if not isinstance(step.get("title"), str) or not step["title"].strip():
            errors.append(f"{where}.title must be a non-empty string")
        kind = step.get("kind")
        if kind not in STEP_KINDS:
            errors.append(f"{where}.kind must be one of {STEP_KINDS}")
        if kind in ("question", "upload"):
            if not isinstance(step.get("prompt"), str) or not step["prompt"].strip():
                errors.append(f"{where}.prompt must be a non-empty string")
        if kind == "question":
            questions = step.get("questions")
            if not isinstance(questions, list) or not questions:
                errors.append(f"{where}.questions must be a non-empty list")
                continue
            keys: set[str] = set()
            for q_index, question in enumerate(questions):
                qwhere = f"{where}.questions[{q_index}]"
                if not isinstance(question, dict):
                    errors.append(f"{qwhere} is not an object")
                    continue
                key = question.get("key")
                if not isinstance(key, str) or not key.strip():
                    errors.append(f"{qwhere}.key must be a non-empty string")
                elif key in keys:
                    errors.append(f"{qwhere}.key is duplicated")
                else:
                    keys.add(key)
                if not isinstance(question.get("label"), str) or not question["label"].strip():
                    errors.append(f"{qwhere}.label must be a non-empty string")
                if "required" in question and not isinstance(question["required"], bool):
                    errors.append(f"{qwhere}.required must be a boolean")
                if "ascii" in question and not isinstance(question["ascii"], bool):
                    errors.append(f"{qwhere}.ascii must be a boolean")
                if "input" in question and question["input"] not in ("text", "textarea"):
                    errors.append(f"{qwhere}.input must be text or textarea")
        if kind == "review" and "questions" in step and not isinstance(step["questions"], list):
            errors.append(f"{where}.questions must be a list when present")
    return errors


def _parse_content(content: Any) -> tuple[dict[str, Any] | None, str | None]:
    if isinstance(content, dict):
        return content, None
    if not isinstance(content, str) or not content.strip():
        return None, FallbackReason.EMPTY
    text = content.strip()
    if text.startswith("```"):
        # 容忍围栏，但仍然要求围栏内是合法 JSON。
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None, FallbackReason.MALFORMED
    if not isinstance(parsed, dict):
        return None, FallbackReason.SCHEMA
    return parsed, None


def _usage_of(response: Mapping[str, Any]) -> dict[str, Any]:
    usage = response.get("usage")
    if not isinstance(usage, Mapping):
        return {}
    result: dict[str, Any] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "latency_ms"):
        value = usage.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result[key] = int(value)
    return result


def generate_plan(
    description: str,
    *,
    context: Mapping[str, Any] | None = None,
    client: PlanClient | None = None,
    mode: str | None = None,
    model: str | None = None,
) -> PlanOutcome:
    """生成计划；失败一律回退，绝不返回半成品计划。

    调用方（M5 的持久化层 / 路由）负责把 ``as_agent_view()`` 放进响应、
    把 ``as_model_call_row()`` 写进 ``model_calls``。
    """
    resolved = resolve_mode(mode)
    requested = resolve_model(model)
    messages = build_messages(description, context=context)
    prompt_text = messages[-1]["content"]
    base = {
        "model_requested": requested,
        "prompt_chars": len(prompt_text),
        "prompt_sha256_prefix": _fingerprint(prompt_text),
    }

    if resolved != "llm":
        return PlanOutcome(mode=resolved, plan=None, fallback=False, fallback_reason=None, **base)
    if client is None:
        return PlanOutcome(
            mode=resolved,
            plan=None,
            fallback=True,
            fallback_reason=FallbackReason.NO_CLIENT,
            **base,
        )

    try:
        response = client.complete(messages, model=requested)
    except TimeoutError:
        return PlanOutcome(mode=resolved, plan=None, fallback=True,
                           fallback_reason=FallbackReason.TIMEOUT, **base)
    except ConnectionError:
        return PlanOutcome(mode=resolved, plan=None, fallback=True,
                           fallback_reason=FallbackReason.NETWORK, **base)
    except Exception:  # noqa: BLE001 - 任何传输异常都必须降级，且不回显原文
        return PlanOutcome(mode=resolved, plan=None, fallback=True,
                           fallback_reason=FallbackReason.UNKNOWN, **base)

    if not isinstance(response, Mapping):
        return PlanOutcome(mode=resolved, plan=None, fallback=True,
                           fallback_reason=FallbackReason.UNKNOWN, **base)

    usage = _usage_of(response)
    returned_model = response.get("model") if isinstance(response.get("model"), str) else None
    request_id = response.get("request_id") if isinstance(response.get("request_id"), str) else None

    plan, parse_reason = _parse_content(response.get("content"))
    if plan is None:
        # 空内容/坏 JSON/非对象：都是回退，不猜计划。
        return PlanOutcome(
            mode=resolved, plan=None, fallback=True, fallback_reason=parse_reason,
            model_returned=returned_model, usage=usage, request_id=request_id, **base
        )

    errors = validate_plan(plan)
    if errors:
        return PlanOutcome(
            mode=resolved, plan=None, fallback=True, fallback_reason=FallbackReason.SCHEMA,
            model_returned=returned_model, usage=usage, request_id=request_id, **base
        )

    plan.setdefault("mode", "llm")
    return PlanOutcome(
        mode=resolved, plan=plan, fallback=False, fallback_reason=None,
        model_returned=returned_model, usage=usage, request_id=request_id, **base
    )
