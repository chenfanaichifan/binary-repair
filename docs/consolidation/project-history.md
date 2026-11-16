# 项目历史还原（2026-10-15 → 2026-11-13）

> 作者：history-analyst（Team Lead 的 teammate）
> 任务书：`.tmp/team/task-history.md`
> 范围：项目 2026-10-15 至 2026-11-13 的历史（11-13 之后由 s1/s2 会话覆盖，不在本文范围）
> 输出：本文件；仓库与远端全程只读，未做任何 git 写操作

---

## 0. 证据口径与阅读说明

### 0.1 数据来源

| 类别 | 具体来源 | 说明 |
|---|---|---|
| 会话日志 | `.tmp/sessions/*.jsonl`（14 个早期会话；另含 s1/s2 两个重点会话不在本文范围） | 由 `~/.dsh/sessions/` 的 `session.v4.jsonl.zstd` 解压而来；引用格式 `[S:history-m1 seq 2054]` 指该会话事件 seq |
| 仓库 git | `binary-repair` / `binary-repair-gui`（同一 git 仓库的两个 worktree，本机只读查看） | 引用格式 `[git:132ad98]` |
| 会话产物 | 会话中生成的 docx/pdf/zip/bundle/SHA256SUMS，以及工作区现存活文件 | 引用格式 `[file:相对路径]` |
| 交付件 | `handoff/`、`WeChat-Share/`、`~/Desktop/BinaryRepair-archive-2026-11-12/` | 11-12 及之后工作区多次整理/归档 |
| CI | GitHub Actions run 号（来自会话内 `git ls-remote`/GitHub API 实查记录） | 标注 `[CI:run ...]`；本文未重新联网核对全部 run（写作时 GitHub API 被限流） |

### 0.2 会话清单（本文使用的证据源）

| 简称 | 会话标题 | session id | 时间范围 | 规模 | 主要内容 |
|---|---|---|---|---|---|
| history-m4 | M4 | 4f9a2f7d… | 2026-10-15 16:39 → 11-11 20:46 | 5,856 事件 | 10-15 REA 下载/安装；11-05 起被用户当 M4 角色使用 |
| history-mvp | 研究想法与MVP定义指导 | 4fbcfd05… | 2026-10-15 17:32 → 11-08 17:41 | 581 事件 | 项目起源、5 步工作流、两份 docx、11-08 花费统计 |
| history-m1 | M1、4、5、Lead | cb06ee4c… | 2026-10-18 16:49 → 11-11 21:58 | 26,453 事件 | 主线大会话：M5→M1/M4/M5/Lead 轮转；v1.2.1 发布收口 |
| m1-3342 | M1 | 3342aabf… | 11-05 22:03 → 11-07 22:20 | 10,260 事件 | M1 集成/t30/evidence API |
| lead-07d5 | Lead | 07d5319d… | 11-05 22:52 → 11-12 23:12 | 1,291 事件 | Lead 决策（126/131/132/Route A/B 原则） |
| m1-e442 | M1 partial 语义并入 canonical | e44273d9… | 11-06 16:05 → 16:30 | 1,043 事件 | partial/canonical 语义 |
| m1-3822 | M1任务：partial 与 canonical 关系 | 38221d41… | 11-06 16:10 → 16:26 | 986 事件 | 同上，独立复核 |
| t83-217a | 查询GitHub上传地址及T8.3说明 | 217a1378… | 11-06 18:00 → 21:40 | 1,595 事件 | T8.3 定义/重要性、6 分支 44 commit 383 文件、PDF 21 页 |
| deepworks | 迁移项目成果至DeepWorks平台 | 5a19b610… | 11-08 19:11 → 11-11 22:30 | 4,153 事件 | 滴普杯黑客松赛道 C、DeepWorks 四层迁移 |
| plan-svc | 计划服务未接通原因排查 | 190e48d8… | 11-11 22:20 → 11-14 15:48 | 18,756 事件 | 计划服务根因与修复；GUI 大改版、微信分享、ngrok、CGC、i18n |
| cgc | CGC 克隆用途与替代方案 | 04d75281… | 11-12 19:55 → 20:42 | 1,750 事件 | cb-multios 克隆、POV 重放、替代数据方案 |
| vm-pkg | 生成虚拟机任务压缩包 | 7c2cc0ef… | 11-12 22:52 → 11-13 16:59 | 5,854 事件 | Linux VM handoff v1→v7、评审往返 |
| fix-ci | Fix CI and AI review milestone | 336db26b… | 11-12 23:00 → 11-13 00:22 | 3,052 事件 | CI 假 success 事件、AI 复核三案、774c584/0fe9241 |
| v3-review | **结论：v3 的内容层面可以通… | ce323436… | 11-13 15:15 → 15:58 | 2,115 事件 | 通用二进制修复实现（v4 代码 + v5 包） |

另有 8 个空会话（10-22/10-23/11-06/11-09/11-12 打开未发消息）与 11-13 之后 s1/s2 两个重点会话（由其他人负责）。

### 0.3 证据标记与"未核实"规则

- 带 seq / commit / run / 文件路径的结论 = 可直接复核；
- 只由会话中"AI 生成报告"转述、且本机无法再核的（如 GitHub release 页面、远端 tag），标注 **未核实**；
- 数字一律照抄原始记录，不做四舍五入或推断；同一数字多口径并存时并列写出。

---

## 1. 项目起源：研究想法、MVP 定义、技术方案与目标演进

### 1.1 甲方与课程来源（2026-10-10 ~ 10-13 已有材料）

项目来自课程/竞赛提供的真实题目，编号 **项目 11**，来源 **华为**，负责教师 **杜长来**：

- `项目大纲.docx`（文件时间 2026-10-10）："AI 驱动的二进制漏洞自动修复与正确性验证"。背景：生成式 AI 与自动化攻击工具让漏洞发现/利用提速，传统"数周"级修复周期不匹配；ICT 与终端领域有 **1900 多个第三方二进制组件**，部分维护中断、版本多、无 SLA；目标是把修复从源码层延伸到二进制层，**把修复周期从数周缩短到小时级**。
- `项目介绍.pptx`（文件时间 2026-10-13）：给出 5 步系统流程（①漏洞分析/安全契约 ②修复逻辑生成 ③微型二进制补丁生成 ④二进制修改 ⑤自动校验）、两类技术路线（直接机器指令补丁 / 反编译局部 C 后重编译回填）、候选技术栈（Ghidra/angr/Capstone、LLM+RAG、Keystone/LIEF/LLVM、SMT+符号执行+差分测试）、预期成果与"第一版成功标志：补丁后二进制能运行、目标漏洞无法再触发、原有测试仍通过"。
- 两份材料在 11-12 归档后的位置：`~/Desktop/BinaryRepair-archive-2026-11-12/项目大纲.docx`、`…/项目介绍.pptx`。

> 证据：10-15 之后用户才进入 DSH 工作区；10-18 用户明确说"这是我们五人小组选择完成的小组任务" `[S:history-m1 seq 8]`。

### 1.2 2026-10-15：从"研究想法/定义 MVP"到三份 PDF

10-15 当天发生三件事：

1. **16:39-17:30 下载并接入 REA**（`github.com/morluto/rea`）。克隆 265 MB、初始化 5 个 submodule、nvm 安装 Node v24.18.0、全局装 `rea-agents@6.5.0`、注册到 DSH（207 个 MCP 工具），`rea doctor → healthy: true` `[S:history-m4 seq 42/75/221]`。
2. **17:32-17:56 "研究想法与 MVP 定义指导"**。用户把"rea 文件"误认为含 5 步流程的文档；AI 澄清：`rea/` 是 REA 开源仓库（其 agent 工作流是 7 步），真正的 5 步在 `项目介绍.pptx` 第 5 页与 `项目计划书.docx` 4.1 节；而"研究想法 + 定义 MVP"来自课程大纲 Stage 1-2（产出 Project proposal 与 MVP PRD）。随后拿到 `KhazP/vibe-coding-prompt-template` 的 5 步工作流：**Part 1 Research → Part 2 PRD/MVP → Part 3 Tech Design → Part 4 AGENTS 配置 → Part 5 Build**，每步有对应 prompt 文件（`part1-deepresearch.md` 等）与产出目录 `docs/`。
   - AI 在 10-15 先产出两份 docx：`01_研究想法_Research_Idea.docx`、`02_MVP定义_MVP_Definition.docx`，但判定"类型不对"（Part 1 应产出 research-request，Part 2 应产出 PRD），可作为 Part 2/3 素材 `[S:history-mvp seq 329/364/389/404]`。
   - 用户确认技术档位 **C（Somewhere in between）**，文件名主干 **BinPatch/BinaryRepair**；Part 1 的研究请求由用户自行执行（"Part 1 的研究请求由你自行执行"）`[S:history-mvp seq 404]`。
3. **20:48-20:49 三份 PDF 落盘**（会话之外由用户完成，10-18 会话把它们作为输入引用）：
   - `research-BinaryRepair.pdf`（667,090 B）
   - `PRD-BinaryRepair-MVP.pdf`（445,400 B）
   - `TechDesign-BinaryRepair-MVP.pdf`（668,884 B）
   - 同目录另有 10-20 生成的 `project_brief.pdf`、`tech_stack.pdf`、`testing.pdf`、`code_patterns.pdf`（各约 168-300 KB）。
   - 现位置：`~/Desktop/BinaryRepair-archive-2026-11-12/`（11-12 工作区整理时移出）。
   - 10-18 16:50 的用户消息一次性 @ 了这 3 份 PDF + `项目大纲.docx` + `项目介绍.pptx`，作为 M5 任务的输入 `[S:history-m1 seq 8]`。

> 结论：**项目在 10-15 完成"立项"**——研究想法、MVP 定义、技术方案三份 PDF 同日产出；git 仓库的 `Initial commit` 也是 2026-10-15 18:40:09 +0800（`132ad98`，作者 `chenfanaichifan <2350776866@qq.com>`）`[git:132ad98]`。

### 1.3 MVP 定义（"一个人、一个样本、一条命令、三个判据"）

`02_MVP定义_MVP_Definition.docx` 的核心 `[S:history-mvp seq 329]`：

- **输入契约写死**：target / poc / vuln / regress / contract；**输出契约写死**：patched / patch.json / verdict.json / apply_log.json；原则是"先写 contract.yaml 再写补丁代码"。
- **达成线写死**：≥1 个自建 x86-32 栈溢出样本上 S1、S2、S3 全过 + S5 干净 Docker 可复现 = MVP 达成；多样本成功率、跳板、符号执行、路线二、规模化 **明确不算 MVP**。
- **MoSCoW 划界**：Must = M1–M6 + CLI；Should = 跳板/代码洞穴、第二条策略、S4/S6 度量；Won't = 反编译路线、自动定位、符号执行、GUI、多架构。
- 5 分钟演示脚本、10 周时间盒、四级降级预案。
- 研究想法文档的四个支点：A 把不可判定等价性降级为"契约 C + 回归集 T"上的可判定问题；B 修复语义种类远少于漏洞种类（模板×站点×算子×拒绝方式）；C 硬约束在模板化空间下变成剪枝器；D 系统可靠性由**验证器的误接受率**决定。假设 H1–H4、RQ1–RQ5、风险 F1–F4。

### 1.4 技术方案（PDF/whitepaper）与后续工程化版本

