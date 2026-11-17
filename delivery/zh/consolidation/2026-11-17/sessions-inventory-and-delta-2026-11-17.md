# 03 · 全量会话清单、目标演进、11-16→11-17 增量

> 作者：协作子 Agent #3（分工：全量会话清单 + 目标演进 + 11-16 后增量）
> 时间：2026-11-17 09:00 SGT　范围：本工作区 41 个顶层会话 + 43 个子会话；重点补 2026-11-16 08:06（旧报告截止）→ 2026-11-17 01:31（会话二终）的增量。
> 方法：`zstd -dc session.v4.jsonl.zstd` 流式解析（`.tmp_inventory.py` / `.tmp_extract.py`，见 `review/2026-11-17/`），配合 `git log/show/ls-remote` 只读核验。所有数字均为本次重新测量，未照抄旧报告。
> 状态口径：**已验证**（有测试/CI/产物证据）｜**仅文档/声明**｜**部分实现**｜**未运行（not_run）**。

---

## 0. 一页结论

1. **会话总量**：41 个顶层会话（129,750 事件，102.9 MB）+ 43 个子会话（266,075 事件，143.2 MB），合计 **84 个目录 / 246.1 MB**。其中 **12 个"种子 fork"占 92.6 MB / 219,998 事件**——它们是 11-16 22:38 与 22:44 两次"6 路强制协作"派生的子会话，**整段复制父会话历史**，不是独立工作。所谓"两个大会话 17MB/15MB"只是父本，真实磁盘开销是 6 倍。
2. **旧报告附录 A 的 38 会话表已过时**：现为 **41 个**，新增 3 个（`b75be565` 门户轮、`0dd3685e` 空会话、`0842a3d0` 本轮 Lead），**无删除**；**归档从 7 个变 8 个**（`791a36c4` 已归档）。
3. **目标演进比旧报告的"三段/五段"更细**：实际是 **六个阶段**（课程 MVP → 任意二进制 v4–v7 → AI 修复研究 P0–P24 → 自主能力设施 Phase-7/8A/8B/8C → 产品化 + 四成员能力攻关 → P31–P40/Phase-8D 双线）。旧报告把后两段合成一段，漏掉了 P31–P40 的**路线定义**（用户 11-16 22:38 明确给出 P31–P40，只落地 P31–P34）。
4. **11-16→11-17 的核心增量是两条 6 路并行的新线**：`P31–P34`（统一 LLM Gateway/OpenRouter/Ollama/preflight/stability，**离线实现，真实网络调用全部 NOT_RUN**）与 `Phase-8D`（D00–D10 开放世界发现与 Acceptance 2.0，**8 个审计缺口仍 open，0 能力晋级**）。
5. **最关键的仓库事实（旧报告与任务说明都未覆盖）**：`final/consolidated-2026-11-16` 的 tip 是 `c0f9feb`（只含 P31–P34），**不含 Phase-8D**；含 Phase-8D 的完整树是 `a1d7150`（`release/2026-11-17-phase8d-final-evidence`）。原因是 **11-17 00:45:57 会话一试图把 `d37bfad` 推到 `final/consolidated-2026-11-16` 时被 non-fast-forward 拒绝**（`anc=1`，`hint: before pushing again`），随后会话陷入重复工具调用并终止。**合流动作至今没有完成。**
6. **本地备份已明显落后**：`backup/binary-repair-mirror-2026-11-16.git` 含 `f1bb1f4`，**不含** `c0f9feb / d37bfad / 996060d / a1d7150`（本次逐个 `cat-file -e` 实测 ABSENT）。也就是说 11-16 12:19 之后 13 小时的成果**只存在于工作树与 GitHub 远端**，无离线副本。
7. **数字层面新增可信锚点**：c0f9feb 树全量套件 **2319 passed / 0 failed / 9 skipped**（离线）；d37bfad 本地冻结树 release gate **13/13**、全量 pytest **1,064,207 ms（≈17.7 min）通过**；d37bfad 的 GitHub CI run `43907137267` 与 Ubuntu `43907136876` 均 success。

---

## 1. 全量会话清单（41 个顶层会话，含 8 个归档）

数据来源：`~/.dsh/storages/workspace.json` → `tables.workspaces[1dee4cf4-…].sessionIds`（41 项）+ `global.archivedSessionIds`（本工作区命中 8 项）；逐会话解析 `session.v4.jsonl.zstd`（事件数、首末时间、末次 `session/title`、压缩体积）。

