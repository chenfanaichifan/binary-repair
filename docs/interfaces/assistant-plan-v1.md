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