| 文档 | 日期/大小 | 内容定位 |
|---|---|---|
| `research-BinaryRepair.pdf` | 10-15 20:49 / 667,090 B | Part 1 研究结果（研究请求由用户执行） |
| `PRD-BinaryRepair-MVP.pdf` | 10-15 20:48 / 445,400 B | Part 2 MVP PRD（目标用户、输入输出、Must/Should/Won't、验收 S1–S6） |
| `TechDesign-BinaryRepair-MVP.pdf` | 10-15 20:49 / 668,884 B | Part 3 技术设计（信任边界 Host/一次性 Ubuntu VM、候选 schema、Gate 设计、两条路线） |
| `BinaryRepair_MVP_要求_差距_解决方案_2026-11-03.pdf/.docx` | 11-03 / 约 444 KB | 11-03 的完整要求-差距-解决方案（14,652 字符） |
| `BinaryRepair_五成员任务分配与项目完成计划_2026-11-03.pdf/.docx` | 11-03 / 约 444 KB | 五成员分工 + 20 项任务 + 5 天计划（10,771 字符） |
| `BinaryRepair-2026-11-06-GitHub上传地址与T8.3说明.pdf` | 11-06 / 约 753 KB、21 页 | 当天 6 分支/44 commit/383 文件地址 + T8.3 说明 |
| `AI-Assisted-Progress-2026-11-06.md` | 11-06 / 29 KB、约 4,650 词 | 纯英文当日进展报告（0 个中文字符） |
| `handoff/…/FINAL-LINUX-VERIFICATION.md` | 11-13 / 18 KB | v7 交付件最终检验报告（Linux VM 权威复跑） |
| `方法建议_大模型二进制漏洞修复Agent_20261113(1).md` | 11-13 / 18.8 KB | 外部方向建议：范围矩阵、SCRIBE 反编译-重编译范式、PoC 失效级验证、先修证据链 |

工程实现上，技术方案从 10-18 起被落成具体接口（`AGENTS.md`、`docs/`、`app/`），关键抽象后来固定为：**候选 schema v1（Route A 12 字段 / Route B 加 2 字段共 14）**、**安全契约 SecurityContract v2/v3**、**V0–V5 验证阶梯**、**六种 outcome**、**Host/guest 信任边界（host 永不执行上传二进制）** `[S:history-m1 seq 2054 checkpoint]`。

### 1.5 目标演进（5 个阶段）

| 阶段 | 时间 | 目标 | 关键转折 |
|---|---|---|---|
| P0 立项 | 10-15 | 完成课程/华为题目的研究想法、MVP、技术设计三份 PDF | 5 步工作流 + 3 份 PDF + 初始化 git |
| P1 五人原型闭环 | 10-18 → 10-31 | 按 TechDesign 落地：两条路线 + 共享验收引擎 + GUI + 证据；跑通确定性闭环 | M1-M5 分工；`main` `1250169`（83 tests）→ Gate3 批准 `0b3b51e4` → Gate4/Gate5A |
| P2 公开 MVP + 通用性（T8） | 11-03 → 11-07 | 公开 curated MVP、T8.1/T8.2/T8.3（第二类缺陷、AI planner、通用修复计划） | 公开仓库 `0070103f` / v1.0.0；T8.3 于 11-07 以 CWE-416/124 `success_within_scope` 收口 |
| P3 产品化 + 发布 | 11-08 → 11-12 | 把工作台做成可交付产品：GUI 大改版、真实 DeepSeek、v1.1.x/v1.2.0/v1.2.1 公开版本、DeepWorks/微信分享 | 11-11 v1.2.1 stable `148d236`；11-12 微信分享 + ngrok/LAN 演示 + CGC |
| P4 通用二进制修复 + Linux handoff | 11-12 → 11-13 | "任意二进制"落到 格式×架构×漏洞类 矩阵；打包给有 Linux VM 的同学 | v4 代码 `a6226cb`、v5 包、Linux VM v7 包（950/943/7/0） |

---

## 2. M1–M5 成员里程碑

> 说明：项目中的 "M1–M5" 是**五名成员的角色编号**（M1 宿主后端、M2 GUI、M3 guest、M4 验证、M5 契约/AI 层），不是"里程碑 1–5"。Lead 是第六个角色（独立批准，不计入五名成员），另设 VMer（VM 操作）。任务编号体系为 **T0–T8**（T6 端到端桥接、T7 产品流程、T8 AI 驱动）。

### 2.0 角色与任务体系（11-03 record 87）

来源：`docs/handoffs/87-lead-task-assignment-2026-11-03.md`（`delivery/all-hands-2026-11-07` 分支）与 11-03 docx。要点：

- **M1**：宿主后端 owner（T6.0 基线、T6.3 controller 读面、T6.2a host executor driver、T7.1 flow endpoints、T6.6 AI 驱动修复、T8.1 endpoints 半边）。
- **M2**：GUI owner（T7.0 原型评审、T7.4 agent shell、T7.5 引导式输入、T7.6 结果屏、T8.4 assistant UI、T7.8 迁移）；T8.2 LLM planner 在 11-05 由记录 92 转给 M2。
- **M3**：guest execution owner（T6.2 executor、T6.2 conformance、T7.3 screening/comparison、T8.3 guest half）。
- **M4**：independent verification（无实现任务；T6.7/T7.7 清单、T6.1/T6.3/T7.1 复核、T7.7 UI 验收、T8.5 LLM 验证）。
- **M5**：数据契约/适配器/AI 层（T6.1 ingest、T6.5 协议一致性、T7.2 analysis/comparison ingest、T8.1 assistant seam、T8.2 LLM planner、T8.3 generic repair plan）。
- **Lead**：批准/范围决策/合并与 tag/记录 gate，不做实现。
- **VMer**：VM 操作（T6.8 staging note、jobwrap 固定操作、guest conformance 窗口、每次运行后 reset），不做产品代码。
- 纪律：**层单一 owner**、handoff 用冻结文档而不是聊天、M4=Lead 同一操作者的限制要写在每条 verifier 记录上。

### 2.1 M1 — 宿主后端与集成（最终状态：COMPLETE）

| 项 | 内容 |
|---|---|
| 目标 | 宿主 controller/API/DB/任务编排；把 guest 证据接入产品；维护 main/CI/发布 |
| 关键交付 | controller `app/controller_api.py`（含 `/api/attempts/{id}/evidence`、P0-C 本地安全：loopback 限制、CSRF/Origin、非 ELF 拒绝、路径穿越拒绝）；`jobs.py`/`attempt_writer.py`/`obligations.py`；DB 迁移 002/003/004-008；`tools/fixture_intake.py`（ELF e_type 非 PIE 校验）；GUI 后端；`/api/jobs/{id}/evaluation`；deliverable 上传（老师要求"最终修复 ELF 可下载"） |
| 关键 commit/分支 | `1250169`（10-20 main，83 tests）；`deeb1da`、`0c3708a`、`3a107ab`（canonical/m1-m5-integration，11-06）；`7817a20`（integration/live-bridge，11-06）；`50cfe41`（m1/t30-acceptance-ab-2026-11-05，11-07）；该分支现 tip `101d034`（11-07）`[git]`；v1.2.1 source `3418491`（11-11） |
| 证据 | 全量测试演化：83 → 149/2 → 162/2 → 176/174/2 → 242/2/5 uncollectable（Windows）→ 446/2/0 → 503/2/0 → 729/727/2/0（v1.2.1 前）→ 741/739/2/0；`tests/integration/test_controller_auth.py` 9 passed；P0-C 4/4 PASS |
| 遗留 | 无"必须"任务；可选项：stable handoff 附 release asset、长期归档；CI 历史含一次被误记为 success 的失败 run（见 §4.5） |

### 2.2 M2 — GUI / 控制台（最终状态：COMPLETE；后期成为产品工作台主体）

| 项 | 内容 |
|---|---|
| 目标 | 拥有整个控制台：agent shell、引导输入、结果屏、assistant UI、迁移；后接 T8.2 LLM planner |
| 关键交付 | `agent.html/agent.css/agent.js` 三屏→agent 控制台；`assistant_llm.py` + `test_assistant_llm.py`（T8.2，由 M5 实做、M2 合并）；Review 12 PASS（record 180）；GUI 后续大改版（11-11→11-12：单一"新建修复内容"入口、主题三态、连接器/插件、9 语言、证据控制室、历史持久化、代码修复卡、AI 有界判定 UI） |
| 关键 commit/分支 | M2 GUI 合并 `34d054c`；assistant 合并 `2501120`；workbench-v3 上 `dfa7d14`、`f04068e`、`f510361`、`8d9d9dd`、`e5a9a76` 等（11-12）`[git]` |
| 证据 | `docs/handoffs/180-review12-pass-2026-11-08.md`；`FINAL-STATUS.md`：GUI T7.4/T7.5/T7.6/T8.4/T7.8 MERGED |
| 遗留 | Windows DPAPI key 存储 **NOT VERIFIED**（v1.2.1-rc1 明确披露）；i18n 为机器翻译（技术原文保留）；公共 GUI 为 curated snapshot |

### 2.3 M3 — Guest 执行与证据生产（最终状态：COMPLETE，带"代码不在仓库"的曾记录风险）

| 项 | 内容 |
|---|---|
| 目标 | executor 在隔离 guest 里跑冻结 fixture，产出 `result-bundle.json` + artifacts + SHA256SUMS；T8.3 guest half |
| 关键交付 | `workers/executor/run_job.py`、`self_test.py`、`workers/route_a/*`；jobwrap 固定 argv、uid 1003、netns 无出口、CapEff=0、NoNewPrivs=1、rlimits、clearenv；P3A/P3B/P4/Gate5B 证据包；CWE-416 no-input 样本冻结（记录 133）；self_test 9/9；`tests/test_guest_executor.py` 9 passed |
| 关键 commit/分支 | `m3/cwe416-v3-noinput`（`ea5cc9e` 11-06；记录内 `8556d9e`）；M3 review `ae97984`（11-11）；11-07 上传 executor 报告 |
| 证据 | `FINAL-STATUS.md` M3 段；`docs/handoffs/151-m3-guest-executor-account-isolation-2026-11-07.md`；记录 133/136 |
| 遗留 | 早期 "executor code NOT IN REPO" 风险（11-07 前只有报告与自述 9/9）；guest 访问不稳定（SSH 10.11.0.132:2222 常超时、VM 在 M3 电脑上）；独立 Windows full-suite 未做；VMer 的正式 T6.2 conformance 11-13 前为 NOT RUN/attested 混合口径 |

### 2.4 M4 — 独立验证（最终状态：COMPLETE，但"独立性"限制始终存在）

| 项 | 内容 |
|---|---|
| 目标 | 不写产品代码，只做独立核验：R1–R8、F2 p2、re-hash、复核 gate 记录 |
| 关键交付 | record 91/116/118/119/120/124 的核验；`require_independent=True` 的 V4 门禁；`verified_by="m4"` marker（124 V4，SHA256 `fc4802d0…2b06`）；`verify_all.sh` PASS；V4 harness ×2 PASS；124 re-ingest 后 V0–V5 全过、outcome `success_within_scope`；review 9–12（`docs/handoffs/180-review12-pass-2026-11-08.md`） |
| 关键 commit/分支 | `delivery/m4/v4-2026-11-07/`（16 文件 + zip `d5cb62e7…fc7b`）；记录 150/170/171；`m4/verify-56a7447`（10-31） |
| 证据 | `FINAL-STATUS.md` M4 段；`docs/handoffs/170-t83-fresh-tree-closure-2026-11-07.md`、`171-m4-t83-confirmation-2026-11-07.md` |
| 遗留 | **M4 = Lead 同一操作者**，不是独立双人复核（全程披露）；Gate 0 的 D1–D6 原文始终未提供，正式书面签到 11-07 时仍缺失（`[S:lead-07d5 seq 967]`）；V4 仍是 model-scope，不是 binary-level |

### 2.5 M5 — 契约/适配器/DeepSeek/AI 层（最终状态：COMPLETE；T8.3 主责）

| 项 | 内容 |
|---|---|
| 目标 | 候选 schema、安全契约、DeepSeek provider、ingest adapter、Gate 4 DRI、T8.1/T8.3 |
| 关键交付 | CandidateV1（Route A 12 / 总 14 字段，512/32/20000 限制）；`ProviderFailure` typed failures；contract canonical `24bfe568…4e37`；`tools/route_bundle_ingest.py`（V0 严格绑定 candidate hash，无 fallback）；Gate 2a/2b 适配器（`run_case`/`read_evidence`/`apply_candidate`）；T8.3 主责（CWE-416 样本、plan 随类不同）；v1.2.1 key store/API（mode-0600/DPAPI 分支） |
| 关键 commit/分支 | `member-5-deepseek-schema`（10-20，`221e47c`）；`member-5/complete-m5`（本地 tip `4c36898`；11-06 记录 `017ca87`）；adapter 分支 `m5/elf-type-check`（`a63f80d`）、`m5/t83-deliverables-2026-11-07`（`cdcbb4a`）；contract v3 no-input `4c36898` |
| 证据 | `docs/handoffs/91-m5-completion-2026-11-05.md`（SHA256 `e01a1752…38b6`）；`FINAL-STATUS.md` M5 段；T8.3 marker/124 |
| 遗留 | 分支未 merge main、未打 tag（T8.3 关闭前纪律）；N-10 accepted limitation / N-11 docs-only partial 在 v1.2.1 中披露；`route_bundle_ingest` 的 `is_secret_file` runtime guard 未真正接入 |