| # | 开始 | 最后事件 | 标题（末次） | id 前缀 | MB | 事件 | 归档 |
|---|---|---|---|---|---|---|---|
| 1 | 10-15 16:39 | 11-11 20:46 | M4 | 4f9a2f7d | 5.1 | 5,856 | 是 |
| 2 | 10-15 17:32 | 11-08 17:41 | 研究想法与MVP定义指导 | 4fbcfd05 | 0.8 | 581 | 是 |
| 3 | 10-18 16:49 | 11-11 21:58 | M1、4、5、Lead | cb06ee4c | 22.4 | 26,453 | |
| 4–16 | 10-22 16:56 → 10-23 13:41 | 同左 | （空会话，4 事件） | 42f57a46 / 1edb1a82 / 2f54838b / f48df004 / ff9c020b / a1cdccb9 / b67c86c7 / ba1995bd / 3327ffaa / 3d349441 / 474688b9 / 729f766f / aff70696 | 0.0 | 4×13 | |
| 17 | 11-05 22:03 | 11-07 22:20 | M1 | 3342aabf | 7.1 | 10,260 | 是 |
| 18 | 11-05 22:52 | 11-12 23:12 | Lead | 07d5319d | 1.0 | 1,291 | 是 |
| 19 | 11-06 16:05 | 11-06 16:30 | M1 partial 语义并入 canonical | e44273d9 | 0.8 | 1,043 | 是 |
| 20 | 11-06 16:10 | 11-06 16:26 | M1任务：partial 与 canonical 关系 | 38221d41 | 0.7 | 986 | 是 |
| 21 | 11-06 17:38 | 11-06 17:38 | （空） | caf358f3 | 0.0 | 4 | |
| 22 | 11-06 18:00 | 11-06 21:40 | 查询GitHub上传地址及T8.3说明 | 217a1378 | 1.2 | 1,595 | 是 |
| 23 | 11-08 19:11 | 11-11 22:30 | 迁移项目成果至DeepWorks平台 | 5a19b610 | 3.2 | 4,153 | |
| 24–26 | 11-09 20:28 / 20:47 | 同左 | （空） | a50c362f / ad717231 / c20f3715 | 0.0 | 4×3 | |
| 27 | 11-11 22:20 | 11-14 15:48 | 计划服务未接通原因排查 | 190e48d8 | 14.5 | 18,756 | |
| 28 | 11-12 19:55 | 11-12 20:42 | CGC 克隆用途与替代方案 | 04d75281 | 1.1 | 1,750 | |
| 29–31 | 11-12 19:55 / 22:52 | 同左 | （空） | 1309dc6c / 892c4d59 / 5bdf6473 | 0.0 | 4×3 | |
| 32 | 11-12 22:52 | 11-16 21:36 | 生成虚拟机任务压缩包 | 7c2cc0ef | 3.8 | 5,855 | |
| 33 | 11-12 22:52 | 11-16 08:38 | （空，7 事件） | 8152265e | 0.0 | 7 | |
| 34 | 11-12 23:00 | 11-13 00:22 | Fix CI and AI review milestone | 336db26b | 2.2 | 3,052 | |
| 35 | 11-13 15:15 | 11-13 15:58 | **结论：v3 的内容层面可以通 | ce323436 | 1.7 | 2,115 | |
| 36 | 11-13 16:15 | **11-17 00:46** | Linux 虚拟机验证漏洞修复-1 | 879cc62f | 16.3 | **19,989** | |
| 37 | 11-14 15:12 | **11-17 01:31** | 全类型二进制修复-1 | b139b586 | 14.6 | **18,457** | |
| 38 | 11-16 08:06 | 11-16 17:56（end-seed 11-17 08:43） | 项目回顾与四成员任务分配 | 791a36c4 | 2.6 | 2,926 | 是 |
| 39 | 11-16 09:35 | 11-16 09:38 | （空，5 事件） | 0dd3685e | 0.0 | 5 | |
| 40 | 11-16 18:37 | 11-16 20:27 | 测试网页并修复 ELF 文件 | b75be565 | 3.4 | 4,104 | |
| 41 | 11-17 08:43 | 11-17 08:47 | 回顾会话并汇总项目文档（本轮 Lead） | 0842a3d0 | 0.4 | 436 | |

**与旧报告附录 A（38 个 / 7 归档）的差异**

| 类型 | 结论 | 证据 |
|---|---|---|
| 新增 3 个 | `b75be565`（门户轮，4104 事件）、`0dd3685e`（空，5 事件，11-16 09:35）、`0842a3d0`（本轮 Lead，436 事件） | 旧报告 `项目总体回顾…2026-11-16.md:1547-1591` 对比本次 41 项 sessionIds |
| 删除 0 个 | 38 个 id 全部仍在 sessionIds 内 | 集合差 `old-cur = ∅` |
| 归档 7→8 | `791a36c4` 进入 `archivedSessionIds`；其余 7 个不变 | `workspace.json` → `global.archivedSessionIds` |
| 体积口径变化 | 879cc62f 16.6→**16.3 MB / 19,989 事件**；b139b586 13.6→**14.6 MB / 18,457 事件**（旧报告为压缩前估算） | 本次 `os.path.getsize` |
| 旧报告"16.6/13.6 MB" | 与本次测得不同，属**计量口径差异**，不影响结论 | 同上 |
| 空会话仍是 13 个 | 10-22(8)、10-23(5) 的 13 个 4 事件会话 + 11-06/09/12/16 各若干 | 表内 #4–#16 |

### 1.1 子会话结构（43 个，depth=1）

| 类别 | 数量 | MB | 事件 | 说明 |
|---|---|---|---|---|
| **种子 fork**（`isSeeded=true`，`origin=subagent`） | **12** | **92.6** | **219,998** | 11-16 22:38–22:46 由两次"6 路强制协作"派生，**完整复制父会话历史**（17–19k 事件/个），随后只追加 100–400 个新事件就结束 |
| 普通子 Agent（`isSeeded=false`） | 31 | 50.7 | 46,077 | 791a 的 8 个（s1/s2/history/repo 审计 + M1–M4）、b75be565 的 3 个（门户前端/漏洞 ELF/独立验收）、两个大会话的工具型 teammate（i386 引擎、heap-engine、pipeline、audit-tools 等） |
| 合计 | 43 | 143.2 | 266,075 | — |

**12 个 fork 与分工**（这是"6 路并行"的真实内容，旧报告完全未记录）：

| 父会话 | fork id | 序号 | 分工（`## 你这一份的分工`） | 新工作截止 |
|---|---|---|---|---|
| 879cc62f | 51d2fd7c | 1/6 | 审计现有 LLM/Key/config 双轨逻辑，输出兼容接口与风险（只读） | 11-16 22:41 |
| 879cc62f | 6850f239 | 2/6 | 实现 LLM Gateway 核心包 + OpenRouter/Ollama/Mock adapters（只写新包） | 22:41 |
| 879cc62f | bfdd3a3d | 3/6 | 凭证 / typed errors / usage 子模块及离线测试 | 22:41 |
| 879cc62f | 978ac2c0 | 4/6 | 把 assistant_llm / binaryrepair_ai / ai_* 调用点接入 gateway，保留兼容 | 23:10 |
| 879cc62f | 628458cf | 5/6 | 修 stability runner 超时/状态/checkpoint/expected counts 并写测试 | 22:41 |
| 879cc62f | 4c44ab6e | 6/6 | 写离线集成测试、验收文档并复核 P31–P34（不改生产代码） | 22:43 |
| b139b586 | e1aa4f68 | 1/6 | D00+D01 基线冻结与 capability universe | 22:51 |
| b139b586 | fbd3df43 | 2/6 | D04 heap-malloc ABI 根因独立分析 | 22:52 |
| b139b586 | 0d7b605e | 3/6 | D05 hidden 0-candidate 阶段归因（匿名聚合） | 22:52 |
| b139b586 | 7384706a | 4/6 | D03 Acceptance 2.0 变异 / 假接受 / 假拒绝审计 | 22:51 |
| b139b586 | 8943a46a | 5/6 | D06+D07 外部知识扫描 + 真实变异/蜕变发现机制 | 22:58 |
| b139b586 | b0e57d68 | 6/6 | D02+D09+D10 Gap Registry / 隔离审计 / 晋级门 | 22:57 |

