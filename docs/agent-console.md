# 修复控制台（/agent）使用说明

> 归属：M2（GUI owner）。对应 Lead 87 号分配的 T7.4 / T7.5 / T7.6 / T8.4，T7.8 部分完成。
> 基线：`origin/post-final/host-importer-broker` @ `1da22ff`，工作分支 `member2/agent-console`。
> 本页只做 UI：不实现 planner、不调模型、不新增写接口、不判定修复结论。

## 一、怎么跑

```bash
# 项目根目录，使用项目虚拟环境
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# 然后打开启动时打印的带 token 地址（或先访问 /?token=... 建立会话）
```

| 地址 | 用途 |
|---|---|
| `/agent` | 真实模式。后端未提供引导计划时会**如实说明**，不假装有助手 |
| `/agent?fixture=1` | 全演示模式：占位 plan + 占位快照，**不会创建真实任务**，演示横幅常显 |
| `/agent?fixture=1&scenario=pending` | 演示「等待测试机回传」：诊断区是占位，不渲染 `not_run` |
| `/agent?fixture=1&scenario=success` | 演示成功：diff、义务全 passed、`llm` 徽章 + 降级横幅 + model/token |
| `/agent?fixture=1&scenario=failure` | 演示失败：原因卡 + 建议卡，`not_run` 逐字显示 |
| `/agent?plan=fixture` | **引导用占位 plan，但创建任务走真实 `POST /jobs`**，之后真实轮询 |
| `/agent?job=<任务ID>` | 按 URL 恢复某个任务，2 秒轮询，页面隐藏时降为 8 秒 |

## 二、界面结构

```
顶栏：助手模式徽章 · 任务 id · 轮询心跳
降级横幅：仅在后端给出 fallback 时出现
视图：对话引导 / 结果与证据 / 切换到表单（旧页面保留）
主列：终端流（助手消息、可展开工具块、问题卡、上传卡、复核卡）+ composer
右栏：当前步骤 · 执行状态 · 阶段 · 契约 · 助手调用元数据 · 产物
```

- **工具块**默认折叠为一行摘要，点击展开看字段与原始 JSON。
- **composer**：`Enter` 发送、`Shift+Enter` 换行；`/skip` 用默认答案、`/status` 看状态、`/restart` 重开引导，演示模式下还可用 `/fixture fresh|pending|success|failure` 切场景。
- **上传**：本机 `FileReader` 读取并显示真实读取进度，`crypto.subtle` 算 SHA-256；不是 ELF 头时给警告但不阻断（演示样本仍可提交）。**真正的上传发生在你点击「创建任务」时**，用 XHR 显示真实上传进度。
- **复核卡**：每一项都能点「修改」回到对应步骤，已填内容保留。

## 三、诚实性规则（有测试锁死）

1. 结论只读 `verdict`，前端不推断、不聚合；没有 verdict 时显示「尚无 verdict（等待验收引擎）」。
2. 义务结果**逐字**渲染后端取值，`not_run` 不翻译、不美化。
3. `execution.receipt_pending` 为真时，诊断区只显示「等待执行结果回传」占位，**不渲染 `not_run`**。
4. 模式徽章如实显示 `scripted v1` / `llm`；后端没给就显示「后端未提供」。
5. 发生降级时**必须**出现降级横幅；model/token 没给就显示「未提供」，不编数字。
6. 未登记的 `reason_code` 显示「未知原因 + 请把 status.json 发给 M1/M4」，不猜原因。
7. 创建任务只能由用户点击触发；助手不发起运行、不写 verdict。

## 四、fixtures 的边界

`app/static/js/agent.fixtures.js` 是**开发期占位数据**，文件头已标注：

- 字段名与枚举值以 `docs/interfaces/execution-bridge-v1.md` 和 M5 的 plan schema 为准，本文件不是接口依据。
- 渲染层只消费 `agent.js` 的 `normalize()` 输出；协议到位后只改 `normalize()` 与取数函数。
- 真实接口联调通过后应删除该文件。
- 其中所有 `default` 值都是 ASCII，因为它们会进入提交 payload。

## 五、测试

```bash
# 服务端：路由、会话/host 门、诚实性、越界扫描、语言策略、旧页面回归
.venv/Scripts/python.exe -m pytest tests/test_agent_console.py -q

# 核心回归
.venv/Scripts/python.exe -m pytest tests/test_agent_console.py tests/test_language_policy.py tests/test_status_honesty.py tests/test_smoke.py tests/test_security.py tests/test_verdict_view.py tests/test_export_bundle.py -q

# 浏览器（本机 Edge + CDP，无需下载 Playwright）
.venv/Scripts/python.exe -m pytest tests/e2e -q

# 截图（T7.8）
.venv/Scripts/python.exe tests/e2e/capture_agent_screens.py
```

本次实测：`test_agent_console.py` 16/16；核心回归 46 项全通过；`tests/e2e` 12/12（旧 7 + 新 5）。

**已知预存在失败（与本次改动无关，已用 stash 对照确认）**：`tests/test_evidence_endpoint.py` 5 项在基线上同样失败，报 `attempts/<id>.json` 文件不存在，属后端持久化问题，归 M1/M5，不在 M2 范围。

## 六、带标注截图（docs/screenshots/）

| 文件 | 标注 |
|---|---|
| `agent-guided.png` | 对话引导首屏：终端流 + 上传卡 + composer + 右栏状态面板，演示横幅常显 |
| `agent-pending.png` | 等待回传：诊断区为占位文案，**没有** `not_run` 列表；右栏执行状态为 `awaiting_ingest` |
| `agent-failure.png` | 失败：原因卡（`worker_env_missing`）+ 建议卡（负责方与可否重试），义务 `not_run` 逐字 |
| `agent-success.png` | 成功：`llm` 徽章 + 降级横幅 + model/token，修改前后给 unified diff 与双哈希 |

## 七、还没做 / 等别人

| 事项 | 等谁 |
|---|---|
| 引导计划来自真实 `GET/POST /api/jobs/{id}/assistant` | M5 T8.1（plan）+ M1 T8.1（端点，11-18） |
| 右栏执行状态直读 `execution.status` 标准枚举 | M1 T7.1 + execution-bridge-v1 正文 |
| 时间线接入真实 attempt / run 节点 | M1 T6.2a、M5 T6.1 |
| 结果屏接入真实 `analysis` / `comparison` | M5 T7.2、M1 T6.3 |
| 旧页面重定向到 `/agent`（T7.8 收尾） | 需与 M4 的 e2e 口径一起改，**暂未启用**，避免旧验收断裂 |
| `docs/prototype/agent-console.html` 原型评审（T7.0，11-06 截止） | Lead 提供原型文件 |