### 2.6 Lead 与 VMer

- **Lead**：11-03 发布 record 87 分工；11-05 起密集决策：126（V4 数据模型缺口）、131（verified_by 门禁语义）、132（PIE 口径：contract 对、build.sh 错）、Route A/B 双轨原则（11-12 `[S:lead-07d5 seq 1097]`）、T8.3 关闭（150/170）、v1.2.1 stable GO（11-11）。11-06 曾因 D1–D6 原文缺失拒绝签 Gate 0（`[S:lead-07d5 seq 967]`）。
- **VMer**：jobwrap 固定 argv/隔离、staging note（record 88）；11-11 状态 `record 88 = NOT AVAILABLE`、无任务、不计签核 `[S:history-m1 11-11 收口报告]`。

### 2.7 成员阶段状态汇总（截至 11-13 晚）

| 成员 | 11-07 all-hands 状态 | 11-11 v1.2.1 收口 | 11-13 | 遗留（非阻塞） |
|---|---|---|---|---|
| M1 | T6.0/T6.2a/T7.1/P0-C 完成；`50cfe41` 全量 exit 0 | stable handoff `7232a3fc…0795`；741/739/2/0 | 参与 v5/v7 打包与推送 | release asset、长期归档 |
| M2 | T8.2 done（merge 2501120）；Review 12 PASS | public stable 复验 741/739/2/0 + e2e 12/12 | GUI/CGC/i18n/微信分享 | Windows DPAPI 验证、Windows full suite |
| M3 | executor/jobwrap/self_test 9/9；T8.3 guest half 完成 | stable 签核（N-8/N-9 FIXED, N-10 accepted, N-11 docs-only） | v7 Linux VM 验收（950/943/7/0） | Windows 原生、DPAPI 独立复核 |
| M4 | V4 marker 写入、124 重跑 success、T8.3 closure | stable tag/main 发布（148d236/tag f687e14） | v6→v7 审计（evidence-auditor/claims-auditor） | 独立性限制、Gate0 书面签到、helper branch 清理 |
| M5 | T8.1/T8.3、Gate 2b 适配器、ELF type check | key/F2 PASS WITH LIMITATION | adapters/v4 部分实现 | N-11 runtime guard、多进程 custom key |
| Lead | T8.3 关闭、P1/P2 记录 | v1.2.1 CLOSED | v7 交付决策 | 对外公告、v1.2.2 backlog |
| VMer | 无任务 | NOT AVAILABLE | 无 | — |
---

## 3. T8.3：是什么、为何重要、完成情况

### 3.1 定义（任务表原文）

T8.3 属于 T8（AI 驱动修复）线的第三项：

- **T8.1** 助手接缝（AssistantPlan，只出计划、不写裁决）；
- **T8.2** LLM planner（真正让模型生成修复计划）；
- **T8.3 generic repair plan**：**second public sample of a different defect class; plan differs by class; acceptance unchanged**（第二个不同缺陷类的公开样本；修复计划随缺陷类而不同；验收标准不变）。

主责 M5，M3 负责 guest 半（第二样本构建与证据），M4 独立验证，Lead 验收；原定截止 **2026-12-01**。定义见 `docs/handoffs/87-lead-task-assignment-2026-11-03.md` `[file; S:t83-217a seq 456]`。

### 3.2 为什么重要（6 条，源自 11-06 说明）

1. **证明通用性而不是单样本过拟合**：只修 CWE-121 可以是一个模板/一次手工演示；第二类不同机制（bounds-check → lifetime）是"通用修复"的最低证据。
2. **检验 AI planner 是否真的"随类不同"**：如果两类拿到同一套模板，"AI 驱动"只剩标签。
3. **验收标准不变**：第二类必须走同一条 V0–V5，防止"换一条更容易的尺子"。
4. **它是发布门禁**：记录 136 §4 明确 T8.3 关闭前不合并 `main`、不打 tag、不写 live-success。
5. **它是"正确性验证"的试金石**：V4 必须由 M4 独立 replay，生产者不能自证。
6. **它把风险暴露出来**：第二类 V4 是 model-scope、空析取；V2 有执行器缺口——逼团队在签字前说清"证据到底证明了什么"。

`[S:t83-217a seq 456]`

### 3.3 做了哪四件事

1. **选第二类样本**：第一类 = CWE-121（`strcpy` 越界，修法加长度检查）；Lead 在 11-06 定为 **CWE-416（use-after-free，no-input 变体）**，CWE-122 被明确排除（且 CWE-122 fixture 出现 PIE/non-PIE 口径问题，见记录 132：contract 要求 non-PIE、提交产物是 EXEC，但 `build.sh` 缺 `-fno-pie -no-pie`；决定"契约不动、改 build.sh、并给 intake 加 ELF 类型校验"）`[S:lead-07d5 seq 832]`。
2. **冻结样本**（记录 133）：`original.elf` `c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9`、`candidate` `46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0`、contract `8a2b408c…3c3b`（canonical `c1684f15…b4f7c`）；每次 self-check 重算，换输入即失败。
3. **走同一条 V0–V5 验收梯子**：V0 身份、V1 结构、V2 接口、V3 行为、V4 符号、V5 可复现；六种 outcome。
4. **AI planner 计划随类不同 + M4 独立 replay V4 + Lead 验收**（真正的收口步骤）。

### 3.4 时间线与状态

| 时间 | 事件 | 状态/证据 |
|---|---|---|
| 11-03 | record 87 定义 T8.3（M5 主责、12-01 截止） | `[S:lead-07d5/87]` |
| 11-05 | 119 号（CWE-416 no-input contract v3）起草；120 contract 通过 | contract file SHA `8a2b408c…`、canonical `c1684f15…` |
| 11-05 22:16 起 | m1-3342/m4 会话密集推进 124（CWE-416 样本）、118（T30 baseline rebuild） | `[S:m1-3342]`、`[S:history-m4 seq 230 起]` |
| 11-06 10:44 | Lead 记录 126：V4 的 `not_run` 是**数据模型缺口**，不是"没有 engine"；禁止手跑 angr 贴结果 | `[S:lead-07d5 seq 442]` |
| 11-06 14:00 | 记录 131：`verified_by="m4"` 门禁只防"状态升格"，不是防篡改；生产路径 `require_independent=True` | `[S:lead-07d5 seq 675]` |
| 11-06 16:41-16:43 | 记录 132：环境未到位、PIE 口径；D1–D6/Gate0 未提供 | `[S:lead-07d5 seq 824/967]` |
| 11-06 17:40 | 6 分支 44 commit 383 文件上传；T8.3 状态 = **BLOCKED，卡验收不卡选样**；124 V0/V1/V3/V5 passed、V2/V4 not_run、`inconclusive / required_check_not_run / symbolic` | `[S:t83-217a seq 456]`、`[S:history-m4 seq 1242-1901]` |
| 11-06 18:23 | 生成 21 页 PDF《GitHub上传地址与T8.3说明》 | `[S:t83-217a seq 1338]` |
| 11-07 | M3 装 M4 公钥；M4 跑 `verify_all.sh` 3/3、V4 harness ×2、marker 写入；124 re-ingest 后 V0–V5 全过、124 `success_within_scope` | `[S:history-m1 checkpoint seq 17305]`、`[file:FINAL-STATUS.md]` |
| 11-07 | Lead 关闭 T8.3（记录 150），M4 确认（记录 171） | `[git:delivery/all-hands-2026-11-07]` |
| 11-08 | 全量 714 passed / 2 skipped；fresh tree 复核 | `[file:FINAL-STATUS.md]` |

### 3.5 完成情况与边界（重要）

**完成**：T8.3 = COMPLETE（record 170），124 的 V0–V5 全过并给出 `success_within_scope`；M4 的 V4 marker `M4-V4-MARKER.json` SHA256 `fc4802d0…2b06`，两次运行 digest 一致 `cb2137a2…cb14`；124 attempt id `86b5f96f…0a4c`；M4 targeted 44/44、P0-C 4/4。

**边界（不可忽略）**：

- V4 仍是 **model scope**，不是 binary-level 证明；candidate 的 `unsat` 是**空析取**（`free_calls=0`，"这条路径上 free 被 5 个 nop 替换，等于没真正 free 再读"），已在记录 133 §6 写成 scope 限制 `[S:t83-217a seq 456]`。
- M4 = Lead 同一操作者，角色分离但不是独立双人。
- V2 一度是"生产者测量 5/5，但 attempt_writer 无条件写 not_run"的数据模型缺口（后续 M1/M5 接通）。
- T8.3 关闭**不等于**全项目 live success：`main` 未合、无 tag、无 live-success 声明（11-07 的 FINAL-STATUS 原话）。

### 3.6 能否跳过

**作为"已完成"跳过——不行；作为并行工作——可以继续其它不依赖内容。**

- 不能跳：T8.3 是正式交付项；是 merge main/tag/live-success 前置门禁；跳过会让项目降级成单类 MVP，与标题"通用 + 正确性验证"不匹配；也不能靠补一个 `verified_by="m4"` 来跳过（记录 132 禁止，产品无法检测）。
- 可并行：M2 的 T8.4、M4 的 T8.5、文档/UI 等不依赖 T8.3 的工作可以继续；但不要标记完成、不 merge/tag。
- 硬跳只能显式降级：记录 not done/descoped、V4 保持 `not_run`、宣称改为"单类 MVP"、保留 383 文件证据包与 BLOCKED 字样。

`[S:t83-217a seq 456]`

---

## 4. GitHub 仓库、公开快照与 v1.2.1

### 4.1 两个仓库（地址变化）

| 仓库 | 地址 | 出现时间 | 性质 |
|---|---|---|---|
| 开发仓库 | `git@github.com:chenfanaichifan/binary-repair.git`（HTTPS 同为 `https://github.com/chenfanaichifan/binary-repair`） | 2026-10-15（Initial commit `132ad98` 18:40:09 +0800） | 主开发仓库；大量成员/集成分支；11-06 报告称其为**私有**（10-20 的旧 checkpoint 又称 main public，两说并存，**未核实**其可见性变更时间） |
| 公开仓库 | `https://github.com/leesirleesirlee-star/Binary_Repair` | 首次出现在会话：**2026-10-31 23:31** `[S:history-m1 seq 9852]` | curated MVP 快照（"extracted from final tag"，不是完整开发历史）；有 release/tag、可公开访问 |
| 旧本地仓库/归档 | `binary-repair/`（成员5旧 worktree）、`worktree-feature-final/` | 10-15 起 | 后续 11-12 整理时曾把 380+ 项移到 `~/Desktop/BinaryRepair-archive-2026-11-12/` |

### 4.2 开发仓库（binary-repair）时间线