> **D08（实验/证据 Bundle）没有对应 angle**，由父会话（b139b586）自行补齐，这也解释了它为何最"薄"（10 条记录，全部 `promotion_effect=none`）。

---

## 2. 目标演进（2026-10-15 → 2026-11-17，六阶段）

| 阶段 | 时间 | 目标定义 | 关键产出 | 状态 |
|---|---|---|---|---|
| **① 研究想法 + MVP**（会话 2、1） | 10-15 → 10-31 | 把《方法建议》的 5 步 REA 方法论落成可演示、可审计的二进制修复工作台（Route A 调用重定向 + Route B 恢复重编译 + V0–V5 验收） | 研究想法/MVP 定义、项目大纲、M1–M5 五人角色体系、T8.3（CWE-416 no-input 契约） | **已完成**（含遗留） |
| **② 公开稳定版**（会话 3、17、18、22、23） | 10-31 → 11-11 | 从"五人角色协作"收口成 v1.2.0/1.2.1 公开稳定版 + WeChat 分享包 + DeepWorks 迁移 | 889/1/0（Ubuntu CI）、v1.2.1 tag、docs/handoffs 1.2.1 系列、118 VERIFIED / 124 inconclusive | **已完成** |
| **③ 任意二进制 v4–v7**（会话 27、32、34、35、36） | 11-11 → 11-13 | 从"单 fixture"扩到 ELF/PE/Mach-O × x86_64/arm64/i386 的确定性矩阵；任意文件 triage + 明确 disposition；Linux VM 权威验收交付件 v6→v7 | v5 任意二进制（`72db891`）、两条 AI 路径（`aa45b36`）、v7 交付件 950/943/7/0、CI `43390831537` | **已完成** |
| **④ AI 修复研究 P0–P24**（会话 36） | 11-13 → 11-16 | 两条 AI 直接修复路径（asm_roundtrip / binary_direct）+ 真实 provider + 真实失败反馈 + 跨二进制 benchmark + 独立验证器 + 稳定性实验 | P16-R3 严格 7/10、P21 冻结 profile、P22 8 recovered/2 missing、P23 runner+smoke；**CWE-121/134 负结果、60 次未完成** | **部分完成** |
| **⑤ 自主能力设施 Phase-7/8A/8B/8C**（会话 37） | 11-14 → 11-16 | 66/68 项能力缺口自发现、Autonomy Foundation、Ground Truth v2 + Hidden Benchmark、验收模型审计、Release gate 13/13 | `2bfa112`→`bd9cbf6`→`227f45b`→`4a7b235`；17 合同 / 240 cells / 30 场景 meta-audit / 64 gap；**未新增修复能力** | **基础设施完成** |
| **⑥a 产品化 + 四成员能力攻关**（会话 38 `791a`、40 `b75be565`） | 11-16 08:06 → 11-16 20:27 | 复盘定稿 + 战略重排（能力与产品优先）+ M1–M4 四成员首增量 + 固定成果门户 + 漏洞 ELF 样本 | 166KB 总报告、四份 `M1–M4任务.md`、`final/consolidated-2026-11-16`=`f1bb1f4`、portal `127.0.0.1:8899`、`vuln-demo-x86_64.elf` | **已完成首增量** |
| **⑥b P31–P40 + Phase-8D**（会话 36 尾、37 尾） | 11-16 22:38 → 11-17 01:31 | 会话一：P31–P34（统一 LLM 调用层 / OpenRouter+Ollama / 凭证 preflight / 稳定性 runner）；会话二：Phase-8D D00–D10（开放世界发现与 Acceptance 2.0） | `a9db731`+`c0f9feb`（P31–P34）、`d1b73bf`→`996060d`（8D）、`d37bfad`（P31–P34 × 8D 树）、`a1d7150`（最终证据）；**P35–P40 未开始** | **部分完成，且未合流** |

### 2.1 阶段判据的三次变化（比旧报告"三次演进"更准确）

1. **10-15 → 10-31：以"能演示"为判据**。产出物是文档 + 五人角色分工 + V0–V5 验收口径；"完成"= 老师/小组能看到一条可信的修复链路。
2. **11-11 → 11-16：以"证据可审计"为判据**。引入 release gate、claims.json、capability matrix、ground truth/hidden benchmark；"完成"= 每个能力声明都有独立证据，`not_run` 不得写成 `pass`。此阶段把"能力"让位给"治理"，旧报告 §1.5.3 因此判定**边际递减**并战略重排。
3. **11-16 22:38 之后：以"可持续测量 + 产品可用"为判据**。用户在两份长指令里明确：① 只用 **OpenRouter + Ollama + 统一 Gateway**，不再多 provider 申请 key；② Phase-8D 只做**测量与治理**、不新增能力、不晋级；③ 修复验收权威只能是独立验证器。判据从"堆设施"转为"可复现测量 + 诚实边界"。

> 注意：`M1–M5` 是**五名成员角色**（控制器/V4 证据、GUI、Route A producer、独立验证、schema+DB+交付），不是里程碑 1–5。旧报告 §5.7.2 已澄清，本次核对 session-4f9a2f7d（"M4"）、session-3342aabf（"M1"）、session-cb06ee4c（"M1、4、5、Lead"）标题一致。

---

## 3. 11-16 08:06 → 11-17 01:31 增量（核心）

### 3.1 时间轴

