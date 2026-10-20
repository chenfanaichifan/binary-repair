# BinaryRepair MVP · GUI 骨架（Member 2）

这是「项目 11：AI 驱动的二进制漏洞自动修复与正确性验证」的**图形界面第一步**：
把三个页面（新建/复核 → 进度对比 → 证据导出）跑起来，并用**明确标注的演示数据**
把状态语义和字段固定下来。真实执行链路（VM、Route A/B、angr 校验）由其他成员接入。

> **重要**：当前所有阶段推进和结论都是演示 fixture，页面顶部有横幅标注。
> 它不是修复结果，不能当作“补丁已验证”的证据。接真实数据后横幅会消失。

## 0. 语言规范（重要，2026-10-18 团队决定）

- **界面（UI）允许中文**：标题、按钮、状态徽章、说明文字都是中文。
- **上传 / API / 导出数据一律英文 ASCII**：缺陷描述、复现输入、环境、契约四项、
  obligations、结论原因、变更区域、产物角色、导出 JSON 全部英文。
- 服务端校验：非 ASCII 表单内容返回 `422`；浏览器在提交前也会先拦截。
- 上传文件名自动转成 ASCII 安全名（例如 `样本.bin` -> `sample.bin`），避免中文进入导出数据。
- 有测试守护：`/api/jobs/{id}` 与导出 JSON 扫描不到中日韩字符，UI 页面仍为中文
  （见 `tests/test_language_policy.py`）。

## 1. 快速开始（Windows）

前提：已经装好 Python 3.13（本机已装），并在项目目录里有 `.venv` 虚拟环境。

在**项目目录**打开终端（PowerShell 或命令提示符），任选一种：

```powershell
.\start.ps1          # PowerShell 一键启动
```

```bat
run.bat              :: 双击也可以
```

或者手动：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
```

然后浏览器打开 **<http://127.0.0.1:8123>**（只监听本机，别人访问不到）。

如果 `.venv` 不存在（换电脑/重装后）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 2. 你会看到什么（第一次演示流程）

1. 打开后进入 **① 新建任务与契约复核**：选择任意文件当样本（演示只算哈希）、填缺陷描述、看/改安全契约；
2. 点「登记任务并进入复核」→ 进入 **② 进度与对比**：两条路线并排，此时都是“草稿”；
3. 点「批准并启动（演示）」→ 阶段每约 1.2 秒推进一次，页面每 2 秒自动刷新；
4. 结束后：Route A 显示 **被拒**（有效输入回归失败），Route B 显示 **不确定**（有界符号预算用尽）——
   这是故意设计的，用来演示“未完成 / 未通过不能被显示成成功”；
5. 点「查看证据」→ **③ 证据与导出**：V0–V5 义务、范围、产物哈希、诊断候选标注、导出 JSON；
6. 「导出证据 JSON」下载的文件里同样带 `demo: true` 和“导出不代表生产批准”的说明。

## 3. 三个页面和需求的对应

| 页面 | 对应需求 | 本骨架已实现 |
|---|---|---|
| ① `setup.html` | PRD **F1** 图形化建任务与契约复核 | 上传、SHA-256 登记、缺陷/测试/环境输入、可编辑契约、执行前校验（空文件 422、超大 413） |
| ② `comparison.html` | PRD **F5**、UI/UX Direction | 双路线并排、阶段独立指示、六类结论徽章、测试/验证/兼容/耗时/人工介入/AI 用量、取消、轮询 |
| ③ `evidence.html` | PRD **F4/F5** | V0–V5 义务表、范围与假设、产物哈希、diagnostic candidate 标注、导出、replay 说明 |

状态语义按技术设计实现：`phase`（draft/screening/analyzing/roundtrip/generating/applying/validating/finished）与
`outcome`（success_within_scope/unsupported/rejected/inconclusive/error/cancelled）**两条轴分开显示**；
`not_run` 不会被算成通过。

## 4. 目录结构

```
binaryrepair-mvp/
├─ app/
│  ├─ main.py            # FastAPI 入口、三屏路由、状态接口、导出接口
│  ├─ demo.py            # 演示数据（阶段推进、义务 V0–V5、产物）；接真实后端时替换这里
│  ├─ i18n.py            # 中文显示标签（只给模板/前端用，不进入 API 与导出）
│  ├─ templates/         # base + 三屏模板（Jinja2）
│  └─ static/            # css/app.css、js/poll.js
├─ tests/test_smoke.py   # 冒烟测试（三屏 200、Host 校验、导出）
├─ fixtures/public/      # 只放公开样本（规则见该目录 README）
├─ docs/                 # 说明文档（含 member2 须知）
├─ var/jobs/             # 运行时产物，已在 .gitignore 中忽略
├─ requirements.txt
├─ start.ps1 / run.bat
└─ README.md
```

## 5. 跑测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

覆盖：三屏可打开、Host 校验拒绝外部域名、建任务后哈希是 64 位、启动后阶段不再是 draft、
证据页含 V0 与 diagnostic candidate、导出带 attachment 且 `demo: true`、取消后状态是 cancelled；
另有语言规范测试：API/导出无中日韩字符、中文表单内容返回 422、中文文件名被转 ASCII、UI 仍为中文。

## 6. 常见问题

| 现象 | 原因 / 解决 |
|---|---|
| `uvicorn: command not found` | 不要直接敲 `uvicorn`，用 `.\.venv\Scripts\python.exe -m uvicorn ...` |
| 端口被占用 | 换端口：把命令里的 `8123` 改成 `8124` 等 |
| `无法加载文件 start.ps1，因为在此系统上禁止运行脚本` | PowerShell 执行策略限制：改用 `run.bat`，或执行 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 后重试 |
| 页面 403 | 用 `localhost` / `127.0.0.1` 打开；Host 校验会拒绝其他域名 |
| 装依赖很慢/失败 | 换镜像：`.\.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| 改了 `.py` 不生效 | uvicorn 没开自动重载，重启即可；开发可加 `--reload` |