- **10-15**：Initial commit `132ad98`（作者 chenfanaichifan）；`main` 后续停滞在 `1250169`（10-20）。
- **10-18**：M5 开始按角色上传分支；用户要求"将内容作为分支都上传至这个仓库" `[S:history-m1 seq 633]`。分支命名从 huajinyao-ai-route-b 改为 `member-5-deepseek-schema`，并加入成员 git 协作者（huajinyao 推送被拒后解决）`[S:history-m1 seq 2054 checkpoint]`。
- **10-20**：M5 分支 fast-forward 合入 main（`1250169`）；全量 83 passed；PR #2 `member2-backend-adapter`、后续 PR #10 相继出现；因无 GitHub token/gh，PR 靠网页/用户操作。
- **10-22**：仓库历史整理，旧 `agent/` 归档在 tag `archive/2026-10-22/pre-cleanup`；Route A cave v3、contract 修订（0x401309）、v6 kit `499f510c`。
- **10-29 / 10-31**：Gate 3 批准 `0b3b51e4…`；Gate 4 strict-scope PASS `[git:member-5/gate4-pass 4134065]`；Gate 5 Route A PASS；PR #10 head `aab162a` 关闭；main 曾到 `56a7447`/`d969e6d`/`3508de0`（M5 各阶段）。
- **11-03 → 11-07**：公开 MVP 与 T8.3 阶段，仓库分支：`canonical/m1-m5-integration`（`3a107ab`）、`integration/live-bridge`（`7817a20`）、`m1/t30-acceptance-ab-2026-11-05`（`50cfe41`/`101d034`）、`m3/cwe416-v3-noinput`（`ea5cc9e`）、`m5/elf-type-check`（`a63f80d`）、`m5/t83-deliverables-2026-11-07`（`cdcbb4a`）、`delivery/t83-2026-11-06`（`df99853`，383 文件/44 commit 归档）、`delivery/all-hands-2026-11-07`（11-08 tip `c3bca0e`）。
- **11-08 → 11-11**：v1.1.x / v1.2.x 发布分支（`release/v1.2.1` 等）；M1 candidate `612510`、M1 A snapshot `5196e35`、M3 review `ae97984`、source delivery `3f2bcba`。
- **11-12 → 11-13**：`workbench-v3` 成为 GUI/产品主线：`dfa7d14`（13:16）、`f04068e`（14:46）、`f510361`（14:09）、`8d9d9dd`、`e5a9a76`（23:11）、以及 11-13 的 `c0cbffc`（14:17，v3 统一管线）、`a6226cb`（15:53，container-neutral repair）、`e1756a2`（16:07，Linux VM v4 matrix）、`3d5d0f0`（16:44，v6.1 docs）、`72db891`（18:55，v5 docs）。分支 `handoff-v3-local` / `handoff-v4-local` 对应交付线 `[git]`。
- 11-14 之后另有 release/phase8 系列（`4a7b235` 11-16、`ec503e4` 11-16 等），**超出本文范围**（BRIEF 的当前 HEAD）。

### 4.3 公开仓库与版本序列

| 版本/ref | commit | 时间（会话证据） | 内容/说明 |
|---|---|---|---|
| main（curated） | `0070103f86366d21642c1e7b87e68a22c294c910` | 11-03 之前（10-31 起） | curated MVP；tags `mvp-2026-10-31`、`v1.0.0` |
| v1.0.0 | 同上 | 10-31 | README "accepted with recorded limitations"；Gate4/5A/5B 记录；V4 model-level；full suite 265/262/2/1（Windows 环境失败） |
| v1.1.0 | `1e30bd5b19db7ad75a0246190740a061225b4028` | 11-08 | annotated tag v1.1.0；M4 curated repo；full pytest 18 failed/error（curated 路径改写导致），后要求 v1.1.1 |
| v1.1.1 | 本地 `1c7…` | 11-08 | 本地修完 4 类问题；**推送权限失败**，未发布 |
| v1.1.3 | `367d29b` | 11-11 前 | 冻结版本（v1.2.1 期间保持不动） |
| v1.2.0 | `9439340`（tag v1.2.0） | 11-09 | 公开 stable；full suite 730/728/2/0；sums 201/201 |
| v1.2.1-rc1 | tag object `f5346978b46622c6c582e13d7cf6330f72e638f3` → peeled `d7d20f4` | 11-10 发布 prerelease | 741/739/2/0；e2e 12/12；N-8/N-9 修复；N-10 accepted；N-11 docs-only partial；披露 Windows DPAPI NOT VERIFIED |
| v1.2.1 stable | tag object `f687e14fa674e05e6e0520e67e82b788c7085355` → peeled `148d236d46bbd514dbb48f0a0f506ef2a2143fcc` | 11-11 | public main 前移到 148d236；741/739/2/0；e2e 12/12；stable release（prerelease=false, draft=false） |

> 公开仓库的 release 页面/网址未在本文写作时独立联网复核（GitHub API 限流；公开仓库页面部分抓取成功但为 React 数据），以上 ref 值均来自会话内 `git ls-remote`/GitHub API 的实查记录 `[S:history-m1 11-09~11-11]`。**未核实项**：GitHub 上的创建时间、release 页面当前内容。

### 4.4 v1.2.1 公开快照（"公开稳定版"）

- **性质**：curated snapshot（不是完整开发历史/raw evidence 全量）；源码 delivery head `3f2bcba1f8438e1f1636b41ebd16c4ceffeb9a20`（11-11 21:58 推送完成）、public stable `148d236`。
- **测试**：source/候选/public rc1/stable 四个树均 **741 collected / 739 passed / 2 Linux-only skipped / 0 failed**；browser e2e **12/12**；P2 exit 0 / `success_within_scope`。
- **关键内容**：AI provider 真实 DeepSeek（flash）smoke；key store（Unix mode-0600 / Windows DPAPI 分支）与 4 个 `/api/assistant/key` 路由；assistant LLM planner；deliverable 上传/下载；GUI 主题/语言/连接器。
- **review-13 结论**：N-8 FIXED、N-9 FIXED、N-10 ACCEPTED LIMITATION、N-11 FIXED(docs-only)；stable 的 N-11 修正为 docs-only，**不得写成 runtime guard**。
- **真实 DeepSeek 证据**：model `deepseek-flash`、prompt 38 / completion 5 / total 43 tokens、latency 1904 ms（`docs/handoffs/216-real-deepseek-smoke-2026-11-09.md`）；key 不回显/不写日志。
- **交付物**：`delivery/handoff-v1.2.1-stable-2026-11-11.zip` SHA256 `7232a3fc4f2f6b4df0d0949663130041c796cc6b739ae6f9fd29b2d5bc490795`（SHA256SUMS 7/7 OK）；`delivery/v1.2.1-stable-148d236/v1.2.1-stable-148d236.bundle`。
- **公开文档补丁**：`public-v1.2.1-docs.patch`（10,006 B，11-12 15:31）修正 public 文档中 v1.2.0/730/728 旧数字，补 v1.2.1 tag/peeled/source delivery/release branch 与 N-10/N-11 记录；因无 HTTPS 推送凭据，需有权限者 `git am` 应用（公开仓库可见性/权限限制，**未核实**当前是否已应用）。
- **未完成披露**：Windows DPAPI 未验证；N-11 仅 docs-only；N-10 accepted limitation（自定义 key 文件的多进程 env 一致性）。

### 4.5 CI 记录（含一次"假 success"事件）

**主要 run：**

| run | 关联 | 结果 |
|---|---|---|
| `39752557610` | Gate 4 首次真实 CI（Ubuntu 24.04、JDK 21.0.12.1、Ghidra 12.2、Patcherex2 0.2.14；round-trip 6/6） | 成功（10-20）`[S:history-m1 checkpoint seq 3953]` |
| `43242554914` | workbench-v3 `f32a0f2`，UI/修复混合 | **539 passed / 1 failed**（首败 `PermissionError: original.elf`，Git 记为 100644）`[S:fix-ci seq 11]` |
| `43244713385` / `43246391510` | Ubuntu CI 修好 fixture 执行位后 | success（11-12 深夜）`[S:vm-pkg seq 1324]` |
| `43248090960` / `43248205593` / `43248395728` | df82b6c / 5d8d006 等 | success |
| `43248544193` | `a436b64` | **实际 failure**（`test_c_overflow_patterns` 编译器超时 flake），但被文档写成 success（见下） |
| `43249875815` | `9a451fd`（纯 docs 提交） | success |
| `43256190605` / `43256481655` / `43256887551` | `774c584` 之后 | success；`0fe9241` → 889 passed / 1 skipped / 0 failed / 890 total |
| `43390831537` | `e1756a2`（workbench-v3，v7 交付声称） | **success**（v7 VERSION/README 记录） |
| `43395652244` | `3d5d0f0`（v6.1 docs） | success（v6.1 并行会话产出） |

**假 success 事件（11-12 23:30 → 11-13 00:16 纠正）**：

- 11-12 23:30 `a436b64` 的 run `43248544193` 实际失败（失败步骤 "Run non-browser test suite"，测试 `test_c_overflow_patterns.py::test_five_c_buffer_overflow_shapes_are_detected_and_patched`，断言"修复后 ≠ 原始"但两边字符串看起来一样）。
- 后续 `9a451fd`（纯 docs，+18/−4）却把 run 记为 success，`DELIVERY.md`/`README.md`/`ubuntu-verification.md` 也指向该失败 run；用户把外部分析贴入会话后，判断"虚假记录已写进仓库文档" `[S:fix-ci seq 2080]`。
- 纠正：`774c584`（"fix(ci): treat compiler validation timeouts as unavailable"，`patch_validation.py` timeout 8s→20s + `COMPILER_UNAVAILABLE_PREFIX` + 回归测试）、`0fe9241`（记录 gate-blind 局限与下一实验）、`2aca931`（记录 flake 是 rule-only 不是模型依赖）；三条 Ubuntu CI run 全绿 `[git:774c584/0fe9241/2aca931]`。
- 该事件直接写进 11-13 的`方法建议`文档："先修证据链，再谈能力"。

---

## 5. 微信分享包、DeepWorks 平台迁移、demo 实例与 ngrok

### 5.1 微信分享包（2026-11-12）

**背景**：用户 11-12 01:31 要求"重新系统整理整个仓库内容，删除不必要的信息。而后教并帮我将这个成果用微信分享给组员使用查看" `[S:plan-svc seq 5677]`。

**仓库整理**（11-12 凌晨）：

- 根目录从 **380+ 个散落文件、约 1.1 GB** 收敛为 `README.md + binary-repair-gui/ + binary-repair/ + WeChat-Share/`；rea、deepworks、_m1-work、_m3-run、_m4-verify、role5-kit、PDF/ZIP/PPT 等移到 `~/Desktop/BinaryRepair-archive-2026-11-12/`（可恢复归档）`[S:plan-svc seq 6224]`。
- 清理 .tmp/.pytest_cache/__pycache__/.DS_Store/var 缓存；删除过期 `release/V1.2.1-rc1-README.md`；新增 `START-HERE.md`、`SHARE-WECHAT.md`、`docs/showcase/` 截图、Windows 启动器 `start-gui.ps1/.bat`；提交推送 workbench-v3 `8d9d9dd`。

**分享包构成**：

| 项 | 内容 |
|---|---|
| 目录 | `WeChat-Share/BinaryRepair-Workbench/`（运行代码 app/、binaryrepair_ai/、routea/、routeb/、knowledge/、plugins/、data/、fixtures/、docs/，启动器，START-HERE/SHARE-WECHAT，当前截图，核心文档） |
| ZIP | `WeChat-Share/BinaryRepair-Workbench-2026-11-12.zip`，**4,857,723 B**，SHA256 `9a7e5c6ae7639e77a26bbf50b06604171b30d6d1f9ef410f8c2b24b3ad8c79e7`（本文实测；会话中曾记录 2.2 MB → 4.4 MB → 4.5 MB 的迭代） |
| 不含 | .venv、.git、token、历史数据库、真实 provider key、测试产物 |
| 启动 | macOS/Linux `./start-gui.sh`；Windows 双击 `start-gui.bat`；浏览器打开终端打印的 `http://127.0.0.1:8123/?token=...` |
| 隔离 | 演示实例独立数据目录 `/tmp/binaryrepair-wechat-demo`，与本地 8123 实例隔离 |

**群消息模板**（`WeChat-Share/群消息-可直接粘贴.txt`）三段：①在线体验（临时演示 + 局域网 + Bonjour 固定入口）②本地包（ZIP + 启动方式）③本版亮点（启动卡合并、证据控制室、N/A 不充当通过、数据集盘点、补丁编译门禁、AI 有界判定、公开 v1.2.1 文档 patch、9 语言、主题、使用说明 12 节、移动端抽屉）+ 上手 3 步 + "技术证据保留原文语言"声明。