| 时间 | 会话 | 事件 | 证据 |
|---|---|---|---|
| 11-16 08:23 | 791a | 用户提出与本次**完全相同**的回顾 + 推送 + 删痕需求（第三轮） | `791a36c4#seq=8 @11-16 08:23:16` |
| 08:26 | 791a | 4 个只读审计子 Agent（s1-analyst / s2-analyst / history-analyst / repo-auditor） | 子会话 `68b50f0d`、`bea3af8b`、`9e2296a2`、`16b0bcb6` |
| 11:49 | 791a | 产出改定版总报告 166KB（含 §1.5 组长复核决议） | `项目总体回顾_完成现状_剩余任务与解决方案_2026-11-16.md` |
| 11:52 | 791a | 四成员任务下发（M1 非 loop/CWE-121/134；M2 跨函数原型；M3 产品化；M4 安全/备份/治理） | `M1任务.md`–`M4任务.md`；子会话 `9e60ba8d`/`a9eb06b4`/`fac5d990`/`e737e081` |
| 11:52–12:19 | 791a | 四份成员报告 + 集成 4 个 commit（`afaf75a`/`71a8d6d`/`a23931b`/`77a3173`）→ `38dd93d` → 备份重建 → `f1bb1f4` | `791a36c4#seq=2436/2588/2765`；`binary-repair@f1bb1f4` |
| 12:19 | — | **备份快照落盘**（mirror 129MB + bundle 119MB + refs + SHA256） | `backup/`（mtime 11-16 12:20）、`backup/SHA256SUMS` |
| 17:54–17:56 | 791a | 回答"我还需解决什么/是否卡住成员"，列出 P0-1 key 轮换、P0-2 CI 与已删 ref 对齐、P1-3 默认分支、P1-5 live 授权、P1-6 下一轮分派、P1-7 两个技术决策 | `791a36c4#seq=2921` |
| 18:37–20:27 | **b75be565** | 固定成果门户 + 漏洞 ELF；发现并修复**程序头注入假阳性**（旧产物覆盖 `.rodata` 仍 gate 18/18） | `b75be565#seq=8`；`results-portal/`；`review/STATE.md`"修复产物缺陷修正"节 |
| 22:38:42 | 879cc62f | 用户长指令（24,113 字符）：唯一推荐路线 = OpenRouter + Ollama + 统一 LLM Gateway + 独立验证器；定义 **P31–P40** | `879cc62f#seq=19363` |
| 22:38–22:39 | 879cc62f | 6 路强制协作（fork 1/6–6/6）实现 P31–P34，基线 `a1755a5`，工作树 `worktree-feature-final` | 12 个 fork 表的 S1 部分 |
| 22:44:55 | b139b586 | 用户长指令（54,311 字符）：Phase-8D **D00–D10** 定义 | `b139b586#seq=16667` |
| 22:46–22:58 | b139b586 | 6 路强制协作（fork 1/6–6/6）实现 D00–D10，隔离 worktree `phase8d-open-world`（base `f1bb1f4`） | fork 表 S2 部分；`b139b586#seq=16786`（brief） |
| 23:30:21 | 879cc62f | `a0e6a24` feat(p31-p34)（`worktree-feature-final`，**悬空 commit**，无分支包含） | `git show -s a0e6a24` |
| 23:31:19 | 879cc62f | `a9db731` 同内容重提交到 `final/consolidated-2026-11-16` | `git log final/consolidated-2026-11-16` |
| 23:32:58 | b139b586 | `d1b73bf` feat(phase-8D)（worktree `phase8d-open-world`） | 同上 |
| 23:50:53 | b139b586 | `78edb97` fix(ci): fetch full history + product demo 解释器可移植 | 同上 |
| 00:05:37 | 879cc62f | `c0f9feb` test(p31-p34) → **push 到 `final/consolidated-2026-11-16`（成功，远端同 SHA）** | `879cc62f#seq=19790/19798` |
| 00:16:10 | b139b586 | `996060d` docs(phase-8D) → push `phase8d-open-world` | `b139b586#seq=17901` |
| 00:24:07 | 879cc62f | 在 `worktree-p31-ci` 基于 `996060d` 重放 P31–P34：`e01fc9e`→`13d3c1d`→`b896f1b`→`d37bfad`，push `workbench-v3`（=`d37bfad`） | `879cc62f#seq=19907/19923` |
| **00:45:47** | 879cc62f | 触发"重复同一工具调用"告警（同一 `job_output(wait=true,1800s)` 的 `bash-3a95be9b94f24972` 被连调两次） | `879cc62f#seq=19953/19960/19967` |
| **00:45:57** | 879cc62f | `git merge-base --is-ancestor c0f9feb HEAD` → `anc=1`；`git push origin HEAD:final/consolidated-2026-11-16` → **non-fast-forward 拒绝**，会话终止 | `879cc62f#seq=19978` / result `#seq=19981 @00:46:01` |
| 00:49–01:31 | b139b586 | 补 8D 证据：`bdd3f84`（01:02，`release/2026-11-17-phase8d-evidence`）、`a1d7150`（01:25，`release/2026-11-17-phase8d-final-evidence`）；01:26:15 打最终状态快照后收尾 | `b139b586#seq=18193/18365/18384/18414` |
| 11-17 08:43 | 0842a3d0 | 本轮 Lead 从 791a `session/end-seed` 分叉启动 | `791a36c4` 末事件 `session/end-seed @11-17 08:43:18` |

### 3.2 791a 复盘轮（第三轮同需求）的实际产出与遗留

| 产出 | 状态 | 证据 |
|---|---|---|
| 166KB 总报告（8 节 + 4 附录，1,737 行；附录 A 起于第 1547 行） | **仅文档** | `项目总体回顾_完成现状_剩余任务与解决方案_2026-11-16.md` |
| §1.5 组长复核决议（key 轮换 P0、非 loop 3/6 口径修正、战略重排、备份/默认分支） | **仅文档** | 同文件 `:80-108` |
| 四份任务文件 + 仓库 ASCII 副本 | **仅文档** | `M1任务.md`–`M4任务.md`；`binary-repair@f1bb1f4 delivery/zh/handoff/M1-task.md` |
| M1：`failure_behavior` 结构化契约 + CWE-134 字段级诊断 + 受控调用模板 | **代码已实现，验证为 deterministic stand-in（非 AI 质量）** | `binary-repair@f1bb1f4 app/services/repair_spec.py`；成员报告 `.tmp/handoff/reports/m1-report-20261116-121008.md`；61 passed |
| M2：只读 CFG/callgraph/跨函数数据流/保守别名原型 | **代码已实现（analysis_only）** | `app/services/analysis/{cfg,callgraph,dataflow,alias}.py`；28 passed；真实 ELF 1,256 functions / 834 条间接调用全 unresolved |
| M3：产品化包 + 一键 demo（2 VERIFIED + 1 REFUSED 大端负例） | **已实现（离线、无 key）** | `tools/product/`；11 passed |
| M4：6 份 ops 文档 + 2 个安全脚本 + 备份/默认分支/轮换建议 | **仅文档 + 脚本** | `docs/operations/*`；`tools/handoff/scan-secrets.sh` |
| 团队看板 4 个共享任务全部 completed | **已完成** | 791a `team/task` 事件；各成员报告 |
| 备份重建 + 恢复演练 ALL PASS | **已完成（但只到 f1bb1f4）** | `backup/`；`git cat-file -e a1d7150` = ABSENT |
| 未完成 | key 轮换（owner）、异地备份（user 路径）、默认分支（owner）、live 模型（未授权）、下一轮分派 | `791a36c4#seq=2921` 的 P0/P1 清单 |

