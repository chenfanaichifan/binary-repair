# Member 2 须知 · 图形界面（GUI）

> **汇总自**：项目文档集 2026-10-15 版 —— `research-BinaryRepair.pdf`、`PRD-BinaryRepair-MVP.pdf`（v1.0）、`TechDesign-BinaryRepair-MVP.pdf`（v1.0）
> **范围**：只汇总 GUI 分工需要知道的内容，不替代原文档；每条标注出处，冲突以原文档为准
> **版本**：2026-10-18 · 维护：Member 2
> **建议入库位置**：GitHub 仓库 `docs/member2-gui-notes.md`
> **团队分工**：2026-10-18 团队决定 —— 成员 1 控制器/契约（卸掉集成测试后专注提案）、成员 2 三页（你，独立）、成员 3 样本+VM（受 VM 阻塞，provenance 先纸上）、成员 4 验收规则+三套测试（独立，反哺所有人）、成员 5 DeepSeek 适配器+schema（部分独立）。本文档以该分工为准。

---

## 0. 30 秒版本

你是 **Member 2 — Graphical interface**。负责三个页面：**setup/review（建任务+复核契约）→ progress/comparison（双路线进度与对比）→ evidence/export（证据与导出）**。技术栈是 **FastAPI + Jinja2 服务端渲染 + 2 秒轮询**，不是前后端分离。下周交付物是"**能跑通的本地浏览器流程 + 真实的状态标签**"，不要求本周真的修复成功。总工时 5 人时（1h 基础 + 3h 三屏 + 1h 复核），提案约 10-22 截止。

**你这条路是独立的**：不用等 VM（成员 3）、DeepSeek（成员 5）或真实样本，只要拿到契约 API 和 fixture JSON 就能并行开工；但结论语义（什么算通过、六类 outcome 怎么判）以成员 4 的验收规则和 PRD 为准，不能自己发明。

---

## 1. 你的角色、时间与交付物

| 内容 | 出处 |
|---|---|
| 角色行：`2 — Graphical interface`；`1 h foundations; 3 h setup/comparison/evidence screens; 1 h review`；结果：**Working local browser flow with truthful stage labels** | TechDesign §14 下周 25 人时计划 |
| 每人每周 5 小时，合计 25 人时/周（含学习、复核、集成、演示准备） | TechDesign §1 |
| 本周团队目标是"垂直切片"：建任务 → 哈希/筛查 ELF → 记录复核过的契约 → 显示真实分析/候选结果 → 双路线状态 → 导出如实标注的部分报告 | TechDesign §14 |
| **Route A 真正落补丁、Route B 语义不变往返是本周 stretch，不假设完成** | TechDesign §14 |
| 下周演示（进度演示）定义：可运行的本地 GUI + **部分完成**的修复流水线，**未完成阶段必须可见**；具体日期待定 | TechDesign §1 |
| 如果隔离/样本环境吃掉了时间：**保留 GUI 与验收引擎可用**，用明确标注的 synthetic 开发数据，展示真实 blocker，执行保持不可用；**不要在宿主机上跑二进制**；历史结果只能作为带输入哈希/日期的 replay 展示 | TechDesign §14 |
| 提案截止：2026-10-15 起一周，约 **10-22**（具体时间与格式待定） | PRD 概览 |

**一句话责任边界**：你保证"用户在浏览器里看到的一切是真实的、可追溯的、状态语义正确的"；不负责让补丁真的打成功（那是成员 1/3/4/5 的链路）。

### 1.1 团队分工（2026-10-18 团队决定，非文档原文）

| 成员 | 负责 | 独立性 | 对你的含义 |
|---|---|---|---|
| 成员 1 | 控制器 / 契约 | 独立；**卸掉集成测试后专注提案** | API 契约仍是你的上游；集成测试不再由他兜，归属要当面确认 |
| **成员 2（你）** | **三个页面** | 独立 | 只依赖契约接口与数据形状，不等 VM / DeepSeek / 真实样本 |
| 成员 3 | 样本 + VM | 受 VM 阻塞；**provenance 先在纸上做** | 你先按 agreed fixture JSON 做界面，provenance 字段等他的表出来再接 |
| 成员 4 | 验收规则 + 三套测试 | 独立，**反哺所有人** | 你的状态标签与结论展示必须跟他的验收规则一致；负例与测试数据可直接复用 |
| 成员 5 | DeepSeek 适配器 + schema | 部分独立 | 你展示候选状态与 AI 用量；schema 变更要他提前通知你 |