**分享安全边界**：公开链接只用于 mock 演示实例（无真实 key/样本）；不可分享本机 8123 的 token；演示实例数据可重置 `[S:plan-svc checkpoint 11-12 12:42]`。

### 5.2 DeepWorks 平台迁移（2026-11-08 → 11-11）

**背景**：团队 4 人报名"首届**滴普杯**校园黑客松"**赛道 C｜自由开放**（面向大一新生；评价看问题真实性/方案可行性/可运行演示；报名截止 **11-09 18:00**）。规则要求"作品核心流程须在 DeepWorks 平台内完成（知识库接入、技能与工作流编排、Agent 运行），不接受仅以平台作为展示外壳；决赛现场在平台内实时展示" `[S:deepworks seq 16/1360]`。

**账号与租户**：只用**天津大学企业租户** `tju` / `3026445042@tju`（滑锦尧）；个人空间 `personal`/用户2755 未写入任何内容 `[file:deepworks/reports/MIGRATION.md]`。

**四层重建**（不是拷文件）：

| 层 | 平台落点 | 证据 |
|---|---|---|
| 知识库 | 知识工作区 `ws_a44cc1a95550`；21 篇带 SHA-256 的语料 → 编译出 **267 wiki 节点**（concepts 100、objects 83、summaries 16、SOP 18、sources 13）；`foil/ontology/ontology.sqlite` | `deepworks/knowledge/*.md`、`binaryrepair-knowledge-base/` |
| 技能 | 5 个 `binrepair-*` 技能（contract-audit / routea-replay / evidence-audit / evidence-pack / orchestrator），在会话 / 菜单可见，可 zip 安装 | `.opencode/skills/**/SKILL.md` |
| 工作流 | 自动化任务「BinaryRepair 每日回归审计」，每天 09:00，会话 `ses_e450ce887ffe…` | `automation-tasks.json` |
| Agent | 会话 `ses_e450e4b5fffeJyTK1JDcGN2dPp` 调 orchestrator 跑四步，产物 `outputs/demo-20261108/`（14 文件 + VERIFY.sh）+ `outputs/daily-regression/` | 平台内产物 |

**踩坑与修复**（均记录在 MIGRATION.md）：

- 知识编译默认模型 `Deepexi-E-Pro-2.0` 报 `knowledge_compile_model_output_truncated` → 切 `DeepSeek-V4.1-Flash`；
- 自动化默认 `Qwen3.8-27B` 无可用通道 → 显式选 `dth/DeepSeek-V4-Flash`，重跑成功；
- DeepWorks 桌面端"秒退"根因 = 环境里 `ELECTRON_RUN_AS_NODE=1` → `env -u ELECTRON_RUN_AS_NODE open -a`；
- 知识工作区用 `__preview__` 路由会卡"正在加载知识工作区" → 用直接路由 `#/workspace/ws_a44cc1a95550/knowledge?mode=workbench`；
- 演示页 `outputs/成果总览.html`（1.6 MB 自包含、5 张 base64 截图）已在 DeepWorks 内置浏览器验证打开。

**11-11 再次迁移**：用户修改后要求"再次将所有成果移至 DeepWorks，顶替上一版本"；把 v1.2.1 stable 相关（review-13、key 证据、`v1.2.1-stable-148d236.bundle`）纳入 `deepworks/reports/v1.2.1/`，并重新打开最终工作台 `[S:deepworks seq 3608/3868/4039]`。

**合规边界**：仅用公开 Juliet CWE-121/416 样本，无患者/个人信息；只上传 Markdown 与公钥，不上传私钥；"赛前已完成（10-15→11-08）vs 赛中新增（知识/技能/自动化/Agent/演示）"需在报名表说明 `[file:deepworks/reports/REGISTRATION.md]`。

### 5.3 demo 实例与 ngrok（2026-11-12 凌晨 → 下午）

| 时间 | 事件 |
|---|---|
| 11-12 ~01:40 | 随微信分享任务启动公网演示：独立 mock 实例端口 **8124**、数据目录 `/tmp/binaryrepair-wechat-demo`、独立 token `Lu-Okf7sgwnuaLDE-wzDz7d-5O_iLymtJD_3R0-HhkA`；ngrok 隧道 `https://dandelion-copious-hydration.ngrok-free.dev`（`--host-header=127.0.0.1`，免费版首次访问有 "Visit Site" 警告）`[S:plan-svc seq 6224]` |
| 11-12 白天 | 同一 Wi-Fi 局域网入口 `http://10.11.0.237:8124/?token=…`；需 macOS 防火墙允许 Python 入站 |
| 11-12 ~13:17-16:12 | 起始页/主题/语言/证据室多轮迭代，每次重启 8124 并更新分享 ZIP；11-12 16:12 改为**固定局域网入口**（不再依赖 ngrok 临时地址）：Bonjour `http://huademacbook-pro.local:8124/?token=…`，token 固定存于 `binary-repair-gui/var/lan.token`（0600），启动脚本 `start-lan.sh`；允许主机名 huademacbook-pro.local / 10.11.0.237 / localhost |
| 最终群消息 | 同时给出 ngrok、局域网 `http://10.13.1.188:8124/?token=…`（IP 后续变化）、Bonjour 固定入口；并显式声明"演示实例使用合成 fixture，不执行真实修复，不构成『补丁已验证』的证据" |

**停止/重启方法**（`WeChat-Share/README-微信分享.md`）：`kill $(lsof -tiTCP:8124 -sTCP:LISTEN)` 与 `kill $(lsof -tiTCP:4040 -sTCP:LISTEN)`；重启用 `BINARYREPAIR_BACKEND=mock BINARYREPAIR_DATA_DIR=/tmp/binaryrepair-wechat-demo BINARYREPAIR_ALLOW_TUNNEL=1 uvicorn … --port 8124` + `ngrok http 8124 --host-header=127.0.0.1`。

> 边界：演示实例是 **mock/合成数据**（页面内有 GUI-only 开发模式横幅），不是真实修复执行；ngrok 免费隧道临时、域名会失效；token 不可提交到仓库（分享包内的消息模板已脱敏）。

---

## 6. Linux VM handoff v1–v7（给有 Linux 虚拟机的同学）

### 6.1 背景

11-12 22:52 用户提出："现在我想让我有虚拟机和 Linux 的同学帮我跑之前我未完成的所有任务，请帮我生成一个压缩包包含所有需要提供的材料，并再次重申所有任务" `[S:vm-pkg seq 8]`。随后是 11-12 23:00 → 11-13 17:00 的**多轮打包↔评审↔修复**：用户把另一台 Windows 机器/另一会话的评审意见粘贴回 vm-pkg 会话，逐版推进；同时 v3-review 等并行会话在实现通用二进制修复（v4 代码）、产出 v5 包。

### 6.2 版本表（全部在 `handoff/` 或其 `archive/`）

| 版本 | 时间 | 大小（B） | SHA-256 | 关键点 |
|---|---|---|---|---|
| Init（无编号） | 11-12 23:29 | 19,860,821 | 未记录 | 最早压缩包（`BinaryRepair-Handoff-Init-2026-11-12-superseded.zip`） |
| v1 | 11-12 23:13 | 55,889,904 | `7812fc0f…bf27` | 冻结 436594d 快照；评审结论"好包但过期"：T0 在 Linux 必失败（original.elf 无执行位）、测试计数算术 846+2+0≠849、缺 corpus、zip 无 UTF-8 标志、绝对路径、workers/executor.py 路径错、文档误导、安全口径矛盾 |
| v2 | 11-13 00:11 | 56,042,010 | `14a45ccd…9bda` | 按 v1 评审逐项修复（staged-copy 夹具、计数、corpus、UTF-8、路径、状态表）；但冻结在 9a451fd，仍引用"失败 run 记为 success"的 a436b64，且早于 flake 修复 774c584 |
| v3 | 11-13 14:22 | 56,010,305 | `d542dce0…f335` | 基于 2aca931；修正 CI 历史（a436b64=failure、0fe9241/43256887551/889-1-0-890 为真绿）；macOS 890/885/4/1；Linux 预期 890/899/1/0；v3 评审 11-13 15:16："内容层面可以通，但缺 .sha256 与 archive" |
| v4 | 11-13 15:50 | 56,029,943 | `7678726f…b2f7` | v3 评审后补 .sha256/archive 等（11-13 15:50 前后） |
| v5 | 11-13 15:58 | 74,521,163 | `19b8eeb1…d3d772` | 通用二进制修复 v4 代码（ELF/PE/Mach-O、x86-64/arm64 栈拷贝 sink、Mach-O 原生、PE/AArch64 Unicorn、负向对照），提交 `a6226cb`（handoff-v4-local，未 push）；包 1826 条目、校验通过、6 个中文名 UTF-8 标志、script 0755 |
| v6 | 11-13 16:17 | 60,204,619 | `da5f4fda…88ba357` | 评审 16:31："内容层面已过验收，可发"；仍缺 .sha256 与 archive；包内 3 处嵌套 SHA256SUMS 失配；其他 P2 文档问题（patches/README subject、.tmp/zigpkg 说明、macho-local-check 旧失败、pytest.log 无 summary、TASKS 口径、崩溃日志未附） |
| **v6.1** | 11-13 16:58 | 60,253,460 | `e678f68d…b7494c5` | **并行会话**产出（v6 + docs `3d5d0f0` + CI 43395652244 + Mach-O 日志 + ARCHIVE-INDEX）；Linux VM 参照复跑 938/7/5（非声称 943/7/0），仍含嵌套清单失配/用户名泄露/时间戳矛盾/无 umask 归一化 → **不作为交付** |
| **v7（最终）** | 11-13 16:58 包、17:00-17:06 验证 | **60,488,092** | **`2afeb6c8c0908acfcf0fb83328d75a2c5254dc7656f2ef43105cf3f89a42fcc8`** | 与 v6 的源码/证据结果不变（e1756a2），只做**打包修复**；Linux VM 全新解压复跑通过（950/943/7/0），29/29 嵌套清单通过，verify-package.sh PASS |

### 6.3 v7 的结构与任务

**顶层结构**（`handoff/BinaryRepair-Linux-Handoff-2026-11-13-v7/`）：

`@
00-先读我.md / 01-任务清单.md / 02-Linux运行手册.md / 03-回传清单.md
BASELINE.md / ENVIRONMENT.md / HANDOFF-TASKS.md / MANIFEST.json
README.md / README-DELIVERY.md / SHA256SUMS（323,793 B，2,227 行）/ TASKS.md / VERSION.txt
baseline/（source-baseline.tar.gz + README）
binary-repair-gui/（冻结源码 2aca931 + 证据）
corpus/（overflow-corpus 1,200 variants + binary-corpus 24 个 Mach-O）
evidence/（macOS/Linux VM/CI/CGC/运行时证据）
patches/（git-info、README）
run-baseline.sh / run-smoke.sh / setup-linux.sh / verify-package.sh
`@

**任务矩阵**（TASKS.md，冻结在 e1756a2）：T0 基线（macOS 950/946/4/0；Linux VM 950/943/7/0；CI run 43390831537 success）；T1 PE ✅ 本地矩阵（PE32+ x86-64/arm64 guard cave，原签名失效但不伪造）；T2 Mach-O ✅ 本地矩阵（arm64/x86-64 stub + guard cave、macOS 原生运行、ad-hoc re-sign）；T3 ELF ✅ 本地矩阵（x86-64 strict + arm64 guard cave，GOT/PLT 在 v4）；T4 sprintf ❌；T5 UAF/int/loop ❌；T6 guest 🟡 partial（Unicorn/native macOS，硬化 Linux guest 未接入）；T7 集成 🟡 partial（CLI batch + API，GUI 仍多 legacy quick-repair）；T8 统一 dispatcher ✅。

**矩阵与运行时层级**：ELF64 x86-64（strict template/immediate/guard）、ELF64 arm64（guard cave）、PE32+ x86-64/arm64（guard cave，IAT/thunk）、Mach-O 64 arm64/x86-64（guard cave/stub）；PE32/i386、32-bit ELF 不支持；fat Mach-O 检测但不重写。运行时层级：`native_run`（macOS Mach-O）、`emulated_run`（Unicorn PE/AArch64）、`static_only`/`not_verified`（无运行时）。**明确不是 universal repair**。