> **遗留判定**：791a 结束时四名成员全部 idle，其"下一步"清单在 22:38/22:44 被两份新长指令**整体覆盖**——M1–M4 的下一增量（DWARF 对象大小、per-callsite RepairSpec、uaf/heap-canary、CI/refs 对齐）**从未被执行**，也没有被新指令正式作废。

### 3.3 b75be565 门户轮（11-16 18:37 → 20:27）

| 交付 | 状态 | 证据 |
|---|---|---|
| 固定成果门户 `http://127.0.0.1:8899/`（FastAPI + 纯静态单页；10 指标卡 / 9 成果区 / 26 报告 / 下载中心 / 边界待办） | **可运行（本次 09:0x 实测 HTTP 200）** | `results-portal/server.py`、`results-portal/README.md`；`curl 8899 → 200` |
| 产品工作台嵌入 `127.0.0.1:8123`（带本机 token） | **可运行（实测 401 = 存活需鉴权）** | `results-portal/run/workbench-8123.pid`；`curl 8123 → 401` |
| 测试台 4 个真实 job（demo 46.6s / ELF 11 cases / scan findings=6 / quick 34 passed） | **已实测并通过，证据落盘** | `results-portal/run/{demo,elf,scan,quick}/`、`results-portal/evidence/` |
| 漏洞 ELF `delivery/zh/vuln-elf/vuln-demo-x86_64.elf`（4,997,992 B，CWE-121/122/134/416 四 case + 源码 + PoC + 11 条 Lima+qemu 证据） | **已交付** | `delivery/zh/vuln-elf/`（mtime 11-16 18:49–20:26） |
| **新发现的验证器缺陷**：旧修复产物 `f8a04…` 覆盖 `.rodata` 48 字节，gate 仍给 18/18 `verified_patch` → **假阳性**；修正程序头槽位选择后新产物 `fd03c64d…` 干净 | **已修复 + 已复验** | `b75be565` 末条 assistant 消息；`results-portal/evidence/SAMPLE-ELF-REPAIR-2026-11-16.md` |
| 未做 | 门户与 ELF **未进 git**（`git ls-tree a1d7150` 中 `results-portal/` 命中 0）；"独立验证器字节级 gate 检查"仅作为后续建议 | `git ls-tree -r a1d7150 --name-only \| grep -c ^results-portal/` = 0 |

### 3.4 P31–P34（会话一，11-16 22:38 → 11-17 00:46）

用户长指令给出的**唯一路线**：`1 个云端入口（OpenRouter）+ 0 个云端 Key（本地 Ollama）+ 1 个修复验收权威（独立验证器）`，并明确 **P31–P40 顺序**（`879cc62f#seq=19363`）。实际只落地 P31–P34：

| 项 | 内容 | 状态 | 证据 |
|---|---|---|---|
| **P31** | `app/services/llm_gateway/`：`base.py`（请求/结果、typed errors、精确模型身份）、`client.py`（provider 选择 + `gateway_from_env`，无网络）、`providers/{mock,openrouter,ollama}` | **代码已实现 + 离线测试** | `binary-repair@c0f9feb app/services/llm_gateway/`；`docs/acceptance/p31-p34-2026-11-16.md` |
| **P32** | OpenRouter（OpenAI 兼容，usage/request-id/latency + typed HTTP/timeout/transport 错误）；Ollama `/api/chat`；测试注入 `httpx.MockTransport` | **代码已实现；真实网络调用 NOT_RUN** | 同上；`artifacts/p31-p34-2026-11-16/README.md` |
| **P33** | `credentials.py`（脱敏）+ `scripts/run_model_preflight.py`（配置级 preflight：缺 key → `BLOCKED`） | **代码已实现；keychain/GitHub Secret 验证 NOT_RUN** | 同上 |
| **P34** | `scripts/run_stability_matrix.py`：以独立验证而非 generator gate 定最终状态；分离 `PLAN_INVALID/NO_CANDIDATE/ARTIFACT_MISSING/VERIFIER_ERROR/TIMEOUT`；超时捕获；expected/started/completed/eligible 计数；checkpoint/resume | **代码已实现；live 60-run NOT_RUN** | 同上 |
| 测试 | `test_llm_gateway_credentials.py` 15、`test_llm_gateway_integration.py` 9、`test_stability_matrix_hardening.py` 6、`test_stability_matrix.py` 1 | **已验证（离线）** | 同上 |
| 全量套件 | **2319 tests, 0 failed, 0 errors, 9 skipped**（c0f9feb 树） | **已验证** | `docs/acceptance/p31-p34-2026-11-16.md` §Tests |
| 未做 | **P35**（正式 60-run）、**P36**（CaveABIBlock）、**P37**（Authorization Record）、**P38**（CWE-121）、**P39**（CWE-134）、**P40**（GDB+AFL++） | **未开始** | `879cc62f#seq=19363` 路线表；无对应 commit/产物 |

### 3.5 Phase-8D（会话二，11-16 22:44 → 11-17 01:31）

用户指令定义 D00–D10（`b139b586#seq=16667`），6 路 fanout 实现，父会话集成。**「实现与证据已交付；0 能力晋级」**：