**"独立"的正确用法**：可以并行开工，但界面上的判定语义必须来自成员 4 的验收规则与 PRD，不能自己发明一套"看起来对"的状态。

### 1.2 协作契约：你收到什么 / 交付什么

| 方向 | 对象 | 具体内容 | 何时要 |
|---|---|---|---|
| 收 | 成员 1 | API 路径与字段、状态枚举、错误码（409/422/413）、idempotency、契约 revision/hash 语义 | 开工前 30 分钟对齐 |
| 收 | 成员 4 | 六类 outcome 判定规则、obligations 结构、`not_run` 语义、三套测试划分与负例数据 | 做 status / evidence 屏之前 |
| 收 | 成员 3 | fixture JSON、provenance 字段（输入哈希/来源/构建信息）、wrong-architecture 错误样例 | 做 setup 屏时 |
| 收 | 成员 5 | attempt 状态字段、model call usage 是否可得（不可得就标 unavailable） | 做 comparison 屏时 |
| 给 | 成员 4 | 稳定的 DOM 标识（建议 `data-testid`）、三屏状态截图、GUI 旅程 e2e 用例 | 他写 GUI/验收测试时 |
| 给 | 成员 1 | 前端对 API 的真实需求与字段缺失问题 | 联调时 |
| 给 | 全队 | 三屏截图、5 分钟演示脚本、提案里的 GUI 章节素材 | 提案/演示前 |

---

## 2. 三个页面各自必须有什么

| 页面 | 必须显示 / 必须支持 | 出处 |
|---|---|---|
| **① Setup / Review** | 上传 Linux x86-64 ELF、缺陷描述、复现输入、有效输入测试、环境信息；显示输入 `original_sha256`；错误架构/损坏文件/缺必填在**执行前**给可执行提示；显示 binary summary、recovered function/location；**可编辑的安全契约**（有效输入域、禁止行为、非法输入应有行为、假设）；复核者确认；两条路线引用**同一** original hash + 已复核契约；原始源码不是输入 | PRD F1；TechDesign §7 |
| **② Progress / Comparison** | 一个 job 的两条路线并排卡片（含部分失败/不成功）；每条路线独立阶段指示；状态用文字+图标+颜色；显示 changed/added regions、测试计数、验证结果、兼容结果、耗时、人工介入、AI 用量（拿不到标 unavailable）；取消；浏览器刷新不丢状态；长分析时页面保持可响应；**未完成阶段可见** | PRD F5、UI/UX Direction；TechDesign §7 |
| **③ Evidence / Export** | 每个 attempt 的 obligations 与 scope（含边界/假设，必须放在结论旁边）；反例/失败原因；输入与候选哈希一致；HTML + JSON 报告；候选与证据下载（attachment、安全文件名）；失败/不确定产物标 **diagnostic candidate**；replay 说明；导出不代表生产批准 | PRD F4、F5；TechDesign §7、§13 |

> **三屏不是随便分的**：设计文档明确"操作者使用三个视图：setup/review、repair comparison、evidence/export"，模板服务端渲染，JS 只拉小状态更新。

---

## 3. 状态模型（最容易做错的地方）

### 3.1 phase 与 outcome 必须分成两条轴

**phase（阶段）**，Route B 多一个 `roundtrip`：

`draft` → `screening` → `awaiting_review` → `queued` → `analyzing` → `generating` → `applying` → `validating` → `finished`（来源：TechDesign §6）

**outcome（结论）**，与 PRD 六类一致：

| 枚举值（代码用） | 含义 | 展示要求 |
|---|---|---|
| `success_within_scope` | 声明范围内所有必需检查通过 | 必须同时展示边界与假设 |
| `unsupported` | 能力/放置/接口超出支持条件 | 解释限制，**不能显示为成功** |
| `rejected` | 候选未通过必需检查 | 给原因，保留诊断证据 |
| `inconclusive` | 证据不足以确立必需性质 | 显示未解决的 obligation，**不能接受** |
| `error` | 工具/服务失败 | 显示阶段与原因，保留已完成证据 |
| `cancelled` | 操作者取消 | 停止后续工作，如实标注保留的证据 |

### 3.2 三条铁律

1. **`not_run` ≠ `passed`**：缺测/未实现的检查记录为 not_run，界面上绝不能显示成通过。
2. **phase 与 outcome 分开显示**：阶段跑完不等于结论成功，反之亦然。
3. **不编造进度百分比**（文档原话：Never use fabricated progress percentages）。用阶段+事件+计数，不用假进度条。