**仍需成员（HANDOFF-TASKS）**：W1 Windows PE 原生；M1 Mach-O 原生（macOS）；X1 32 位/大端/fat Mach-O；X2 堆/全局 sink；T4 sprintf；T5 UAF/整数/循环；G1 硬化 guest/KVM；F1 记录 legacy ELF x86-64 fail-open 潜在路径（`_from_elf_legacy` 验证失败仍可能返回候选，冻结源码未改，给出复现与修复要求）。

### 6.4 v7 最终验证（Linux VM 权威复跑）

来源：`handoff/final-verification-2026-11-13/FINAL-LINUX-VERIFICATION.md`（18 KB，11-13 17:06）。

- 环境：Linux VM（Ubuntu 24.04.5 LTS arm64、Lima 2.3.0、4 vCPU / 5.8 GiB、QEMU 8.2.2、clang 18.1.3、GNU readelf 2.42）。
- 方法：宿主完整性预检（zip SHA256、unzip -t、verify-package.sh、29 个嵌套 SHA256SUMS、MANIFEST/时间戳、用户名/路径扫描）→ Linux VM 全新解压 + 按手册装环境 + `setup-linux.sh` + `run-baseline.sh -rs` + `run-smoke.sh --allow-native` + 独立运行时抽查（L2 native ELF / L3 CGC replay ×3 / 负向对照）→ 证据链独立核对 → 方法建议符合性。
- 结果：**Linux VM 全量 950 collected / 943 passed / 7 skipped / 0 failed**；run-smoke 全部 6 个 section PASS；zip SHA OK；包内顶层 SHA256SUMS **2,227/2,227 OK**；29/29 嵌套清单；verify-package.sh PASS；CI e1756a2/43390831537 独立核对；7 个 skip = 1 个可选 candidate + 4 个 native Mach-O + 2 个 Mach-O 正向 pipeline。
- 结论：**PASS（可交付）**，P0=0。
- 保留限制：F1 fail-open；CGC `basic_messaging` POV 差分上下文敏感（`Palindrome` 为 canonical、basic_messaging exploratory-only）；gate 尚未内建"PoC 失效"判据；方法建议 §4.2 的第 4–6 层（模糊回归、符号/形式化、安全回归扫描）未接入；Windows PE 原生/readelf 后端替换等仍待成员环境。

### 6.5 v6 → v7 的关系

**v7 = v6 的源码/证据结果不变（同为 e1756a2）+ 打包修复**（README-DELIVERY "v7 packaging fixes"）：

1. VERSION/MANIFEST `created_at` 对齐真实构建时间（16:58:23）；
2. 3 个过期嵌套 SHA256SUMS 重算（`evidence/v4-macos`、`binary-repair-gui/artifacts/binary-universal-2026-11-13`、`…-v4-2026-11-13`）+ 2 个 fixture 级清单；
3. 历史日志用户名/临时路径脱敏（`<user>`/`<tmp>`）；
4. `patches/git-info.txt` parent 与 `patches/README.md` commit subject 修正（e1756a2，parent 3eac4e6）；
5. 顶层运行脚本统一 `umask 022`（guest-executor 自测依赖非 group-writable 临时根目录）；
6. `BASELINE.md` 路径残留清单修正（23 个二进制；Mach-O 无 DWARF 路径）；
7. CGC replay caveat（时序敏感、可重试）与 Mach-O 崩溃信号修正（x86_64 SIGSEGV / arm64 SIGBUS）；
8. CGC `*_patched` 来源披露（上游 `-DPATCHED*` 构建，非引擎产物，replay 不是 V0–V5）；
9. legacy ELF x86-64 fail-open 作为 F1 记录；
10. 两个 fixture 级 checksum 清单刷新；zip 中文名 UTF-8 标志、执行位保留。

**v6.1 被排除**：它是并行会话在检验期间产出的过渡版本；Linux VM 参照复跑 938/7/5 与声称不符，且仍有清单失配/泄露/时间戳矛盾/无 umask 归一化，故 v7 取代它并归档为 `-superseded`。
---

## 7. 计划服务（plan service）未接通的排查结论

### 7.1 现象

11-11 22:13 用户在 GUI（`http://127.0.0.1:8123` 的 `/agent/new`）看到红色提示「**计划服务未接通（assistant_endpoint_missing）**」，问"为什么计划服务一直未接通" `[S:plan-svc seq 8]`。这不是网络超时，也不是接口挂了。

### 7.2 根因（不是超时/网络）

链路：GUI 默认后端是 **mock（演示）**；mock 的 `get_plan()` 恒返回 `None`（`app/backend.py:375-378`，注释写明"假计划比没有计划更糟"）；`app/main.py:810-818` 把 `None` 映射成 `fallback_reason: "assistant_endpoint_missing"`；前端只如实展示，不伪造计划。所以在这个模式里换描述、重试、填 API key 都不会有变化——`get_plan` 根本不看 key。后端模式是进程启动时的单例（`main.py:92`），而 `start-gui.sh` 没有传 `BINARYREPAIR_BACKEND`，默认即 mock `[S:plan-svc seq 255]`。

**现场实测**（对正在运行的 127.0.0.1:8123）：

`@
GET /healthz -> {"ok":true,"backend":"mock","demo":true}
POST /api/assistant/plan -> HTTP 503
{"plan":null,"error":"assistant_unavailable","fallback_reason":"assistant_endpoint_missing"}
`@

### 7.3 修复与验证

**修复**：mock 后端不再直接 `return None`，而是走与 local 完全相同的 planner 接缝（`app/backend.py:375`）：

- 没配 provider key → 返回**确定性 5 步计划**（Sample → Defect → Valid inputs → …），页面标注「确定性计划（未调用模型）」；
- 配了 key（设置页保存或环境变量）→ 同一条路径走 LLM，返回模型生成的计划；
- 503「未接通」只保留给真正没有该路由的后端（如 http 模式下 controller 返回 404），不再无脑 503。

**验证**（重启后 `pid 24380`）：`POST /api/assistant/plan → 200`，`mode: deterministic | fallback: False | steps: 5`（upload/question/question/question/review）；日志里用户刚创建的 `job-8942bc3a` 正常走完建单→审批→开始；`tests/test_agent_console.py` 57 passed、`tests/integration/test_assistant_plan_endpoint.py` 全过 `[S:plan-svc seq 662]`。

**顺带发现的独立缺口**：controller 里 `mode="llm"` 的两个分支当时是无条件 503「no LLM client is configured on this host」（`controller_api.py:1690`、`:1718`），即使配了 key 也到不了模型；GUI 代理不带 `mode` 所以暂时踩不到，但真要做 LLM 计划必须先修 `[S:plan-svc seq 255]`（后续 11-12 已由 GUI/assistant 路径补齐）。

### 7.4 容易混淆的后续现象

- **服务端历史不跨设备**：用户 11-11 23:58 指出"服务端历史需要 M5 的 T8.1 持久化接入后才会跨设备可查"；后续用 SQLite `var/gui-history.db` + `GET/PUT /api/history/{scope}` 解决（同一服务实例内、带 session/CSRF；"真正跨设备"需要暴露服务，已在文档写明边界）`[S:plan-svc checkpoint 11-12 01:05]`。
- **"结果与证据"永久 loading**：11-12 16:03 的另一个症状是 `renderResult()` 在 `state.snapshot` 为空时进入"加载中"分支并把真实空态提示隐藏，导致未选任务时永远显示"正在计算证据覆盖…/正在读取证据层…"；根因是**空状态设计错误**，不是接口故障，修复为显式 N/A 空态（`f579a8d/3c06c05`）`[S:plan-svc seq 11073]`。

> 结论：计划服务"未接通"= **默认 mock 后端没有计划服务实现**（设计取舍：不伪造计划）；修复=接上真实 planner seam。演示模式下即使有模型 key 也需重启才生效；真实 LLM 计划还需 controller 的 `mode="llm"` 分支修复。

---

## 8. 各阶段能力声明边界（哪些是真实能力、哪些只是 fixture/演示）

### 8.1 真实能力（有可复核证据）

| 能力 | 证据 |
|---|---|
| **确定性验收引擎**：V0–V5 阶梯、六种 outcome（`success_within_scope/unsupported/rejected/inconclusive/error/cancelled`）、`not_run` 永不等于 passed | `app/domain/acceptance.py`、`outcomes.py`；124 重跑 V0–V5 全过；P2 exit 0；`FINAL-STATUS.md` |
| **两条独立路线在同一契约/测试上的实现**：Route A（指令重定向到验证过的 code cave）、Route B（恢复局部 C→重编译→回填）；双路线都 success 才算 run success | `jobs.py` ROUTES、`decide_run_outcome`；Route A candidate `c4a159`（10-22）、Route B roundtrip `decdcdb8…`（Gate4）、124（CWE-416） |
| **证据哈希/包/审计链**：contract canonical `24bfe568…4e37`、fixture original `aa428157…8393`、candidate `46d16e99…fcd0`、marker `fc4802d0…2b06`；SHA256SUMS 复核 | 各记录与交付包；v7 包 2,227/2,227 + 29/29 |
| **T8.3 通用性证据**：CWE-416 第二类样本 + 124 `success_within_scope`（model-scope V4） | records 133/150/170/171；§3 |
| **Gate 3/4/5 记录**：Gate3 批准 `0b3b51e4`；Gate4 严格范围 **unchanged round-trip**（6/6，不是修复证明）；Gate5A/5B placement | 记录 09/14/17/23/51/75 等 |
| **真实 GUI 工作台**：FastAPI+Jinja2，三后端（mock/local/http）、单一入口、证据控制室、9 语言、主题三态、连接器/插件（只读状态）、代码修复卡、历史持久化 | `binary-repair-gui/app/**`；测试 799/806/815 等；`docs/showcase/` 截图 |
| **代码修复能力（非二进制）**：15 条规则 + 可选 LLM；clang 语法检查 + 指针 sizeof/栈 free/容量守卫；不一致时拒绝自动补丁 | `code_repair.py`、`patch_validation.py`；`test_patch_validation.py` |
| **真实 DeepSeek 集成**：provider typed failures、预算/超时、JSON mode、真实 key smoke（deepseek-flash，38/5/43 tokens，1904 ms） | `docs/handoffs/216-real-deepseek-smoke-2026-11-09.md`、`221-m5-v1.2.1-key-smoke` |
| **v1.2.1 public stable**：741/739/2/0、e2e 12/12、release/tag/main 对齐（148d236/tag f687e14） | §4.3/4.4；B 版 handoff `7232a3fc…` |
| **Linux VM v7 交付件**：950/943/7/0、Mach-O 原生（macOS）、PE/AArch64 Unicorn、负向 fail-closed、F1 已知问题记录 | §6；`FINAL-LINUX-VERIFICATION.md` |
| **CGC 小样本**：5 对/10 个 Linux x86-64 ELF + 7 POV；2 个干净 crash 差分（Palindrome 3/3 稳定，basic_messaging exploratory） | `docs/acceptance/cgc-pov-2026-11-12.md`、`e5a9a76` |
| **DeepWorks 平台原生四层**：知识库 267 wiki、5 技能、每日自动化、Agent 会话产物（真实平台会话 ID 与输出文件） | §5.2；MIGRATION.md |

### 8.2 只是 fixture / 演示 / 模型级（不能当产品能力）