| 工作流 | 交付 | 实测结果（本次从 artifact 复核） | 状态 |
|---|---|---|---|
| D00 | Phase-8C 基线冻结 + frozen tags（`phase8d-frozen-phase8c-release/evidence`） | `4a7b235`/`ec503e4` 对象可解析；原 refs 已在整合时删除 | 已验证 |
| D01 | 297 单元 capability universe + 合法分母 | **297 units**：not_applicable 131 / discovered 98 / analysis_only 32 / unmeasurable 24 / unknown 7 / independently_verified **2** / unsupported 2 / candidate_generated 1 / generalized **0** / promoted **0**；public 分母 24 → **2/24=0.0833**；hidden 分母 6 → **0/6**；表外 unknown = **null（不是 0）** | 已验证（`artifacts/phase8d-capability-universe-2026-11-17/registry.json`） |
| D02 | 增量 Gap Registry | **8 条全部 open**（GAP-8D-AUDIT-01…08；critical 2 / high 6）；历史 64 条只读不改写 | 已验证（`artifacts/phase8d-gap-registry-2026-11-17/gaps.json`） |
| D03 | Acceptance 2.0（L0–L7）+ 变异战役 | `matched=18`、`mutation_detection_rate=1.0`、`false_accepts=0`、`false_rejects=0`、`inconclusive=2`、`not_run=2`、`no_false_promotion=true`；`mutation_results` 记录 **7** 条（发布文档称"14/14 声明变异"，与机器计数口径不同，见 §4） | 已验证（`report.json`），14/14 待核 |
| D04 | heap-malloc ABI 根因 | 主因 `generator_plan_incorrect` + `abi_proof_insufficient`，次因 `verifier_rule_incorrect`；**未放宽任何 verifier 规则，候选仍 rejected** | 已验证 |
| D05 | hidden 阶段归因 | 6 个 runtime 样本全部执行；`first_blocking_stage_counts={'detection':6}`、`no_candidate_reason_counts={'detection_missed':6}`、`runtime_candidate_count=0`；仅发布匿名聚合 | 已验证（`aggregate.json`） |
| D06 | 外部知识快照（CWE 5.0 / Schema 8.0） | 984 条（CWE 4.19 为 969 条；新增 **15**、删除 0）→ **232** 条映射候选、**752** 未映射；`external-knowledge.json.mapping.candidate_count=232`；原始 XML 不提交（仅 241KB 投影）；不产生支持声明 | 已验证（`docs/operations/phase8d-external-discovery.md` + `external-knowledge.json`） |
| D07 | 蜕变/输入变异发现 + 机制注册表 | 4 个同源编译变体（2 executed/analysis_only、2 stripped→unsupported），`differences=2`、`mutation_runs=11`、`not_run=2`；**11/11 输入变异**经真实 Lima guest oracle；`sample_based` 仍 not_run；机制注册表 6/7 有真实证据（3 集成 + 3 独立），artifact 内 `mechanisms` 仅 3 条新增记录 | 已验证（`discovery.json`） |
| D08 | 实验/证据 Bundle | **10 条**有界实验记录，全部 `promotion_effect=none` | 已验证（无专属 angle，父会话补） |
| D09 | hidden 隔离审计 | 运营性检查通过；**same-UID/root 可读**仍是文档化限制（非密码学隔离） | 已验证（含限制） |
| D10 | 能力晋级门 | 4/4 评估的 8C 迁移全部 deny；`promoted=0` | 已验证 |

**发布/证据链**

| 对象 | SHA | 说明 |
|---|---|---|
| Phase-8D 集成分支 | `996060d`（`phase8d-open-world`） | 8D 主体 + docs；CI `43905664704` / Ubuntu `43905664754` success |
| workbench 全量树 | `d37bfad`（`workbench-v3`=`feature/ai-binary-repair`=`release/2026-11-17-phase8d-final`） | + P31–P34 重放；CI `43907137267` / Ubuntu `43907136876` success |
| 8D 侧证据分支 | `bdd3f84`（`release/2026-11-17-phase8d-evidence`） | `artifacts/release-gate-2026-11-17-phase8d/` |
| 8D 最终证据 | `a1d7150`（`release/2026-11-17-phase8d-final-evidence`） | d37 gate 13/13、require 策略、mainline_unchanged |
| 门禁 | `artifacts/release-gate-2026-11-17-phase8d-final/gate.json` | `ok=true`、13 checks、全量 pytest **1,064,207 ms**、`not_run=[github_actions, international_provider_matrix, self_hosted_nightly_lima_capture]`、`evidence_scope="local frozen-tree gate"` |

> **诚实标注**：gate 的 `not_run[github_actions]` 指"gate 自身未在 Actions 里跑"，不等于没有 CI——`d37bfad` 的两条真实 CI run 记录在 `docs/release-phase8d-final-mainline-evidence-2026-11-17.md`。这两句必须成对出现，否则会被误读。

### 3.6 合流失败与分支拓扑（本次最重要的新事实）

```
f1bb1f4 (11-16 12:19, 四成员集成 + 总报告)
├── a9db731 (11-16 23:31) ── c0f9feb (11-17 00:05)        ← final/consolidated-2026-11-16（远端同 SHA）
│     只含 P31–P34，**不含 Phase-8D**
└── d1b73bf (23:32) ── 78edb97 (23:50) ── 996060d (00:16)  ← phase8d-open-world
                                            └── e01fc9e → 13d3c1d → b896f1b → d37bfad (00:24)  ← workbench-v3 / feature/ai-binary-repair / release-…-final
                                                                                   └── a1d7150 (01:25)  ← release/…-final-evidence（**当前最完整树**）
```

- `git merge-base --is-ancestor c0f9feb d37bfad` → **否**；`a9db731` 亦**不是** `a1d7150` 的祖先（P31–P34 在 8D 树上是 `e01fc9e` 重放，而非 merge）。
- 因此：**`a1d7150` 含 M1–M4 + P31–P34 + Phase-8D + 最终证据；`c0f9feb` 含 M1–M4 + P31–P34；两者互不包含。**
- 会话一在 00:45:57 想用一次普通 push 把 `final/consolidated-2026-11-16` 快进到 `d37bfad`，被 non-fast-forward 拒绝后**没有改用 merge 或 `--force-with-lease`**，直接终止。**这是"两个会话成果整合后推送新分支"任务在 11-17 01:31 时的真实断点。**
- 另有一个**悬空 commit `a0e6a24`**（23:30，同 P31–P34 内容，位于 `worktree-feature-final`，无任何分支包含）——`worktree-feature-final` 目前 detached 在它上面，属"未收尾产物"。

### 3.7 refs 增量与备份状态

**11-17 新增/移动的远端 heads（7 条，其余 90 条未变）**

| ref | SHA | 产生者 |
|---|---|---|
| `final/consolidated-2026-11-16` | `c0f9feb` | 会话一（push 成功） |
| `phase8d-open-world` | `996060d` | 会话二 |
| `workbench-v3` | `d37bfad` | 会话一（基于 8D 树重放 P31–P34） |
| `feature/ai-binary-repair` | `d37bfad` | 同上（随 workbench-v3） |
| `release/2026-11-17-phase8d-final` | `d37bfad` | 会话二 |
| `release/2026-11-17-phase8d-evidence` | `bdd3f84` | 会话二 01:02 |
| `release/2026-11-17-phase8d-final-evidence` | `a1d7150` | 会话二 01:25 |

