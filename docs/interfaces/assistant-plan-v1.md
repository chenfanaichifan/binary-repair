# AssistantPlan v1（前端消费契约）

状态：**已收口（v1）** · 提出方 M2 · 已与 M5 的 `origin/member-5/complete-m5` 核对

这份文档只固定“工作台渲染一个引导计划需要什么”，不规定 planner 的内部实现。
确定性的 plan 内容和持久化仍归 M5（T8.1）；LLM 分支归 M2（T8.2）。

## 1. 为什么需要它

`/agent/new` 在没有后端计划时只能显示“后端还没有提供引导计划”。前端不定义计划内容，
也不猜结构：拿到什么就按下面的契约渲染，不符合就回退并说明原因。

## 2. 结构

```json
{
  "plan_id": "string",
  "mode": "deterministic | llm",
  "fallback": false,
  "fallback_reason": null,
  "model": null,
  "tokens": null,
  "steps": [
    {
      "id": "sample",
      "kind": "upload",
      "title": "第 1 步 · 样本",
      "prompt": "把要修复的二进制拖进来……"
    },
    {
      "id": "defect",
      "kind": "question",
      "title": "第 2 步 · 缺陷",
      "prompt": "用一句话说清哪里不对。",
      "questions": [
        {
          "key": "defect",
          "label": "缺陷描述（英文 ASCII）",
          "input": "textarea",
          "required": true,
          "ascii": true,
          "default": "strcpy in stack_buf does not check length"
        }
      ]
    },
    {
      "id": "review",
      "kind": "review",
      "title": "第 5 步 · 复核并创建",
      "prompt": "核对任务单，确认后由你点击「创建任务」。"
    }
  ]
}
```

## 3. 约束

| 字段 | 规则 | 违反时 |
|---|---|---|
| `steps` | 1–6 条 | 视为 schema 错误，回退 |
| `step.id` | 非空、唯一 | 同上 |
| `step.kind` | `upload` / `question` / `review` | 未知 kind 不猜渲染 |
| `step.title` | 非空 | 同上 |
| `step.prompt` | `upload` / `question` 必填 | 同上 |
| `step.questions` | `question` 必填且非空 | 同上 |
| `question.key` | step 内唯一 | 同上 |
| `question.label` | 非空 | 同上 |
| `question.input` | `text` / `textarea` | 同上 |
| `question.required` / `ascii` | 布尔 | 同上 |
| `question.default` | ASCII | 前端拦截，避免 `POST /jobs` 422 |
| `review` 位置 | 最后一步 | 前端用 `steps.length - 2` 判断“进入复核” |
| `fallback` | 布尔；为真时必须给 `fallback_reason` | 横幅显示原因为空即违规 |

其它：

- `mode` 使用 `deterministic` 或 `llm`；`scripted v1` 仅用于 M2 的开发 fixture，不作为契约值。
- `tokens` 形如 `{"prompt": int, "completion": int}`；无数据用 `null`，不填 0。
- 助手运行态（`current_step`、`execution.status`）在任务快照的 `agent` 里，不在 plan 内。
- plan 不包含 verdict、obligation 结果、哈希或任何结论性字段。

## 4. 获取方式（待 M1 定端点）

新建流程没有 `job_id`，因此需要无状态入口。建议：

```
POST /api/assistant/plan
{"description": "...", "context": {"workspace": "local", "mode": "standard"}}

200 {"available": true, "plan": {...}, "agent": {...}}
4xx {"available": false, "error": "..."}
```

已有任务可以复用 `GET /api/jobs/{id}/assistant`，但新建路径不能依赖它。

M2 的接入点：`app/static/js/agent.js` 的 `init()`，当前 else 分支（约 1162–1168 行）只显示提示；
端点到齐后在这里加一次请求，校验通过就进入 `startGuidedFlow()`，失败则保留提示并给出原因。

## 5. 校验实现

M2 已实现等价的校验器：`app/services/assistant_llm.validate_plan`（`tests/test_assistant_llm.py`）。
M5 的 planner 也应通过同一组断言；两边一致可以避免“后端产出、前端拒渲染”。

## 6. 已决（原“未决”）