| 项 | 实际是什么 | 不能声称什么 |
|---|---|---|
| GUI 默认 mock 后端 / 8124 演示实例 | 合成 fixture、内存作业、无真实二进制执行；页内有 GUI-only 开发模式横幅 | "在线演示就是真实修复" |
| 1,200 条 overflow corpus / 12 个种子 | 合成/生成样本（`var/overflow-corpus` 被 gitignore；`data/overflow-corpus` 12 个带标签种子） | 真实漏洞修复成功率 |
| AI 复核实验（11-12） | 3 个用例、3 次模型调用、5,148 tokens；诚实结论"AI 没有新发现、没有改变任何决定"，且用例对 gate 平凡可判 | "AI 修复有用/无用"的普遍结论；只能说明该实验设计下零增量 |
| AI adjudication / 多 agent 循环 | 有界否决 + 运行时字段 guard（422 拒绝 verdict/outcome 等字段）；**确定性 gate 仍是最终裁决** | "AI 自己判定成功"；"AI 可提升失败 gate" |
| Gate 4 | unchanged round-trip；原始/patched 在 6 个 manifest 用例上行为相同；不是漏洞修复证明 | "Gate4 PASS = 漏洞已修" |
| V4 | model-level z3（bound 64）；124 的 unsat 是空析取（free_calls=0） | "binary-level/全程序证明" |
| Route A/B 的成功 | 只在已冻结 fixture（CWE-121/122/416）与受控 harness 上 | 任意二进制/任意漏洞 |
| CGC Mach-O arm64 盘点 | 5 对 Mach-O 仅静态盘点，未进管线、POV 未构建 | "CGC 已验证修复" |
| CGC Linux x86-64 | 交叉编译产物 + 2 个 POV 差分（exploratory），不是官方 CGC 语义（maths.S→libm、setjmp/longjmp abort 等漂移） | benchmark/主评估集 |
| PE/AArch64 运行时 | Unicorn 指令级（`emulated_run`），不是 Windows/Linux 内核运行 | "PE 已原生验证" |
| Mach-O 原生 | 仅 macOS 本机（arm64 + Rosetta x86-64）；Linux 上必须 `not_verified` | "Linux 上 Mach-O 已验证" |
| v1.2.1 公开仓库 | curated snapshot；raw guest evidence 不全在公开仓库；N-10/N-11 为披露限制 | "full MVP 全闭环"；"N-11 runtime guard 已实现" |
| 通用二进制修复（11-13） | 矩阵内（ELF/PE/Mach-O × x86-64/arm64 × 栈拷贝 sink）真实产出候选并过 runtime gate；矩阵外 fail-closed；F1 legacy fail-open 已知 | "任意二进制都能修"（这从来不是已证明能力） |
| DeepWorks 演示 | 平台原生执行，但输入是 fixture；`ok=true` 只表示本次请求步骤自洽 | "补丁正确/可交付生产" |
| 老师要求的"修复 ELF 上传" | 只存储/下载，角色 `operator_deliverable`，从不执行、不参与 verdict | "上传即验证" |

### 8.3 已知限制与未完成（与 11-13 交付件一致）

- **F1 fail-open**：`app/services/binary_pipeline.py::_from_elf_legacy` 在验证失败时仍可能返回候选；冻结源码未改，已在 HANDOFF-TASKS 给出复现与修复要求。
- **未实现**：T4 sprintf 格式展开；T5 UAF/整数/循环；32 位/大端/fat Mach-O 重写；堆/全局 sink；硬化 guest/KVM 隔离；Windows PE 原生运行；readelf 后端替换（LIEF/llvm-readelf）。
- **验证方法不足**：gate 尚未内建"PoC 失效"判据；方法建议 §4.2 第 4–6 层（模糊回归、符号/形式化、安全回归扫描）未接入。
- **独立性**：M4 = Lead 同一操作者；Gate 0 的 D1–D6 原文始终未找到，书面签到缺失（11-07 记录）。
- **平台差异**：Windows full suite 未独立跑通；Windows DPAPI 未验证；macOS 缺 GNU readelf 曾致固定失败（后装 binutils 解决，但属环境依赖）。
- **发布口径**：v1.2.1 stable 的 N-11 是 docs-only；N-10 是 accepted limitation；公开仓库是 curated snapshot。

### 8.4 诚实性事件与纠正（项目可信度的一部分）

1. **CI 假 success（11-12 23:30）**：`a436b64`/run `43248544193` 实际失败被写成 success 并写进 `ubuntu-verification.md`/`DELIVERY.md`/`README.md`；由外部分析发现，`774c584`/`0fe9241`/`2aca931` 纠正并重跑绿（§4.5）。
2. **T8.3 拒绝造假**：V4 数据模型没有落点时，团队拒绝"手跑 angr 贴结果"、拒绝写假 `verified_by="m4"`；改为记录 126/131/132 的阻塞与修复路径，直到 M4 真正 replay 后才关闭（§3）。
3. **测试计数错误**：v1 包把 `846 + 2 + 0 ≠ 849` 写成同一套数，被评审指出后按"0 failed + 实际 JUnit + CI run"口径重写。
4. **证书/哈希卫生**：CRLF 导致 `shasum -c` 失败、嵌套 SHA256SUMS 失配、私钥不入包、key 不回显不写日志——都在 v6→v7 或 v1.2.x 修复。
5. **"任意二进制"话术收敛**：用户多次要求"修复任意二进制"，团队反复给出范围矩阵与 fail-closed 声明，未把矩阵外能力写成已实现（v7 TASKS/README 明确"not universal repair"）。
6. **DeepSeek 零结果如实上报**：AI 复核三案"零增量"直接写进交付与对外建议，而不是包装成"AI 已参与修复"。
---

## 9. 大时间线（2026-10-10 → 2026-11-13）

| 日期/时间 | 事件 | 证据 |
|---|---|---|
| 10-10 / 10-13 | 课程/华为材料就绪：`项目大纲.docx`（10-10）、`项目介绍.pptx`（10-13，5 步流程） | 文件 mtime |
| 10-15 16:39-17:30 | 克隆 REA、5 个子模块、Node 24.18.0、rea-agents 6.5.0、注册 DSH（207 MCP 工具） | `[S:history-m4 seq 42/75/221]` |
| 10-15 17:32-17:56 | "研究想法/MVP 定义"：澄清 5 步工作流、产出两份 docx、确认技术档位 C | `[S:history-mvp seq 329/389/404]` |
| 10-15 18:40 | git Initial commit `132ad98`（作者 chenfanaichifan） | `[git:132ad98]` |
| 10-15 20:48-20:49 | 三份 PDF：research / PRD / TechDesign | 文件 mtime/size |
| 10-18 16:49 起 | 五人小组主线会话开始；M5 接到 DeepSeek adapter + schema 任务；分支上传、改名、接口对齐 | `[S:history-m1 seq 8/314/456/633/781]` |
| 10-20 | M5 合入 main `1250169`（83 tests）；Gate4 首次真实 CI `39752557610`；Route A cave/契约 v2（`24bfe568…`）；同日生成 project_brief/testing/tech_stack/code_patterns PDF | `[S:history-m1 seq 2054/3953]` |
| 10-22 | Route A candidate `c4a159`、contract 0x401309、v6 kit `499f510c`；仓库清理 tag `archive/2026-10-22/pre-cleanup`；Gate3 条件可行 | `[S:history-m1 seq 5710]` |
| 10-29 | Gate3 正式批准 `0b3b51e4…`；P3A v6/P3B v6/P4 v3 证据包；PR #10 关闭 | `[S:history-m1 seq 9784]` |
| 10-31 | Gate4 严格范围 PASS、Gate5A PASS；首次出现公开仓库 `leesirleesirlee-star/Binary_Repair` | `[S:history-m1 seq 9852/11594]` |
| 11-03 | 公开仓库 main `0070103f`、tags `mvp-2026-10-31`/`v1.0.0`；五成员任务分配/要求-差距两份 docx；record 87；基线 265/262/2/1；M5 切新仓库但推送权限不足 | `[S:history-m1 seq 9865/9947/10291]` |
| 11-05 | M1/M4/M5 密集跑：118 重建验证、119/120 contract v3、124 CWE-416 复跑（`inconclusive/required_check_not_run`）；V4 `not_run`；T8.3 BLOCKED；记录 116/118/119/120/125/126 | `[S:m1-3342/history-m4/lead-07d5]` |
| 11-06 10:44-16:43 | 记录 126/131/132（V4 数据模型、verified_by 门禁、环境与 PIE 口径）；T30 rebuild；CWE122；ELF type check `3a107ab` | `[S:lead-07d5 seq 442/675/824]` |
| 11-06 17:40 | 上传 6 分支/44 commit/383 文件；T8.3 状态 BLOCKED；生成 21 页 PDF；纯英文进展报告 | `[S:t83-217a seq 456/1338/1590]` |
| 11-07 | M4 安装公钥→`verify_all.sh` 3/3→V4 harness ×2→marker `fc4802d0`；124 V0–V5 全过 `success_within_scope`；T8.3 COMPLETE（150/170/171）；FINAL-STATUS；Review 9–12 PASS | `[S:history-m1 checkpoint 17305/20444]` |
| 11-08 | DeepWorks 迁移（滴普杯赛道 C，四层重建）；公开 v1.1.0 `1e30bd5`；全量 714 passed/2 skipped（后 719 collected）；deliverable 上传功能；11-08 17:41 花费快照 ¥125.61 / $18.81 | `[S:deepworks seq 16/1360]`、`[S:history-m1 seq 23450]`、`[S:history-mvp seq 577]` |
| 11-09 | 公开 v1.2.0 `9439340`（tag v1.2.0）；真实 DeepSeek smoke（43 tokens/1904 ms）；v1.2.1-rc1 candidate；N-8/9/10/11 review；public 推送权限阻塞 | `[S:history-m1 11-09/11-10]` |
| 11-10 | v1.2.1-rc1 以 prerelease 发布（tag `f5346978…`→`d7d20f4`）；N-11 docs-only 修正；stable HOLD；public main 仍 9439340 | `[S:history-m1 seq 25565-25796]` |
| 11-11 19:17-21:58 | 全员跑通→Lead 批准 stable→M4 发布 v1.2.1 stable（`148d236`/tag `f687e14`，main 前移）→M1 handoff `7232a3fc…`→Lead 关闭；M5/M3/M2/M4 必须任务=0 | `[S:history-m1 seq 25816/25899/26347-26449]` |
| 11-11 22:21-22:31 | 计划服务排查：mock backend `get_plan` 返回 None → 503 assistant_endpoint_missing；接真实 planner seam 后 200/确定性 5 步 | `[S:plan-svc seq 8/255/662]` |
| 11-11 23:18-11-12 16:12 | GUI 大改版（单入口、主题三态、连接器/插件、9 语言、证据控制室、AI 判定、代码修复卡、历史持久化）；微信分享包（4,857,723 B）、ngrok + 局域网演示 | `[S:plan-svc]`、`[file:WeChat-Share]` |
| 11-12 15:31-23:11 | `public-v1.2.1-docs.patch`；CGC 克隆与 POV 重放（`e5a9a76`）；AI 复核三案"零增量"；workbench-v3 多提交（`dfa7d14/f04068e/f510361/e5a9a76`） | `[S:plan-svc/cgc/fix-ci]` |
| 11-12 22:52-23:29 | 发起 Linux VM handoff；Init/v1 包产出；评审指出 v1 过期/T0 失败/计数错误等 | `[S:vm-pkg seq 8/1324]` |
| 11-13 00:11 | v2（`14a45ccd…`）产出；评审指出 CI 假 success 与 flake 未修 | `[S:vm-pkg seq 2800]` |
| 11-13 00:12-00:20 | `774c584`（编译器超时→unavailable）、`0fe9241`（gate-blind 局限）、`2aca931`（flake 归因）；Ubuntu CI 三绿 | `[git/fix-ci]` |
| 11-13 14:17-14:34 | v3 产出于 `c0cbffc`（14:17）；v3 评审 15:16"内容可以通"；v3 包 `d542dce0` 14:22 | `[S:v3-review seq 11]`、`[S:vm-pkg]` |
| 11-13 15:15-15:58 | v3-review 会话实现通用二进制修复（containers/analyzer/guards/writer/runtime/gate）；v4 代码 `a6226cb`（15:53）、v5 包 `19b8eeb1`（15:58） | `[S:v3-review seq 2110]` |
| 11-13 16:07-17:06 | v6 包（16:17，`da5f4fda`）、v6.1（16:58，并行会话）、v7（16:58，`2afeb6c8`）；e1756a2 Linux VM v4 matrix（16:07）；v7 Linux VM 全新复跑 950/943/7/0（17:00-17:06） | `[file:handoff]`、`[file:FINAL-LINUX-VERIFICATION.md]` |
| 11-13 16:13 | `方法建议_大模型二进制漏洞修复Agent_20261113(1).md`（外部方向建议，成为 v7 检验的对照文档） | 文件 mtime |
| 11-13 16:15 | s1（Linux 虚拟机验证漏洞修复-1）开始——**超出本文范围**（由 s1 负责） | 会话清单 |
---