**11-16/17 新增 tags（6 条，均为 annotated，tag 对象 → commit）**：`release-2026-11-17-phase8d`（`b8916ee` → `996060d`）、`…-phase8d-evidence`（`4abbebe` → `bdd3f84`）、`…-phase8d-final`（`19a91bc` → `d37bfad`）、`…-phase8d-final-evidence`（`602da11` → `a1d7150`）、`phase8d-frozen-phase8c-release`（`b989bc5` → `4a7b235`）、`…-frozen-phase8c-evidence`（`44764b0` → `ec503e4`）。
远端现状：**heads 97 / tags 101 行（含 `^{}` 解引用）/ 默认分支仍 `main`=`8869b07`**。

**备份（硬证据）**

| 对象 | 覆盖 | 证据 |
|---|---|---|
| `backup/binary-repair-mirror-2026-11-16.git` | 到 **`f1bb1f4`**（`final/consolidated` 当时 tip） | `git --git-dir=… cat-file -e f1bb1f4` → 存在 |
| 同上，缺 | `c0f9feb / d37bfad / 996060d / a1d7150` **全部 ABSENT** | 逐个 `cat-file -e` 实测 |
| `backup/local-refs-2026-11-16.bundle`（124 MB）+ `remote-refs-2026-11-16.txt` + `SHA256SUMS` | 11-16 12:20 快照 | `backup/` mtime；`SHA256SUMS` 两条 |
| 11-17 备份 | **不存在**（`find backup -newermt "2026-11-16 13:00"` 为空） | 本次实测 |

### 3.8 交付边界：哪些东西根本不在这两个仓库工作树里

| 工作区路径 | 内容 | 是否被 git 跟踪 | 风险 |
|---|---|---|---|
| `results-portal/`（含 `server.py`、`data/`、`evidence/`、`run/`、`static/`） | 成果门户 + 4 个 job 证据 | **否**（`git ls-tree a1d7150` 命中 0） | 门户是"唯一能对外演示"的增量，不入库则 GitHub 上看不到 |
| `tools/portal/`、`tools/vuln-elf/`、`tools/handoff/` | 启停脚本、样本生成、成员工具 | **否**（除 `tools/product/` 在库内） | 与上同 |
| `delivery/zh/vuln-elf/`（含 `vuln-demo-x86_64.elf` 4.99MB、PoC、源码、11 条证据） | 漏洞 ELF 样本 | **否** | 需要显式 `git add`，且 4.99MB 二进制入库需评估 |
| `review/`（`STATE.md`、本轮报告） | 工作区自我认知 + 评审产物 | **否** | 由 Lead 决定是否随分支交付 |
| `.tmp/`（**373 MB**，含 `sessions/` 明文会话导出） | 团队中间产物、成员报告、会话 JSONL | **否**（且不在仓库根之下：repo root 是 `binary-repair-gui/`） | **P0**：`.tmp/sessions/` 是明文会话导出，含已泄露 key（`[REDACTED]`，791a 记录 3 个），**绝不可打包/入库** |

> 仓库根 = `binary-repair-gui/`（`git worktree list` 显示 `binary-repair/`、`worktree-*`、`.agents/worktrees/*` 均为其 worktree）。因此工作区根下的 `results-portal/`、`tools/`、`delivery/`、`review/` 与 **373MB 的 `.tmp/`** 都在版本控制之外——"把成果推上 GitHub"必须显式挑选文件，且必须排除 `.tmp/`。

---

## 4. 数字核验（旧报告口径 vs 本次实测）

| 旧报告/任务说明的说法 | 本次核验 | 判定 |
|---|---|---|
| `final/consolidated-2026-11-16` = `c0f9feb`（已推送） | 本地=远端=`c0f9feb` | **一致** |
| 远程 `workbench-v3`、`feature/ai-binary-repair` 均 `d37bfad` | `git ls-remote` 与本地跟踪一致 | **一致** |
| `phase8d-open-world` = `996060d` | 一致 | **一致** |
| 远程 heads 97 / tags 101 | `git ls-remote --heads` 97 行；`--tags` 101 行 | **一致** |
| 旧报告"已删 23 分支 + 14 标签、0 残留" | 11-17 又新增 **7 heads + 6 tags**；旧结论对 11-16 成立，对现在**不成立** | **过时** |
| 备份 mirror 覆盖到 11-16 12:20 | 实测到 `f1bb1f4`，缺 8D/P31-34 全部 commit | **一致但需强调缺口** |
| 791a "2.7MB"（任务说明）/ 旧报告 "1.4MB" | 实测 **2.6 MB / 2,926 事件** | **修正**（口径不同） |
| 879cc62f "约 19,989 事件 / 17MB" | 19,989 事件 / **16.3 MB** | **事件数一致，体积修正** |
| b139b586 "15.2MB" | **14.6 MB / 18,457 事件** | **体积修正** |
| 41 个 sessionIds / 约 8 个归档 | 41 / **8** | **一致** |
| 旧报告"38 会话 / 7 归档" | 现 41 / 8 | **过时** |
| D03"14/14 声明变异检出" | `report.json`: `mutation_results` 记录 7 条、`mutation_detection_rate=1.0`、`matched=18`；"14"未在机器计数中直接出现 | **待 04 号或实现者澄清**（可能为记录内变异条目合计） |
| gate 13/13"required checks passed" | `gate.json`: 13 checks、`ok=true`、全量 pytest 1,064,207 ms、3 项 not_run | **一致（需带 not_run）** |
| P31–P34"已实现" | 离线实现 + 2319 tests passed；**真实 OpenRouter/Ollama 与 60-run 全部 NOT_RUN** | **部分实现** |
| Phase-8D"交付" | 10/11 工作流有机器 artifact；**8 个 gap 仍 open、0 晋级** | **实现完成、能力零增量** |
| 旧报告 §5 各项能力/测试数字 | 本次未逐条重测（属 04 号分工）；c0f9feb 树 2319 tests 与旧报告 §5.2.2 的测试规模演进需对齐 | **交由 04 号核验** |

---

## 5. 旧报告需要改写的具体位置（给 Lead 合并用）

