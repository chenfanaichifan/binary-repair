# AI 驱动的二进制漏洞自动修复与正确性验证
## 项目总体计划 · 完成现状 · 剩余任务与解决方案（2026-11-17 全量版）

> **汇总日期**：2026-11-17（Asia/Singapore）
> **汇总范围**：本工作区 `AI驱动的二进制漏洞自动修复与正确性验证` 的**全部会话**——41 个顶层会话（其中 8 个已归档）+ 43 个子会话，合计 84 个会话目录 / 246.1 MB；以及对应的 GitHub 仓库 `chenfanaichifan/binary-repair` 的 97 个 heads、71 个真实 tag、170 次 Actions run、6 个 worktree。
> **重点会话**：**「Linux 虚拟机验证漏洞修复-1」**（`session-879cc62f`，2026-11-13 16:15 → 2026-11-17 00:46，19,989 事件 / 36 turn）与**「全类型二进制修复-1」**（`session-b139b586`，2026-11-14 15:12 → 2026-11-17 01:31，18,457 事件 / 16 turn）。
> **方法**：`zstd -dc` 流式回放会话 JSONL（不修改原始日志）+ `git log/show/ls-tree/diff/ls-remote` 只读核验 + 已提交 junit/gate/claims/registry 解析 + `pytest` 小subset 复跑 + GitHub Actions API 只读查询。所有关键数字给证据指针；无法核实的标「未核实」。
> **与旧版关系**：本文**取代** `项目总体回顾_完成现状_剩余任务与解决方案_2026-11-16.md`（166KB）。旧版截止 11-16 08:06，未覆盖 P31–P34、Phase-8D、门户轮、两会话末段合流失败；本文修正其 6 处过时/失实表述（见 §5.7）。
> **一句话**：项目已经形成一条**有界、可审计、失败保留**的二进制修复流水线；但它不是通用修复器——公开集 2/24、hidden 0/6、Phase-8D 八个审计缺口全开、P35–P40 未开始。**本轮完成了两会话成果的真正合流**：新分支 `final/consolidated-2026-11-17`（首批 `9194b02`，基线 `d37bfad`；最终 tip 以 `git log -1` 为准），并删除 7 个会话 heads + 6 个 tags；仓库痕迹的"对象级残留"不可清零，已如实说明。

---

# 目录