### 3.3 批准（approval）绑定与失效

approval 绑定：original hash、contract revision、test-manifest hash、patch policy、environment profile、verification scope。**任何一项被编辑，approval 立即失效，必须新开 run**，旧 run 保留。

GUI 影响：契约保存后显示新 revision/hash；`approve` 带精确期望哈希，**stale 值返回 409**，界面要提示"契约已变更，请重新复核"，不能静默重试。

### 3.4 实现覆盖率 ≠ 修复结论

下周演示允许没有通过的候选，但必须能显示"哪些阶段真的实现了"。这两件事在界面上要分开呈现（TechDesign §9 末段、§14）。

---

## 4. GUI 消费的 API（只碰这些）

来源：TechDesign §7 Planned API surface。

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/jobs` | multipart 上传 ELF + 结构化测试清单 + 缺陷信息；返回 job ID 与 original hash |
| POST | `/api/jobs/{id}/analysis` | 排队做筛查与二进制分析；202 + run/task id |
| GET | `/api/jobs/{id}` | 摘要、当前契约、phases、capabilities、outcomes |
| PUT | `/api/jobs/{id}/contract` | 提交校验过的契约体 + expected revision；返回新 revision/hash |
| POST | `/api/jobs/{id}/approve` | 带精确的 input/contract/manifest/scope 哈希；stale → 409 |
| POST | `/api/jobs/{id}/runs` | 已批准 revision + idempotency key；两条路线入队；202 |
| GET | `/api/runs/{id}/events?after=sequence` | 有界增量事件 + 当前摘要（轮询用） |
| POST | `/api/runs/{id}/cancel` | 幂等取消请求 |
| GET | `/api/attempts/{id}/evidence` | obligations、scope、计数、changed regions、artifact IDs |
| GET | `/api/artifacts/{id}/download` | 仅注册过的普通文件；attachment + 安全文件名 |
| POST | `/api/runs/{id}/exports` | 生成确定性报告包；返回 artifact ID |

**错误码语义**（界面要给对应提示，不要统一弹"出错了"）：

- `422` 结构化输入非法 · `413` 超出大小限制 · `401/403` 会话或 Origin 失败 · `404` 对象不可用 · `409` stale approval / 非法状态迁移
- 每个响应/错误带 **correlation ID**；**绝不把 traceback 或带密钥的 provider 响应回显到浏览器**
- 排队的任务"能力不支持"要在 job evidence 里表达，**不能靠 HTTP 200 暗示修复成功**

**测试清单（manifest）约束**：只能是参数数组、stdin artifact ID、期望 return/stdout/stderr、可选的允许输出文件；**不能**包含任意宿主命令、shell 脚本、不受限文件路径。GUI 上传表单不能留"自由命令"入口。

**轮询**：每 2 秒拉持久化事件/状态；长分析必须脱离请求线程（worker 进程），页面不能被阻塞。

---

## 5. 本地服务安全（硬要求，不是加分项）

来源：TechDesign §11、§12。下周骨架阶段就要落地，后面补很贵。

- 只绑 `127.0.0.1`
- launcher → browser 的**随机一次性 session token** 引导；随后用 `HttpOnly; SameSite=Strict` 会话 cookie；**从地址栏移除 token、不记日志、拒绝复用**
- 校验 Host 与 Origin；状态变更请求要求 CSRF token
- **禁用宽松 CORS**；本地 HTTP，**不要宣称传输加密**，也不要暴露到远程
- 模板自动转义 + `DOM textContent` 处理不可信输出；静态资源用限制性 CSP；`nosniff` + frame 限制
- 二进制/原始产物**强制下载**（attachment）
- 生成的证据 HTML 必须走可信模板渲染，**绝不把 worker 提供的 HTML 当活动内容展示**
- session/auth token 与 API key 不得出现在报告、浏览器 bundle、guest 环境、日志里
- 导出只打包**注册过的安全相对路径** + 独立生成的哈希清单，不打包整个 job 目录
- 失败/不确定产物标为 diagnostic candidate；**导出不是生产批准**

> 注意：localhost 也要防——恶意网页可以尝试请求本地服务。文档明确要求测试这一点。

---

## 6. UI/UX 硬要求（逐条可验收）

来源：PRD UI/UX Direction、TechDesign §7。

1. 重要限制放在**对应结果旁边**，不要集中塞到页面底部
2. 状态同时用**文字 + 图标 + 颜色**（不能只靠颜色区分）
3. 技术细节可展开，但主结论要一眼可懂
4. 两条路线易对比，但**不能暗示"补丁更小 = 更安全"**
5. 某个阶段失败时**保留已完成阶段的证据**
6. 长时间分析时浏览器导航保持可响应
7. 双路线都显示（包括部分成功/失败），各自有独立阶段指示与可访问状态标签
8. AI 用量/成本：拿得到就显示，拿不到标 `unavailable`（**不能写 0**，也不能编）
9. 界面上不允许出现"整体程序已证明安全""全局最小补丁""生产可用"这类宣称

---

### 6.1 语言规范（2026-10-18 团队决定）

- **界面（UI）**：允许中文 —— 标题、按钮、状态徽章、说明文字。
- **上传 / API / 导出数据**：一律英文 ASCII —— 缺陷描述、复现输入、环境、契约四项、
  任务字段、obligations、结论原因、变更区域、产物角色、导出 JSON。
- 服务端校验：非 ASCII 表单内容返回 `422`；前端提交前先拦截。
- 上传文件名转 ASCII 安全名，避免中文名进入导出数据。
- 测试守护：`/api/jobs/{id}` 与导出 JSON 扫描无中日韩字符；UI 页面仍为中文
  （`tests/test_language_policy.py`）。
- 好处：证据/报告可直接给英文语境的客户、队友和提案使用，不需要二次翻译。

---

## 7. 开发模式与数据真实性（演示的红线）

- 加一个**显式的 GUI-only 开发模式**：用 stored/synthetic 结果驱动界面，**页面必须明确标注**（如 "development fixture — execution disabled"）；该模式**永远不能产出 accepted-patch 证据**（TechDesign §12）
- API 默认**执行关闭**，直到隔离自检通过；GUI 要能显示"执行未启用"这种真实状态
- 哈希是**身份标识**，不是正确性或真实性证明——界面文案不要写"已验证"
- 下周可以没有成功候选，但**不能**把 fixture 结果说成真实修复，也不能在宿主机跑二进制来"让演示好看"

---

## 8. 测试与验收（自己验自己）

来源：TechDesign §13 GUI 行、§11 边界行；PRD 成功指标。

必须手过的 GUI 场景：

| 场景 | 期望 |
|---|---|
| Setup → review → start → compare → export | 完整走通，**不用终端** |
| 工作执行中 | 页面可响应、状态更新、不假死 |
| 取消 | 幂等、状态变 cancelled（或 error/termination_unconfirmed）、证据保留 |
| 浏览器刷新 | 状态不丢、不重建重复 job |
| 未完成阶段 | 可见且如实标注 |
| 负例 | wrong architecture / missing inputs / stale approval / 409 / 422 / 413 都有可读提示 |
| 本地边界 | 缺 session、跨源 POST、导出路径穿越/符号链接被拒 |

工具：应用存在后用 **Playwright Python** 跑关键浏览器旅程（TechDesign §13）；提交前渲染三屏，检查状态与错误态可读性再合并。

PRD 成功指标里与你直接相关的两条：
- **GUI 旅程**：一次完整 setup → review → repair → compare → export，操作者不用终端（环境准备可以要技术操作）
- **拒绝准确率**：所有定义的 unsupported/error/inconclusive 场景都得到正确标签

演示脚本（5 分钟建议）：建 job（显示哈希）→ 复核契约（改一下再保存，展示 revision/hash 变化）→ 启动 → 双路线状态 → 一条失败/一条未完成 → 证据页（obligations/scope/哈希）→ 导出（HTML+JSON）→ 明确说"导出不代表生产批准"。

---

## 9. 5 小时怎么排

来源：TechDesign §14 你的分配行，加上团队垂直切片目标。

| 时段 | 做什么 | 产出 |
|---|---|---|
| 0–1 h（基础） | 和成员 1 敲定 API 契约与状态枚举；跑通/建出 `app/main.py`、`app/templates/`、`app/static/` 骨架；理解三屏与六类 outcome | 骨架能起、能建 job、能轮询 |
| 1–2 h | Setup/Review 屏：上传、哈希、执行前校验、契约编辑、approve（含 409 处理） | F1 走通（无终端） |
| 2–3 h | Progress/Comparison 屏：双路线卡片、阶段指示、状态标签、取消、刷新恢复、未完成可见 | 能如实对比两条路线 |
| 3–4 h | Evidence/Export 屏：obligations/scope、bounds、changed regions、下载、HTML+JSON、diagnostic 标注 | F5 走通 |
| 4–5 h（复核） | 按第 8 节场景手工回归 + 三屏截图 + 1 页 GUI 说明给提案人 | 演示可跑 + 提案素材 |

> 时间不够时的优先级：骨架 → setup → progress → evidence（最小可用）。evidence 可以只做摘要 + 下载，不做花哨排版。

---

## 10. 依赖与对接

| 依赖 | 找谁 | 需要拿到什么 |
|---|---|---|
| API 契约、job 生命周期、跨屏字段 | 成员 1（集成/提案） | 字段名、状态枚举、409/422 语义、idempotency |
| 上传/哈希/架构筛错 | 成员 3（binary/sample） | 真实 fixture 或可用的筛查接口与错误码 |
| evidence 数据结构 | 成员 4（验收规则 + 三套测试） | obligations、scope、counts、changed regions、V0–V5 摘要、六类 outcome 判定规则 |
| 测试边界 | 成员 4（主）+ 你（GUI e2e） | 验收规则测试、负例/安全测试由他主写；GUI 旅程 e2e 由你写；集成测试归属当面确认（成员 1 已卸下） |
| 双路线阶段/结论、AI 用量 | 成员 5（AI/Route B） | attempt 状态、usage 是否可得 |

**最大的依赖是 API 契约**——先花 30 分钟和成员 1 对齐，不然三屏字段会反复改。

### 10.1 "三套测试"与你的关系

团队分工里成员 4 负责"验收规则 + 三套测试"并反哺所有人。按 TechDesign §13 的测试分组，和你最相关的是：

- **验收规则测试**（acceptance / identity-state）：决定 outcome 怎么判 → 直接决定你界面上的标签与颜色，**先读规则再做状态 UI**
- **负例 / 安全测试**（wrong architecture、stale approval、provider failure、budget exhaustion……）：正是 setup 屏错误提示的素材，向他要清单
- **GUI / replay 测试**（Setup→review→start→compare→export、取消、刷新、未完成阶段可见）：这是你的 e2e，按 `data-testid` 约定写 Playwright

开工第一天就把"谁写 `tests/e2e/test_gui_journey.py`"写死：**你写、成员 4 审**。这样既满足"验收方独立于实现方"，又不重复劳动。注意"三套"具体是哪三套按你们口头约定为准，以上是按文档 §13 的合理对应。

---

## 11. 范围护栏（明确不做）

来源：PRD 范围外、TechDesign 选型对比。

- 不做 React/前后端分离、不做 SSE/WebSocket（2 秒轮询足够）
- 不做多用户/登录/OAuth/远程访问/企业授权
- 不做移动端优化
- 不编造进度百分比、不把 fixture 数据当真实结果、不在宿主机跑二进制
- 不为了实现方便削弱验收规则（文档：agent/实现不得为了让测试变绿而弱化测试或删除验证 gate）
- 不宣称整体正确性、全局最小补丁、生产就绪

---

## 12. GitHub 交付约定（团队约定，供参考）

> 你的产物要进 GitHub。下面是按文档结构整理的落库方式，具体以团队仓库为准。

### 12.1 建议仓库结构（文档 §12 布局，标出你的文件）

```
binaryrepair-mvp/
├─ app/
│  ├─ main.py                  ← 你
│  ├─ api/                     ← 你（现有路由壳）
│  ├─ templates/
│  │  ├─ setup.html            ← 你
│  │  ├─ comparison.html       ← 你
│  │  └─ evidence.html         ← 你
│  ├─ static/
│  │  ├─ css/app.css           ← 你
│  │  └─ js/poll.js            ← 你
│  ├─ domain/                  ← 成员 1（契约/schema/状态枚举）
│  ├─ services/                ← 成员 1（job controller/导出）
│  └─ db/                      ← 成员 1
├─ workers/                    ← 成员 3/4/5
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  └─ e2e/test_gui_journey.py  ← 你（Playwright）
├─ fixtures/public/            ← 成员 3（公开样本）
├─ docs/
│  ├─ member2-gui-notes.md     ← 本文件
│  └─ gui-screens/             ← 截图
├─ var/jobs/                   ← 运行时产物，**不进仓库**
├─ pyproject.toml
├─ .gitignore
└─ README.md
```

测试归属：`tests/unit`、`tests/evals` 归成员 4；`tests/integration` **待确认**（成员 1 已卸下，建议由成员 4 接）；`tests/e2e` 归你。两边都不要为了让测试变绿而改测试或删验证 gate。

### 12.2 提交内容边界

**可以提交**：源码、模板、CSS/JS、测试、文档、公开样本 fixture、截图（注意体积）、`docs/` 里的说明。

**绝对不能提交**：
- 任何 API key / `.env`（只提交 `.env.example`）
- 客户二进制或机密派生内容（PRD 数据边界：客户物默认留本地，外传需显式授权；前期材料也写明不上传 GitHub）
- VM 镜像、大产物、`var/jobs/` 运行时目录、日志中出现密钥的内容
- 三份 PDF 属于团队内部文档：如果要入库，放 `docs/reference/` 并确认团队同意；否则用 README 链接说明版本，靠哈希（`SHA256SUMS.txt`）追溯

### 12.3 `.gitignore` 起步片段

```gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.mypy_cache/
.env
var/jobs/
*.log
node_modules/
.DS_Store
```

### 12.4 分支 / PR / commit

- 每屏一个 PR：`feat(gui): setup+review view`、`feat(gui): comparison view`、`feat(gui): evidence+export view`
- PR 描述里贴：验收项（对应本文件第 2、6、8 节）、三屏截图、手工回归记录
- commit 示例：`feat(gui): add status polling and truthful phase labels`、`docs(gui): add member2 must-know`
- 提交前自查：`pytest`（能跑的层级）、`ruff check .`、三屏手工检查

### 12.5 README 必须写清

1. 本地如何启动（`uvicorn app.main:app --host 127.0.0.1 --port 8000` 一类的真实命令）
2. GUI-only 开发模式怎么开、会显示什么标注
3. 证据边界：什么算通过、什么只是 diagnostic、导出不代表批准
4. 三屏截图与一句话说明

---

## 13. 术语速查

| 术语 | 对你的意义 |
|---|---|
| **Contract（安全契约）** | 复核者确认的一套假设与要求：有效输入域、禁止行为、非法输入应有行为、环境假设；GUI 里可编辑、有 revision 和 hash |
| **Obligation** | 一条必需检查（required/not required），结果 passed/not_run/inconclusive 等；证据页的核心数据 |
| **V0–V5** | 验证阶梯：身份/前置 → 结构/放置 → 接口/兼容 → 具体行为 → 有界符号 → 可复现；证据页按层展示摘要 |
| **Route A / Route B** | A=直接改机器指令；B=恢复 C → 编译 → 回填；两条都必须成功才算 MVP 成功 |
| **diagnostic candidate** | 失败/不确定产物，可下载但明确标为诊断用 |
| **bounded verification** | 在声明的域/模型内检查性质，**不是**整体程序安全证明；界面必须带 bounds/assumptions |
| **roundtrip** | Route B 的"语义不变往返"前置门；只有 phase，不是可选装饰 |
| **not_run** | 未执行/未实现，不能算通过 |
| **idempotency key** | 防重复启动/重复计费；GUI 双击不能生成两个 run |

---

## 14. 出处索引（需要看原文时）

| 主题 | 文档 | 位置 |
|---|---|---|
| 三视图、计划 API、错误码 | TechDesign | §7（约 p.7–8） |
| phase/outcome、approval 绑定、幂等、取消 | TechDesign | §6（约 p.6–7） |
| 验证阶梯 V0–V5、验收规则、符号验证边界 | TechDesign | §9（约 p.10–11） |
| 本地服务安全、产物处理 | TechDesign | §11（约 p.13–14） |
| 目录布局、开发命令、配置名、dev mode | TechDesign | §12（约 p.14–15） |
| 测试场景、导出包内容、replay | TechDesign | §13（约 p.15–16） |
| 你的分工行、垂直切片、时间不够的退路 | TechDesign | §14（约 p.16–17） |
| F1/F5 验收标准、六类结论、UI/UX 方向、成功指标 | PRD | MVP Features / UI/UX Direction / Success Metrics（约 p.2–6） |
| 数据与保密边界 | PRD | AI / Automation Scope、Constraints（约 p.7–8） |
| 为何不能宣称"证明了安全"、三条关键发现 | research | 第 1 节 Executive feasibility assessment |

---

*本文件是 GUI 分工的工作索引。文档本身是设计稿：命令未执行、代码未实现、数字是计划值；引用时保留"proposed / default / not measured"的限定。*