| 问题 | 结论 |
|---|---|
| `plan_id` 谁生成、格式 | M5 的 `AssistantPlan` 设为**必填** 1–64 字符；deterministic planner 用 `uuid4().hex`。LLM 未给时由 M2 补 uuid，不让模型决定身份 |
| `default` 空字符串 | 允许；`None` 也允许。两者都表示“未填”，不是“校验通过” |
| `step.summary` | 不引入。复核页的折叠标题继续用 `title` |

## 7. M5 实现与本文档的字段 diff（2026-11-05）

核对对象：`origin/member-5/complete-m5` 的 `app/domain/assistant.py`。

| # | 本文档（`c3bb709`） | M5 实现 | M2 的处理 |
|---|---|---|---|
| 1 | `plan_id` 未决、可缺省 | 必填 `str`，1–64 | LLM 缺省时补 `uuid4().hex` |
| 2 | `step.prompt` 仅 `upload` / `question` 必填 | **所有 step 必填**（含 `review`） | 按 M5 校验；review 缺 prompt 即回退 |
| 3 | `questions` 仅 `question` 必填 | `kind != question` 时**禁止非空** `questions`（空列表允许） | 按 M5 校验 |
| 4 | 未说明额外字段 | `extra="forbid"`（plan / step / question 三层） | 多给字段即 schema 失败并回退 |
| 5 | `question.default` 为 string | string 或 `null`，ASCII，≤2000 | 两者都接受 |
| 6 | `tokens` 可 null，否则 `{prompt, completion}` | 同，且必须非负 int | 一致；只填后端真值 |
| 7 | 示例 title / prompt 为中文 | `deterministic_plan` 为英文 ASCII | **待定**：GUI 要中文，需翻译层或 M5 提供中文内容 |

第 7 条不是字段问题，但会影响 `/agent/new` 的观感：契约层允许任意语言，内容是 M5 的。
在端点接通前不影响交付；M1 的端点到位后需要二选一。

## 8. 端点包裹（M2 消费侧，2026-11-05）

```
POST /api/assistant/plan          # 无 job_id；M1 的 controller 提供，GUI 同源代理
Content-Type: application/json
X-CSRF-Token: <GUI session csrf>

{"description": "…", "context": {"filename": "…"}}

200 {"plan": { …AssistantPlan… }}
503 {"plan": null, "error": "assistant_unavailable",
     "fallback_reason": "assistant_endpoint_missing" | "llm_client_not_configured",
     "detail": "…"}
422 {"plan": null, "error": "invalid_request", "detail": "…"}
```

规则：

- `plan` 必须是完整 `AssistantPlan`；GUI 只渲染 `steps`，不补内容、不改 `mode`。
- 503 表示“没接通”，`/agent/new` 显示“计划服务未接通（原因）”；**不**退回 fixture。
- `?plan=fixture` 仍保留，仅用于本地预览，页面明确标注是占位。
- plan 的 `title` / `prompt` 是界面文案，允许中文；`context` 里的业务字段仍按提交语言策略用 ASCII。
- GUI 不轮询、不跨任务缓存计划；每次由用户描述触发一次请求。

## 9. Provider 配置（M2，2026-11-05）

`assistant_llm.generate_plan` 在没有显式 `client` 时调用 `client_from_env()`。

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `BINARYREPAIR_ASSISTANT_PROVIDER_KEY` | 是 | — | 没有它就不发起真实调用，返回 `fallback_reason=llm_client_not_configured` |
| `BINARYREPAIR_ASSISTANT_PROVIDER_BASE_URL` | 否 | `https://api.openai.com/v1` | OpenAI 兼容根路径 |
| `BINARYREPAIR_ASSISTANT_PROVIDER_TIMEOUT` | 否 | `30` | 秒 |
| `BINARYREPAIR_ASSISTANT_MODEL` | 否 | `deepseek-chat` | 请求体 `model` |

key 只存在 `HttpJsonClient` 内存里：`repr` 不打印，错误只带 HTTP 状态、不带响应体。

### M1 的注入约定

controller 的 `POST /api/assistant/plan` 这样接：

```python
from app.services.assistant_llm import client_from_env

plan = assistant.generate_plan(description, data_dir=..., client=client_from_env())
```

`client_from_env()` 返回 `None` 时，`assistant.generate_plan` 走 deterministic，
不读环境、不发起调用。controller 不需要自己判断 key。

GUI 徽章的 `data-assistant-available` 也由 `client_from_env() is not None` 决定，
有 key 才显示 `1`。