1. [先读：口径、证据等级与十条结论](#1-先读口径证据等级与十条结论)
2. [项目是什么：目标、边界与六阶段计划](#2-项目是什么目标边界与六阶段计划)
3. [全部会话总览（41 顶层 + 43 子会话）](#3-全部会话总览41-顶层--43-子会话)
4. [会话一：Linux 虚拟机验证漏洞修复-1](#4-会话一linux-虚拟机验证漏洞修复-1)
5. [会话二：全类型二进制修复-1](#5-会话二全类型二进制修复-1)
6. [当前完成现状（2026-11-17）](#6-当前完成现状2026-11-17)
7. [尚未完成的任务与全部问题（27 项）](#7-尚未完成的任务与全部问题27-项)
8. [对应解决方案与 90 天路线](#8-对应解决方案与-90-天路线)
9. [本次仓库整合与痕迹清理（已执行）](#9-本次仓库整合与痕迹清理已执行)
10. [对外口径：可以/不可以声称什么](#10-对外口径可以不可以声称什么)
11. [附录](#11-附录)

---

# 1. 先读：口径、证据等级与十条结论

## 1.1 三种"完成"必须分开

| 状态 | 定义 | 本项目例子 |
|---|---|---|
| **S1 已验证** | 有代码/测试/产物/CI 至少两类独立证据，可复现 | 2411 tests 0 fail；marcx 14/14 + 28/28；8B 2 verified；13/13 gate |
| **S2 仅文档/声明** | 只有 claims、runbook、设计稿、报告文字 | key 轮换 runbook；P37 授权 profile；D08 实验 bundle |
| **S3 部分实现** | 离线/mock/单架构/单样本成立，live 或多架构未成立 | P31–P34（离线完成、live 全 NOT_RUN）；Phase-8D（框架完成、能力零增量） |
| **S4 未开始/not_run** | 无代码或无真实执行；**not_run ≠ pass** | P35–P40；GDB/AFL++；self-hosted nightly；sample_based 发现 |

本文所有"完成"都带 S1–S4 标注；任何把 S2/S3 写成 S1 的表述都视为虚报。

## 1.2 十条结论（读完可掌握全局）

1. **项目定位**：BinaryRepair 是"AI 生成候选 + 确定性 gate/独立验证器验收"的**有界**二进制修复工作台，不是"任意二进制/任意漏洞 100% 修复"。
2. **能力上限**：公开修复集 **2/24 verified（8.33%）**；hidden runtime **0/6**；能力宇宙 **297 units** 中 `independently_verified=2`、`generalized=0`、`promoted=0`；Phase-8D **8 个 audit gap 全部 open**（2 critical / 6 high）。
3. **两会话分工**：会话一是"**能力线**"（v5 任意二进制 → v6 两条 AI 路径 → 硬案例 → 范式 A → P5–P24 → P31–P34）；会话二是"**测量与治理线**"（marcx 容量修复 → 68 gap 审计 → 连续 8 次 release gate → Phase-7/8A/8B/8C/8D）。两线在 11-17 00:24 才在 `d37bfad` 树上叠加。
4. **合流曾经失败**：11-17 00:45:57，会话一试图把 `d37bfad` 普通 push 到 `final/consolidated-2026-11-16`，被 **non-fast-forward 拒绝**（`anc=1`）；随后会话以 `job_output(wait=true, 1800s)` 重复轮询 CI 并结束。结果是 `c0f9feb`（缺 Phase-8D）与 `d37bfad`（含 Phase-8D）**互不包含**——"两会话成果已整合"在 11-17 01:31 时**不成立**。
5. **本轮已修复该断点**：以 `d37bfad` 为基线新建 `final/consolidated-2026-11-17`，补入 `a1d7150`/`bdd3f84` 独有的 Phase-8D 证据，保留全部历史 gate，推送成功（首批提交 `9194b02`）；随后删除 7 个会话 heads + 6 个 tags，远端 heads **97 → 91**（含新分支）、tag 行 **101 → 89**、会话相关残留 **0**。
6. **测试与门禁是真的**：`d37bfad` 全量 **2411 tests / 0 failed / 0 errors / 9 skipped / 1015.7s**；本地 frozen-tree release gate **13/13**（20.8 min，`not_run` 3 项显式保留）；GitHub CI `43907137267` 与 Ubuntu `43907136876` 在 `d37bfad` 上均 **success**。
7. **Phase-8D 不是能力提升**：它交付了 297-unit 能力宇宙、Acceptance 2.0（L0–L7）、8 条 gap registry、promotion gate（4/4 denied）、hidden 阶段归因（6/6 `detection_missed`），但**没有新增一个修复能力、没有晋级一个单元**。
8. **P31–P34 只完成离线部分**：统一 LLM Gateway、OpenRouter/Ollama adapter、凭证 preflight、stability runner 有代码与离线测试；真实 OpenRouter/Ollama 调用、Keychain/GitHub Secret、live 60-run **全部 NOT_RUN**；P35–P40 **未开始**。
9. **未完成项共 27 条**：P0 6 条（凭据轮换、hidden 0/6、CWE-121/134 无 live 证据、备份缺口、GUI 工作树半回退 + 未提交 `code_cave` 修复、单一交付 SHA——本轮已修）、P1 11 条、P2 10 条。每条的方案/验收见 §8。
10. **最危险的三个非代码风险**：① 4 个 provider key 仍未轮换且明文进过会话；② `binary-repair-gui` 工作树 41 项脏改动，含**任何分支都没有**的 `code_cave.py` phdr 修复（它修的是一类 gate 未拦住的 `.rodata` 静默破坏）；③ 11-16 备份不覆盖 11-17 成果（本轮已重建 129MB mirror + 128MB bundle）。

---

# 2. 项目是什么：目标、边界与六阶段计划

## 2.1 系统定义

- **输入**：一个存在已知漏洞的二进制（ELF / PE / Mach-O，主支持 Linux x86-64，扩展 i386/arm64；PE/Mach-O 仅部分 cell），可选 PoC/回归 manifest。
- **处理**：结构解析与 triage → 漏洞根因/修复点分析 → 生成 RepairSpec/patch plan → 确定性模板或 AI 生成候选 → 直接改写字节/注入 code cave/重定位 → 重新解析并在 guest（Lima/qemu）执行差分。
- **输出**：一个带 `disposition` 的结果——`verified_patch` / `static_only_patch`（显式 opt-in、不验证）/ `analysis_only` / `unsupported` / `rejected` / `invalid`，以及 report、gate checks、SHA256、冻结 manifest、候选下载。
- **核心原则**：**AI 只产生候选；验收权属于确定性 gate + 独立验证器**。模型解释不是证据；不可用标 `not_run`，绝不把 `not_run` 当 `pass`；不降 gate 换绿灯。

## 2.2 六阶段完成计划（2026-10-15 → 2026-11-17）

| 阶段 | 时间 | 目标 | 关键产出 | 状态 |
|---|---|---|---|---|
| **① 研究想法 + 课程 MVP** | 10-15 → 10-31 | 把《方法建议》的 5 步 REA 方法论落成可演示、可审计的工作台（Route A 调用重定向 + Route B 恢复重编译 + V0–V5 验收） | 研究想法/MVP 定义、项目大纲、M1–M5 五人角色体系、T8.3（CWE-416 no-input 契约） | **已完成**（含遗留） |
| **② 公开稳定版 v1.2.1** | 10-31 → 11-11 | 收口成公开稳定版 + WeChat 分享包 + DeepWorks 迁移 | v1.2.0/1.2.1 tag、889/1/0（Ubuntu CI）、118 VERIFIED / 124 inconclusive、docs/handoffs | **已完成** |
| **③ 任意二进制 v4–v7** | 11-11 → 11-13 | 从单 fixture 扩到 ELF/PE/Mach-O × x86_64/arm64/i386 的确定性矩阵；任意文件 triage + 明确 disposition；Linux VM 权威交付件 | v5 任意二进制 `72db891`、两条 AI 路径 `aa45b36`、v7 交付件 950/943/7/0、CI `43390831537` | **已完成**（确定性矩阵） |
| **④ AI 修复研究 P0–P24** | 11-13 → 11-16 | 两条 AI 直接修复路径（`asm_roundtrip` / `binary_direct`）+ 真实 provider + 真实失败反馈 + 跨二进制 benchmark + 独立验证器 + 36 次稳定性 | P16-R3 严格 7/10、P21 冻结 profile、P22 8 recovered/2 missing、P23 runner+smoke；**CWE-121/134 负结果、60 次未完成** | **部分完成** |
| **⑤ 自主能力设施 Phase-7/8A/8B/8C** | 11-14 → 11-16 | 缺口自发现、Autonomy Foundation、Ground Truth v2 + Hidden Benchmark、验收模型审计、release gate 13/13 | `2bfa112`→`bd9cbf6`→`227f45b`→`4a7b235`；17 合同 / 240 cells / 30 场景 meta-audit / 64 gap | **基础设施完成**（能力零增量） |
| **⑥a 产品化 + 四成员首增量** | 11-16 08:06 → 20:27 | 复盘定稿 + 战略重排 + M1–M4 四成员首增量 + 固定成果门户 + 漏洞 ELF | 166KB 总报告、`M1–M4任务.md`、`final/consolidated-2026-11-16`=`f1bb1f4`、门户 `127.0.0.1:8899`、`vuln-demo-x86_64.elf` | **首增量完成** |
| **⑥b P31–P40 + Phase-8D 双线** | 11-16 22:38 → 11-17 01:31 | 会话一：P31–P34（统一 LLM 调用层 / OpenRouter+Ollama / 凭证 preflight / stability runner）；会话二：Phase-8D D00–D10（开放世界发现 + Acceptance 2.0） | P31–P34：`a0e6a24`/`a9db731`/`c0f9feb`/`e01fc9e`→`d37bfad`；Phase-8D：`d1b73bf`→`996060d`、`bdd3f84`、`a1d7150` | **部分完成且曾未合流；本轮已合流** |

## 2.3 最终目标的正式定义

> 在**明确声明支持范围**内自主发现二进制漏洞、分析根因、规划并执行修复、独立验证结果，并**持续发现未知能力缺口与验收模型错配**，通过可复现实验不断扩展"已验证能力"的 **Autonomous Binary Repair Intelligence**。

12 条成功标准（会话中已达成共识，本文保留）：

1. 所有已声明支持的能力都有可验证的实现证据；
2. 所有已声明支持的漏洞类型都有独立 Ground Truth；
3. 所有修复候选都必须经过独立验证；
4. 所有失败进入统一 Failure/Gap Registry；
5. 所有重要失败都能触发根因分析；
6. 所有根因都能触发候选能力缺口或实验；
7. 所有新发现都经过重复性、独立性和重要性评估；
8. 所有能力晋级都必须经过隐藏测试、回归测试和独立验证；
9. 所有验收模型都能被持续测试、比较、审计和更新；
10. 所有无法验证的情况必须显式标记，不能伪装成功；
11. 系统能持续发现能力注册表之外的潜在缺口；
12. 新漏洞/新架构/新技术/新知识能进入发现流程。

**关键判据**：最终不是"没有任何缺口"，而是"没有被隐藏的已知缺口；所有已知缺口都有明确状态；所有重要未知风险都有持续发现机制；任何能力晋级都有独立证据"。

## 2.4 明确的非目标与不可证明边界

以下内容在全程被反复确认**不能声称**（任何文档都必须保留限定）：

- **不声称"任意二进制/任意漏洞 100% 修复"**：绝对全覆盖不可证明（输入空间、漏洞组合、编译变体无限；程序语义等价一般不可判定）。使用"已知能力宇宙可穷尽审计 + 未知空间 `not_measurable`"的开放世界框架。
- **不声称 whole-program / 形式化安全保证**：V4 是 model-level；PoC/回归通过不等于程序无其他漏洞。
- **不声称 hidden benchmark 泛化能力**：hidden 8 样本（6 runtime + 2 analysis-only）公开口径 0 candidate、0 verified；`hidden_available=false`。
- **不把 `not_run`/`unavailable` 当 `pass`**：self-hosted Lima nightly、国际 provider 矩阵、external ingestion、GDB trace、AFL fuzzing 等未运行项均显式记录。
- **不把 AI 评审/模型解释当验收**：AI 只能 hold/要求更多检查，不能把失败 gate 提升为成功。
- **不把 fixture 绿灯当通用能力**：公开集 2/24、hidden 0/6、非 loop 0/6、UAF/heap-canary 0；这些负结果是项目结论的一部分。

---

# 3. 全部会话总览（41 顶层 + 43 子会话）

## 3.1 规模与结构（本次重新测量）

| 项 | 值 |
|---|---|
| 顶层会话 | **41**（102.9 MB / 129,750 事件） |
| 归档会话 | **8**（`4f9a2f7d`、`4fbcfd05`、`3342aabf`、`07d5319d`、`e44273d9`、`38221d41`、`217a1378`、`791a36c4`） |
| 子会话 | **43**（143.2 MB / 266,075 事件；`delegationDepth=1`） |
| 其中"种子 fork" | **12**（11-16 22:38/22:44 两次 6 路强制协作，整段复制父会话历史；92.6 MB / 219,998 事件） |
| 合计 | **84 个目录 / 246.1 MB** |
| 空会话 | **22 个**（4–7 事件：10-22/23 共 13 个、11-06/09 共 4 个、11-12 共 4 个、11-16 1 个） |

> **重要更正**：旧报告说"38 会话 / 7 归档"，现为 **41 / 8**；新增 `b75be565`（门户轮）、`0dd3685e`（空）、`0842a3d0`（本轮）。12 个种子 fork 不是 12 个独立项目，只是同一父会话历史的 6 路并行副本；把它们计入"会话数"会虚增 92.6 MB / 22 万事件。

## 3.2 有效会话清单（去掉 22 个空会话）

| # | 开始 | 最后事件 | 标题 | id 前缀 | MB | 事件 | 归档 |
|---:|---|---|---|---|---:|---:|---|
| 1 | 10-15 16:39 | 11-11 20:46 | M4 | `4f9a2f7d` | 5.1 | 5,856 | 是 |
| 2 | 10-15 17:32 | 11-08 17:41 | 研究想法与MVP定义指导 | `4fbcfd05` | 0.8 | 581 | 是 |
| 3 | 10-18 16:49 | 11-11 21:58 | M1、4、5、Lead | `cb06ee4c` | 22.4 | 26,453 | |
| 4 | 11-05 22:03 | 11-07 22:20 | M1 | `3342aabf` | 7.1 | 10,260 | 是 |
| 5 | 11-05 22:52 | 11-12 23:12 | Lead | `07d5319d` | 1.0 | 1,291 | 是 |
| 6 | 11-06 16:05 | 11-06 16:30 | M1 partial 语义并入 canonical | `e44273d9` | 0.8 | 1,043 | 是 |
| 7 | 11-06 16:10 | 11-06 16:26 | M1任务：partial 与 canonical 关系 | `38221d41` | 0.7 | 986 | 是 |
| 8 | 11-06 18:00 | 11-06 21:40 | 查询GitHub上传地址及T8.3说明 | `217a1378` | 1.2 | 1,595 | 是 |
| 9 | 11-08 19:11 | 11-11 22:30 | 迁移项目成果至DeepWorks平台 | `5a19b610` | 3.2 | 4,153 | |
| 10 | 11-11 22:20 | 11-14 15:48 | 计划服务未接通原因排查 | `190e48d8` | 14.5 | 18,756 | |
| 11 | 11-12 19:55 | 11-12 20:42 | CGC 克隆用途与替代方案 | `04d75281` | 1.1 | 1,750 | |
| 12 | 11-12 22:52 | 11-16 21:36 | 生成虚拟机任务压缩包 | `7c2cc0ef` | 3.8 | 5,855 | |
| 13 | 11-12 23:00 | 11-13 00:22 | Fix CI and AI review milestone | `336db26b` | 2.2 | 3,052 | |
| 14 | 11-13 15:15 | 11-13 15:58 | 结论：v3 的内容层面可以通 | `ce323436` | 1.7 | 2,115 | |
| 15 | **11-13 16:15** | **11-17 00:46** | **Linux 虚拟机验证漏洞修复-1** | `879cc62f` | 16.3 | **19,989** | |
| 16 | **11-14 15:12** | **11-17 01:31** | **全类型二进制修复-1** | `b139b586` | 14.6 | **18,457** | |
| 17 | 11-16 08:06 | 11-16 17:56 | 项目回顾与四成员任务分配（上轮同需求） | `791a36c4` | 2.6 | 2,926 | 是 |
| 18 | 11-16 18:37 | 11-16 20:27 | 测试网页并修复 ELF 文件 | `b75be565` | 3.4 | 4,104 | |
| 19 | 11-17 08:43 | 进行中 | 回顾会话并汇总项目文档（本轮 Lead） | `0842a3d0` | 0.4 | 436+ | |

> 归档会话 8 个已全部被本次回顾覆盖（上表标注"是"的 7 个 + `791a36c4`）。空会话 22 个：`42f57a46`、`1edb1a82`、`2f54838b`、`f48df004`、`ff9c020b`、`a1cdccb9`、`b67c86c7`、`ba1995bd`、`3327ffaa`、`3d349441`、`474688b9`、`729f766f`、`aff70696`（10-22/23，13 个，4 事件/个）；`caf358f3`、`a50c362f`、`ad717231`、`c20f3715`（11-06/09，4 个）；`1309dc6c`、`892c4d59`、`5bdf6473`、`8152265e`（11-12，4 个）；`0dd3685e`（11-16，1 个）。

## 3.3 子会话：12 个种子 fork 的真实分工

| 父会话 | fork | 序号 | 分工 | 新工作截止 |
|---|---|---|---|---|
| 879cc62f | `51d2fd7c` | 1/6 | 审计既有 LLM/Key/config 双轨逻辑（只读） | 11-16 22:41 |
| 879cc62f | `6850f239` | 2/6 | 实现 LLM Gateway 核心包 + OpenRouter/Ollama/Mock adapters | 22:41 |
| 879cc62f | `bfdd3a3d` | 3/6 | 凭证 / typed errors / usage 子模块及离线测试 | 22:41 |
| 879cc62f | `978ac2c0` | 4/6 | 把 assistant_llm / binaryrepair_ai / ai_* 接入 gateway | 23:10 |
| 879cc62f | `628458cf` | 5/6 | 修 stability runner 超时/状态/checkpoint/expected counts | 22:41 |
| 879cc62f | `4c44ab6e` | 6/6 | 离线集成测试、验收文档、P31–P34 复核 | 22:43 |
| b139b586 | `e1aa4f68` | 1/6 | D00+D01 基线冻结与 capability universe | 22:51 |
| b139b586 | `fbd3df43` | 2/6 | D04 heap-malloc ABI 根因独立分析 | 22:52 |
| b139b586 | `0d7b605e` | 3/6 | D05 hidden 0-candidate 阶段归因（匿名聚合） | 22:52 |
| b139b586 | `7384706a` | 4/6 | D03 Acceptance 2.0 变异/假接受/假拒绝审计 | 22:51 |
| b139b586 | `8943a46a` | 5/6 | D06+D07 外部知识扫描 + 变异/蜕变发现 | 22:58 |
| b139b586 | `b0e57d68` | 6/6 | D02+D09+D10 Gap Registry / 隔离审计 / 晋级门 | 22:57 |

> D08（实验/证据 bundle）**没有专属 angle**，由父会话（b139b586）自行补齐——这也解释了它为何最"薄"（10 条记录，全部 `promotion_effect=none`）。

---

# 4. 会话一：Linux 虚拟机验证漏洞修复-1

> `session-879cc62f-ff8b-476f-b06b-9e5f24ef1a28`｜2026-11-13 16:15:49 → 2026-11-17 00:46:14｜19,989 事件 / 36 turn / 80.5 h｜`deepseek-account / deepseek-flash`，`reasoningEffort=max`。

## 4.1 36 个 turn 的阶段总表（合并为 12 个阶段）

| 阶段 | turn | 目标 | 关键交付/commit | 测试 | 判定 |
|---|---|---|---|---|---|
| v7 handoff 终检 | 1 | Linux VM 终检 v7 交付包 | `BinaryRepair-Linux-Handoff-2026-11-13-v7.zip`（60,488,092 B，sha256 `2afeb6c8…fcc8`） | 950 collected / 943 passed / 7 skipped | ✅ 完成 |
| v5 任意二进制 | 2–3 | 任意输入有确定性结论（i386 引擎+运行时+UI） | `915f362`（68 files，+8531/−316）→ `47465e0`→`f65c2dc`→`72db891` | 1014→1039 / 0 fail | ✅ 代码+推送 |
| v6 两条 AI 路径 | 4–6 | `ai_plan`/`ai_bytes`，后重做为 `asm_roundtrip`/`binary_direct` | `abeab27`→`6d525ca`→`af8f674`→`61287fd`→`aa45b36` | 1118→1128 / 0 fail | ✅ 链路完成、增量未证明 |
| 硬案例与公平性消融 | 8–15 | 证明"确定性 baseline 修不了、AI 能修" | `4ee5e5d`→`0adcd68`→`853dd04`→`eb1f0a4`→`24f8e2b`→`afb1e85` | 1143 | ✅ 增量 1（0/2→1/2）；消融 0/0/0 vs 6/10 |
| 多 provider/凭证 | 17–25 | 8 家 provider 配置、严格 model identity、4 模型矩阵 | `91e4706`→`afe4aee`；`c3dae2f`（4 模型 6/6/0/0） | 1149→1161 | ✅ 真实调用；国际站 402、三平台 key 401 |
| 范式 A（loop） | 21 | Path A call 白名单 + code cave 闭环 | `148df69`→`d69c84b` | 1155 | ✅ loop 6/6 |
| CWE-121 非 loop | 22 | 首个非 loop 范式 A | `fa80f50`→`12d05ec` | 1155 | ✅ 2/2 PoC + 4/4 reg |
| P0–P4 归因 | 27–28 | ud2、auto symbols、ld_preload errno | `f2392fd`→`2739ead`→`12945c3`→`a8934fe` | 1626→1641 | ✅ 3/3 非 loop AI VERIFIED（转折点） |
| P5–P15 | 29–30 | native feedback、RepairSpec v2、跨二进制 benchmark、36 次稳定性 | `bd9cbf6`→`dad21c9` | 1954→1966 | ⚠️ 4/6；19/36=52.8% |
| P16–P24 | 31–35 | 严格独立验证、冻结 profile、artifact 审计、stability runner | `c5d87b5`→`106d1cd`→`085fc38`→`f42e6c4`→`a1755a5` | 2041→2048 | ✅ P16-R3 7/10；⚠️ 60-run 未跑 |
| P31–P34 | 36 | 统一 LLM Gateway / OpenRouter+Ollama / preflight / runner 加固 | `a0e6a24`（孤儿）+ `e01fc9e`→`13d3c1d`→`b896f1b`→`d37bfad`；`a9db731`→`c0f9feb` | 2411 / 0 fail | ⚠️ 离线完成；P32/P33 live NOT_RUN |
| 收尾 | 36 末 | 合流 + 最终报告 | push 被拒；4,844 字符报告 | — | ❌ 合流失败 |

> 会话一几乎是"单线推进、每 turn 至少一个可核验 commit"：从 `915f362` 到 `d37bfad` 共 40+ 个 sha。最有价值的三个转折点：`0adcd68`（首个硬案例增量 1）、`a8934fe`（3/3 非 loop AI VERIFIED）、`f42e6c4`（PT_LOAD 统一映射 → 严格验证 7/10）。

## 4.2 关键结果（可对外引用）

- **确定性矩阵**：批准计划内 100%（v5 任意二进制 8 cell + 7 种 disposition）。
- **AI 两条路径**：`asm_roundtrip`（ELF 三架构）与 `binary_direct`（ELF x86-64）链路完成；6 条 verified，但候选与确定性 baseline 相同 → **增量未证明**。
- **范式 A**：单函数级成立——loop 6/6、CWE-121 2/2 PoC + 4/4 reg、3/3 非 loop（`a8934fe`）；**不是通用**。
- **严格独立验证**：P16-R3 **7/10** verified（PT_LOAD 统一映射后）。
- **稳定性**：36 次 **19/36 = 52.8%**（flash 12/18、v4-pro 7/18；cwe121 0/6）。
- **hidden**：1 例成功（CWE-476）——但 Phase-8C 的 hidden 正式口径是 **0/6**（见 §6.3；CWE-476 属早期 hidden 单例，不是 8C hidden 集）。
- **多模型**：4 模型真实矩阵 6/6/0/0；`deepseek-chat` 请求实际服务 `deepseek-flash`（`identity_ok=false` 如实记录）；Qwen 小模型 0/12；SiliconFlow 国际站 402。

## 4.3 负结果（一个都不能丢）

| 负结果 | 数值 | 根因/说明 |
|---|---|---|
| CWE-121 AI | 0/6 | Behavior Contract：候选 `exit 0`/空 stdout vs 契约 `exit 1` + 精确 stderr |
| CWE-134 AI | 恒 `PLAN_INVALID` | 格式串计划无法通过 schema/ABI |
| UAF 探针 | 0/1 | 无生命周期分析 |
| heap-canary | 0/1 | 无堆容量/哨兵分析 |
| Path B callee-context A/B | 0 vs 0 | 上下文注入未改变结果 |
| `deepseek-v4-pro` ABI 管线 | 0/3 | 模型选择救不了非 loop |
| Qwen 小模型 | 0/12 | 能力不足 |
| SiliconFlow 国际站 | HTTP 402 | 余额/额度 |
| 三平台 key | 401 | 凭证无效 |

## 4.4 最终卡点：不是"死循环"，是"把 30 分钟等待当轮询"

- turn 36 耗时 2 h 07 m，其中约 90 min 在等 CI；全会话 `job_output` 阻塞累计约 **1,499 min（25 h，占 80.5 h 的 31%）**——这是**流程缺陷**，不是模型死循环。
- 框架在 `#seq=19967 @00:45:47` 发出第 5 次"你正在重复完全相同的工具调用"告警后，模型才换命令。
- 最后一个动作 `#seq=19978 @00:45:57`：`git push origin HEAD:final/consolidated-2026-11-16`，因 `c0f9feb` 不是 `d37bfad` 的祖先（`anc=1`）被 **non-fast-forward 拒绝**；模型选择不强推，会话以 `turn/end reason=completed`（`#seq=19987`）正常结束，并输出 4,844 字符最终报告。
- **后果**：`workbench-v3 = d37bfad`（含 Phase-8D + P31–P34）与 `final/consolidated-2026-11-16 = c0f9feb`（仅 P31–P34、无 Phase-8D）并存。**这就是本轮要修的断点。**

## 4.5 未提交 / 未推送 / 未收尾产物

| # | 项 | 状态 | 风险 |
|---|---|---|---|
| R1 | `a0e6a24`（P31–P34 feature 线原始提交） | **孤儿提交，无 ref** | `worktree-feature-final` 一删就不可达（内容已由 `e01fc9e` 重放，但提交/message 丢失） |
| R2 | `worktree-feature-final` | detached HEAD（`a0e6a24`） | 误 checkout 后难找回 |
| R3 | `worktree-p31-ci` | detached HEAD（`d37bfad`） | 无本地分支跟踪 |
| R4 | `final/consolidated-2026-11-16` | 分叉且缺 Phase-8D | 已在本轮删除，本地有备份 |
| R5 | P35–P40 | 完全未执行 | 用户 turn 36 任务书只完成 P31–P34 |
| R6 | 真实 OpenRouter/Ollama 凭证 | 未配置 | P32/P33 永远 `LIVE_NOT_RUN` |
| R7 | 8124/8123 网页 token | 明文出现在会话/报告 | 需轮换、脱敏 |
| R8 | 用户两次粘贴的 API key | 已进会话日志 | 需吊销/轮换（`[REDACTED]`） |

> 本轮已为 `a0e6a24`、`c0f9feb`、`bdd3f84`、`a1d7150` 建本地 `backup/*` 保护分支，并写入 129MB mirror + 128MB bundle。

---

# 5. 会话二：全类型二进制修复-1

> `session-b139b586-985b-475c-af5a-1ee7f0082668`｜2026-11-14 15:12 → 2026-11-17 01:31｜18,457 事件 / 16 turn｜作者身份 `BinaryRepair`（86 个提交）。

## 5.1 16 个 turn 的阶段总表

| turn | 时间 | 目标 | 关键产出 | 结果 |
|---:|---|---|---|---|
| T1 | 11-14 15:14–16:01 | marcx 容量混淆修复 | `app/services/repair/capacity.py`；gate `patch.capacity`；`runtime.evidence/tier/contract` | **14/14 gate、28/28 guest 差分、16/16 挑战矩阵**；1224 passed |
| T2 | 18:34–19:37 | 66 项 gap 审计 | `scripts/audit_capability_coverage.py`；coverage-matrix/gap-report | 66 gaps = 51 closed + 1 mitigated + 3 open + 11 non-goal |
| T3 | 19:39–20:39 | P0–P3 全落地 | target scope、Mach-O 限制、legacy guard、11 non-goal、CI coverage-gate | **55 closed / 0 open / 11 non-goal**；marcx 21/21、heap 19/19 |
| T4 | 20:45–22:22 | 六类系统性差距 | whole-image 默认 analysis_only；provider 12/12 真实调用 | AI target 6/12；`identity_ok=false` 如实记录；9/9 release gate |
| T5 | 22:24–23:31 | 发布一致性/证据/provider 维度 | 11/11 gate、68 gaps（55+1+12+0 open）、240 cells | full pytest 564.9s；真实 Lima 通过 |
| T6 | 23:40–01:13 | 12/12 冻结发布 | `fd6ca41`；`release_freeze.py`；provenance | 12/12；并发冻结 fail-closed 实测 |
| T7 | 11-15 01:28–03:05 | 13/13 + 真实 CI 首次全绿 | `a8934fe`；CI 43628367481 / Ubuntu 43628367473 | 13/13；1034.6s |
| T8 | 03:05–04:44 | Phase-7 Autonomy Foundation | `2bfa112`；20 维宇宙 240 cells；64 gap registry；反思 12 问/91 记录 | 13/13；CI 43637263062 |
| T9–T12 | 12:42–16:12 | Phase-8A | `bd9cbf6`；Readiness G01–G30；Ground-Truth v1；独立验证器 MVP | 12 样本：2 deterministic verified，但独立验证 **0 verified / 10 unknown / 2 disagreement**（引出 8B） |
| T13 | 16:30–21:50 | Phase-8B 验证器语义闭合 | `227f45b`；`verification_semantics.py`；7 条根因全部 confirmed | **2 verified / 0 false verified / 0 disagreement**；1 个 deterministic claim 被撤回 |
| T14 | 22:05–11-16 03:18 | Phase-8C Ground Truth v2 + Hidden | `4a7b2355`；32 公开样本 / 8 hidden；17 contracts | 24 eligible → **2/24 = 0.0833**；hidden 0/6；false_verified=0 |
| T15 | 11-16 22:44–11-17 01:26 | Phase-8D 开放世界 | `d1b73bf`→`78edb97`→`996060d`；`bdd3f84`；`a1d7150`；`d37bfad` | D00–D10 全交付；**0 能力晋级**；gate 13/13 |
| T16 | 11-17 01:31 | 收尾 | 只做最终确认，未重复执行 | 正常 completed；无未推送提交 |

## 5.2 全类型矩阵（8 cell，不是"任意二进制"）

声明矩阵：**ELF i386/x86_64/arm64 + PE i386/x86_64/arm64 + Mach-O x86_64/arm64（仅小端 thin）**。产物 `artifacts/binary-universal-v5-2026-11-13/`（scan/repair/baseline 各 8 组 + 4 组负例）。

| 家族 | cells | 真实运行层级 | 说明 |
|---|---|---|---|
| ELF | 3 | 模拟执行（qemu/Lima） | x86-64 为主；i386 全链；arm64 部分 |
| PE | 3 | 仅 Unicorn/分析 | **从未在 Windows 上跑**；改写能力有限 |
| Mach-O | 2 | native（macOS x86-64） | arm64 仅分析；32-bit/fat/大端不支持 |

> `asm_roundtrip` 仅 ELF 三架构；`source_roundtrip` 未实现；whole_image 永不 verified。任何"任意二进制修复"的表述都不成立。

## 5.3 Phase-7/8A/8B/8C/8D 的关键数字

| 阶段 | 冻结 SHA | gate | 核心结果 |
|---|---|---|---|
| Phase-7 | `2bfa112` | 13/13 | 240 cells / unknown 0；64 gap；反思 verified_true=0 |
| Phase-8A | `bd9cbf6` | 13/13 | 12 样本：2 deterministic verified，独立验证 0/10/2 |
| Phase-8B | `227f45b` | 13/13 | 2 independently verified；false_verified=0；1 claim 撤回 |
| Phase-8C | `4a7b235` | 13/13 | 32 public（24 runtime/8 analysis）；**2/24**；hidden 0/6；17 contracts |
| Phase-8D | `996060d` / `d37bfad` | 13/13 | 297 units；8 gaps open；D05 6/6 detection_missed；0 promoted |

**Phase-8D 的 D00–D10**：

| 工作流 | 交付 | 真实结果 |
|---|---|---|
| D00 | 8C 基线冻结 + frozen tags | 8C release/tree/evidence/gate/CI 事实全部记录 |
| D01 | 297-unit / 20 维能力宇宙 | 240 声明 cell + 32 public + 2 hidden + 3 prototype；**2 verified / 0 generalized / 0 promoted**；表外 unknown=null |
| D02 | Gap Registry | **8/8 全 open**（critical 2 / high 6）；历史 64 条只读不改写 |
| D03 | Acceptance 2.0（L0–L7） | 18 cases；`mutation_results` 7 条但 `mutation_detection_rate=1.0`；0 false accept / 0 false reject；2 inconclusive + 2 not_run |
| D04 | heap-malloc ABI 根因 | 主因 `generator_plan_incorrect` + `abi_proof_insufficient`；贡献 `verifier_rule_incorrect`；**候选仍 rejected，规则未放宽** |
| D05 | hidden 阶段归因 | 6/6 执行；first blocking stage **`detection_missed` 6/6**；0 candidates；仅匿名聚合 |
| D06 | CWE 5.0 / Schema 8.0 | 984 entries / 232 mapped / 15 new / 752 unmapped；无 support claim |
| D07 | metamorphic + input mutation | 4 变体（2 executed / 2 stripped unsupported）；11/11 input mutations；sample_based 仍 not_run |
| D08 | 实验/证据 bundle | 10 条记录，全部 `promotion_effect=none`；verified_true=0 |
| D09 | hidden 隔离审计 | 操作隔离通过；same-UID/root 可读，非密码学隔离 |
| D10 | promotion gate | **4/4 transition denied**；promoted=0 |

## 5.4 归属澄清（必须分开写）

| 项 | 属于会话一？ | 属于会话二？ | 证据 |
|---|---|---|---|
| P31–P34 | ✅ 是（turn 36） | ❌ 否 | `a9db731`/`c0f9feb`/`e01fc9e`/`d37bfad`；author `operator（身份已脱敏）` |
| Phase-8D | ❌ 否（只在 turn 36 的指令里出现） | ✅ 是（T15） | `d1b73bf`/`78edb97`/`996060d`/`bdd3f84`/`a1d7150`；author `BinaryRepair` |
| 36 次稳定性 19/36 | ❌ 否 | ❌ 否 | p10–p15 的 `d4263f9`；会话二只把它写进 LIMITATIONS |
| M1–M4 四成员 | ❌ 否 | ❌ 否 | 791a 会话（上轮回顾）在 11-16 12:17 集成 `38dd93d` |
| 门户 + 漏洞 ELF | ❌ 否 | ❌ 否 | `b75be565`（11-16 18:37–20:27） |

> 会话二两次 `TRANSPORT` 中断（T11/T12）与一次 loop-guard（T14，`job_output` 轮询长 gate）都自行恢复；真正未恢复的是会话一终局的 non-fast-forward push。

## 5.5 会话二结束时的"完成/未完成"

**完成且有真实证据**：marcx 14/14 + 28/28 + 16/16；68 gaps = 55 closed + 1 mitigated + 12 non-goal + 0 open；连续 8 次 release/nightly gate 全过（11/11→12/12→13/13×6）；Phase-7/8A/8B/8C/8D 五阶段全部落地且每阶段 0 promotion；8B 2 verified / 0 false verified；8D 297 units / 8 gaps open / hidden 6/6 detection_missed / promotion 0/4。

**未完成/not_run**：hidden 泛化 0 verified；heap-malloc 仍 rejected；sample_based 发现 not_run；第二 Linux 编译器（跨编译器）无；国际 provider 矩阵 `not_satisfied`；self-hosted Lima nightly not_run；真实 OpenRouter/Ollama 与 live 60-run NOT_RUN；Acceptance 2.0 的 correct-but-new-layout false reject 未充分测量；hidden 隔离仅 operational。

---

# 6. 当前完成现状（2026-11-17）

## 6.1 权威提交与分支拓扑

```
f1bb1f4 (11-16 12:19, 四成员集成 + 166KB 总报告)
├── a9db731 ── c0f9feb        final/consolidated-2026-11-16（仅 P31–P34，无 8D；本轮已删，本地备份）
└── d1b73bf ── 78edb97 ── 996060d        phase8d-open-world（8D 集成；本轮已删）
                              └── e01fc9e ── 13d3c1d ── b896f1b ── d37bfad        workbench-v3（8D + P31；本轮已删）
                                                                    └── a1d7150   final evidence（本轮已删）
                                                                                  └── 9194b02 → …（docs 提交）   final/consolidated-2026-11-17（本轮新分支；tip 见 git log）
```

| 提交 | 角色 | 说明 |
|---|---|---|
| `d37bfad` | **被 gate/CI 验证的最终树** | 2,359 tracked files；2411 tests；Phase-8D + P31–P34 + M1–M4；CI 43907137267/43907136876 success |
| `a1d7150` | 最终证据提交 | `d37bfad` 子提交；+final gate 13/13；**删除 33 个历史 gate 文件**（本轮不采用其删除） |
| `bdd3f84` | 8D-only 证据 | 独有 `release-gate-2026-11-17-phase8d/` + final evidence 文档 |
| `c0f9feb` | 上一轮 final | 仅 P31–P34；**无 Phase-8D**；2319 tests |
| `9194b02` | **本轮新分支首批提交** | `d37bfad` + a1/bdd 新增证据 + 9 份文档 + CI 触发重定向；`build_phase8d_capability_universe.py --check` OK |

## 6.2 测试、CI 与门禁

| 项 | 值 | 证据 |
|---|---|---|
| 全量测试（`d37bfad`） | **2411 tests / 0 failed / 0 errors / 9 skipped / 1015.7s** | `artifacts/binary-universal-v5-2026-11-13/macos-junit.xml` |
| 独立 collection | 2423（249 文件，含 e2e 12） | `/tmp` 干净导出树 `pytest --collect-only` |
| 浏览器 e2e | 12/12（11-15 记录，非 11-17 复跑） | `artifacts/browser-e2e-2026-11-14/junit.xml` |
| 本地 frozen-tree gate | **13/13**，20.8 min，`ok=true`，`violations=[]` | `artifacts/release-gate-2026-11-17-phase8d-final/phase8d-final-gate/gate.json` |
| gate `not_run` | `github_actions`、`international_provider_matrix`、`self_hosted_nightly_lima_capture` | 同上；**not_run 不是 pass** |
| GitHub CI | `43907137267`（CI）/ `43907136876`（Ubuntu）在 `d37bfad` 上 **success** | GitHub Actions API |
| 8D 集成 CI | `43905664704` / `43905664754` 在 `996060d` 上 success | 同上 |
| 当前 HEAD 的 CI | 新分支（首批 `9194b02`）的 CI 由本轮 push 触发（见 Actions 页面）；**不声称已绿** | — |

## 6.3 能力现状（唯一权威口径）

| 指标 | 值 |
|---|---|
| 公开修复集 | **2/24 verified = 8.33%**（30 executed / 1 rejected / 1 withdrawn / false_verified=0） |
| hidden runtime | **0/6**（8 样本 = 6 runtime + 2 analysis-only；0 candidate / 0 verified） |
| 能力宇宙 | **297 units**：not_applicable 131 / discovered 98 / analysis_only 32 / unmeasurable 24 / unknown 7 / independently_verified **2** / unsupported 2 / candidate_generated 1 / generalized **0** / promoted **0** |
| Phase-8D gaps | **8 open**（critical 2 / high 6） |
| 36-run 稳定性 | **19/36 = 52.8%**（flash 12/18、v4-pro 7/18；cwe121 0/6） |
| provider 统计 | 4 模型 / 2 provider / 96 case-run / 36 verified；Wilson [0.285, 0.475]；intl 402 |
| 全类型矩阵 | 8 cell（ELF×3 + PE×3 + Mach-O×2）；PE 从未在 Windows 跑 |

## 6.4 工程与产品现状

| 资产 | 状态 | 说明 |
|---|---|---|
| GUI 工作台 | 运行中 `127.0.0.1:8123`（401 = 鉴权生效） | 但主 worktree **脏 41 项**、P31 半回退；不能声称"当前工作树 = P31 完整特性" |
| 成果门户 | 运行中 `127.0.0.1:8899`（200） | 数据停在 11-16（2301 tests/240 cells/"0 open"）；**未入 git** |
| 漏洞 ELF | `delivery/zh/vuln-elf/vuln-demo-x86_64.elf`（4.99MB，CWE-121/122/134/416） | **未入 git**；本轮未纳入分支（属 b75be565 会话产物，不属两个重点会话） |
| Lima guest | `binaryrepair` Running（aarch64，4 CPU/6GiB） | `gdb`/`afl-fuzz`/`zig` **MISSING**；clang/gcc/readelf/qemu-x86_64 存在 |
| P31 Gateway | `app/services/llm_gateway/`（11 文件）+ preflight + runner | 离线测试 30 passed；live 全 NOT_RUN |
| M1–M4 首增量 | `afaf75a`/`71a8d6d`/`a23931b`/`77a3173` | M1 确定性替身；M2 只读原型；M3 产品化；M4 ops 文档/脚本 |
| 备份 | 11-16 mirror 只到 `f1bb1f4`；本轮新建 129MB mirror + 128MB bundle | 见 §9.4 |

## 6.5 治理现状

- `docs/status/claims.json` 的 `ci_evidence.gated_sha` 仍是 `78edb97`（run 43900916188），**不是** `d37bfad`；最终发布 CI 记录在 `docs/release-phase8d-final-mainline-evidence-2026-11-17.md`。这是治理债，不是"CI 未通过"。
- 远端默认分支仍是 `main`（`8869b07`，11-12）；本轮未改（无 admin token）。
- 远端 heads 91（含新分支）、tag 行 89（65 真实 tag）、会话相关残留 0；`refs/pull/*` 与 170 条 Actions run 仍在。
- 4 个 provider key（K1 SiliconFlow CN、K2 SiliconFlow Intl、K3 DashScope、K4 DeepSeek）仍标 COMPROMISED，轮换 `blocked_by=owner`。

## 6.6 旧报告（11-16 版）需要修正的 6 处

| # | 旧表述 | 2026-11-17 实测 | 处理 |
|---|---|---|---|
| 1 | 「两会话成果已整合，0 残留 refs」 | `final/consolidated-2026-11-16` 缺 Phase-8D；11-17 又新增 7 heads + 6 tags；push 曾失败 | 本文 §4.4/§9 改写；本轮已重做 |
| 2 | 「non-loop 3/6」 | 仓库权威口径是 **12-case 矩阵 non-loop 0/6**（两模型各 0/6）+ RepairSpec 3 个 hard case 3/3（仅 flash，v4-pro 0/3）；"3/6"只是 36-run 表里 hard-nonconst 单 case | 本文 §4.2/§4.3 修正 |
| 3 | 「以 mainline `4a7b235` 为权威」 | 当前最全树是 `d37bfad`；8C `4a7b235` 只是其祖先 | 本文 §6.1 修正 |
| 4 | 「38 会话 / 7 归档」 | **41 / 8**；另有 43 子会话（12 个种子 fork） | 本文 §3 替换 |
| 5 | 「已删除 23 分支 + 14 标签、会话残留 0」 | 对 11-16 成立；11-17 又新增 7 heads + 6 tags；本轮再次删除 7+6 | 本文 §9 记录两轮 |
| 6 | 「tests 2243 / cells 240 / gaps 0 open」 | `d37bfad` **2411 tests**；8D **297 units / 8 gaps open**；240 cells 是 8C 口径 | 本文 §6.2/§6.3 |

---

# 7. 尚未完成的任务与全部问题（27 项）

> 分级：**P0** 阻塞交付/签核（安全、单一 SHA、核心能力上限、备份、工作树完整性）；**P1** 能力/验证缺口；**P2** 治理/债务。每项给现状、证据、影响、根因、方案、验收。方案细节见 §8。

## 7.1 P0（6 项）

### P0-1 凭据未轮换（安全，owner 阻塞）

- **现状**：K1–K4 四个 provider key 仍为 COMPROMISED；runbook 已写（`docs/operations/security-key-rotation-2026-11-17.md`），执行 `blocked_by=owner`。会话日志/本机 key store 有明文历史。
- **影响**：任何"交付签核"不成立；旧 key 可消耗账户/污染实验。
- **方案**：① owner 在 4 个控制台吊销再新建；② GUI key store 迁移 macOS Keychain；③ CI/pre-commit secret scan；④ 对 `handoff/archive`（~1.5GB）做离线扫描（当前 not_run）。
- **验收**：4 个旧 key 全部 401/失效；跟踪文件 `git grep` 0 命中；GUI 重启可调用且 key 不出现在页面/日志。

### P0-2 单一交付 SHA 缺失（本轮已修复）

- **现状（修复前）**：`final/consolidated-2026-11-16`=`c0f9feb` 与 `d37bfad` 互不包含（final 独有 2 提交、d37 独有 7 提交）；P31 关键路径 diff 为空。
- **本轮处理**：以 `d37bfad` 为基线建 `final/consolidated-2026-11-17`（首批 `9194b02`），补 a1/bdd 证据，推送成功；删除旧 final/workbench/phase8d refs。
- **验收**：新分支 `git merge-base --is-ancestor d37bfad HEAD` 与 `4a7b235 HEAD` 均 0；`git ls-remote` 只有 1 条交付分支；README/CONSOLIDATION 只指向它。

### P0-3 hidden 泛化 0/6：卡在 detection

- **现状**：6/6 runtime hidden 样本 `first_blocking_stage=detection`、`no_candidate_reason=detection_missed`；parse/target-scope 已观察，后续阶段 not_reached；0 candidate、0 verified。
- **证据**：`docs/operations/phase8d-hidden-stage-attribution.md:47-58`；`artifacts/phase8d-hidden-attribution-2026-11-17/aggregate.json`。
- **根因（含一处需修正的叙述）**：① 真实根因待证——hidden 为 Zig 变体/不同优化/可能 stripped；D07 已实测 stripped 变体 `target could not be resolved to a unique function with a determinable end address`（2/4 unsupported），与 detection 失败高度同源（假设，需 private 阶段计数验证）。② **叙述错误**：D05 文档称引擎"claimed detected=true/repairable=true 却 0 findings"；实际 `universal.detected`=容器格式识别、`repairable`=矩阵单元存在（`app/services/binary_pipeline.py:286-287`），真实检测是 `bool(findings)`（`app/services/benchmark_runner.py:846,850`）。0 findings 事实不变，但"引擎自相矛盾"不成立。
- **方案**：① 字段改名 `format_detected/matrix_supported` + 新增 `finding_count`，保留旧键一版；② 公开集复现 hidden 失败（4→8 编译器变体 × stripped/not）；③ 修 stripped 目标解析（线性 sweep + 符号 size + 函数边界投票），失败必须 `function_boundary_unknown`；④ 扩检测模板（内联 `rep movs`/向量 mov/`__memcpy_chk`），每条配正/负 fixture；⑤ 私有阶段计数随 hidden lane 输出，公开只发 counts。
- **验收**：hidden runtime detection ≥1（6/6 有明确 stage 结论）；public 2/24 不降；false_verified 仍 0；`--check` 通过；公开产物无 per-sample 字段。

### P0-4 非 loop 剩余 3 例仍 0；CWE-121/134 只有确定性替身

- **现状**：非 loop 0/6（12-case 矩阵，两模型各 0/6）；CWE-121 public、UAF-noinput、heap-canary 仍 0；M1 的 CWE-121/134 成功均为 reference/scripted 汇编，`no live model call`；`3/6` 未变 `4/6`。
- **证据**：`docs/operations/m1-2026-11-16.md:153-161`；`artifacts/stability-2026-11-16/README.md`；claims `explicitly_unimplemented`。
- **方案**：① CWE-121 live 复跑 6 次（记录 model identity），验收 ≥1 次独立 verified 且 stdout/stderr/exit 精确匹配；0/6 则如实发布并关闭 P38；② CWE-134 live 1 plan + PoC，验收 plan_valid 且 `%s` 行为正确，否则降级 non_goal；③ UAF/heap-canary 转 P1-5（先检测/分析后修复）；④ 预算闸门（≤120 次调用），失败即停。
- **验收**：新增 `artifacts/live-cwe121-134-2026-1x/`（requested/served model、identity_ok、独立验证状态）；报告明确"AI 3/6 → 3/6 或 4/6"。

### P0-5 备份不覆盖当前交付链（本轮已重建）

- **现状（修复前）**：mirror 的 final=f1bb1f4，`d37bfad` 对象不存在；bundle 实际 SHA 与文档不符；异地副本缺。
- **本轮处理**：`backup/2026-11-17/binary-repair-mirror-2026-11-17.git`（129MB，167 refs（清理后刷新），`a1d7150`/`c0f9feb` 可检出）；`local-refs-2026-11-17.bundle`（128MB，complete history）；refs/SHA256SUMS/patch 全部落盘。
- **验收**：`git -C mirror cat-file -t <新分支SHA>` 成功；`git bundle verify` complete；恢复演练到空目录可检出首批 `9194b02`/`d37bfad`/`4a7b235`。
- **剩余**：异地副本仍缺（需 owner 提供路径）。

### P0-6 GUI 工作树半提交 + 未提交 writer 修复（本轮已保全，未合入）

- **现状**：`binary-repair-gui` 有 **41 项** status：10 个 `llm_gateway` 文件 + 3 个 P31 测试 + `run_model_preflight.py` + P31 文档被**暂存删除**；磁盘上 `llm_gateway/` 只剩 3 个文件（`__init__/base/client/providers` 缺）；`import app.services.llm_gateway` 变成 namespace package，`create_gateway` 不可导入。同时有**任何分支都没有**的未提交改动：`code_cave.py`（+76/−36，修 phdr 槽位写进 `.rodata` 的回归）、`binary_pipeline.py`（+138，`suggest_repair_targets`）、`agent.js`（+140）。
- **影响**：① 在该树 `git commit -am` 会删掉 gateway/P31 测试，交付树不可运行；② 忽略未提交改动会丢掉**能避免静默破坏 `.rodata` 的 writer 修复**——这是一类 gate 未拦住的 false-accept，直接动摇 `false_verified=0` 的置信度。
- **本轮处理**：未在该树提交；已保全 `backup/2026-11-17/gui-worktree-dirty-2026-11-17.patch`（622KB）、staged/unstaged、status、untracked tgz；新分支从干净 `d37bfad` 构建，gateway 完整。
- **方案**：① 从干净 worktree 重放 3 个独有补丁（`code_cave`、`suggest_repair_targets`、`agent.js`），**不重放 staged 删除**；② 为 `code_cave` 加回归测试（phdr 后紧邻 `.rodata` 的 ELF；patch 后 `.rodata` 字节不变、`--list` 含 `format_case` 与分隔线）；③ 全量 pytest + gate 后再单独提交。
- **验收**：干净树 2411 tests 0 fail；新回归测试在旧 writer 上失败、新 writer 上通过；gateway 可 `from ... import create_gateway`；`--list` 输出完整。

## 7.2 P1（11 项，能力/验证缺口）

| ID | 问题 | 现状 | 方案（摘要） | 验收 |
|---|---|---|---|---|
| P1-1 | D04 heap-malloc ABI 根因未闭环 | 已分类 `generator_plan_incorrect`+`abi_proof_insufficient`；候选仍 rejected | plan 优先声明注入 cave；verifier 解析 `call/jmp [rip+disp]` 与尾跳，失败仍 fail-closed；重跑 benchmark + acceptance 2.0 | heap-malloc 9/9 或仍 rejected 但证据完整、规则未放宽；正/负例各 ≥2 |
| P1-2 | P36 CaveABIBlock 出口语义只覆盖 `ret` | 仅 `ret`；`tail_jump/continuation_jump/noreturn` 无结构 | 新增 `cave_abi_contract.py`：出口分类器 + 每类允许条件 + 2 正 1 负测试 | 4 类出口各有独立测试；未知出口 fail-closed；P16-R3 7/10 不降 |
| P1-3 | P37 授权仍是 STATIC_REFERENCE_ONLY | 无签名、不绑定 ELF/plan/bytes | Ed25519 记录 `{policy,issuer,expiry,binary_sha,plan_sha,actions,scope}`；验证器验签+时效+逐字节绑定 | 伪造/过期/越权/越界 4 类拒绝；1 正例通过 |
| P1-4 | Verifier 2.0 语义保持 + false-reject/规则变异套件缺失 | Acceptance 2.0 仅 18 案/14 变异；3 条 false-reject 缺口是记录性 | 每类 AM01–AM28 配 ≥1 合法修复夹具；规则变异 test-only；6 维行为差分；失败→rejected | false_reject 有非零分母且 ≤阈值；变异 14+/14；≥1 行为改变负例被拒；false_accept 0 |
| P1-5 | UAF/整数/heap-canary/字符串矩阵 0 覆盖 | 多数 analysis-only/not_run | 每类先做检测+定位（malloc/free 状态机、range、堆容量/哨兵、格式串），每类 ≥2 fixture | 每类 ≥1 verified 或明确 not_run + 证据；不得 analysis-only 冒充修复 |
| P1-6 | P35 60-run、P32/P33 live、5–6 模型矩阵未完成 | 60-run 未跑；OpenRouter/Ollama live NOT_RUN；4 模型/2 provider | P32 live identity probe；P33 Keychain/GitHub Secret；P35 2×10×3=60；OpenRouter 增 1–2 模型 | 60/60 有记录；live 各 1 条证据；5 模型或明确 not_satisfied |
| P1-7 | 跨函数/别名/全局/结构体容量；M2 未接入 | M2 只读原型，not consumed by gate/planner | feature flag 注入 planner packet；DWARF 对象尺寸；stripped 解析；1 跨函数 fixture + 2 负例 | "当前失败/M2 定位成功"；接入后 ≥1 verified；alias 负例 fail-closed |
| P1-8 | 发现机制 7 缺 2（sample_based、knowledge_source_scan） | mutation/metamorphic 部分；sample_based not_run；knowledge 仅目录扫描 | 扩 8 变体；本地许可语料 ≥20；7 机制统一 registry | 7/7 有状态与原因；≥1 可复现 gap；历史 registry 字节不变 |
| P1-9 | P40 GDB N3–N6 + AFL++ 未运行 | guest `gdb`/`afl-fuzz` MISSING | 安装 gdb/afl++；qemu-x86_64 -g + gdb remote；N3–N6 探针；AFL 1 fixture | ≥1 寄存器/栈 trace + ≥1 AFL crash 可复现；否则保持 not_run |
| P1-10 | GUI 真实 LLM 联调缺失 | 模板/JS 无 provider 选择；无 live e2e | 设置页 provider/model/base_url；`/api/assistant/status` 返回 identity；mock+live smoke | GUI 可切 mock/openrouter/ollama；记录 model identity；页面无 key |
| P1-11 | promotion/reflection 未闭环 | gate 4/4 denied；reflection 101 条/0 执行 | gate 加人工审批签名 + 合法转移 CLI；执行 1 个带证伪条件的实验 | 1 个实验真实执行；决策含审批字段；仍 0 自动晋级 |

## 7.3 P2（10 项，治理/债务）

| ID | 问题 | 方案 | 验收 |
|---|---|---|---|
| P2-1 | 口径漂移（门户 2301/240/0-open vs 实际 2411/297/8-open；claims 留 non-loop 0/6 与历史 CWE-121 2/2） | 门户从 claims+registry 读取；gaps 拆 Phase-7 audit（0 open）与 Phase-8D audit（8 open）；claims 每条加 `as_of`+`scope` | 所有数字可在 claims/registry 找到同值；无 2301/240 残留 |
| P2-2 | CI 分层/默认分支：self-hosted inert；claims 指针 78edb97；main 8869b07 | claims 增 `final_release_sha`/`final_release_gate`；新分支 CI 绑定；owner 切默认或 FF main | claims 两层 SHA 清晰；CI 至少 1 次 success 绑定 tip |
| P2-3 | refs 膨胀 + 两套 P31 + `post-final/*` | 本轮已删 7+6；`post-final/*` 先确认来源再归档/删 | heads ≤ 25 且无 session/phase8/release-2026-11-1x 残留 |
| P2-4 | 备份文档 SHA/refs 与实物不一致 | 重建 2026-11-17 备份；文档只写 as-of + 命令；SHA 由 SHA256SUMS 提供 | 文档 SHA 与 `shasum` 一致；SHA256SUMS 覆盖 mirror/bundle/refs |
| P2-5 | hidden 隔离仅操作层（同 UID/root 可读） | 保持 operational；release 前只读检查（root mode/commitment/泄漏扫描） | 每次 release 有 isolation.json；不改口为 cryptographic |
| P2-6 | 反思 101 条/12 决策无执行器 | 与 P1-11 合并执行 1 个实验；其余标 proposed/not_run | 1 条 executed 记录（input/output/exit/oracle） |
| P2-7 | 平台/格式边界 + readelf 外部依赖 | 保持限制表；readelf 换 LIEF/llvm-readelf（保留兼容）；每项 contract+measured+negative | LIMITATIONS 平台表与实测一致；macOS 默认环境跑通替代后端 |
| P2-8 | 全量 1015s / gate 1250s；无性能基线 | 分层（unit/integration/e2e）+ 并行非 gate + 缓存；记录 gate 时间基线 | gate ≤ 20 分钟；分层命令与耗时写入 docs |
| P2-9 | 工作区残留（`.tmp` 373MB、handoff 1.7GB、capacity 464KB）+ portal 未入库 | 归档后清理；portal 以 `delivery/portal/` 入新分支（去掉 run/token）；README 指向 | 无 >100MB 未归档目录；portal 可 `--no-workbench` 启动 |
| P2-10 | gateway 生产化：无 routing/queue/限流/成本；preflight 默认 mock-model | 增加 routing/有限重试/并发上限/cost=null；preflight 按 provider 设默认模型并拒绝 mock+live | 401/402/429/5xx/timeout 各有单测；preflight 默认非 mock |

## 7.4 Phase-8D 八个 AUDIT gap 的处置映射

| AUDIT | 严重度 | 现状 | 处置 | 本文条目 |
|---|---|---|---|---|
| 8D-01 hidden 零候选无阶段归因 | high | D05 已加私有阶段计数；检测未修 | 字段语义 + stripped 解析 + 检测模板 | P0-3 |
| 8D-02 heap-malloc ABI 拒绝未分类 | high | 已分类 | 修 plan 的 abi_block + verifier 间接调用/尾跳 | P1-1 |
| 8D-03 七机制四未跑 | high | mutation/metamorphic 部分；sample_based 未跑 | 扩 7/7 状态；本地许可语料 | P1-8 |
| 8D-04 无 false-reject 类 | high | Acceptance 2.0 仅 3 条记录性缺口 | 合法修复夹具 + false_reject_rate | P1-4 |
| 8D-05 无规则变异 | high | 14/14 变异检出基础 | 阈值/scope/evidence 变异套件 | P1-4 |
| 8D-06 反思只计划不执行 | high | 101 条/0 执行 | 执行 1 个带证伪条件实验 | P2-6/P1-11 |
| 8D-07 无晋级状态机 | **critical** | gate 4/4 denied；缺人工审批/服务化 | 签名审批 + 合法转移 CLI | P1-11 |
| 8D-08 hidden 隔离非密码学 | **critical** | 19 项 audit pass；同 UID 可读 | 保持 operational；release 前只读审计 | P2-5 |

---

# 8. 对应解决方案与 90 天路线

## 8.1 执行顺序（硬约束）

| 阶段 | 内容 | 出口条件 |
|---|---|---|
| **W0（1–2 天）** | P0-1 轮换；P0-6 保全现场并重放 3 个补丁；P0-2 已完成（新分支）；P0-5 已完成（备份） | 干净树 + 单一 SHA + 可恢复备份 + 旧 key 失效 |
| **W0–W1** | P0-4 live CWE-121/134（若 key 到位）；P2-1 口径修正；P2-2 claims final 字段 | 有 live 证据或明确 BLOCKED；门户/claims 无自相矛盾 |
| **W1–W3** | P1-6（P32/P33 live + 60-run 启动）；P1-1 plan/verifier ABI 修复 | 60/60 记录；heap-malloc 结论稳定；false_verified=0 |
| **W3–W6** | P0-3 detection（字段语义→stripped 解析→模板）+ P1-7 callgraph/M2 接入 | hidden 至少 1 detected/candidate；stripped 变体不再 unsupported |
| **W6–W10** | P1-2/P1-3（CaveABI/授权）、P1-4（false-reject/语义保持） | 4 类出口测试；签名授权；false_reject 有分母 |
| **W8–W12** | P1-5（UAF/整数/heap-canary）、P1-8（7/7 机制）、P1-9（gdb/AFL）、P1-10（GUI e2e） | 每类 ≥1 verified 或 not_run；7/7；trace/crash；GUI live |
| **持续** | P2-2/3/4/7/8/9/10 | 交付分支 CI 绿、refs 收敛、文档一致 |

## 8.2 每项的"最小可执行第一步"

| 项 | 第一步（今天/本周可做） | 命令/文件 |
|---|---|---|
| P0-1 | 列出 4 个 key 的 owner/控制台；先吊销 K4（DeepSeek，影响最大） | `docs/operations/security-key-rotation-2026-11-17.md` §2 |
| P0-3 | 修字段语义 + 加 `finding_count`；跑 2 个 stripped 变体复现 | `app/services/binary_pipeline.py:286-287`、`benchmark_runner.py:846,850` |
| P0-4 | 配 1 个有效 DeepSeek key，跑 CWE-121 live 6 次（预算上限 120 调用） | `scripts/run_stability_matrix.py` |
| P0-6 | 在干净 worktree 应用 `code_cave` 补丁 + 写回归测试 | `backup/2026-11-17/gui-worktree-unstaged-2026-11-17.patch` |
| P1-1 | 写 2 个 ABI 正例 + 2 个负例（间接 call/尾跳） | `app/services/independent_verifier.py:1023-1045` |
| P1-6 | 跑 `run_model_preflight.py --provider openrouter --strict`，记录 BLOCKED/identity | `scripts/run_model_preflight.py` |
| P2-1 | 把门户 `overview.json` 的 4 个数字改为从 claims/registry 读取 | `results-portal/data/overview.json:18,26,58,82` |

## 8.3 硬闸门（不满足不得宣称完成）

1. `git status` 干净 + **单一交付 SHA**；
2. 2411 tests 0 fail + gate 13/13；
3. public 2/24 不降、`false_verified=0`；
4. hidden 只发 counts、无泄漏；
5. `not_run` 全部显式；
6. 旧 key 失效。

## 8.4 不能声称 vs 可以声称

| 不能声称 | 可以声称 |
|---|---|
| 通用二进制修复 / 任意漏洞 100% | 有界模板修复（public 2/24） |
| hidden 泛化成立 | hidden 0/6 已测量、根因在 detection |
| CWE-121/134 已被 AI 修复 | 确定性替身通过独立验证；live 未跑 |
| 多模型可复现 | 4 模型/2 provider 有真实矩阵；非 loop 仍 0/6 |
| CI nightly 通过 | 本地 frozen-tree gate 13/13；hosted CI 2 条 success |
| 0 残留 refs | 7 heads + 6 tags 已删；对象/PR/CI run 残留不可清零 |

---

# 9. 本次仓库整合与痕迹清理（已执行）

## 9.1 用户要求与执行原则

用户要求：把两会话完成的任务整合后推送到 GitHub **新分支**，删除它们在仓库中的原位置/信息存放痕迹，并告知仓库地址。执行原则：

1. **不重写历史**（会破坏 main/全部历史与 11 个 PR）；只删除会话产生的**可达 ref**；
2. **先备份后删除**（mirror + bundle + refs + 工作树补丁）；
3. **基线必须含 Phase-8D**（不能用 `c0f9feb`）；
4. **不把未提交/半回退的工作树状态混入交付分支**；
5. **诚实说明对象级残留**。

## 9.2 基线选择：`d37bfad` + 只增不删

| 候选 | 含 Phase-8D | 含 P31–P34 | 含 13/13 gate | 判定 |
|---|---|---|---|---|
| `c0f9feb` | 否 | 是 | 否 | 不可用（缺 Phase-8D：161 文件 / −76,859 行） |
| `d37bfad` | 是 | 是 | 否 | **基线**（被 CI 验证） |
| `a1d7150` | 是 | 是 | 是 | 不作基线：删除 33 个被 `baseline.json`/universe builder 依赖的历史 gate 文件（实测 `--check` exit 1） |
| `bdd3f84` | 是 | 否 | 部分 | 仅取 9 个独有路径 |

实际：`d37bfad` + `a1d7150` 的 final gate 目录/文档 + `bdd3f84` 的 8D gate 目录/文档；**保留**全部 7 个历史 `release-gate-*`。验证 `scripts/build_phase8d_capability_universe.py --check` → `phase8d: check OK`。

## 9.3 新分支内容

- 基线：`d37bfad`（2,359 tracked files；2411 tests；Phase-8D + P31–P34 + M1–M4）。
- 新增：18 个 Phase-8D 证据路径 + 9 份整合文档 + CI 触发重定向 + 根 `CONSOLIDATION.md`。
- 文档目录：`delivery/zh/consolidation/2026-11-17/`
  - `PROJECT-MASTER-REPORT-2026-11-17.md`（本文）
  - `session-1-linux-vm-analysis-2026-11-17.md`
  - `session-2-all-types-analysis-2026-11-17.md`
  - `sessions-inventory-and-delta-2026-11-17.md`
  - `repo-verification-2026-11-17.md`
  - `open-items-and-solutions-2026-11-17.md`
  - `git-delivery-plan-2026-11-17.md`
  - `CONSOLIDATION-2026-11-17.md`（执行记录）
  - `refs-manifest-2026-11-17.txt`（删除前 refs）
- 首批提交：`9194b02`（`docs(consolidation): integrate session 879cc62f and b139b586 into final/consolidated-2026-11-17`）。

## 9.4 删除清单与结果

**heads（7 条，全部删除成功）**

| ref | SHA | 归属 |
|---|---|---|
| `workbench-v3` | `d37bfad` | 会话一/二共同推进 |
| `feature/ai-binary-repair` | `d37bfad` | 会话一 |
| `phase8d-open-world` | `996060d` | 会话二 |
| `release/2026-11-17-phase8d-final` | `d37bfad` | 会话二 |
| `release/2026-11-17-phase8d-final-evidence` | `a1d7150` | 会话二 |
| `release/2026-11-17-phase8d-evidence` | `bdd3f84` | 会话二 |
| `final/consolidated-2026-11-16` | `c0f9feb` | 上轮整合 |

**tags（6 个，全部删除成功）**：`release-2026-11-17-phase8d`、`…-phase8d-evidence`、`…-phase8d-final`、`…-phase8d-final-evidence`、`phase8d-frozen-phase8c-release`、`phase8d-frozen-phase8c-evidence`。

**实测结果**：

| 指标 | 删除前 | 删除后 |
|---|---:|---:|
| 远端 heads | 97 | **91**（−7 +1 新分支） |
| 远端 tag 行 | 101（71 真实） | **89**（65 真实） |
| `git ls-remote` 总行（含 `refs/pull/*` 11 条 + HEAD 1 条） | 210 | **192** |
| 会话相关 ref 残留 | 7 heads + 6 tags | **0** |
| 默认分支 | `main`=`8869b07` | 不变 |
| 新分支 | — | `final/consolidated-2026-11-17`=`9194b02`（首批；tip 见 git log） |

## 9.5 备份（删除前完成，可恢复）

| 项 | 路径 | 校验 |
|---|---|---|
| 远端 mirror | `backup/2026-11-17/binary-repair-mirror-2026-11-17.git`（129 MB） | 167 refs（清理后刷新）；`a1d7150`/`c0f9feb` 可检出 |
| 本地全 refs bundle | `backup/2026-11-17/local-refs-2026-11-17.bundle`（128 MB） | `git bundle verify` → complete history |
| 删除前 refs | `backup/2026-11-17/remote-refs-2026-11-17.txt` | 198 行 |
| GUI 工作树现场 | `backup/2026-11-17/gui-worktree-*.patch` / `-status.txt` / `-untracked.tgz` | 622KB dirty patch；6 个 untracked |
| 本地保护 refs | `backup/final-consolidated-2026-11-16`、`backup/p31-p34-feature-a0e6a24`、`backup/phase8d-evidence-bdd3f84`、`backup/phase8d-final-evidence-a1d7150` | 防 GC |
| SHA256 | `backup/2026-11-17/SHA256SUMS-2026-11-17` | 7 个文件 |

## 9.6 诚实边界（不可宣称"0 残留"）

- 删 ref ≠ 删对象：`c0f9feb`/`d37bfad`/`a1d7150` 等 commit 仍可按 SHA 访问，直到 GitHub GC。
- 11 个已关闭 PR 的 `refs/pull/*`、170 条 Actions run 仍保留分支名/提交引用。
- 默认分支仍是 `main`（`8869b07`，11-12）；无 admin token，未切换。
- 本分支是**交付整合**，不是重新 gate 的 release；被 gate 的 SHA 仍是 `d37bfad`（13/13、CI success）。
- 仓库是 **public**；凭据轮换（K1–K4）仍未执行，优先级高于痕迹清理。
- 旧 11-16 整合文档仍在 `delivery/zh/consolidation/`（历史），其中"0 残留"表述已被本轮取代。

## 9.7 仓库地址

- **仓库**：<https://github.com/chenfanaichifan/binary-repair>
- **SSH**：`git@github.com:chenfanaichifan/binary-repair.git`
- **新分支**：`final/consolidated-2026-11-17`（tip 以 `git log -1` 为准；首批提交 `9194b02`）
- **默认分支**：`main`（`8869b07`）
- **克隆/切换**：

```bash
git clone git@github.com:chenfanaichifan/binary-repair.git
cd binary-repair
git checkout final/consolidated-2026-11-17
```

- **仓库内总报告**：`delivery/zh/consolidation/2026-11-17/PROJECT-MASTER-REPORT-2026-11-17.md`
- **执行记录**：`delivery/zh/consolidation/2026-11-17/CONSOLIDATION-2026-11-17.md`

---

# 10. 对外口径：可以/不可以声称什么

## 10.1 可以声称（都有 S1 证据）

1. 项目交付了一条**有界、可审计**的二进制修复流水线：ELF x86-64 为主，覆盖 8 cell 确定性矩阵、7 种 disposition、PoC/回归差分、独立验证器。
2. 公开修复集 **2/24 verified（8.33%）**，`false_verified=0`；1 个 deterministic claim 被独立验证器**主动撤回**（heap-malloc），而不是掩盖。
3. Phase-7/8A/8B/8C/8D 的基础设施与测量体系：297-unit 能力宇宙、Acceptance 2.0、8 条 gap registry、promotion gate 4/4 denied、13/13 frozen-tree gate、2411 tests。
4. 两个重点会话的成果已在 `final/consolidated-2026-11-17` 合流（基线 `d37bfad`，含 Phase-8D + P31–P34 + M1–M4）。
5. 远端 7 个会话 heads + 6 个 tags 已删除；备份可恢复；仓库地址与分支已知。

## 10.2 不可以声称

1. "通用二进制修复 / 任意漏洞 100%"；
2. "hidden 泛化成立"（0/6，卡在 detection）；
3. "CWE-121/134 已被 AI 修复"（只有确定性替身，无 live 模型）；
4. "P31–P40 完成"（只完成 P31–P34 离线；P35–P40 未开始）；
5. "Phase-8D 提升了修复能力"（0 generalized / 0 promoted）；
6. "CI nightly 通过"（self-hosted nightly 仍 not_run；hosted CI 是另一层）；
7. "0 残留 refs / 痕迹彻底清除"（对象、PR、Actions run 不可清零）；
8. "GUI 当前工作树 = P31 完整特性"（41 项脏改动、gateway 半回退）。

---

# 11. 附录

## 附录 A：41 个顶层会话总表（含 8 归档）

见 §3.2 的 19 个有效会话 + 22 个空会话（`42f57a46`、`1edb1a82`、`2f54838b`、`f48df004`、`ff9c020b`、`a1cdccb9`、`b67c86c7`、`ba1995bd`、`3327ffaa`、`3d349441`、`474688b9`、`729f766f`、`aff70696`、`caf358f3`、`a50c362f`、`ad717231`、`c20f3715`、`1309dc6c`、`892c4d59`、`5bdf6473`、`8152265e`、`0dd3685e`）。完整 41 项 sessionIds 与档案状态以 `~/.dsh/storages/workspace.json` 为准；归档 8 个已在 §3.1 列出。

## 附录 B：关键 commit / CI / tag 索引

| 对象 | SHA / ID | 用途 |
|---|---|---|
| v7 handoff | `3d5d0f0`（v6.1）/ `e1756a2`（v7 CI） | 950/943/7 |
| v5 任意二进制 | `72db891` | 8 cell 确定性矩阵 |
| 两条 AI 路径 | `aa45b36` | `asm_roundtrip`/`binary_direct` |
| 3/3 非 loop 转折 | `a8934fe` | 严格验证起点 |
| P16-R3 | `f42e6c4` | 7/10 verified |
| P21–P24 | `a1755a5` | 冻结 profile/runner |
| Phase-7 | `2bfa112` | 13/13 |
| Phase-8A | `bd9cbf6` | 13/13；0/10/2 |
| Phase-8B | `227f45b` | 2 verified；1 claim 撤回 |
| Phase-8C | `4a7b235` | 2/24；hidden 0/6 |
| Phase-8D 集成 | `996060d` | tag `release-2026-11-17-phase8d` |
| 8D 最终树 | `d37bfad` | 13/13 gate；2411 tests；CI 43907137267/43907136876 |
| 8D final evidence | `a1d7150` | final gate 证据 |
| 上一轮 final | `c0f9feb` | 仅 P31–P34（已删） |
| 本轮新分支 | `9194b02`（首批） | `final/consolidated-2026-11-17` |

## 附录 C：证据文件索引

| 主题 | 路径 |
|---|---|
| 能力声明 | `docs/status/claims.json` |
| 13/13 gate | `artifacts/release-gate-2026-11-17-phase8d-final/phase8d-final-gate/gate.json` |
| 8D universe | `artifacts/phase8d-capability-universe-2026-11-17/registry.json` |
| 8D gaps | `artifacts/phase8d-gap-registry-2026-11-17/gaps.json` |
| hidden 归因 | `artifacts/phase8d-hidden-attribution-2026-11-17/aggregate.json` |
| Acceptance 2.0 | `artifacts/phase8d-acceptance-2-2026-11-17/report.json` |
| 2411 tests | `artifacts/binary-universal-v5-2026-11-13/macos-junit.xml` |
| marcx | `artifacts/marcx-repair-2026-11-14/README.md` |
| 36-run 稳定性 | `artifacts/stability-2026-11-16/README.md` |
| P31–P34 | `docs/acceptance/p31-p34-2026-11-16.md` |
| 安全轮换 | `docs/operations/security-key-rotation-2026-11-17.md` |
| 备份 | `docs/operations/backup-2026-11-17.md` |
| 本轮 6 份子报告 | `delivery/zh/consolidation/2026-11-17/` |

## 附录 D：术语表

| 术语 | 含义 |
|---|---|
| Route A | 调用重定向到 code cave 的确定性修复路线 |
| Route B | 恢复 C 源码、打补丁、重编译的路线 |
| 范式 A | 反编译 C → LLM 补丁 → 二进制感知重编译（区别于 `asm_roundtrip` 的 B 家族） |
| `asm_roundtrip` | ELF→汇编→修复→装回的 AI 路径 |
| `binary_direct` | ELF→不转汇编→二进制层直接改的 AI 路径 |
| RepairSpec / patch plan | 可独立重放的字节级修复计划 |
| 独立验证器 | 从原始字节重放 plan、逐字节等于 candidate 的 verifier |
| disposition | `verified_patch`/`static_only_patch`/`analysis_only`/`unsupported`/`rejected`/`invalid` |
| frozen-tree gate | 在干净冻结树上跑的 13 项发布门禁 |
| not_run | 未运行；**不等于 pass** |
| capability universe | 297 个能力单元的注册表（20 维 + 240 cell + 32 public + 2 hidden + 3 prototype） |
| Acceptance 2.0 | L0–L7 八层验收 + 变异战役 |
| promotion gate | 能力晋级门；4/4 denied |

---

> **文档结束**。本文与仓库内 `delivery/zh/consolidation/2026-11-17/PROJECT-MASTER-REPORT-2026-11-17.md` 同步；执行记录见同目录 `CONSOLIDATION-2026-11-17.md`，refs 删除前快照见 `refs-manifest-2026-11-17.txt`。