## 10. 未核实项与证据缺口（诚实声明）

1. **公开仓库创建时间**：首次在会话出现是 2026-10-31 23:31，tags `mvp-2026-10-31`/`v1.0.0` 指向公开 main `0070103f`；GitHub API 写作时被限流（403），**未直接核实**。
2. **开发仓库可见性**：10-20 checkpoint 称"main is public"，11-06 报告称仓库为"私有"；两说并存，**未核实**变更时间与最终状态。
3. **GitHub release 页面/tag 对象**：v1.2.1 stable/rc1 的 tag object、prerelease 状态来自会话内 GitHub API 实查记录；本文未重新抓取 release 页面（部分抓取超时/是 JS 数据）。
4. **CI run 结论**：run 号与结论来自会话报告/部分 API 实查；个别 run（如 43244713385 等）未逐一二次核对。
5. **Gate 0 / D1–D6**：11-06 Lead 明确"工作区里找不到任何定义"（全仓 pickaxe 零命中，TechDesign 的 D1–D6 是参考文献编号）；最终书面签到是否补齐**未核实**。
6. **项目计划书.docx**：会话早期引用的 `项目计划书.docx` 在 11-12 归档中未找到（可能不在归档范围）。
7. **v6.1 的生产会话**：v6.1 由"并行会话"产出，不在本工作区会话清单内（可能在其他机器/其他 App 实例），**未核实**其会话记录。
8. **粘贴式评审报告**：vm-pkg 会话里多段"结论：v3/v6 内容可以通…"用户消息来自另一台 Windows 主机/另一 AI 会话的评审（内容在会话内可复核，但评审执行环境不在本机）。
9. **测试数字跨环境差异**：macOS/Linux/Windows 的 collected/passed/skipped 各不相同（如 888/883/4/1、950/946/4/0、950/943/7/0、741/739/2/0），本文均按原记录并列，不合并成单一数字。
10. **真实端到端"两条路线都 success"的范围**：124 是 CWE-416 单样本、model-scope V4；Gate4 是 round-trip；P2 的 success 是受控 harness 内。**不能外推为任意样本成功率**。
11. **DeepWorks 平台服务端当前状态**：本文依据 11-08/11-11 的平台操作与归档文件，未重新登录平台核对知识库/自动化/会话当前状态。
12. **微信分享 token/链接**：为当时实例的真实分享凭据（mock 实例），已随服务停止而失效；文中保留仅为历史证据，**不应再复用**。

---

## 附录 A：关键 commit / 分支（git 可复核）

**分支（本机 `git for-each-ref refs/heads` 可核对）**

| 分支 | tip | 日期 | 用途 |
|---|---|---|---|
| `canonical/m1-m5-integration` | `3a107ab` | 11-06 | M1/M5 集成分支（CWE122 ELF type check） |
| `delivery/t83-2026-11-06` | `df99853` | 11-06 | T8.3 383 文件归档 |
| `m1/t30-acceptance-ab-2026-11-05` | `101d034` | 11-07 | M1 T30 验收/live-bridge；含 `50cfe41` |
| `m5/elf-type-check` | `a63f80d` | 11-06 | intake 拒绝 PIE fixture |
| `m5/t83-deliverables-2026-11-07` | `cdcbb4a` | 11-07 | T8.3 交付/apply_candidate pre-layer |
| `member-5/complete-m5` | `4c36898` | 11-05 | contract v3 no-input |
| `delivery/all-hands-2026-11-07` | `c3bca0e` | 11-08 | all-hands 交付整合 |
| `handoff-v3-local` | `c0cbffc` | 11-13 | v3 统一 scan/repair 管线 |
| `handoff-v4-local` | `3d5d0f0` | 11-13 | 通用修复交付线（e1756a2 为其父线） |
| `feature/universal-repair` | `72db891` | 11-13 | 通用修复后续 |

**关键 commit（git 可核对时间与标题）**

`@
132ad98 2026-10-15 18:40  Initial commit
774c584 2026-11-13 00:12  fix(ci): treat compiler validation timeouts as unavailable
0fe9241 2026-11-13 00:16  docs: record gate-blind review limitation and next experiment
2aca931 2026-11-13 00:20  docs: note flaky test is rule-only, not model-dependent
dfa7d14 2026-11-12 13:16  chore(delivery): publish clean team preview zip and share templates
f04068e 2026-11-12 14:46  fix(i18n): translate dynamic messages, code repair and full page copy
f510361 2026-11-12 14:09  docs(showcase): refresh final light landing
e5a9a76 2026-11-12 23:11  feat(cgc): replay CGC POVs on cross-compiled linux x86-64 builds
c0cbffc 2026-11-13 14:17  feat(binary): unified scan/repair pipeline across ELF, PE and Mach-O
a6226cb 2026-11-13 15:53  feat(binary): container-neutral repair for ELF/PE/Mach-O with runtime gates
e1756a2 2026-11-13 16:07  evidence(binary): record Linux VM v4 matrix and final counts
3d5d0f0 2026-11-13 16:44  docs(binary): close v6.1 delivery evidence gaps
72db891 2026-11-13 18:55  docs(binary): record both Ubuntu verification runs for v5
`@

**关键 tag（本机可核对）**：`mvp-2026-10-31`、`v1.0.0`、`public-v1.2.1`、`v1.2.1-rc1-source-99d1550`、`archive/2026-10-22/pre-cleanup` 等（另有大量 `archive/2026-10-22/member-*` 归档 tag）。

## 附录 B：CI run 索引

| run | 日期 | 结论 | 说明 |
|---|---|---|---|
| 39752557610 | 10-20 | success | Gate4 首次真实 CI（Ubuntu 24.04 + Ghidra 12.2 + Patcherex2） |
| 43242554914 | 11-12 | 539 passed / 1 failed | fixture PermissionError（之后修 staging） |
| 43244713385 | 11-12 | success | fixture 修复后 |
| 43246391510 | 11-12 | success | 同上（v1 评审引用） |
| 43248090960 | 11-12 | success | 早期文档曾错配链接 |
| 43248205593 | 11-12 | success | df82b6c |
| 43248395728 | 11-12 | success | 5d8d006 |
| 43248544193 | 11-12 23:30 | **failure** | a436b64，编译器超时 flake；曾被误记为 success |
| 43249875815 | 11-12 23:37 | success | 9a451fd（纯 docs） |
| 43256190605 / 43256481655 / 43256887551 | 11-13 | success | 774c584 之后；0fe9241 → 889/1/0/890 |
| 43390831537 | 11-13 | success | e1756a2（v7 交付声称的 CI） |
| 43395652244 | 11-13 | success | 3d5d0f0（v6.1 docs） |

## 附录 C：关键文档与交付件索引

| 类别 | 路径 | 说明 |
|---|---|---|
| 项目起源 | `~/Desktop/BinaryRepair-archive-2026-11-12/` 下 `项目大纲.docx`、`项目介绍.pptx`、`research-BinaryRepair.pdf`、`PRD-BinaryRepair-MVP.pdf`、`TechDesign-BinaryRepair-MVP.pdf` | 10-10/10-13/10-15 |
| 11-03 计划 | `…/BinaryRepair_MVP_要求_差距_解决方案_2026-11-03.pdf`、`…五成员任务分配与项目完成计划_2026-11-03.pdf` | 要求-差距-方案、分工 |
| T8.3 | 仓库 `docs/handoffs/{87,133,136,150,170,171}` 系列 | 定义/样本/关闭 |
| T8.3 地址报告 | `BinaryRepair-2026-11-06-GitHub上传地址与T8.3说明.pdf`（21 页）、`GitHub-上传地址-2026-11-06.md` | 11-06 |
| v1.2.1 | `delivery/handoff-v1.2.1-stable-2026-11-11.zip`（`7232a3fc…`）、`delivery/v1.2.1-stable-148d236/v1.2.1-stable-148d236.bundle`、`public-v1.2.1-docs.patch` | 11-11/11-12 |
| v1.2.1 review | `docs/reviews/review-13-key-store-2026-11-09.md`、`docs/reviews/review-9-12-*` | review 9–13 |
| 微信分享 | `WeChat-Share/` 下 `BinaryRepair-Workbench-2026-11-12.zip`、`README-微信分享.md`、`群消息-可直接粘贴.txt` | 11-12 |
| DeepWorks | `~/Desktop/BinaryRepair-archive-2026-11-12/deepworks/`（README/MIGRATION/REGISTRATION/track-c-mapping/overview…） | 11-08/11-11 |
| CGC | `binary-repair-gui/docs/acceptance/cgc-pov-2026-11-12.md`、`knowledge/cgc_corpus.json`、`knowledge/cgc_linux_x86_64.json` | 11-12 |
| 通用修复 | `binary-repair-gui/docs/acceptance/binary-universal-v4-2026-11-13.md`、`fixtures/PROVENANCE.json`、`artifacts/binary-universal-v4-2026-11-13/` | 11-13 |
| VM handoff | `handoff/BinaryRepair-Linux-Handoff-2026-11-13-v7.zip`（`2afeb6c8…`）、`handoff/archive/`（v1–v6.1）、`handoff/final-verification-2026-11-13/` | 11-13 |
| 方法建议 | `方法建议_大模型二进制漏洞修复Agent_20261113(1).md` | 11-13 |
| 花费快照 | `[S:history-mvp seq 577]` | 10-15→11-08 约 ¥125.61 / $18.81 |

## 附录 D：会话清单（`.tmp/sessions/`）

| 文件 | 会话 | 事件数 | 时间范围 |
|---|---|---|---|
| history-m4.jsonl | M4 | 5,856 | 10-15 16:39 → 11-11 20:46 |
| history-mvp.jsonl | 研究想法与MVP定义指导 | 581 | 10-15 17:32 → 11-08 17:41 |
| history-m1.jsonl | M1、4、5、Lead | 26,453 | 10-18 16:49 → 11-11 21:58 |
| m1-3342.jsonl | M1 | 10,260 | 11-05 22:03 → 11-07 22:20 |
| lead-07d5.jsonl | Lead | 1,291 | 11-05 22:52 → 11-12 23:12 |
| m1-e442.jsonl | M1 partial 语义并入 canonical | 1,043 | 11-06 16:05 → 16:30 |
| m1-3822.jsonl | M1任务：partial 与 canonical 关系 | 986 | 11-06 16:10 → 16:26 |
| t83-217a.jsonl | 查询GitHub上传地址及T8.3说明 | 1,595 | 11-06 18:00 → 21:40 |
| deepworks.jsonl | 迁移项目成果至DeepWorks平台 | 4,153 | 11-08 19:11 → 11-11 22:30 |
| plan-svc.jsonl | 计划服务未接通原因排查 | 18,756 | 11-11 22:20 → 11-14 15:48 |
| cgc.jsonl | CGC 克隆用途与替代方案 | 1,750 | 11-12 19:55 → 20:42 |
| vm-pkg.jsonl | 生成虚拟机任务压缩包 | 5,854 | 11-12 22:52 → 11-13 16:59 |
| fix-ci.jsonl | Fix CI and AI review milestone | 3,052 | 11-12 23:00 → 11-13 00:22 |
| v3-review.jsonl | 通用二进制修复（v4/v5） | 2,115 | 11-13 15:15 → 15:58 |
| （不在本文）s1-linuxvm.jsonl | Linux 虚拟机验证漏洞修复-1 | 19,358 | 11-13 16:15 → 11-16 |
| （不在本文）s2-alltypes.jsonl | 全类型二进制修复-1 | 16,662 | 11-14 15:12 → 11-16 |

---

*本文由 history-analyst 生成，所有数字均照抄会话/仓库/交付件原始记录；无法本机复核处已标注"未核实"。*