## 7. 下一步（按依赖顺序）

1. **和成员 1 对齐 API 契约**：把 `demo.py` 的字段换成 `/api/jobs/{id}` 真实返回；页面与轮询逻辑不用改。
2. **从成员 4 拿验收规则**：六类 outcome 的判定、`not_run` 展示、负例清单；本页的徽章/义务表按他的规则校准。
3. **接成员 3 的 fixture 与 provenance**：上传校验（架构/格式）、来源字段。
4. **GitHub**：本目录已是独立仓库根目录，`git init` 后提交；提交前确认 `.gitignore` 生效（`.venv`、`var/jobs` 不会进库）。
5. 之后按 PRD F1/F5 补：契约 revision 与 409 stale approval、CSRF/session、真实导出包。

## 8. 保密与数据边界（必读）

- 只把**公开样本/自己构造的样本**放进 `fixtures/public/`；
- **不要**把客户二进制、机密派生内容、API key、`.env` 提交到 GitHub；
- 三份项目文档（PRD/研究/技术设计）属团队内部资料，入库前先问团队；
- 导出产物只用于评审，不代表生产批准。

## 9. 文档出处

- PRD（v1.0，2026-10-15）：F1、F4、F5、UI/UX Direction、Success Metrics
- TechDesign（v1.0，2026-10-15）：§6 状态与生命周期、§7 三视图与 API、§9 验证阶梯、§11 本地服务安全、§12 目录与 dev mode、§13 测试、§14 分工
- 分工与协作边界：`docs/member2-须知.md`（2026-10-18 团队分工版）

---

## Route B / AI candidate provider（Member 5）

与 GUI 并列的一条工作流，代码已在仓库根目录：

- [docs/route-b/README.md](docs/route-b/README.md) — DeepSeek 适配器、候选 schema v1、SQLite schema、Route B 可行性套件。
- [docs/route-b/02-member-5-candidate-provider.md](docs/route-b/02-member-5-candidate-provider.md) — `validate_candidate` / `may_leave_host` 契约与 typed provider failure。

```bash
pytest -q tests/test_ai_boundary_contract.py tests/test_provider_failures.py
python schemas/generate.py --check
python app/db/migrate.py --db var/app.db
```