| 旧报告位置 | 现状 | 建议 |
|---|---|---|
| §1.2"目标的三个演进"表（行 36–44） | 实际六阶段；第 ⑤ 阶段已被 11-16 22:38 的 P31–P40 指令与 Phase-8D 取代 | 换成 §2 的六阶段表，并把"未开始/规划中"改为"P31–P34 完成、P35–P40 未开始、Phase-8D 完成但 0 晋级" |
| §2.1 时间线（行 113–124） | 缺 11-16 18:37 门户轮、22:38/22:44 两份长指令、11-17 00:05/00:24/01:25 三个里程碑 | 追加 4 行 |
| §5.1"以 mainline 4a7b235 为权威"（行 669） | 权威树应改为 `a1d7150`（最完整）/`d37bfad`（被 gate 与 CI 验证）/`c0f9feb`（final 分支但缺 8D） | 明确三者的包含关系 |
| §5.2 测试与 CI（行 688–724） | 新增 c0f9feb 2319 tests、d37bfad 13/13 gate + 1,064,207 ms、CI `43907137267`/`43907136876` | 更新数字与 run id |
| §6.3 C1"成果散落多个分支"（行 1096） | **仍未解决**，且新增 7 heads/6 tags；合流在 00:45 失败 | 升级为 P0 并写明失败原因 |
| §8 整合与交付（行 1397–1544） | 只覆盖 11-16 的 23 分支/14 标签清理 | 追加"11-17 新增 refs"与"新分支必须包含 8D" |
| 附录 A（行 1547–1593） | 38→41、7→8 归档、体积口径 | 直接用 §1 表替换 |
| 全文"0 残留"表述 | 现在有 7 heads + 6 tags 的会话产物 | 改为"11-16 清理后 11-17 又新增 N 条，待二次清理" |

---

## 6. 结论

1. **会话层**：41 顶层 + 43 子（12 个种子 fork 复制父历史，占 92.6 MB）＝ 246.1 MB；旧报告 38 会话表已过时，需以本表替换。
2. **目标层**：六阶段演进；第六阶段在 11-16 22:38 被拆成 **P31–P40**（会话一）与 **Phase-8D D00–D10**（会话二）两条并行线，均只完成前半（P31–P34 / D00–D10）。
3. **增量层**：11-16 08:06 之后新增 3 个顶层会话、12 个 fork、7 个 heads、6 个 tags；11-16 22:30 之后共 **12 个 commit**（P31–P34 线 7 个：`a0e6a24`/`a9db731`/`c0f9feb`/`e01fc9e`/`13d3c1d`/`b896f1b`/`d37bfad`；8D 线 5 个：`d1b73bf`/`78edb97`/`996060d`/`bdd3f84`/`a1d7150`），另有 2 份 24KB/54KB 长指令；门户与漏洞 ELF 是唯一"可给外部看"的产品化增量，且**未进 git**。
4. **仓库层（最关键）**：`final/consolidated-2026-11-16`=`c0f9feb` **不含 Phase-8D**；最完整树是 `a1d7150`；合流因一次 non-fast-forward push 失败而中断，**至今未完成**。任何"成果已整合"的说法都不成立。
5. **风险层**：本地备份缺 13 小时成果；D03 的 14/14 与机器计数需澄清；D08 无专属 angle；P35–P40 与 8 个 open gap 是明确的未完成任务。

---

## 交接给 Lead（5–10 条）

1. **必须用 `a1d7150` 或 `d37bfad` 作为新分支基线，不能用 `c0f9feb`**：`final/consolidated-2026-11-16` 缺整个 Phase-8D（`git merge-base --is-ancestor c0f9feb d37bfad` = 否）。这是本轮交付最容易犯的错。
2. **"两个会话成果已整合"是假的**：会话一 11-17 00:45:57 的 `git push origin HEAD:final/consolidated-2026-11-16` 被 non-fast-forward 拒绝（`anc=1`），随后陷入重复 `job_output` 轮询并终止。合流需要一次真正的 merge 或在新分支上直接以 `a1d7150` 为基线。
3. **旧报告附录 A 必须换表**：38→41 会话、7→8 归档、+`b75be565`/`0dd3685e`/`0842a3d0`，且 12 个 fork（92.6 MB）此前完全未被记录——它们不是独立工作，别当成"12 个新项目"。
4. **P31–P34 只能写"离线实现"**：真实 OpenRouter/Ollama 调用、live 60-run 全部 NOT_RUN；能引用的硬数字只有 2319 tests passed（c0f9feb 树）与 4 个测试文件 15/9/6/1 passed。
5. **Phase-8D 的正确口径**：297 units、2/24、hidden 0/6、0 generalized、0 promoted、8 个 gap 全 open、D05 六样本全部 `detection_missed`、gate 13/13 但 `evidence_scope=local frozen-tree` 且 3 项 not_run。写"8D 已交付"必须紧跟"能力零增量"。
6. **备份缺口是 P0 级**：`backup/` 只到 `f1bb1f4`，`c0f9feb/d37bfad/996060d/a1d7150` 全部 ABSENT，11-17 无新备份。新分支推送前应先做 mirror+bundle（含 8D），否则离线不可恢复。
7. **12 个 commit 的归属已查清**：P31–P34 = `a0e6a24`(悬空)/`a9db731`/`c0f9feb` + 8D 树上的 `e01fc9e/13d3c1d/b896f1b/d37bfad`；8D = `d1b73bf/78edb97/996060d/bdd3f84/a1d7150`。写 CONSOLIDATION 时按此分线，别按时间顺序混写。
8. **`worktree-feature-final` 悬空在 `a0e6a24`**（无分支包含），属未收尾产物；`worktree-p31-ci`、`worktree-p31-final`、`binary-repair`(老分支 `member-5-deepseek-schema` @ `221e47c`) 也都不在主交付线上，交付前需说明或清理。
9. **待澄清（不要写成结论）**：D03 文档"14/14 变异检出" vs `report.json` 的 7 条 `mutation_results`/`matched=18`；旧报告 §5 的能力与测试数字需 04 号重测后才能引用。
10. **交付时"哪些不在 git 里"必须显式处理**：`results-portal/`、`tools/portal|vuln-elf|handoff/`、`delivery/zh/vuln-elf/`、`review/` 均未被 `a1d7150` 跟踪（仓库根是 `binary-repair-gui/`），门户与漏洞 ELF 是本轮唯一"产品化成果"，不 `git add` 就永远上不了 GitHub；同时**必须排除工作区 `.tmp/`（373 MB 明文会话导出，含已泄露 key `[REDACTED]`）**，否则一次 `git add -A` 会把密钥推上公开仓库（该仓库是 public）。
