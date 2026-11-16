# AI 驱动的二进制漏洞自动修复与正确性验证
## 项目总体计划 · 完成现状 · 剩余任务与解决方案（全量汇总）

> 汇总日期：2026-11-16（Asia/Singapore）
> 汇总范围：本工作区 `AI驱动的二进制漏洞自动修复与正确性验证` 的**全部会话**（38 个会话，其中 7 个已归档；另含重点会话派生的 teammate/子会话），以及与之对应的 GitHub 仓库、远端 refs、发布标签、CI 记录与本地交付物。
> 重点会话：**「Linux 虚拟机验证漏洞修复-1」**（session-879cc62f，2026-11-13 16:15 → 2026-11-16，19,358 个事件）与**「全类型二进制修复-1」**（session-b139b586，2026-11-14 15:12 → 2026-11-16，16,662 个事件）。
> 数据可信度：本文所有数字/结论均来自两种以上独立证据源（会话事件回放、仓库文件、git 历史、GitHub API/CI 记录、会话最终报告）。凡属会话中"声称但未在仓库/远端核实"的内容，均标注"未核实"。

---

# 目录

1. 项目总体目标与最终定义
2. 从头到尾的完整执行计划与阶段划分
3. 重点会话一：Linux 虚拟机验证漏洞修复-1
4. 重点会话二：全类型二进制修复-1
5. 当前完成现状（以最终 mainline 为权威）
6. 尚未完成的任务与全部问题清单
7. 对应解决方案与执行路线
8. 本次仓库整合与交付（新分支 / 痕迹清理 / 仓库地址）
9. 附录：会话清单、关键 commit/CI 索引、证据文件索引、术语表

---

# 1. 项目总体目标与最终定义

## 1.1 项目是什么

**BinaryRepair** 是一个"AI 驱动的二进制漏洞自动修复与正确性验证"系统/研究项目：

- **输入**：一个存在已知漏洞的二进制程序（ELF / PE / Mach-O，主要 Linux x86-64），以及可选的 PoC / 回归用例清单（manifest）；
- **处理**：自动分析二进制结构与漏洞根因 → 生成修复计划（RepairSpec / patch plan）→ 生成候选补丁（确定性模板 或 AI 生成）→ 直接改写二进制字节/注入代码洞 → 重新解析并执行；
- **输出**：一个带"处置结论（disposition）"的结果：`verified_patch` / `static_only_patch`（显式 opt-in，不验证）/ `analysis_only` / `unsupported` / `rejected` / `invalid`，以及完整证据包（report、gate checks、SHA256、冻结 manifest、可下载候选）；
- **核心原则**：**AI 只产生候选，验收权永远属于确定性 gate**；模型解释不是证据；不可用就标 `not_run`，绝不把 `not_run` 当成 `pass`；不降 gate 换绿灯。

## 1.2 目标的三次演进（从 MVP 到 Autonomous Binary Repair Intelligence）

| 阶段 | 目标定义 | 时间 | 状态 |
|---|---|---|---|
| ① 课程 MVP | 交给老师/小组的"可演示、可审计"二进制修复工作台：Route A（调用重定向到代码洞）+ Route B（恢复 C 重编译）+ V0–V5 验收 + 证据链 | 2026-10-15 → 2026-11-11 | **已完成**（v1.2.1 公开稳定版） |
| ② 任意二进制修复（v4/v5/v6/v7） | 从"单个 fixture"扩展到 ELF/PE/Mach-O、x86-64/arm64/i386 的确定性矩阵；任意文件 triage + 明确 disposition；Linux VM 权威验收交付件 | 2026-11-12 → 2026-11-13 | **已完成并交付 v7**（950/943/7/0） |
| ③ AI 修复研究系统（P0–P24） | 两条 AI 直接二进制修复路径（asm_roundtrip / binary_direct）；真实 provider、真实失败反馈、跨二进制 benchmark、独立验证器、36 次稳定性实验 | 2026-11-13 → 2026-11-16 | **部分完成**（P16-R3 7/10 严格验证，CWE-121/134 负结果） |
| ④ 自主能力体系（第 6–8C 阶段） | 覆盖矩阵/缺口自发现、验收模型审计、发布治理、Autonomy Foundation、Ground Truth v2、Hidden Benchmark、独立验证语义闭合 | 2026-11-14 → 2026-11-16 | **基础设施完成**（Phase-8C 已发布，但**未新增修复能力**） |
| ⑤ 最终目标 | **Autonomous Binary Repair Intelligence**：持续发现能力缺口/验收错配 → 反思根因 → 设计并执行实验 → 独立验证 → 只在严格证据下晋级能力 | 规划中（Phase-8D–16） | **未开始/规划中** |

## 1.3 最终目标的正式定义（会话中已达成共识的版本）

> 构建一个能够在**明确声明支持范围**内自主发现二进制漏洞、分析根因、规划并执行修复、独立验证修复结果，并**持续发现未知能力缺口与验收模型错配**，通过可复现实验不断扩展"已验证能力"的 **Autonomous Binary Repair Intelligence**。

最终成功标准（12 条，摘自用户/组长在会话中确认的路线图）：

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

## 1.4 明确的非目标与不可证明边界

以下内容在整个项目中被反复确认**不能声称**（任何文档/报告都必须保留这些限定）：

- **不声称"任意二进制/任意漏洞 100% 修复"**：绝对全覆盖不可证明（输入空间、漏洞组合、编译变体无限；程序语义等价一般不可判定）；明确使用"已知能力宇宙可穷尽审计 + 未知空间 `not_measurable`"的开放世界框架。
- **不声称 whole-program / 形式化安全保证**：V4 是 model-level；PoC/回归通过不等于程序无其他漏洞。
- **不声称 hidden benchmark 泛化能力**：Phase-8C hidden 8 样本 0 candidate、0 verified；`hidden_available=false`。
- **不把 `not_run`/`unavailable` 当 `pass`**：self-hosted Lima nightly、国际 provider 矩阵、external ingestion、GDB trace、AFL fuzzing 等未运行项均显式记录。
- **不把 AI 评审/模型解释当验收**：AI 只能 hold/要求更多检查，不能把失败 gate 提升为成功。
- **不把 fixture 绿灯当通用能力**：公开集 2/24 verified、hidden 0 verified、非 loop 家族 0/6 等负结果是项目结论的一部分。

---

# 2. 从头到尾的完整执行计划与阶段划分

## 2.1 总时间线（2026-10-15 → 2026-11-16）

| 日期 | 阶段 | 主要目标 | 关键产出/结果 | 状态 |
|---|---|---|---|---|
| 10-15 | 项目启动 | 下载/研究 REA 方法（5 步），完成"研究想法 + MVP 定义"（前两步） | 研究想法、MVP 定义、项目大纲/介绍材料 | 完成 |
| 10-18 → 11-06 | M1–M5 攻关 | 5 人小组分工：M1 控制器/类型化 V4 证据、M2 GUI、M3 Route A/V4 producer、M4 独立验证、M5 schema/DB/交付；T8.3（CWE-416 no-input 契约） | 118 VERIFIED、124 inconclusive、V4 model-level、T8.3 契约冻结、证据链体系 | 完成（含遗留） |
| 11-06 → 11-11 | v1.2.0/1.2.1 发布 | 公开稳定版、WeChat 分享包、DeepWorks 迁移准备 | 889/1/0（Ubuntu CI）、v1.2.1 tag、docs/handoffs 1.2.1 系列 | 完成 |
| 11-11 → 11-12 | 工程收尾 | 计划服务排查、CGC POV 移植、VM 任务包、CI 修复、v3 评审 | CGC 5 对 ELF + 7 POV、v3 评审通过、CI 历史纠正 | 完成 |
| 11-12 → 11-13 | v4/v5/v6/v7 交付 | 任意二进制矩阵（ELF/PE/Mach-O + i386）、Linux VM 交付包 | v6→v7 重打包、Linux VM 950/943/7/0、P0=0 | **完成（重点会话一前段）** |
| 11-13 → 11-16 | 会话一（Linux VM → 通用修复 → AI 研究） | v7 检验后继续：修复任意二进制 v5、两条 AI 直接二进制路径、P0–P24 研究执行 | P16-R3 7/10 严格验证、36 次稳定性 19/36、CWE-121/134 负结果 | **部分完成（重点会话一）** |
| 11-14 → 11-16 | 会话二（全类型二进制修复） | marcx 失败根因 → 66/68 项能力缺口审计 → 发布治理 → 第 7 阶段 Autonomy Foundation → Phase-8A/8B/8C | 0 open 缺口、Release gate 13/13、Ground Truth v2（32 public / 8 hidden）、真实 2 独立验证 | **基础设施完成（重点会话二）** |
| 规划中 | Phase-8D–16 | 开放世界发现、跨函数语义、整数/字符串/UAF 修复、验证 2.0、自主规划/实验/晋级、Release 2.0 | 见第 7 节路线图 | **未开始** |

## 2.2 两条主线的分工与合流

项目的实际执行是**两条并行主线**，最终在 `workbench-v3` 合流：

- **修复能力主线**：确定性矩阵（v4/v5）→ 两条 AI 路径 → RepairSpec/ABI/native feedback → P10–P24 研究执行；
- **验证/治理主线**：V0–V5 验收 → 独立验证器 → 能力缺口自发现 → 验收模型审计 → 发布门禁/证据链 → Autonomy Foundation → Ground Truth/Hidden Benchmark。

两条主线共享一个铁律：**能力声明必须由测量生成；没有独立证据的能力不晋级**。

## 2.3 代码与分支演进（主要 ref）

| Ref / Tag | 含义 | 最终 SHA |
|---|---|---|
| `main` | 旧默认分支（11-12 后未再前进） | 8869b07 |
| `workbench-v3` | **最终 mainline**（两会话全部成果合流点） | **4a7b235** |
| `feature/universal-repair` | v5 任意二进制矩阵（会话一） | 72db891 |
| `feature/ai-binary-repair` | 两条 AI 路径 + P21–P24（会话一） | a1755a5 |
| `feature/phase8b-verifier-semantics` | Phase-8B 独立验证语义（会话二） | 227f45b |
| `feature/phase8c-ground-truth-v2` | Phase-8C Ground Truth v2（会话二） | ceb2061 |
| `release/2026-11-16-phase8c-final` | Phase-8C 发布分支 | 4a7b235 |
| `release/2026-11-16-phase8c-evidence` | Phase-8C 证据分支（post-tag addendum） | ec503e4 |
| tag `release-2026-11-16-phase8c` | Phase-8C 发布 tag | 4a7b235 |
| tag `release-2026-11-14/15/16` 系列 | 更早的发布/证据 tag（会话二各阶段） | 见附录 |

> 说明：远端现有 113 个分支 + 117 个标签，共 242 个 refs（其中大量属于 M1–M5 早期和两个重点会话的中间态）。本次整合将把两个重点会话的成果收敛到一个新分支，并清理其原有 refs（见第 8 节）。

---


# 3. 重点会话一：Linux 虚拟机验证漏洞修复-1

- 会话 ID：`session-879cc62f-ff8b-476f-b06b-9e5f24ef1a28`
- 时间：2026-11-13 16:15 → 2026-11-15 23:39（35 个 turn；11-16 08:05–08:06 仅有 session/end-seed 与标题事件）
- 规模：19,358 个事件；35 个 turn；33 条真人指令；2500 次工具调用；35 份正式阶段报告；6 个 teammate（12 个 teammate 会话文件：evidence-auditor、claims-auditor、i386 引擎/运行时、产品前端、AI 路径二校验器等）；10 个共享任务全部 completed
- 工作方式：Team Lead + 子 agent/teammate 并行；每阶段以"执行报告 + commit + CI + 证据目录"收尾

## 3.1 会话目标与真人指令时间线

| # | 用户指令（摘要） | 对应的执行阶段 |
|---|---|---|
| 1 | 需要 Linux 虚拟机最后检验（附《方法建议》文档） | A. v6 交付件检验 → v7 重打包与权威复跑 |
| 2 | 请一次性实现"修复任意二进制文件"这一功能 | B. v5 任意二进制矩阵（ELF/PE/Mach-O + i386） |
| 3 | 询问"任意二进制修复"是否完成；未完成则继续，直到成功；按最推荐计划执行并推送 | B 的补齐（动态 ELF32/PE32 FF15/memcpy immediate/extend-rx/fat Mach-O） |
| 4 | 完成"直接在二进制层面修复、不转汇编再反编译"的功能，形成两条 AI 路径 | C. 两条 AI 直接二进制修复路径 |
| 5-8 | 反复核对两条路径的定义（第一条汇编往返、第二条纯二进制）并纠正实现 | C 的返工与澄清（asm_roundtrip / binary_direct） |
| 9 | 按组长建议继续：PoC 差分进 gate、gate 盲区、真实 provider、范式 A 不混入 | D. Path A / 范式 A / 4 模型矩阵 / CWE121 |
| 10-12 | Ghidra/JDK 安装、API key、继续跑通 | D 的工具链与环境 |
| 13-20 | 按组长问题清单逐轮执行（P0–P4、3/3 非 loop、P5–P9、P10–P15、P16–P20） | E–H. AI 研究阶段 |
| 21-26 | P16-R、P18 稳定性、N3–N6、fuzzing、60 次实验等 | I–K. 验证链收敛 |
| 27-33 | 继续按 P21–P24/P25–P30 优先级推进；核对报告 | L. 冻结基线、artifact 审计、稳定性 runner、统计工具 |

## 3.2 阶段 A：Linux VM 最终检验（v6 → v7 交付件）

### 3.2.1 目标与方法

对 `handoff/BinaryRepair-Linux-Handoff-2026-11-13-v6` 交付包做**独立、可复现的 Linux VM 权威验收**，并修复打包级问题后重打 **v7** 作为唯一可发送交付件。

检验链路（双源独立）：

1. **宿主完整性预检**：重算 zip SHA256、`unzip -t`、全新解压、`verify-package.sh`、29 个嵌套 `SHA256SUMS`、MANIFEST 计数/时间戳、用户名/本机路径/密钥扫描；
2. **Linux VM 端到端**：Ubuntu 24.04.5 LTS arm64（Lima 2.3.0，4 vCPU/5.8 GiB，QEMU 8.2.2，clang 18.1.3，GNU readelf 2.42）→ 全新解压 → `setup-linux.sh` → `run-baseline.sh -rs` → `run-smoke.sh --allow-native` → 独立运行时抽查（L2 native ELF / L3 CGC replay ×3 / 负向对照）→ 环境记录；
3. **证据链核对**：GitHub API 核对 CI run/head_sha/conclusion/check-run annotations；解析 junit/pytest 日志；逐项核对 7 个 skip；MANIFEST/嵌套清单交叉验证；
4. **方法建议符合性**：按《方法建议》§4（验证闭环/证据链）与 §9（macOS/Linux 环境分层）逐条对照。

### 3.2.2 最终结果（v7，PASS 可交付）

| 检查项 | 结果 |
|---|---|
| 交付件 | `handoff/BinaryRepair-Linux-Handoff-2026-11-13-v7.zip` |
| SHA-256 | `2afeb6c8c0908acfcf0fb83328d75a2c5254dc7656f2ef43105cf3f89a42fcc8`（60,488,092 字节，双源一致） |
| `unzip -t` | 通过（2,228 文件条目，解压 157 MB） |
| 包内顶层 `SHA256SUMS` | **2,227/2,227 OK**，0 失败 |
| 29 个嵌套 `SHA256SUMS` | **29/29 通过**（v6 为 26/29） |
| `verify-package.sh` | PASS（checksums + secret hygiene） |
| MANIFEST 计数 | files=2,226 / bytes=157,757,081 / by_top_level 六项与实际一致 |
| VERSION/MANIFEST 时间戳 | created_at=2026-11-13T16:58:23+08:00，早于 zip mtime 16:58:31，一致 |
| 禁止项扫描 | 0 命中（`__pycache__/.venv/.git/.DS_Store/.env/var 密钥/浏览器 profile`） |
| 文本用户名/本机路径 | 0 命中（v6 有 2 个文件泄露） |
| Linux VM 全量 pytest | **950 collected / 943 passed / 7 skipped / 0 failed**（69.861 s，hostname=lima-binaryrepair，timestamp=2026-11-13T17:00:01+08:00） |
| `run-smoke.sh --allow-native` | **PASS**（ELF scan/repair、LIEF PE/Mach-O、guest runner、corpus manifests、CGC replay；native ELF 段按设计 skip） |
| macOS junit | 950/946/4/0（4 skip 均为平台门控） |
| CI 证据链 | run `43390831537` = `e1756a2` / `workbench-v3` / **success**（GitHub API + check-run annotations 双源核对，annotations 为 943/7/0/950）；上游绿色 run `43256887551` = 889/1/0/890 |

Linux 的 7 个 skip 逐项核对为：1 个可选 `BINARYREPAIR_CANDIDATE_ELF` 测试、4 个 `test_repair_macho_native.py`（Linux 无 Mach-O 原生运行）、2 个 `test_binary_pipeline_v4.py` 的 Mach-O 正向用例 —— 均为平台真实限制，**未发现"跳过以掩盖失败"**。

L3 CGC POV replay（exploratory，不作 gate）：

- `Palindrome` vulnerable 3/3 `cb_signal=11`、patched 3/3 `cb_exit=0` → **canonical 证据**；
- `basic_messaging` vulnerable 在脚本化验收中 0/9（v6 3/3 未触发、v7-rc/v7-final 9/9 未触发），但独立 shell 复跑 20+ 次均触发 → 判定为 qemu-user 运行时随机性，**降级 exploratory-only，不作 gate**；
- `*_patched` 是上游 `-DPATCHED*` 源码构建，不是本引擎修复产物，该 replay 不是 V0–V5。

### 3.2.3 v6 发现的问题与 v7 处置

| ID | 级别 | v6 问题 | v7 处置 | 复验 |
|---|---|---|---|---|
| P1-1 | P1 | VERSION/MANIFEST 的 created_at 晚于 zip 封包且互相矛盾 | 统一取真实构建时间 | ✅ |
| P1-2 | P1 | 3 个嵌套 SHA256SUMS 与证据失配（v4-macos 1/4、artifacts-v4 26/28、artifacts-old 10/12） | 按实际字节重算，29/29 | ✅ |
| P1-3 | P1 | 2 个历史日志泄露真实用户名/私有临时路径 | 脱敏为 `<user>`/`<tmp>` | ✅ 0 命中 |
| P1-4 | P1 | `handoff/` 根目录有 2 个解压副本 + `.DS_Store` | v6 归档 `-superseded`；删除副本 | ✅ |
| P1-5 | P1 | `patches/git-info.txt` parent 写错；README commit subject 张冠李戴 | 修正 | ✅ |
| P1-6 | P1 | v6 Linux 计数依赖未记录的 `umask 022`（默认 002 时 5 失败） | 顶层脚本归一化 `umask 022` + 手册说明 | ✅ 943/7/0 |
| P1-7 | P1（审计新增） | CGC patched 来源未说明；basic_messaging 被当稳定证据 | 显式披露 + 降级 exploratory | ✅ |
| P1-8 | P1（审计新增） | legacy ELF x86-64 验证失败仍可能返回候选（fail-open，未覆盖） | 冻结源码不改；`HANDOFF-TASKS F1` 记录复现/影响/修复要求 | 待修 |
| P0 | — | 两轮独立审计（evidence-auditor、claims-auditor）判定 **P0=0** | — | — |

最终报告：`handoff/final-verification-2026-11-13/FINAL-LINUX-VERIFICATION.md`（248 行），配套 `audit-evidence.md`（437 行）、`audit-claims.md`（525 行）、`evidence/` 原始日志与脚本。

### 3.2.4 与《方法建议》的符合性（当时的诚实差距）

| 方法建议条目 | 当时现状 | 评价 |
|---|---|---|
| §4.4 证据链完整性（CI run + conclusion 机器校验） | CI API + annotations 双源 | ✅ 符合 |
| §4.1 把"测试通过"升级为"PoC 失效" | gate success 判据当时尚未内建 PoC 失效 | ⚠️ 后续在 v5/AI 阶段补齐（PoC/回归差分成为 gate 必需谓词） |
| §4.2 验证分层（6 层） | 第 1–3 层已验证；第 4–6 层（模糊/符号/安全扫描）未接入 | ⚠️ 部分 |
| §9.1 macOS 开发 + Linux 动态权威 | 在 linux/arm64 VM + qemu-x86_64 完成权威复跑 | ✅ 符合 |
| §9.3 readelf 后端 | 仍依赖 Linux GNU readelf，未替换 LIEF/llvm-readelf | ⚠️ 遗留 |

## 3.3 阶段 B：「修复任意二进制文件」v5（确定性矩阵）

### 3.3.1 交付内容

- 统一入口：`/binary` 页面、`/api/binary/{scan,repair,matrix}`、`scripts/repair_binary.py` 共用 `repair_any`；report 升级为 schema v4；
- 确定性处置：`verified_patch` / `static_only_patch`（显式 opt-in、`verified=false`、绝不算 success）/ `not_verified` / `analysis_only` / `unsupported` / `rejected` / `invalid`；矩阵由 `app/services/repair_matrix.py` 单一事实源定义；
- 新增 **32 位 x86（i386）**：ELF32/PE32 analyzer（cdecl push 参数、容量=帧顶−目标）、`cdecl_x86` guard 机器码、ELF32 `PT_LOAD` / PE32 `.brfix` 注入、`E8`/`FF15` 调用解析、Unicorn x86-32 运行时证据（`emulated_run` / `unicorn-i386`）；
- 消除历史 fail-open：ELF x86-64 gate 失败不再保留可下载候选；`repair_binary(verify=False)` 明确返回 `not_verified`/`static_only_patch`；
- 产品面：中文 `/binary` 页面（拖拽→扫描→修复→处置徽章→仅在 `delivery.download_allowed` 时下载）、侧栏入口、i18n en 覆盖、CLI batch 统计；
- 夹具与证据：新增 `elf-x86`/`pe-x86` 夹具及 PROVENANCE（8 fixtures），证据在 `artifacts/binary-universal-v5-2026-11-13`。

### 3.3.2 关键提交与验收

| 项 | 值 |
|---|---|
| 初始功能提交 | `915f362 feat(binary): universal repair entry with 32-bit x86 support`（68 files，+8531/−316） |
| 最终 commit | `72db891`（`feature/universal-repair` 与 `workbench-v3` 同一提交） |
| CI | `43412905037`（success）；前两次 `43411767923`、`43412399232` 均 success |
| macOS 全量 | 1039 tests / 0 failed / 0 errors / 4 skipped（162.8 s） |
| Linux VM 全量 | 1039 tests / 0 failed / 0 errors / 7 skipped（178.4 s） |
| 复跑注意 | Linux 需 `umask 022`，并清理 macOS 传输产生的 `._*` AppleDouble 文件（环境问题，非代码） |

### 3.3.3 补齐的 5 个能力缺口

1. **动态 ELF32**：`fixtures/elf/vuln-strcpy-x86-dyn.elf`（`de051d8a…b080c8`），glibc `x86-linux-gnu`、PT_INTERP + `.plt`，`strcpy` 经 PLT 解析 → guard → `verified_patch`；
2. **PE32 直接 IAT（FF15）**：`fixtures/pe/vuln-strcpy-x86-iat.exe`（`59351c0b…f3471a`），`call *__imp__strcpy`（`FF15 abs32`），writer 改为 `E8 rel32 + NOP` 后 verified；
3. **i386 memcpy immediate**：`fixtures/elf/vuln-memcpy-x86.elf`（`0bbe1c86…ab6410`），立即数 64→16 原地修复；新增长度感知 Unicorn 模型（按 ABI 读取 memcpy/memmove 长度），通过 gate 而非 static-only；
4. **ELF32 extend-rx fallback**：合成 phdr 表填满首屏的 ELF32 单测，验证 `method="extend-rx"`、R-X 扩展与 reparse；
5. **fat Mach-O / big-endian**：fat Mach-O 逐 slice 元数据（`slices[].supported`、`container_rewrite=false`）但整体 `analysis_only`；big-endian 合成 ELF `unsupported` 无候选。

另加安全策略：**v5 只修复一个函数/候选**（guard sink 或最早 call site 所在函数），其它函数 sink 只记 limitation，避免下发 runtime 从未执行过的额外 patch。

### 3.3.4 边界（当时明确声明）

确定性矩阵内修复（ELF/PE/Mach-O x86-64/arm64 + ELF32/PE32 i386）；arm32/riscv/mips/ppc、大端、heap/global、sprintf/UAF 等仍 fail-closed；fat Mach-O 只分析不回写；i386 static-libc `compiler_rt.*` 别名 memcpy fail-closed；Unicorn 是函数级指令模拟，不宣称原生内核运行；每候选只修一个函数。

## 3.4 阶段 C：两条 AI 直接二进制修复路径

> 关键澄清：用户最初定义的两条路径是——(1) 二进制 → 汇编文本 → AI 修复 → 汇编回机器码 → 注入 → 输出新二进制（`asm_roundtrip`）；(2) 二进制 → AI 直接输出机器码/同长字节补丁 → 校验 → 写回（`binary_direct`）。第一版实现的 `ai_plan`/`ai_bytes` 被用户判定为"B+AI"而非两条路径，随后**按定义重做为两条产品路径**。

| 代 | 最终 commit | 功能提交 | CI | 测试 |
|---|---|---|---|---|
| 第一代（ai_plan / ai_bytes，被用户判定不符合"两条路径"定义） | `6d525ca`（feature/ai-binary-repair 与 workbench-v3 同一提交） | `abeab27 feat(ai): two direct-binary repair paths with deterministic gate` | `43418615884` success；`43418024120` success | 1118 tests / 0 failed / 0 errors / 4 skipped（217.2 s）/ Linux 7 skipped（209.2 s） |
| 第二代（按用户定义重做：asm_roundtrip / binary_direct） | `aa45b36`（feature/ai-binary-repair 与 workbench-v3 同一提交） | `61287fd`（路径一）+ 路径二实现 | `43427654178` success；`43426508766`（61287fd）success | 1128 tests（macOS / Linux VM 均通过）；11 条脚本化正向 verified 记录（macOS；Linux 9 条，Mach-O native 跳过） |

> 第一代定义为：模型只输出 `{sink_index, strategy}`（ai_plan）或直接输出机器码/同长字节（ai_bytes），全程不经过汇编文本。用户 11-13 20:06 明确两条路径应为：(1) 二进制→汇编文本→AI 修复→汇编回机器码→注入（asm_roundtrip）；(2) 二进制→AI 直接输出机器码/同长字节补丁（binary_direct）。随后按定义重做为第二代，并通过 11 条脚本化证据（ELF i386/x86_64/arm64 × asm，PE x86-64/arm64、ELF i386/x86_64/arm64、ELF i386 memcpy、Mach-O x86-64/arm64 native gate）。

两条路径的安全要点：

- `ai_plan`：模型只收到有界分析元数据包（格式/架构/矩阵/sink/capacity），**不接收原始二进制字节**；只输出 `{sink_index, strategy}`，由确定性 writer 生成 guard 注入或 immediate 钳位；不能编造偏移/容量/机器码，不支持即 fail-closed；
- `ai_bytes`：guard sink 输出 `code_hex`，validator 用 Capstone 完整反汇编 + 指令白名单（拒绝 syscall/特权/间接跳转/块外分支）+ 注入/重定向范围校验；immediate sink 输出同长就地编辑，逐字节校验 `before_hex`、可执行段、长度/数量/重叠，且必须命中选定 sink 的 `length_offset`；
- 两条路径共享同一 `finish_candidate()` reparse/runtime/gate 尾部；**AI 永远不能把失败/不完整 gate 提升为成功**；新增 `buffer_match` runtime 证据，让"结构合法但语义为空"的注入 guard（如单条 `ret`）被确定性 gate 拒绝；
- 新增 `GET /api/binary/ai-paths`、`POST /api/binary/ai-repair`、CLI `--ai-path ai_plan|ai_bytes`、`/binary` 页面两张 AI 路径卡（仅 `delivery.download_allowed=true` 显示下载）。

证据：`artifacts/ai-direct-binary-2026-11-13`（PE x86-64、ELF arm64、ELF i386 三条夹具 × 两条路径 = 6 个 verified 候选，另有 no-op guard 被 gate 拒绝，SHA256SUMS 校验）。

边界：脚本化证据证明协议/validator/写回/gate 集成，**不代表真实 LLM 修复质量**；每候选只修一个 sink；Mach-O AI guard 注入只走结构路由，未进入脚本化正向证据矩阵。

## 3.5 阶段 D：Path A / 范式 A / 多模型 / 工具链

| 轮次 | 结果 | 证据 |
|---|---|---|
| P0 Path B 注入瓶颈 | 根因是模型输出 `ud2` 被 assembly validator 拒绝（不是符号/空间）；加 typed 归因 + 一次 validator feedback 重试；hard-multicall 从 `no_candidate` → `fail`（真实进展，仍失败） | `artifacts/path-b-injection-retry-2026-11-14` |
| P0b Route A 自动符号 | 新增 `available_symbols()`（.symtab/.dynsym + .plt/.plt.sec），GOT/PLT 重名时唯一可执行地址否则 ambiguous；CWE121 不传显式符号产物 SHA 与旧版一致 `463a9758…` | `artifacts/route-a-auto-symbols-2026-11-14` |
| P1 动态依赖白名单 | malloc/calloc/realloc/free 目标有 PLT 才允许，否则 blocked；fork/execve/system/popen/dlopen 绝对拒绝；CWE416 参考 UAF 通过 auto symbols + Patcherex2 + native PoC | `artifacts/dynamic-symbols-2026-11-14` |
| P2 errno 探针 | `runtime/errno_dumper.c` + LD_PRELOAD，捕获**进程退出前 TLS errno**（不是函数返回瞬间），仅 native dynamic ELF；CI 断言 `errno_probe=ld_preload`、精确数值；其它显式 `not_run` | `artifacts/errno-*` |
| P3 非 loop 泛化 | DeepSeek flash 三例：hard-multicall 注入成功但 native fail（模型语义）、hard-sprintf assembler 拒绝 `^`、hard-nonconst 注入成功但 native fail；**AI 非 loop 新增 verified = 0**；但 CWE416 参考修复 PASS 证明工具链可行 | `artifacts/generalization-2026-11-14`、`generalization-uaf-2026-11-14` |
| Path A 选择性调用白名单 | 12 case × 2 DeepSeek 模型：loop 仍 6/12 verified，non-loop 仍 0/6；heap 安全 PoC 过但 valid-input stdout 回归失败 | `artifacts/path-a-call-whitelist-2026-11-14` |
| 范式 A 最小闭环 | Ghidra C 反编译 → LLM → Patcherex2 → PoC 的 loop 闭环跑通；CWE121 `badSink` 函数级 A gate PASS（模型生成 guard + 人工审核 syscall glue） | `artifacts/paradigm-a-loop-2026-11-14`、`paradigm-a-cwe121-2026-11-14` |
| 4 模型真实矩阵 | DeepSeek 2 模型 exact identity 6/12 each；SiliconFlow CN 免费 Qwen3-8B/Qwen2.5-7B 0/12 each；GLM-Z1 身份探测超时；国际站 HTTP 402 余额不足 → 5–6 模型矩阵 not_satisfied | `artifacts/multi-model-matrix-cn-2026-11-14`、`multi-model-matrix-intl-2026-11-14` |
| 工具链 | JDK 25 + Ghidra 12.2 在 M2 Mac 安装并跑通；有效 DeepSeek key 跑通双模型实验 | `docs/reference/ghidra-macos.md` |
| 工程收尾 | errno 代理、Path B A/B、符号黑名单、边界文档全部落地，CI 绿灯；修复 feature 与 workbench-v3 分叉（合并到 `6cc51d3`/后续） | 会话报告 |

## 3.6 阶段 E–H：P0–P15 AI 修复研究

### 3.6.1 3/3 非 loop AI Verified（a8934fe）

- 修复三个真实工程缺陷后，DeepSeek flash 在 hard-multicall / hard-sprintf / hard-nonconst 三例达到 **AI VERIFIED**：
  - **Cave relocation 映射错误**：注入的 PT_LOAD cave VA 落在 `.tbss` 虚拟范围，旧代码按 section 映射把 `.tbss` file offset 当 cave offset，导致重定位写到非执行位置（真正 cave 里仍是 `e8 00 00 00 00`）；修复为 cave VA 始终优先按 PT_LOAD 映射再 fallback section；
  - **模型不写边界检查**：新增结构化 RepairSpec（required_invariant / repair_strategy / failure_behavior / permitted_calls）后才产生 guard；
  - **hard-sprintf 的 `^`**：模型输出绝对地址标签（`0x102cc32:`），新增 assembler preflight feedback retry 改为 `.Lfail`；
  - **ABI 检查器线性栈跟踪**：改为 CFG-aware worklist，两个等价 epilogue 不再误报 `rsp_not_restored`。
- 模型 A/B：同一管线 deepseek-flash **3/3**、deepseek-v4-pro **0/3**（ABI fatal、plan 为空、非法 call 0x0）→ 证明"工具链可承载正确修复"，但模型能力仍是变量。
- 全量测试 1641 通过；CI `a8934fe` = `43628367481`/`43628367473` success。

### 3.6.2 P5–P9（bd9cbf6）

| 阶段 | 内容 | 结果 |
|---|---|---|
| P5 Native Semantic Feedback Retry | 首轮 native gate 失败 → `NativeFeedback` 分类（candidate_crash / retryable）→ 反馈给 planner → 第二轮 replan + assembly → PASS；两轮证据都保留，重试上限 3，timeout 不自动重试 | **闭环完成** |
| P6 RepairSpec v2 | nested schema（vulnerability/program_context/security_invariants/repair/abi/verification）+ v1 兼容 + 严格校验 | 解析/校验完成，但成功实验仍以 v1 为主（不能声称 v2 已证明有效） |
| P7 跨二进制 benchmark | 4 个独立二进制 / 3 类 CWE（121/122/787），每个有 vuln.c/build.sh/build.json/original.elf/reference_fix.c/PoC/defect | DeepSeek flash **4/6 AI verified**，其中 cwe122-heap-copy（未见二进制）verified；CWE121 SECURITY_FAILED、CWE787 ASSEMBLY_REJECTED |
| P8 Model Qualification | 同 6 cases/同管线：deepseek-flash 2/6、deepseek-v4-pro 2/6，但**成功 case 不完全相同** | 建立 per-stage funnel 与模型 A/B 方法 |
| P9 Evidence | `repair_evidence.py` schema v2、candidate/input hash、manifest、funnel、SHA256SUMS、`check` 篡改检测 | **partial**：3 次重复稳定性实验未完成 |

### 3.6.3 P10–P15（dad21c9）

| 阶段 | 内容 | 结果 |
|---|---|---|
| P10 Assembly Diagnostic Feedback | `assembly_policy.py`（绝对分支/directive/forbidden token/调用白名单）+ `assembly_diagnostics.py`（行/列/token 结构化）+ `assembly_feedback.py`（最多 2 轮，不自动改写模型汇编） | CWE-787 从 `^` 失败 → 改本地标签 → **native VERIFIED** |
| P11 36 次独立稳定性实验 | 2 模型 × 6 case × 3 重复 = **36/36 真实运行** | **19/36 verified（52.8%）**：deepseek-flash 12/18、deepseek-v4-pro 7/18；cwe122 6/6、cwe787 6/6、hard-nonconst 3/6、hard-multicall 2/6、hard-sprintf 2/6、cwe121 0/6 |
| P12 RepairSpec v2 真实链路 | CWE-787 上完成 v2 plan → validation → assembly → ABI → injection → native PoC/regression → VERIFIED；plan/assembly/candidate SHA 与证据链接 | 一个真实 case 走通，未证明跨 case 稳定 |
| P13 Benchmark 扩展 | 8 个独立二进制 / 10 个 case / 7 类 CWE，新增 CWE125/190/476/134，dev/hidden split | cwe125/cwe190 dev VERIFIED；**hidden CWE-476 VERIFIED**（首次 hidden 未见二进制 verified）；CWE-134 PLAN_INVALID |
| P14 Native Trace | N1 exit/signal/stdout/stderr、N2 PoC/regression 行为差异 | N3–N6（寄存器/栈/内存/控制流）**not_run**（无 GDB），不伪造数据 |
| P15 验证与 fuzz 首轮 | 确定性 mutation 计划生成器（固定 seed/count/可复现输入）+ independent verifier 结构复用 | **partial**：无 AFL campaign、无符号执行、verifier 未接入全部 benchmark |

## 3.7 阶段 I–L：P16–P24（验证链收敛与冻结）

| 阶段 | 状态 | 核心结果 |
|---|---|---|
| P16 | PARTIAL | independent verifier 接入 benchmark：10 条候选记录 = 6 verified / 1 rejected / 3 not_run（未达 8/8 或 10/10；3 个 not_run 来自缺 artifact） |
| P17 | FAILED（负结果保留） | CWE-121：plan/assembly/injection 均成功但 native SECURITY_FAILED（candidate stdout 空、exit 0；PoC 期望 exit 1 + 精确 stderr）→ 定位为 **Behavior Contract 未满足**；CWE-134 仍 PLAN_INVALID |
| P18 | NOT COMPLETED | 60 次矩阵（2 模型 × 10 case × 3 重复）未执行；只有 P11 的 36 次历史数据 |
| P19 | PARTIAL / BLOCKED | N3–N6 未运行（Linux guest 有 strace、无 gdb） |
| P20 | PARTIAL | 无真实 AFL/AFL++ campaign、无覆盖率反馈、无 crash 去重 |
| P16-R | PARTIAL（更严） | 严格 plan-aware 路径 0 verified / 8 rejected / 2 not_run；暴露 `header_update` 缺 `authorization_ref`、cave ABI 推导错误、target scope+associated changes 未通过、部分候选缺 artifact |
| P16-R2 | PARTIAL | 真实 layout plan 进入 verifier，CWE-122 通过 layout-plan/action-replay/target-scope/runtime-oracle/independence 五项；**ABI 仍 fail**（`symbol_function@… no_ret / branch_target_unknown`）→ 0 verified |
| P16-R3 | **7 verified / 1 rejected / 2 artifact_missing** | 新增 `app/services/elf_mapping.py`（仅 PT_LOAD 映射，6 种状态：MAPPED_FILE_BACKED / MAPPED_MEMORY_ONLY / OUTSIDE_PT_LOAD / AMBIGUOUS_SEGMENT / INVALID_FILE_RANGE / INVALID_ALIGNMENT + p_align 校验）；cave ABI block 先 PT_LOAD 再 section fallback；`verify_repair_benchmark.py` 用真实 `build_patch_plan` 而非伪造。verified：hard-multicall、hard-sprintf、hard-nonconst、cwe122-heap-copy、cwe125-oob-read、cwe190-integer-overflow、cwe476-null-deref；rejected：cwe121-unchecked-strcpy；artifact missing：cwe787-index-write、cwe134-format-string。全量 2044 tests；CI `43723326346`/`43723326360` success |
| P21 | COMPLETE | 冻结 profile `p21-p16r3-658ff8c`（source 658ff8c、verifier P16R3_PLAN_AWARE、authorization STATIC_REFERENCE_ONLY、semantic_trace NOT_RUN、fuzzing NOT_RUN、tests 2044；当前 2048） |
| P22 | COMPLETE | 10 个 case artifact 审计：8 RECOVERED_HISTORICAL + 2 ARTIFACT_MISSING_CONFIRMED（cwe787、cwe134），不用新候选替换历史 artifact |
| P23 | PARTIAL（runner+smoke） | `run_stability_matrix.py` 改用独立 verifier，区分 verified/PLAN_INVALID/NO_CANDIDATE/ARTIFACT_MISSING/NOT_RUN；单次 smoke 成功（hard-multicall → PLAN_INVALID）；完整 60 次在首个 case 后因 live provider 延迟过高被停止，partial 记录明确"这不是 60-run 结果" |
| P24 | PARTIAL（工具完成） | `summarize_stability.py` 能区分 ARTIFACT_MISSING 与模型失败、计算 R_verified/R_robustness、按模型/case 聚合；无完整矩阵报告 |
| P25–P30 | NOT IMPLEMENTED | 完整 CaveABIBlock 出口语义（tail_jump/continuation_jump/noreturn）、policy-issued Authorization Record、CWE-121 Behavior Contract、CWE-134 字段级诊断、GDB N3–N6、AFL++ campaign 均未实现 |

最终基线：`feature/ai-binary-repair = workbench-v3 = a1755a5`，全量 **2048 tests / 0 failed / 0 errors / 9 skipped**，CI `43729513475`/`43729513476` success。

## 3.8 会话一完成项总清单

**已完成（有证据）**

1. v6 交付件完整审计（P0=0，P1=8）与 v7 重打包；Linux VM 权威 950/943/7/0、29/29 嵌套清单、2227/2227 SHA、CI 证据链双源核对；
2. v5 任意二进制矩阵（ELF/PE/Mach-O + i386）与 5 个能力缺口（动态 ELF32、PE32 FF15、i386 memcpy immediate、ELF32 extend-rx、fat Mach-O/big-endian）；
3. 两条 AI 直接二进制修复路径（asm_roundtrip / binary_direct）与确定性 gate 集成、产品 API/CLI/UI、6 组脚本化 verified 证据；
4. Path A 选择性调用白名单、范式 A 最小闭环、CWE121 非 loop 函数级闭环、Ghidra/JDK 工具链、真实 4 模型矩阵；
5. 3/3 非 loop AI Verified（a8934fe）、RepairSpec/ABI 模块、cave relocation PT_LOAD 修复；
6. P5 Native Feedback 闭环、P6 RepairSpec v2、P7 跨二进制 benchmark 4/6、P8 模型 qualification、P9 evidence v2（partial）；
7. P10 assembly diagnostics → CWE-787 verified、P11 36 次稳定性 19/36、P12 RepairSpec v2 真实链路、P13 hidden CWE-476 verified、P14 N1/N2、P15 mutation plan；
8. P16-R3 严格验证 7/10 verified（PT_LOAD ABI 修复后）、P21 冻结 profile、P22 artifact 审计、P23 独立验证稳定性 runner（smoke）、P24 统计工具；
9. 全量 2048 tests、9 skipped、0 failed；CI 双 workflow success；工作区干净（仅 .venv 未跟踪）。

**未完成（会话一结束时）**

1. P16 未达 10/10；2 个 artifact missing（cwe787、cwe134 历史候选）；
2. P17 CWE-121 Behavior Contract 未满足、CWE-134 PLAN_INVALID；
3. P18/P23 60 次稳定性矩阵未完成；
4. P19 N3–N6 缺 GDB 未运行；
5. P20 无真实 fuzzing campaign；
6. P25–P30 全部未实现（CaveABIBlock 完整出口语义、Authorization Record、CWE-121/134、GDB、AFL）；
7. 非 loop AI verified 仍为 0/6（Path A 未提升）；总体成功率约 53%（P11 历史数据）；
8. F1（legacy ELF 验证 fail-open）冻结源码未修；
9. 国际 provider 5–6 模型矩阵被 402 阻断；SiliconFlow 余额问题未解决；
10. 通用性边界：stripped/PIE/static/多架构未扩展；errno 仅进程退出级；ABI cave 出口语义不完整。

## 3.9 会话一的准确能力声明

**可以声称**：有真实二进制修复闭环；P11 有 36 次真实稳定性（19/36）；P12 有一个 v2→Native VERIFIED；P13 有 hidden CWE-476 VERIFIED；P16-R3 有 7 条严格独立验证；CWE-122 通过真实 PT_LOAD cave ABI/layout/oracle/independence 检查；2048 tests 与 CI 当前通过。

**不能声称**：P16 已完成 10/10；CWE-121/CWE-134 已修复；60 次稳定性已完成；N3–N6 已实现；AFL fuzzing 已完成；具备完整 CaveABIBlock/Authorization Record；系统具备通用、稳定或形式化安全保证。

---


# 4. 重点会话二：全类型二进制修复-1

- 会话 ID：`session-b139b586-985b-475c-af5a-1ee7f0082668`
- 时间：2026-11-14 15:12 → 2026-11-16 08:06（14 个 turn；首条指令：上传 `marcx` 二进制，"为什么修复失败，请识别后解决所有问题，完成完整的修复功能"）
- 规模：16,662 个事件；14 个 turn；12 条真人指令；48 个共享任务（团队看板）；19 次 goal 变更（9 个 goal：7 create→complete + 1 resume）；16 份阶段报告（14 份实质报告）；8 个并发 teammate + Lead
- 工作方式：Lead + 并发 teammate（capacity engine / guest runtime / pipeline / GUI / audit tools / heap engine / gate profiles / target-scope / legacy-convergence）；每个 Phase 以"执行报告 + commit/tag/evidence 分支 + 真实 CI"收尾

## 4.1 会话目标与真人指令时间线

| # | 用户指令（摘要） | 对应阶段 |
|---|---|---|
| 1 | 上传 marcx 漏洞二进制：为什么修复失败，识别后解决所有问题，完成完整修复功能 | R0. marcx 容量混淆修复 |
| 2 | 借鉴该问题发现，搜索**全部种类**的修复能力缺口 + 验收模型不匹配，自我发现并反思，做到所有可能全覆盖；直接完成并推送仓库，总结报告与问题 | R1. 66 项能力缺口审计 + 覆盖收尾 |
| 3-5 | 按"仍开放/缓解/非目标/已关闭防回归"四类总结并给方案；继续推进到 0 open / release freeze | R2. 全覆盖阶段 1–3 |
| 6-7 | 最终合并版：给出剩余问题与详细解决方案，继续到 release 闭环 | R3. 最终发布闭环（第 6 阶段） |
| 8-9 | 从 Release 12/12 到"全能力覆盖、自主发现缺口、自我反思和持续进化"的完整技术路线；Autonomy Foundation | R4. 第 7 阶段 Autonomy Foundation |
| 10 | Phase-8A → 自主发现/反思/修复/进化的完整路线 | R5. Phase-8A |
| 11 | "请重试继续项目" | R6. Phase-8B 重试与收尾 |
| 12 | Phase-8B 之后 → 持续自主发现、自我反思与全范围修复能力的完整技术路线 | R7. Phase-8C（C1–C14） |

## 4.2 R0：marcx 容量混淆修复（为什么之前修复失败）

### 4.2.1 根因（会话中确认）

不是 gate 误判，而是**修复能力缺口 + 验收模型不匹配**双重问题：

1. GUI 一键修复 → `binary_review.run_direct_repair()` → 旧字节引擎 `repair_elf()`，只识别 4 类形态：预审模板固定哈希、`sub rsp,N` + 立即数 `edx` 栈读写、立即数 `memcpy`、`strcpy/strcat` code cave；
2. marcx 的真实缺陷：`render()` 的 `OP_SPAN` 分支把**目标写容量 `out_size`**校验误写成**输入池容量 `data_size`**（CWE-131/697 → CWE-787），且 `memcpy` 长度是归档索引里的**运行时值** —— 无立即数 → 引擎全部不匹配 → fail-closed（`supported=False`、`mode=unsupported`、无候选字节）；
3. 旧 gate 的运行时证据模型是 Unicorn 全 ELF 执行 + **栈哨兵** `runtime.no_overflow`，而本缺陷是**堆越界 + 非恒定长度**，栈哨兵产不出用例 → `runtime.*` 全部 `not_run`；
4. 该缺口此前已被记录：`repair_matrix.py` 把 "heap/non-imported inline copy sinks" 列为 non-goal；公平性消融中 CWE121/非恒定长度/堆 canary 家族确定性基线 0 通过。

### 4.2.2 修复内容（不是只修一个样本）

- **新修复引擎** `app/services/repair/capacity.py`：识别"同一函数内 ≥3 个重复内联范围校验、少数派容量变量又恰好是输入大小变量"的缺陷类；对少数派块做**等长原地重写**（`mov T,out_size; sub T,dst; jb fail; cmp T,len; jae copy`，用 `sub` 的 CF 替代被删的 `cmp`），re-decode + 白名单字节 diff + `.rodata` 错误措辞对齐。对 marcx 只改 **16 B `.text` + 49 B `.rodata`**，全文件其余字节不变；
- **gate 扩展**（不降严格性）：新增 required `patch.capacity`（从原始/候选字节**重新推导**每个重写动作，不信引擎报告）；`runtime.evidence/tier/contract` 由**真实 PoC/回归差分**提供；无 manifest / 无 runner → 保持 `not_run`/`inconclusive`，不给下载；
- **真实运行时**：`guest_runner` 支持 native Linux → qemu-user → Lima VM；`poc_runner` 支持 manifest 内嵌二进制夹具（`files` + `{tmp}`）并在 guest 中跑原/候选差分；本机 macOS arm64 实际使用运行中的 Lima 实例（`runner=limactl`, `tier=emulated_run`）；
- **产品化接线**：`repair_any` 的 capacity 回退、`/api/binary/repair-review` 可选 `poc_manifest` 表单字段（≤64 KiB）、CLI `--poc`、GUI 一键修复面板新增 PoC/回归清单选择器与只读 chips（JS 不参与判定）；
- **测试/文档**：`test_capacity_repair.py`、`test_binary_pipeline_capacity.py` 等；架构文档、README、CHANGELOG 更新；**全量 1224 passed / 7 skipped / 0 failed**。

### 4.2.3 验收证据

| 证据 | 结果 |
|---|---|
| 修复后 SHA-256 | `93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2`（原始 `72fb53cb…d54b0d5`） |
| 确定性 gate | **14/14 required checks passed**，`success_within_scope`（`patch.capacity actions=1 sites=0x4020d9 registers=ebx->r12d`） |
| 真实 guest 差分 | **28/28**：4 个 PoC 原始崩溃 / 候选 exit 1 且消息一致；10 个回归用例原/候选逐字节一致（含 `--help`/`--list`） |
| 挑战自带归档矩阵 | **16/16**：8 例行为不变；5 例原崩溃→现拒绝；1 例原静默 1B 越界→现拒绝；`--dump-index` 原崩溃→现拒绝 |
| GUI 端到端 | 浏览器真机上传 marcx+manifest → `decision.success=true`，检查表全绿、下载可用（截图在证据目录） |
| 通用性 | 另一份不同 C 源码/不同寄存器分配的合成样本（`rbp→r12d`）同样被修复并在 guest 通过差分；仓库其余 20+ 样本不误报 |

代码提交：`86587da feat(repair): reviewed capacity-check rewrite for duplicated bounds checks`（42 文件，+9766/−143）；证据：`artifacts/marcx-repair-2026-11-14/`。

边界：仅覆盖这一类内联重复范围校验（容量必须是寄存器分配形态；`-O1` 调试构建/保护页构建那种"每次从结构体字段重载容量"的形态不在范围内，fail-closed）；仅 ELF64 x86-64；可执行区 >2 MiB 显式拒绝；`verified_patch` 必须提供 PoC/回归 manifest + 可用 guest runner；验证结论仅覆盖所给用例，不是整程序证明。

## 4.3 R1：66 → 68 项能力缺口审计与覆盖收尾（P0–P3）

### 4.3.1 自发现审计工具

以 marcx 为模板建立**可复现的自发现审计工具** `app/services/coverage_audit.py` + `scripts/audit_capability_coverage.py`（导入真实 matrix/pipeline/analyzer/runtime/gate/fixtures/PoC/claims，做有界动态探测，确定性、无网络、<5 min）。

| 指标 | 第一轮（11-14） | 覆盖收尾后（P0–P3） | release 模式（最终） |
|---|---:|---:|---:|
| gap 总数 | 66 | 66 | **68** |
| closed | 51 | 55 | **55** |
| mitigated | 1 | 0 | **1**（host-dependent 平台声明） |
| open | 3（0 high） | **0** | **0** |
| non-goal | 11 | 11 | **12** |
| high-severity open | 0 | 0 | 0 |
| dynamic_unverified（静态视图） | — | 6 | 0 |
| universe cells | 205 | 240 | 240（unknown=0） |

产物：`artifacts/capability-gap-audit-2026-11-14/{coverage-matrix.json,gap-report.md,SHA256SUMS}`、`docs/acceptance/capability-gap-audit-2026-11-14.md`。

### 4.3.2 补齐的能力与验收模型

1. **capacity-check 重写重新集成**：此前被隔离在 backup 分支，产品实际仍失败；现在 matrix 策略 `capacity` + 引擎 `repair/capacity.py` + 证据 profile `native_poc_rewrite` + gate `patch.capacity`/`patch.rewrite` 从原始/候选字节重新推导每条改写；
2. **heap 目标容量恢复**：同函数 `malloc/calloc` 立即数 → 返回寄存器 → 复制目标的数据流恢复（`destination_kind=stack|heap`），guard 走 code cave；非栈目标禁用栈/Unicorn 预言机，改走 `native_poc`；
3. **动态 ELF 注入修复**：`code_cave` 原先把程序头表扩到 `PT_INTERP` 上导致候选不可加载 → 改为 PT_NOTE 就地重写（`e_phnum`/PT_INTERP 不变，失败关闭）；
4. **验收模型显式化**：`strict_template / emulated_instruction / native_poc / native_poc_rewrite` 四个证据 profile；`profile.declared/evidence/required_checks`、`container.cell`、`runtime.cell_tier`；不可用 runner → `not_run`（inconclusive，绝不误判 rejected）；无输入/UAF 的 `no_input` 声明；legacy gate 的 manifest 局限显式披露；
5. **基础设施缺口**：x86-64 `.plt.sec`/CET 导入解析（动态 ELF 之前 0 sink）；Lima virtiofs 旧视图导致 qemu SIGBUS 的可见性等待；quick-repair 携带 manifest 时统一走证据 profile（无 manifest 时仍显示候选但 inconclusive，不下载）。

### 4.3.3 P0–P3 收尾结果（测量驱动）

- **P0 target 作用域**：`repair_any(target/require_target)` + `containers.resolve_function_scope` + 必选 `patch.target_scope` 检查（每个 action 的 `site_va` 必须在 `[va,end)` 内，scope 哈希进 `report_sha256`）；
- **P0 Mach-O x86_64 外部 PoC**：`runtime/capabilities.probe()` 声明 `poc_available=False` + 明确原因；`poc_runner._select_runner` 与 native 调度一致，`run_poc` 稳定 unavailable，绝不伪造；
- **P0 legacy gate**：pipeline 在 `repair_elf` 之前拦截 manifest 请求；legacy gate 收到 external PoC 时追加**必失败** `manifest.legacy_gate_unsupported`；
- **P1 11 项非目标显式映射**：`docs/acceptance/non-goals-2026-11-14.md` + `claims.json["non_goals"]`（11/11），coverage gate 强制"未映射即失败"；
- **P2 防回归门禁**：`scripts/verify_coverage_gate.py`（static CI + `--local` 验收模式，`ALLOWED_OPEN=()`）+ CI `coverage-gate` job + target-mode/capability/legacy-route 回归测试；
- **P3 真实验收**：marcx review API 21/21 checks；heap guard 19/19；target-scoped heap 20/20（`patch.target_scope=passed`，`target=heap_bad scope=[0x401130,0x40116c)`）；CLI `--target heap_bad --require-target` → `verified=true`、`target_policy=target_scoped`、输出 `ea222605…`；`--target main` → analysis_only 无候选；无 manifest/错误 target 均 fail-closed；
- 推送：远端 `workbench-v3` 与 `coverage-audit-2026-11-14` 更新到 `0aa9f54`（8 个提交）。

## 4.4 R2/R3：全覆盖阶段 3 与最终发布闭环（第 6 阶段）

### 4.4.1 全覆盖阶段 3

- 安全默认 whole-image 策略（无 target 且无 `allow_whole_image` → `analysis_only`，不产生候选/下载/成功包；whole-image opt-in 记录 `target_policy=whole_image`）；
- 静态审计 `dynamic_unverified` 状态（release 要求 0）、205→240 cells 能力宇宙（unknown=0）；
- meta-audit 18 scenarios（注入已知/伪造 gap，检出 recall/precision 1.0/1.0）、acceptance invariant 引擎（9 packets，0 violations）；
- 12 项非目标产品化（owner/复审/产品化条件/兜底/受影响 cells/检测行为）+ 季度复审（2027-02-14）；
- 真实 12-case provider 矩阵（served-model identity 分层 + cost/seed unavailable 诚实记录）；staged release gate `--pr/--release/--nightly`；
- 26 个非 ASCII Python 注释/docstring 全部修复；语言检查 0；serial verifier ok（5 条 pytest 命令 / 2 workflows）；browser e2e 本地 12/12。

### 4.4.2 最终发布闭环（第 6 阶段，mainline a8934fe）

| 项 | 结果 |
|---|---|
| 最终 mainline | `a8934fefe918b95069b89b42399095dd28bf8710`（tree `1bd4fcc0…`） |
| 本地权威 gate | `release_freeze.py --mode nightly --sha a8934fe` → **exit 0，13/13 required checks，violations=[]**；`frozen_sha==release_sha`、clean tree、mainline 前后不变；1034.6 s |
| full pytest | 849.8 s serial 通过 |
| 真实 Lima capture | 47.1 s（`lima:limactl`, `emulated_run`） |
| provenance | builder=local-frozen-tree、guest available、9 个 acceptance subjects（fixture/candidate SHA 链）、Lima 2.3.0 + VM config digest、artifact digests、`not_run` 显式 |
| meta-audit | 24 scenarios，recall/precision 1.0 |
| universe | 240 cells，unknown=0；11 维方法学 registry digest `d17d3edd…` |
| 审计 | 68 gaps = 55 closed + 1 mitigated + 12 non-goal + 0 open；static 62（44/6/11/1/0）；high=0 |
| provider | 2 provider / 4 model 12-case；pooled AI-target 36/96 = 0.375（Wilson 95% CI [0.285,0.475]）；intl 矩阵 not_satisfied（HTTP 402 证据 sha 绑定） |
| browser | 本地 macOS Chrome 12/12；CI hosted `browser-e2e` success |
| 真实 hosted CI | run `43628367481` success；Ubuntu verification `43628367473` success（head 均为 a8934fe） |
| 推送 | `workbench-v3`=a8934fe、`release/2026-11-16-final`=a8934fe、`release/2026-11-16-evidence`=d6b41db、tag `release-2026-11-16`、`release-2026-11-16-evidence`；post-tag 验证：provenance PASS、evidence branch PASS、drift=0、CI evidence online ok |

## 4.5 R4：第 7 阶段 Autonomy Foundation（mainline a8934fe → 2bfa112）

**定位**：只建设"能力发现、验收审计、反思、统一审计、合同/状态词汇"的基础设施，**不新增、不扩展、不晋级任何漏洞修复能力**。

| 组件 | 内容 | 证据 |
|---|---|---|
| 统一状态机 | `app/services/repair_states.py`：CAPABILITY_STATES / REPAIR_STATES / TERMINAL / FAILURE_STATES；禁止 `verified→release_eligible` 缺 evidence/independence | `tests/test_repair_states.py` |
| 6 份 JSON 合同 | capability / gap / acceptance / repair / evidence / reflection | `contracts/` + `scripts/check_contract_schemas.py` |
| 验收模型 | A01–A08 维度 + AM01–AM20 mismatch 类；`AcceptanceModelMatcher` fail-closed；43 cases（39 负例），recall=precision=1.0 | `app/services/acceptance_models.py`、`artifacts/acceptance-model-audit-2026-11-16` |
| 能力宇宙 | 20 个一级维度 D01–D20；240 cells 映射；`unknown_within_universe=0`；`undiscovered_space=not_measurable`；12 个 out-of-universe 候选 | `app/services/capability_dimensions.py`、`artifacts/capability-universe-2026-11-16` |
| Gap Registry | 64 条记录（12 条来自 claims non_goals + 1 mitigated + failure-driven candidates）；六机制中 knowledge/failure_driven/differential 运行，mutation/metamorphic/sample_based/knowledge_source_scan 显式 not_run | `app/services/gap_registry.py`、`artifacts/gap-registry-2026-11-16` |
| Reflection Engine | 12 问（每问 answer/evidence/status），`verified=false` 恒成立；决策只允许 analysis_only/candidate/not_run；91 条记录、12 个 candidates、0 个 verified_true | `app/services/reflection_engine.py`、`artifacts/autonomous-reflection-2026-11-16` |
| 统一审计入口 | `scripts/autonomous_repair_audit.py --mode full/static --json --evidence-out`；7 个检查，missing→not_run，绝不造假 | `scripts/autonomous_repair_audit.py` |
| 路线图 | 用户 15 项 P0/P1/P2 映射：**implemented 8 / partial 3 / not_started 4**；4 个 not_started 恰是修复能力项 P1-09/10/11/12 | `docs/operations/autonomy-roadmap-2026-11-16.md` |

## 4.6 R5：Phase-8A Repair Readiness（mainline 2bfa112 → bd9cbf6）

**定位**：readiness/验证基础设施；**不新增修复能力、不晋级 verified**。

| 交付 | 内容 |
|---|---|
| G01–G30 readiness 审计 | 30 项（逐条 id/title/phase/priority/dependencies/required_deliverable/probe_spec/blocker）；measured_status：**implemented 13 / partial 7 / missing 5 / not_run 1 / non_goal 4**；每项 `capability_claim: false`；`capability_claims=[]` |
| Ground Truth Benchmark v1 | `benchmark/phase8-v1/manifest.json`，12 个真实 fixture 样本（dev 8 / validation 4）；`hidden_available=false`；deterministic run：12/12 executed、detected 4、candidate 2、deterministic verified 2、**independent verified 0**、false_verified 0、verification_disagreements 2（两个 deterministic 声明被独立验证器撤回，不是 pass） |
| Independent Verifier MVP | 8 项检查从原始/候选字节独立重算；不读生成器 verdict；generator evidence 排除；hermetic selftest 11/11；`scripts/verify_repair.py --selftest` |
| 合同/验收 | contracts 12（6 新）；acceptance AM21–AM24，52 cases / 24 classes；meta-audit 28；均 fail-closed |
| G29 hidden | `hidden_available=false`，无 hidden split 声明 |
| CI | Phase-8 shadow checks 非门禁；release gate 仍 13 required；self-hosted nightly `not_run` |

## 4.7 R6：Phase-8B Independent Verification Semantic Closure（bd9cbf6 → 227f45b）

### 4.7.1 两个 disagreement 的根因（B1 审计）

7 个 gap（V8B-01..V8B-07）全部确认，**两个样本均未观察到 candidate 本身缺陷**；失败来自 verifier 语义与证据交换：

| ID | 结论 |
|---|---|
| V8B-01 | oracle CLI 未注入 `run_poc`（confirmed） |
| V8B-02 | resolved target scope 未交换（stack confirmed；heap 已有 va_range，不适用） |
| V8B-03 | 长度变化被 blanket reject（stack confirmed；heap refuted，等长） |
| V8B-04 | capacity `.rodata` message action 未建模，gate 只看 actions（confirmed） |
| V8B-05 | 无 ABI evidence 派生（confirmed） |
| V8B-06 | 缺 patch-plan 合同（confirmed） |
| V8B-07 | runner 未保存/交换 candidate/plan/report（confirmed） |

### 4.7.2 实现与结果

- **Verifier**：新增 `app/services/verification_semantics.py`；patch-plan 的 `write/insert/replace` 从原始字节**独立重放**，必须逐字节等于 candidate；支持 code cave / appended segment / call redirect / header update / relocation；target scope 使用全部 raw changed ranges；associated change 必须带 `authorization_ref`；ABI block 从 plan/metadata/symbol-backed function/cave 派生，无法派生 → `not_run`；`poc_runner.run_poc` 由 verifier 自己执行，generator verdict 永不读取；resized candidate 无 plan → `not_run`（不再 blanket reject，但绝不自动接受）；`whole_image` 在 Phase-8B **永不 verified**；
- **Contracts/验收**：新增 `patch-plan.schema.json`（contracts 13）；acceptance 62 cases / 28 classes（AM25–AM28）；meta-audit 30；13/13 valid + 13/13 invalid fixtures + SHA256SUMS 全绿；
- **Pipeline/benchmark**：`binary_pipeline` 为 guard/capacity/AI candidate 生成并校验 `patch_plan`；`unified_verification` 的 `patch.rewrite`/`patch.target_scope` 变 plan-aware；`run_repair_benchmark.py` 交换 resolved scope/plan/actions/ABI/real oracle 并保存每个样本证据；
- **真实结果**（12 样本）：12 executed / 2 candidate / **2 independently verified**（`stack-strcpy-x86_64`、`heap-capacity-x86_64`）/ `false_verified=0` / `verification_disagreements=0` / oracle 真实执行 `runner=limactl tier=emulated_run`；其余 10 样本无 candidate，保持 analysis-only；
- **发布**：release SHA `227f45b39d85a7cd95e8589beb07dcfc89cd22d7`、tag `release-2026-11-16-phase8b`、evidence branch tip `528304a9…`；frozen-tree nightly gate **13/13**；hosted CI `43718302033` success、Ubuntu verification `43718302188` success；post-tag provenance/evidence branch/drift/CI evidence 全过。

## 4.8 R7：Phase-8C Ground Truth v2 / Hidden Benchmark / Benchmark Integrity（227f45b → 4a7b235）

### 4.8.1 交付内容

- **Ground Truth v2**：新增 4 个合同（sample / public manifest / hidden commitment / results v2），contracts 总数 **17**；v1 12 个历史样本 **12/12 无损迁移**；旧 13 contracts 与 Phase-8A/8B artifacts 未被改写；
- **公开语料** `benchmark/phase8c/manifest.json`：**32 个样本**（28 core = 12 迁移 + 6 hard-case + 6 repair-benchmark + 4 跨架构 analysis-only；另 4 个经真实 PoC oracle 验证的 Zig `-O2/-O3/-Os`、static/dynamic、strip 变体）；24 runtime-oracle / 8 analysis-only；dev 18 / validation 14；
- **私有 Hidden Benchmark**：8 个样本 = **6 runtime + 2 analysis-only**；私有语料保存在 `~/.binaryrepair/phase8c-hidden`（0700，CI 不访问）；仓库只提交 opaque commitment（`eaec60aadd…bae12`，文件 sha `3ebf2901…`）与聚合结果；
- **C11 Lima 串行化**：`flock` lease + 进程内重入锁 + timeout/blocked + attempt evidence，覆盖 `guest_runner.run_path`/`poc_runner.run_poc` 的 Lima 路径；direct limactl 探针未覆盖（显式记录）；
- **污染/质量审计**：public 与 hidden 污染审计均 clean；full quality `ok`（1 个文档性 warning：public manifest 不内联 hidden commitment，避免循环依赖）；
- **C12/C14**：evidence bundle、claims、LIMITATIONS、release note、CI shadow checks、gate/evidence/tag 全部落地。

### 4.8.2 真实结果

**公开 benchmark**

- 32 样本：30 executed、2 unsupported；无 `not_run`/`blocked`/`invalid`；
- 3 次独立验证尝试：**2 verified、1 rejected、published false_verified=0**；
- 1 个 deterministic claim 被独立 verifier 撤回：`heap-malloc`（独立 ABI 拒绝：`branch_target_unknown`、`call_target_not_allowed`、`no_ret`），保存在 `disagreements.json`，**没有当作通过**；
- 24 个 eligible repair cases，**verified repair rate = 2/24 = 0.0833**；detection / root-cause / localization 各 3/24；
- 两个 serialized repeat 结果完全一致（`a477ea3c…`），记录 `stable_across_repeats=true`，但**不声明无条件稳定**。

**Hidden benchmark**

- 8/8 executed；**0 candidates / 0 independently verified / 0 false_verified**；这是 deterministic engine 在 hidden 变体上的真实覆盖 —— 没有 hidden 修复能力声明，也没有把 0 候选解释成 pass；私有明细报告哈希 `ccbce7e2…`；公开 aggregate 不含 hidden 样本 id/路径/内容。

**Phase-8B 回归**

- 最终树上重验 Phase-8B 两个样本：**2/2 independently verified**，candidate hash 未变（stack-strcpy-x86_64 = `1bc66b2e…`；heap-capacity-x86_64 = `93e27f2f…`）。

### 4.8.3 发布状态

| 项 | 值 |
|---|---|
| release SHA | `4a7b2355ffc5225d013a777bc7d588abac58f944` |
| release tree | `4bf501314b6469328d0256031990bfc402ce6677` |
| mainline `workbench-v3` | 同 `4a7b2355…` |
| release tag / branch | `release-2026-11-16-phase8c` / `release/2026-11-16-phase8c-final` |
| evidence branch / tip / tag | `release/2026-11-16-phase8c-evidence` / `ec503e4b…` / `release-2026-11-16-phase8c-evidence` |
| 本地 frozen-tree nightly gate | **13/13 required checks passed** |
| 最终 hosted CI | CI `43748886046` success；Ubuntu verification `43748886289` success |
| post-tag 检查 | provenance ok（violations=[]）；evidence branch 8/8 checks；drift=0；CI evidence online ok |

### 4.8.4 会话二各阶段的 release gate 演进（关键数字）

| 阶段 | mainline | 本地 nightly gate | CI | 核心新增 |
|---|---|---|---|---|
| 覆盖阶段 3 | `956ee10` | `--release` 9/9 | — | 67 gaps、205 cells、meta 9 |
| 阶段 4 | `f65ed53` / `640d08a` | 11/11 | — | 68 gaps、240 cells、meta 15、invariants 9 |
| 阶段 5 | `fd6ca41` | 12/12（968.2 s） | — | 完整 release 证据、provider 4 模型、meta 18 |
| 阶段 6 | `a8934fe` | 13/13（1034.6 s） | 43626323294 / 43628367481 / 43628367473 success | 真实 hosted CI、provenance、evidence 分支 |
| Phase-7 | `2bfa112` | 13/13（1092.1 s） | 43637263062 / 43637263068 success | Autonomy Foundation |
| Phase-8A | `bd9cbf6` | 13/13（834.5 s） | 43687651314 / 43687651300 success | readiness/GT v1/verifier MVP |
| Phase-8B | `227f45b` | 13/13（1300.5 s） | 43718302033 / 43718302188 success | verifier semantics + 2 verified |
| Phase-8C | `4a7b235` | 13/13（1438.6 s；pytest 1225.3 s；Lima 47.7 s） | 43748886046 / 43748886289 success | GT v2/hidden/17 contracts |

## 4.9 会话二完成项总清单

**已完成（有证据）**

1. marcx 容量混淆修复（新引擎 + gate 扩展 + 真实 guest 差分 + GUI/API/CLI + 1224 tests）；
2. 能力缺口自发现审计工具与覆盖矩阵（66→68 gaps，0 open，240 cells，meta-audit/invariants/coverage gate）；
3. 验收模型统一（4 个 evidence profile、target scope、legacy gate 收敛、runtime capability probe、安全默认策略）；
4. 真实 provider 矩阵（2 provider/4 model，Wilson CI，identity 分层，cost/seed 诚实空值）；
5. 发布治理（release_freeze/staged gate/provenance/evidence branch/drift checker/CI signoff/13 required checks）；
6. 第 6 阶段真实 hosted CI + 本地 nightly 13/13 + final-SHA CI 证据；
7. 第 7 阶段 Autonomy Foundation（状态机、6 合同、20 维宇宙、Gap Registry、Reflection、统一审计、路线图）；
8. Phase-8A（G01–G30 readiness、GT v1、Verifier MVP、12 contracts、AM21–24、meta 28）；
9. Phase-8B（7 个 verifier 语义缺口闭合、patch-plan、2 个真实独立验证、13 contracts、62 cases/28 classes、meta 30、13/13 gate、真实 CI）；
10. Phase-8C（GT v2、17 contracts、32 public samples、8 hidden、contamination/quality、Lima 锁、runner v2、hidden aggregate、13/13 gate、真实 CI、evidence/tag）；
11. 全过程 fail-closed 纪律：0 false_verified、not_run 不冒充 pass、不降 gate、不伪造 CI/统计。

**未完成/仍开放（会话二结束时）**

1. **Hidden 0 verified / 0 candidate**：deterministic engine 在 hidden 变体上无覆盖；不能推出泛化能力；
2. **公开集仅 2/24 verified（8.3%）**：两个 verified 仍是目标 scope 下的 deterministic fixture repair，不是任意二进制/任意漏洞/whole-program 能力；`heap-malloc` 暴露真实 engine/plan-vs-verifier ABI 冲突，已撤回；
3. **C1 一次性 flake**：早期 f42 默认复现出现 `false_verified=1`，加 C11 锁后两次 serialized repeat 未复现；保留 documented warning，不声明无条件稳定；
4. **CI 三轮真实失败**（C3 Zig provenance 误判、C4 hidden root 顺序、claims/artifacts 过期）已修复，失败历史保留；
5. **Hidden 隔离是操作隔离，不是密码学保护**（同 UID/root 可读）；
6. **Public manifest 不内联 hidden commitment**（循环依赖，quality 记录 1 warning）；
7. **claims 与最终 CI 的 SHA 口径**：claims 引用 gated code CI `43744573286`（f1ba37e），最终 release SHA `4a7b235` 的 CI 记录在 evidence-branch addendum；tag SHA = gate SHA = mainline SHA；
8. **未运行项**：self-hosted Lima nightly（无 runner，not_run + signoff）、international provider matrix、external sample ingestion、第二 Linux 编译器（仅 Zig 0.17.1）、跨架构 runtime（C9 analysis-only）；
9. **Phase-8D 开放世界发现/Acceptance 2.0 与 Phase-9–16 均未实现**；
10. 团队看板 48 个任务：44 completed / 2 in_progress（task-13、task-45，实际产物已落地但未改状态）/ 2 pending（task-37、task-46，Lead 集成工作已由 Lead 完成但未认领看板）→ **过程治理问题**，非能力问题。

## 4.10 会话二的准确能力声明

**可以声称**：覆盖矩阵 240 cells、0 open 已知缺口、release gate 13/13、provenance/evidence 强绑定、真实 hosted CI；Ground Truth v1/v2、独立验证器、2 个真实 independent verified、hidden benchmark 已建立但 0 verified；Autonomy Foundation 的治理/审计/反思基础设施。

**不能声称**：新增漏洞修复能力；任意二进制/任意漏洞/whole-program 修复；hidden 泛化；能力晋级；self-hosted nightly 已运行；国际 5–6 模型矩阵；Phase-8D/9–16 完成。

---


# 5. 当前完成现状（以最终 mainline 4a7b235 为权威）

## 5.1 仓库与代码状态

| 项 | 值 |
|---|---|
| 源仓库 | `git@github.com:chenfanaichifan/binary-repair.git`（public；SSH 身份 huajinyao 有写权限） |
| 公开快照 | `github.com/leesirleesirlee-star/Binary_Repair`（v1.2.1） |
| 最终 mainline | `workbench-v3` = `4a7b2355ffc5225d013a777bc7d588abac58f944`（Phase-8C 发布 SHA） |
| 最终 gated tree | `4bf501314b6469328d0256031990bfc402ce6677` |
| 最终 evidence 分支 | `release/2026-11-16-phase8c-evidence` tip `ec503e4b1df53ad39fa836bd34d93a18564d78f9` |
| 旧默认分支 | `main` = `8869b07`（2026-11-12 后未再前进；与 mainline 无关） |
| 本地 worktrees | 3 个：`binary-repair-gui`（main worktree）、`worktree-feature-final`（feature/ai-binary-repair）、`binary-repair`（member-5-deepseek-schema 旧树） |
| 远端 refs | 113 个分支 + 117 个标签 = 242 个（含大量 M1–M5 历史与两会话中间态） |
| 跟踪文件 | 2,074 个 tracked 文件；其中 `artifacts/` 960 个证据文件；17 份 JSON 合同；32 个 public benchmark 样本 + 8 个 hidden commitment（私有本体不入库） |
| Python 环境 | 本地 `.venv` Python 3.11.8；requirements.txt 在线安装（约 40 包） |
| 本地测试收集数 | **2,243 tests**（当前树 `pytest --collect-only`，238 个测试文件） |
| 工作树 | clean（仅 `.venv` 未跟踪） |

## 5.2 测试与 CI 现状

### 5.2.1 最近一次权威 CI（Phase-8C）

| 项 | 值 |
|---|---|
| gated code SHA | `f1ba37eee5146b5bb5de97046a0f8b4b653538ff`（claims 引用） |
| hosted CI | run `43744573286` — **success** |
| Ubuntu verification | run `43744573230` — **success** |
| 最终 release SHA 的 CI | run `43748886046`（CI）/ `43748886289`（Ubuntu verification）— 记录在 evidence-branch addendum |
| 本地 frozen-tree nightly gate | **13/13 required checks passed**，`failed=0`、`unavailable=0` |
| self-hosted Lima nightly | **not_run**（无 self-hosted runner；signoff `docs/operations/phase8c-ci-signoff.md`） |

### 5.2.2 测试规模演进（全量非浏览器套件）

| 时间/阶段 | 测试数 | 结果 |
|---|---|---|
| v1.2.0/1.2.1 | 741 collected / 739 passed / 2 skipped（本地）；Ubuntu CI 889/1/0/890 | 0 failed；浏览器 e2e 12/12 |
| v4/v5 交付件 | 950 | Linux VM 943/7/0 |
| v5 任意二进制 | 1039 | macOS/Linux 0 failed |
| 两条 AI 路径（第一代 6d525ca） | 1118 | 0 failed |
| 两条 AI 路径（第二代 aa45b36，按定义重做） | 1128 | 0 failed |
| 能力缺口审计 | 1160 → 1224 | 0 failed |
| P0–P4 / 3/3 非 loop | 1626 → 1641 | 0 failed |
| P5–P9 | 1954 | 0 failed |
| P10–P15 / P16–P20 | 1966 | 0 failed |
| P16-R / P16-R2 | 2041 | 0 failed |
| P16-R3 | 2044 | 0 failed |
| P21–P24 | 2048 | 0 failed |
| Phase-8A/8B/8C（当前树） | 2,243 collected（当前树；Phase-8C gate 内 full pytest 全绿） | 0 failed |

平台 skip 说明：macOS 4–9 个、Linux 7–17 个，均为平台真实限制（Mach-O 原生运行、Linux 执行类、可选 candidate ELF），不是"跳过以掩盖失败"。

### 5.2.3 CI 工作流

`.github/workflows/ci.yml` 主要 job：`test`、`coverage-gate`、`release-gate-pr`、`browser-e2e`、`release-gate-hosted`、`release-nightly-gate`（self-hosted，inert）、`release-drift`；release gate 的 13 项 required checks 为最终发布门禁。

## 5.3 修复能力矩阵（当前真实边界）

### 5.3.1 容器 / 架构

| 容器 | 架构 | 解析 | 改写 | 运行时证据 |
|---|---|---|---|---|
| ELF | x86-64 | ✅ | ✅ | native Linux / qemu / Lima |
| ELF | i386 | ✅ | ✅（cdecl push 参数、容量=帧顶−目标） | Unicorn x86-32 `emulated_run` |
| ELF | arm64 | ✅ | ✅ | Unicorn（非原生内核运行） |
| PE | x86-64 / i386 / arm64 | ✅ | x86-64/i386 ✅（PE32 IAT/FF15） | Unicorn 指令级仿真（不是 Windows 内核运行） |
| Mach-O (thin, little-endian) | x86-64 / arm64 | ✅ | ✅（仅 native macOS） | macOS 原生；Linux 上 `not_verified` |
| fat Mach-O | 多 slice | ✅（逐 slice 元数据） | ❌ 只分析不回写 | — |
| 其它（arm32/riscv/mips/ppc/big-endian/32-bit Mach-O） | — | 检测/分析 | ❌ `unsupported`/analysis_only | — |

### 5.3.2 可修复的缺陷类（确定性矩阵，已交付）

- 拷贝类栈/heap 目标：`strcpy`/`strcat`/`stpcpy` guard；常量长度 `memcpy`/`memmove`/syscall 长度钳位；i386 memcpy immediate；
- **capacity-check 重复内联范围校验**（marcx 类）：等长原地重写 + `.rodata` 消息；
- **同函数 immediate heap 目标**：`malloc/calloc` 立即数 → 返回寄存器 → 目标的数据流恢复；
- 每个候选只修**一个函数/sink**；多函数、全局目标、动态大小、跨函数别名、结构体成员容量、UAF、`sprintf` 格式串、整数/循环模板、混淆/内联拷贝等仍为 `analysis_only`/`unsupported`。

### 5.3.3 AI 修复路径与真实成绩

| 路径 | 说明 | 真实成绩 |
|---|---|---|
| `asm_roundtrip` | 二进制 → 汇编文本 → AI 修复 → clang 汇编 → 注入 → 重定向（ELF i386/x86_64/arm64） | 非 loop 3/3（deepseek-flash，a8934fe）；P11 36 次 19/36；P16-R3 严格 7/10 |
| `binary_direct` | AI 直接输出机器码/同长字节补丁 → Capstone 白名单/范围校验 → 写回（ELF/PE/Mach-O x86-64/arm64 + i386） | 6 组脚本化 verified（证明协议/校验/写回/gate 集成，**不代表真实 LLM 质量**） |
| 范式 A（C 反编译-重编译） | Ghidra C → LLM → Patcherex2 → PoC | loop 闭环跑通；CWE121 函数级 PASS（1 个函数，非通用） |

真实模型矩阵：DeepSeek flash / v4-pro / SiliconFlow CN Qwen3-8B / Qwen2.5-7B（4 模型）；pooled AI-target 36/96 = 0.375（Wilson 95% CI [0.285, 0.475]）；deterministic target-strict 12/12 期望匹配但 0 verified；国际 5–6 模型矩阵阻塞（HTTP 402/无 key）。

### 5.3.4 验证与验收

- **确定性 gate**：统一 `success_within_scope / inconclusive / rejected / unsupported / error / cancelled`；AI 永远不能提升失败 gate；
- **证据 profile**：`strict_template / emulated_instruction / native_poc / native_poc_rewrite`；不可用 runner → `not_run`（inconclusive）；
- **独立验证器**：9 项 required checks（Phase-8B），从原始/候选字节独立重算：identity、reparse、action replay、scope、associated change 授权、cave 可执行/重定向、relocation、ABI、oracle；不读生成器 verdict；`whole_image` 永不 verified；resized 无 plan → not_run；
- **PoC/回归差分**：supply manifest 时要求 original fails / candidate passes + regression 输出一致；无 manifest 时 fail-closed（不下载、不 success）；
- **target scope**：`--target/--require-target` 时 `patch.target_scope` 必过；无 target 默认安全返回 `analysis_only`；whole-image 需显式 opt-in 且不声明 target 归属。

## 5.4 基准与关键数字

| 基准 | 规模 | 真实结果 |
|---|---|---|
| Phase-8A GT v1 | 12 真实 fixture 样本（dev 8 / validation 4） | 12/12 executed、detected 4、candidate 2、deterministic verified 2、**independent verified 0**、false_verified 0、disagreements 2（后由 8B 闭合） |
| Phase-8B 真实验证 | 同上 12 样本 | 12 executed / 2 candidate / **2 independently verified**（stack-strcpy、heap-capacity）/ false_verified=0 / disagreements=0 |
| Phase-8C public v2 | **32 样本**（24 runtime oracle / 8 analysis-only；dev 18 / validation 14） | 30 executed、2 unsupported；3 次验证尝试 → **2 verified、1 rejected**；false_verified=0；1 个 deterministic claim（heap-malloc）被撤回；verified repair rate **2/24 = 8.33%**；detection/root-cause/localization 各 3/24；两次 serialized repeat 一致 |
| Phase-8C hidden | **8 样本**（6 runtime + 2 analysis-only） | 8/8 executed；**0 candidate、0 verified、0 false_verified**；hidden_available=false；仅公开 opaque commitment + aggregate |
| 稳定性实验（P11） | 2 模型 × 6 case × 3 重复 = 36 runs | **19/36 = 52.8%**（flash 12/18、v4-pro 7/18；cwe122/cwe787 6/6；cwe121 0/6） |
| P16-R3 严格验证 | 10 case | **7 verified / 1 rejected（cwe121）/ 2 artifact missing（cwe787、cwe134）** |
| 模型矩阵 | 4 模型 / 2 provider | pooled AI-target 36/96；deterministic target-strict 0/12 verified（12/12 期望匹配） |
| 浏览器 e2e | 12 用例 | 本地 macOS Chrome 12/12；Linux CI 中 skip 不算 pass |
| 覆盖审计 | 240 cells / 68 gaps | 55 closed / 1 mitigated / 12 non-goal / **0 open** / high=0 / universe unknown=0 |

## 5.5 治理与证据体系现状

- **合同**：17 份 JSON Schema（Phase-8A 12 → 8B 13 → 8C 17），`check_contract_schemas.py` 正/负 fixtures、SHA256SUMS、jsonschema + fallback；
- **验收模型**：A01–A08 维度 + AM01–AM28 mismatch 类；62 cases / 28 classes（8B）；`audit_acceptance_models.py` recall/precision 1.0；meta-audit 30 scenarios；
- **能力宇宙**：20 维 D01–D20、240 cells、unknown=0、`undiscovered_space=not_measurable`、12 out-of-universe 候选（=非目标）；
- **缺口治理**：68 gaps 审计（release 模式）、12 non-goals 产品化 + 季度复审（2027-02-14）、coverage gate（static CI + local 验收）、invariant 引擎；
- **反思/实验**：12 问 Reflection Engine（91 records、0 verified_true）、Experiment Planner（planned/cannot_plan）、Gap Registry 64 条、六机制发现（3 run / 4 not_run）；
- **发布治理**：release gate 13 required checks、`release_freeze.py`（clean tree + SHA 钉住 + mainline 漂移 fail-closed）、provenance、evidence 分支/标签、drift checker、evidence-branch verifier、CI signoff、flake quarantine；
- **证据分层**：本地 frozen-tree 证据 / GitHub-hosted CI 证据 / self-hosted nightly（not_run）分离；JUnit/pytest 日志、gate.json/freeze.json、SHA256SUMS 全量保留；
- **语言/合规**：Python 注释 ASCII 0 violations；markdown 语言检查；serial pytest 校验；flake policy。

## 5.6 项目状态分级（层 × 状态）

| 层级 | 状态 | 说明 |
|---|---|---|
| L1 产品/工程（GUI、API、CLI、文档） | ✅ 完成 | v1.2.1 + v7 交付件 + 工作台 |
| L2 确定性修复矩阵 | ✅ 完成（有界） | 多容器/架构 + 拷贝/容量类 sink |
| L3 AI 修复能力 | 🟡 部分 | 3/3 非 loop（单模型）、19/36、7/10 严格、CWE121/134 负结果 |
| L4 独立验证 | 🟡 部分 | MVP + 2 个真实 independent verified；语义/ABI/授权仍有缺口 |
| L5 Ground Truth / 基准 | 🟡 基础设施完成，覆盖不足 | v1 12 / v2 32 / hidden 8；verified 极少 |
| L6 能力缺口发现 / 验收审计 | 🟡 基础设施完成 | 240 cells、68 gaps、acceptance/reflection/gap registry 已建 |
| L7 发布治理 / 证据链 | ✅ 完成 | 13/13 gate、provenance、evidence/tag、真实 CI |
| L8 自主进化闭环 | ❌ 未开始 | Phase-8D–16（开放世界发现、跨函数语义、修复扩展、自主实验/晋级） |
| L9 通用/生产级能力 | ❌ 未达成 | 明确非目标 |

## 5.7 早期会话历史（2026-10-15 → 2026-11-13，重点会话之前）

> 本工作区共 38 个会话（含 7 个已归档），另有重点会话派生的 teammate/子会话（s1 6 个、s2 8 个）。除两个重点会话外，早期 36 个会话按时间脉络如下（完整证据见 `docs/consolidation/project-history.md`）。

### 5.7.1 项目起源与 MVP（2026-10-15）

- **甲方/课题**：课程/竞赛「项目 11」，来源华为，负责教师杜长来；题目即《AI 驱动的二进制漏洞自动修复与正确性验证》：ICT 与终端领域 1900+ 第三方二进制组件、部分维护中断/无 SLA，目标把修复周期从数周缩短到小时级。
- **2026-10-15 当天**：
  1. 下载并接入 REA（`github.com/morluto/rea`，265 MB、5 submodule、rea-agents 6.5.0、207 个 MCP 工具，`rea doctor` healthy）；
  2. 按 5 步工作流（Research → PRD/MVP → Tech Design → AGENTS → Build）完成"研究想法 + MVP 定义"；
  3. 20:48–20:49 产出三份 PDF：`research-BinaryRepair.pdf`（667,090 B）、`PRD-BinaryRepair-MVP.pdf`（445,400 B）、`TechDesign-BinaryRepair-MVP.pdf`（668,884 B）；git `Initial commit 132ad98`（18:40:09）。
- **MVP 定义**（"一个人、一个样本、一条命令、三个判据"）：输入契约 target/poc/vuln/regress/contract；输出 patched/patch.json/verdict.json/apply_log.json；达成线 = ≥1 个自建 x86-32 栈溢出样本 S1/S2/S3 全过 + S5 干净 Docker 可复现；MoSCoW：Must = M1–M6 + CLI，Should = 跳板/代码洞穴/第二条策略/S4/S6 度量，Won't = 反编译路线/自动定位/符号执行/GUI/多架构。
- **研究四支点**：把不可判定等价性降级为"契约 C + 回归集 T"上的可判定问题；修复语义种类远少于漏洞种类（模板×站点×算子×拒绝方式）；硬约束在模板化空间下变成剪枝器；系统可靠性由验证器误接受率决定。

### 5.7.2 M1–M5 是"五名成员角色"，不是"里程碑 1–5"（2026-10-18 → 10-31）

> 这是项目文档中最容易被误读的一点，特此更正：**M1–M5 = 五名成员的角色编号**；Lead 是第六个角色（批准/范围决策/合并与 tag），另有 VMer（VM 操作）。任务编号体系为 T0–T8。

| 角色 | 职责 | 最终状态与关键交付 |
|---|---|---|
| M1 | 宿主后端（controller/API/DB/任务编排/CI/发布） | COMPLETE；`1250169`（main，83 tests）、`3a107ab`（canonical）、`7817a20`（live-bridge）、`101d034`（m1/t30）；v1.2.1 source `3418491` |
| M2 | GUI/控制台（agent shell、结果屏、assistant UI、迁移） | COMPLETE；`34d054c`、`2501120`；后期成为产品工作台主体（9 语言/主题/证据控制室/历史持久化） |
| M3 | Guest 执行与证据生产（executor/result-bundle/SHA256SUMS） | COMPLETE；T8.3 guest half；hardened guest/KVM 未接入 |
| M4 | 独立验证（清单/复核/UI 验收/LLM 验证） | COMPLETE；但 M4 verifier 与 Lead approver 为同一操作者（role-separated，非双人独立复核） |
| M5 | 数据契约/适配器/AI 层（ingest/协议/assistant seam/LLM planner/generic repair plan） | COMPLETE；SecurityContract v2/v3、candidate schema v1（Route A 12 字段/Route B 14 字段） |
| Lead | 批准/范围决策/合并/tag/记录 gate，不做实现 | — |
| VMer | VM 操作（staging/jobwrap/guest conformance/每次运行 reset），不做产品代码 | — |

**技术抽象固定为**：候选 schema v1、SecurityContract v2/v3、**V0–V5 验证阶梯**、六种 outcome（`success_within_scope/unsupported/rejected/inconclusive/error/cancelled`）、Host/guest 信任边界（host 永不执行上传二进制）。Gate 3 批准 `0b3b51e4`；Gate 4 是 unchanged round-trip（6/6，不是修复证明）；Gate 5A/5B placement。

### 5.7.3 公开 MVP、T8.3 与 v1.2.1（2026-10-31 → 11-11）

- **公开仓库**：`leesirleesirlee-star/Binary_Repair` 于 2026-10-31 23:31 首次出现（curated snapshot），v1.0.0 → v1.2.1；开发仓库 `chenfanaichifan/binary-repair` 自 10-15 起。
- **T8.3**：= **CWE-416 第二类样本**（`original.elf` `c9c2632e…`、candidate `46d16e99…`）；11-07 以 **124 `success_within_scope` + M4 V4 marker `fc4802d0…`** 收口。边界：V4 = **model-scope**（z3 bound 64），124 的 unsat 是**空析取**（`free_calls=0`）；"T8.3 COMPLETE"只代表契约完成，不等于真实漏洞修复能力。
- **118 VERIFIED / 124 inconclusive**：118 是独立验证通过的样本；124 是 model-level V4 pass 但二进制级不完整；两者不能混谈。
- **v1.2.0/v1.2.1**：v1.2.1 stable = `148d236` / public tag `f687e14`；本地 741 collected / 739 passed / 2 skipped / 0 failed；Ubuntu CI 889 passed / 1 skipped / 0 failed / 890 total（[run 43256887551](https://github.com/chenfanaichifan/binary-repair/actions/runs/43256887551)）；浏览器 e2e 12 passed；WeChat 分享包 `WeChat-Share/BinaryRepair-Workbench-2026-11-12.zip`（4,857,723 B，SHA256 `9a7e5c6a…`）。
- **DeepWorks 迁移**（11-08 → 11-11，滴普杯校园黑客松赛道 C）：不是拷文件，而是四层平台原生重建——知识库（21 篇语料 → 267 wiki 节点）、5 个 `binrepair-*` 技能、每日 09:00 回归自动化、Agent 会话（`ses_e450e4b5…`）与产物；只上传 Markdown 与公钥，不上传私钥。
- **计划服务未接通**（11-11）：根因不是网络，而是 GUI 默认 `mock` 后端的 `get_plan()` 恒返回 `None` → 503 `assistant_endpoint_missing`（设计取舍：不伪造计划）；修复为接同一 planner seam——无 key 返回确定性 5 步计划（标注"未调用模型"），有 key 走 LLM；另发现 controller `mode="llm"` 两个分支无条件 503 的独立缺口（后续 11-12 补齐）。

### 5.7.4 CGC、CI 真实性事件与 Linux handoff（2026-11-12 → 11-13）

- **CGC 克隆**（11-12）：把 CGC（cb-multios）移植编译为 Linux x86-64 ELF（zig 0.17.1 交叉编译），**5 对 / 10 个 ELF + 7 个 POV**；Lima + qemu-user 下 POV 真实执行：`Palindrome` 干净崩溃差分 3/3，`basic_messaging` 为 exploratory（脚本化上下文敏感），另有 Board_Game 行为差异、2 个未复现。
- **CI 假 success 事件**（11-12 23:30 → 11-13 00:16）：`a436b64` 的 run `43248544193` **实际 failure**（`test_c_overflow_patterns` 编译器超时 flake），但后续 docs 提交 `9a451fd` 把它写成 success，`DELIVERY.md`/`README.md` 也指向该失败 run。纠正：`774c584`（timeout 8s→20s + `COMPILER_UNAVAILABLE_PREFIX` + 回归测试）、`0fe9241`、`2aca931`；之后 Ubuntu CI 全绿（889/1/0/890）。该事件直接促成"先修证据链、再谈能力"的纪律。
- **Linux handoff v1→v7**（11-12 22:52 → 11-13 17:06）：用户让"有 Linux VM 的同学"帮跑未完成任务，于是产生多轮"打包↔评审↔修复"：

| 版本 | 时间 | 大小（B） | SHA-256（前 8 位） | 关键点 |
|---|---|---|---|---|
| Init | 11-12 23:29 | 19,860,821 | 未记录 | 最早压缩包（superseded） |
| v1 | 11-12 23:13 | 55,889,904 | `7812fc0f` | 冻结 436594d；评审"好包但过期"（T0 在 Linux 必失败等） |
| v2 | 11-13 00:11 | 56,042,010 | `14a45ccd` | 按 v1 评审修复；但仍引用失败 run |
| v3 | 11-13 14:22 | 56,010,305 | `d542dce0` | 修正 CI 历史；评审"内容可通，缺 .sha256 与 archive" |
| v4 | 11-13 15:50 | 56,029,943 | `7678726f` | 补 .sha256/archive |
| v5 | 11-13 15:58 | 74,521,163 | `19b8eeb1` | 通用二进制 v4 代码（ELF/PE/Mach-O、x86-64/arm64） |
| v6 | 11-13 16:17 | 60,204,619 | `da5f4fda` | 评审"内容已过验收，可发"；仍有 3 处嵌套清单失配 |
| v6.1（并行） | 11-13 16:58 | 60,253,460 | `e678f68d` | docs `3d5d0f0` + CI 43395652244；Linux VM 复跑 938/7/5 → **不发送** |
| **v7（最终）** | 11-13 16:58 | **60,488,092** | **`2afeb6c8`** | v6 内容不变 + 打包修复；Linux VM 950/943/7/0，29/29 嵌套清单，verify-package PASS |

- **v7 与 v6 的关系**：v7 = v6 的源码/证据结果不变（同为 `e1756a2`）+ 打包修复（时间戳、3 个嵌套 SHA256SUMS、用户名/路径脱敏、patches 元数据、umask 022 归一化、UTF-8 文件名、CGC caveat、F1 记录）。
- **v3 评审**（11-13 15:15）：结论"v3 内容层面可以通，可以发"，只缺 `v3.zip.sha256` 与 `handoff/archive/`；补齐后可转发。

### 5.7.5 早期阶段的"真实能力 vs 演示/模型级"口径

| 真实能力（有可复核证据） | 只是 fixture/演示/模型级（不能当产品能力） |
|---|---|
| 确定性验收引擎（V0–V5、六 outcome、not_run 永不等于 passed） | GUI 默认 mock 后端/8124 演示实例（合成 fixture、无真实执行） |
| 两条独立路线（Route A 代码洞 / Route B 恢复 C 重编译）+ 共享验收 | 1,200 条 overflow corpus（合成/生成样本） |
| 证据哈希/包/审计链（contract canonical `24bfe568…`、fixture `aa428157…`、candidate `46d16e99…`、marker `fc4802d0…`） | AI 复核实验（3 用例/3 次调用；诚实结论"AI 没有新发现、没有改变决定"） |
| T8.3 通用性证据（CWE-416 第二类样本 + 124 success_within_scope，model-scope V4） | Gate 4（unchanged round-trip，不是漏洞修复证明） |
| 真实 GUI 工作台、代码修复（15 规则 + clang 语法检查）、真实 DeepSeek 集成 | V4（model-level；124 的 unsat 是空析取） |
| v1.2.1 public stable（741/739/2/0；e2e 12/12；tag/main 对齐） | CGC Mach-O arm64 盘点（仅静态，未进管线） |
| Linux VM v7 交付件（950/943/7/0、29/29、verify-package PASS） | CGC Linux x86-64 exploratory（非官方 CGC 语义，maths.S→libm 等漂移） |
| CGC 小样本（5 对/10 ELF + 7 POV；2 个干净 crash 差分） | PE/AArch64 运行时（Unicorn 指令级仿真，不是内核运行） |
| DeepWorks 四层真实迁移（267 wiki/5 技能/每日自动化/Agent 会话） | 老师要求的"修复 ELF 上传"（只存储/下载，不执行、不参与 verdict） |

> **6 起诚实性事件**（项目自我纠正记录）：① `a436b64` 失败 run 被写成 success（`774c584` 纠正）；② v6 声称 943/7/0 但默认 umask 下 938/7/5（v7 归一化 umask）；③ v6.1 对照复跑不符 → 不发送；④ `basic_messaging` POV 不稳定 → 降级 exploratory；⑤ README "100%" 被限定为"批准计划 G1–G5 完成"；⑥ P16-R 宽松 allow-resize 6 verified 与严格路径 0 verified 不能混算。


# 6. 尚未完成的任务与全部问题清单

> 说明：以下清单合并了两个重点会话的最终报告、`docs/acceptance/LIMITATIONS.md`、`claims.json` 的 `not_claimed`/`non_goals`、Phase-8A readiness 的 G01–G30、Phase-8B/8C 的遗留项，以及本次对仓库/远端的实测。按"能力 / 验证 / 治理 / 环境 / 交付"五类分组；每条给出根因、证据、影响与优先级（P0 最高）。**"未完成"不等于"失败"**——多数是明确声明的非目标/阻塞，属于项目可审计的一部分。

## 6.1 A 类：修复能力缺口（核心研究线）

### A1. 非 loop 家族 AI 修复仍为 0/6（P0）
- **现象**：Path A 12 case × 2 DeepSeek 模型：loop 6/12 verified、non-loop 0/6；P3 triage 三例非 loop 全部失败（hard-multicall/hard-nonconst 注入成功但 native fail；hard-sprintf assembler 拒绝 `^`）。
- **根因**：leaf-only 汇编路径禁止外部调用（printLine/exit/strlen）→ 无法实现"拒绝并打印错误"的行为契约；符号/stub 解析靠人工 helper；模型语义（RepairSpec 约束后才有 guard）与真实行为契约之间存在差距；早期把"符号/空间"当根因是误判。
- **证据**：`artifacts/generalization-2026-11-14/README.md`、`artifacts/path-a-call-whitelist-2026-11-14`、`docs/acceptance/p16-p20-2026-11-16.md`。
- **影响**：项目只能证明 loop 家族可修；非 loop 是"通用性"最关键的一步。
- **优先级**：P0（Phase-10 核心）。

### A2. CWE-121 Behavior Contract 未满足（P0）
- **现象**：plan valid / assembly valid / injection success，但 candidate 运行 `stdout="" / exit=0`；PoC 要求 `exit=1 + 精确 stderr`。
- **根因**：`exit()` 是 noreturn 外部调用，leaf-only 汇编无法调用；模型未实现"拒绝 + 打印固定消息"的完整行为；PoC expectations 已传入 planner 但无 guard 语义约束。
- **证据**：P16/P16-R/P16-R2/P16-R3 报告；P11 36 次中 cwe121 0/6。
- **影响**：CWE-121 是内存安全最经典类别之一；该失败说明"能注入"≠"能修复"。
- **优先级**：P0。

### A3. CWE-134 格式串仍 PLAN_INVALID（P1）
- **现象**：CWE-134 在 P13/P16/P16-R/P16-R3 均 `PLAN_INVALID`；只有字段级 v2 规范化补强，没有有效专项 RepairSpec。
- **根因**：v2 一致性检查对格式串修复计划过于严格/字段缺失；缺少字段级 `PLAN_INVALID` 诊断子类型；模型未产出可验证的格式串修复计划。
- **证据**：P10–P15/P16–P20/P16-R2/P16-R3 报告。
- **影响**：7 类 CWE 中 1 类完全无解；benchmark 的"跨 CWE"结论受限。
- **优先级**：P1。

### A4. 跨函数数据流 / 指针别名 / 全局与结构体容量（P0）
- **现象**：Phase-8A readiness：G09 跨函数 data-flow = partial、G10 pointer alias = non_goal、G11 global/struct capacity = non_goal；分析器仍是 same-function/leaf-only。
- **根因**：没有调用图、数据流、别名分析；堆容量只覆盖同函数 immediate malloc/calloc；结构体容量会高估（`malloc(24)` for `char data[16]`）。
- **证据**：`docs/operations/phase8-roadmap-2026-11-16.md`、`LIMITATIONS.md §21`、`artifacts/phase8-readiness-2026-11-16/readiness.json`。
- **影响**：真实世界漏洞大量跨函数/结构体，当前矩阵无法覆盖。
- **优先级**：P0（Phase-8B/Phase-9 核心）。

### A5. 整数 / 字符串 / UAF 修复矩阵（P0/P1）
- **现象**：G12 integer = partial、G13 string = implemented（仅检测/部分）、G14 UAF lifetime = non_goal；确定性模板对 UAF/sprintf/整数/循环几乎为 analysis-only/AI 0。
- **根因**：缺少 range/overflow/truncation/signedness 分析、对象生命周期分析、格式化字符串语义；UAF 修复需要分配器/生命周期建模。
- **证据**：P13 benchmark（CWE-125/190/476 有 verified 但属于 AI 路径；CWE-121/134 失败）；`non_goals` 12 项。
- **优先级**：P0/P1（Phase-10）。

### A6. 间接调用 / 路径敏感 / 并发分析（P1）
- **现象**：G15 indirect call = partial、G16 path-sensitive = missing、G17 concurrency = missing。
- **根因**：无 CFG/indirect call 解析、无路径敏感、无并发模型；当前只做单函数线性/有限 CFG。
- **影响**：真实二进制中常见；限制分析精度与修复定位。
- **优先级**：P1（Phase-9/10）。

### A7. 格式/架构覆盖不足（P1/P2）
- **现象**：32-bit Mach-O、fat Mach-O 重写、arm32/riscv/mips/ppc、big-endian 检测但从不改写；PE 原生运行未实现（仅 Unicorn）；Mach-O x86_64 外部 PoC 在 arm64 宿主不可用（仅 Rosetta 函数级）；Windows PE 原生运行仍为 HANDOFF 任务。
- **根因**：平台/工具链/时间限制；写回器未实现相应容器/架构；无对应运行时证据。
- **证据**：`LIMITATIONS.md §9`、`docs/acceptance/platform-limits-2026-11-15.md`。
- **优先级**：P1/P2（Phase-10/11）。

### A8. Repair Planner / Candidate Manager 未形成完整闭环（P0）
- **现象**：Phase-7 状态机只是"词汇表"；P1-11 planner + candidate state machine = not_started；P1-12 independent verifier 2.0 = not_started；G20/G21 的 readiness implemented 只是既有组件被测量，不是新增能力。
- **根因**：规划器只能产出当前矩阵内的动作；候选生命周期没有强制状态机；没有自动回滚/晋级治理。
- **证据**：`docs/operations/autonomy-roadmap-2026-11-16.md` P1-11/P1-12、`docs/operations/phase8-roadmap-2026-11-16.md` 8C/8D band。
- **优先级**：P0（Phase-12）。

### A9. 多函数 / whole-program 修复（P1）
- **现象**：每候选只修一个函数/sink；其他漏洞函数只记 limitation；`whole_image` 永不 verified（Phase-8B 规定）。
- **根因**：运行时证据只覆盖单个函数；多函数候选无法被同一 oracle 证明；越权修改/patch scope 治理不完善。
- **证据**：`LIMITATIONS.md §9`、Phase-8B 报告。
- **优先级**：P1（Phase-12/13）。

### A10. Hidden 泛化为 0（P0，重大事实）
- **现象**：Phase-8C hidden 8 样本 8/8 executed，但 **0 candidate、0 verified**；公开集 2/24 verified。
- **根因**：deterministic engine 只覆盖特定 fixture 形态；hidden 是 Zig 变体/不同优化/跨架构，暴露真实泛化缺口；不是 gate 问题。
- **证据**：`claims.json phase8c_ground_truth.hidden_benchmark`、`artifacts/phase8c-hidden-2026-11-16/aggregate.json`。
- **影响**：**这是当前最诚实的"能力边界"**：公开 fixture 能修 ≠ hidden 能修。
- **优先级**：P0（Phase-9/10/13）。

### A11. AI 增量未被普遍证明（P1）
- **现象**：真实 provider 6 任务：AI 3/6 vs baseline 6/6，**coverage increment 0**；硬案例基准 AI 1/2；公平性消融 target AI 6/10、blind 0/10、deterministic target-aware 0/10；3/3 非 loop 来自同一 hard-case binary、单模型。
- **根因**：夹具可被确定性引擎修复，无法测增量；AI 只在 gate-blind 用例上有增量；模型质量/随机性明显（P11 52.8%）。
- **证据**：`artifacts/fairness-ablation-2026-11-14/aggregate.json`、`artifacts/ai-real-provider-2026-11-13/`、P8/P11 报告。
- **优先级**：P1（Phase-10/15）。

### A12. CaveABIBlock 出口语义不完整 / 无 policy-issued Authorization Record（P0 验证线）
- **现象**：P16-R3 只覆盖 `ret` 结尾 cave；`tail_jump`/`continuation_jump`/`noreturn` 无独立验证结构；`authorization_ref` 仍是静态字符串，不是绑定原始 ELF/plan hash/修改范围/old-new value 的真实授权记录。
- **根因**：Phase-8B 未完成；v7 的 HANDOFF-TASKS F1/fail-open 也与此相关。
- **证据**：P16-R3 报告"仍未完成"、P21 profile `authorization_profile=STATIC_REFERENCE_ONLY`。
- **优先级**：P0（Phase-11）。

### A13. 独立验证器 2.0（语义保持/行为变化检测）未实现（P0/P1）
- **现象**：Phase-8B verifier 的 9 项检查能验完整性/布局/ABI/i=oracle，但"内存安全但行为改变"的补丁仍可能通过（P15/P12 要求 independent verifier 能 reject 行为变化）；当前只有 PoC/regression 差分，非完整语义等价。
- **根因**：语义保持不可判定；需要行为差分 + 不变量 + 更强的回归/副作用捕获。
- **优先级**：P0（Phase-11）。

### A14. Regression Engine 超出 MVP 的部分（P1）
- **现象**：G25 Regression Engine readiness=implemented 仅为既有 gate 的回归检查；没有独立回归引擎、没有自动生成回归用例、没有跨样本语义回归。
- **优先级**：P1（Phase-11）。

### A15. Fuzzing / 符号执行未实现（P1）
- **现象**：只有确定性 mutation plan（固定 seed/count/可复现输入）；无 AFL/AFL++ campaign、覆盖率反馈、crash/hang 去重最小化、符号执行；无"新 crash 自动进入 regression/verifier"。
- **证据**：P15/P20/P20-R 报告。
- **优先级**：P1（Phase-13）。

### A16. Native Trace N3–N6 与函数返回级 errno（P1）
- **现象**：N1/N2 已实现；N3 寄存器/N4 栈内存/N5 控制流/N6 RepairSpec invariant 语义差未运行（guest 无 gdb）；errno 仅进程退出级 LD_PRELOAD，不是函数返回瞬间。
- **根因**：环境无 gdb/ptrace 方案未实现。
- **优先级**：P1（Phase-11）。

### A17. 副作用等价未证明（P2）
- **现象**：stdout 签名 + 回归捕获了 heap-canary 早退；但无 PoC 的 asm 路径仍可能省略 `puts` 而通过内存 gate；buffered I/O/errno/libc 状态无完整等价。
- **优先级**：P2（Phase-11/15）。

### A18. Provider 矩阵与国际 5–6 模型未满足（P2）
- **现象**：4 模型/2 provider 完成；SiliconFlow 国际站 HTTP 402、GLM-Z1 超时、DashScope 无 key；cost/seed unavailable；served-model identity 与 requested 不一致（deepseek-chat→deepseek-flash）。
- **影响**：模型能力结论只能覆盖 4 模型；不能做 5–6 模型统计。
- **优先级**：P2（Phase-15）。

### A19. 稳定性 60 次未完成、模型随机性明显（P1）
- **现象**：唯一正式稳定性数据仍是 P11 的 36 次 19/36（52.8%）；P18/P23 的 60 次未完成；P23 smoke 单次 `PLAN_INVALID`；同一代码同一 case 不同 run 成功集合不同。
- **根因**：live provider 延迟/成本；冻结 profile 后的完整矩阵未跑；缺自动重试/重放。
- **优先级**：P1（Phase-10/15）。

### A20. 外部语料 ingestion / 第二编译器未完成（P2）
- **现象**：external ingestion `not_run`（无本地 external corpus）；cross-compiler 只有 Zig 0.17.1（4 个变体）；无第二 Linux 编译器验证。
- **优先级**：P2（Phase-13/15）。

### A21. Hidden 隔离非密码学（P2）
- **现象**：private root 0700 + CI 不访问 + 公开只提交 commitment/aggregate；同 UID/root 可读；公开 manifest 不内联 commitment（循环依赖，quality 有 1 warning）。
- **优先级**：P2（Phase-13 治理）。

### A22. 性能/容量限制（P3）
- **现象**：输入 ≤20 MiB；可执行区 >2 MiB 显式拒绝；单函数/单候选；全量测试 ~890–1035s；无性能基准。
- **优先级**：P3。

### A23. v7 冻结交付件中的 legacy fail-open（F1）（P1）
- **现象**：`binary_pipeline.py::_from_elf_legacy` 在验证失败/异常时仍保留 `candidate_available` 并返回候选，CLI 报 `supported=true`；v7 冻结源码未修（只记录在 HANDOFF-TASKS F1）。
- **影响**：v7 交付件存在已知 fail-open 例外；虽然后续 v5 分支已消除，但冻结包未更新。
- **优先级**：P1（交付件修补/说明）。

### A24. readelf 外部依赖（P3）
- **现象**：Route B 依赖 Linux GNU readelf；macOS 缺 readelf 时测试失败（装 Homebrew readelf 解决，不是替换后端）；方法建议 §9.3 要求替换 LIEF/llvm-readelf。
- **优先级**：P3。

### A25. 32 位/fat/大端/Windows PE 原生等覆盖（P2）
- **现象**：32-bit Mach-O/PE external PoC unavailable；fat Mach-O 只分析；大端/arm32/riscv/mips/ppc 不支持；PE 仅 Unicorn 仿真；Windows 不是验收环境。
- **优先级**：P2/P3。

### A26. Authorization / Capability Promotion 治理闭环（P1）
- **现象**：G30 Capability Promotion Governance = partial；没有端到端"实验→独立验证→hidden→晋级"流程；repair_states 只是词汇表；claims 仍为人工维护（虽有检查器）。
- **优先级**：P1（Phase-14/16）。

### A27. 反思/实验执行器未闭环（P1）
- **现象**：Reflection Engine 有 12 问/91 记录，但 `verified=false` 恒成立、不能修复/验证；Experiment Planner 只能 planned/cannot_plan，没有自动执行器；P0-04 六机制有 4 个 not_run（mutation/metamorphic/sample_based/knowledge_source_scan）。
- **优先级**：P1（Phase-14）。

### A28. Hidden/public 数据与版本治理（P2）
- **现象**：hidden commitment 与 public manifest 解耦（避免循环）；contamination 审计已 clean；但 hidden 语料保留/轮换/防污染生命周期未产品化；quality 有 warning。
- **优先级**：P2。

## 6.2 B 类：验证/证据/发布治理问题

### B1. self-hosted Lima nightly 从未真实运行（P1）
- **现象**：CI job inert（无 runner）；所有 release 的 `self_hosted_nightly` 都是 `not_run` + signoff；hosted CI 只等价 portable 层。
- **影响**：无法声称"完整 nightly gate 在 CI 上通过"；只能声称本地 frozen-tree gate。
- **优先级**：P1（治理）。

### B2. claims 的 CI 指针与最终 release SHA 存在口径差（P1）
- **现象**：`claims.json.latest_verified_ci` 指向 gated code CI（`43744573286` / f1ba37e），最终 release SHA `4a7b235` 的 CI（`43748886046/43748886289`）记录在 evidence-branch addendum；原因是"claims 提交会改变树 → 再 gate"的循环。
- **影响**：外部读者可能误以为最终 SHA 没有 CI；需要文档解释/或改变"claims 后置"流程。
- **优先级**：P1。

### B3. Phase-8C CI 三轮真实失败（环境/工具链）（P2）
- **现象**：① C3 builder 在无 Zig 的 CI 主机把 toolchain/source-digest provenance 差异误判为 committed corpus 篡改；② C4 hidden builder 在无 Zig 时先报 `not_run` 而非 insecure root `violation`；③ claims/docs 变更后 capability/gap/provider/reflection 确定性 artifacts 过期。最终修复并验证，失败历史保留。
- **影响**：CI 对环境敏感，需要 toolchain 探测/确定性 artifact 再生成。
- **优先级**：P2。

### B4. release gate 13 required 与 hosted CI 的等价性（P2）
- **现象**：hosted CI 只跑 portable 层（static+claims+targeted pytest+full non-browser pytest），不是完整 13 项（含 Lima capture/本地测量）；平台差异无法在 hosted 复现。
- **影响**：不能声称"CI 上 13/13"；只能声称本地 frozen-tree 13/13 + hosted portable success。
- **优先级**：P2。

### B5. main 分支严重陈旧（P1）
- **现象**：`main` = 8869b07（11-12 后未动），落后 mainline 数百提交；GitHub 默认分支仍是 main。
- **影响**：外部访客默认看到旧代码；与本项目最终成果不符；release/evidence 体系与 main 脱节。
- **优先级**：P1（本次整合可解决）。

### B6. 远端 refs 极度膨胀（P1）
- **现象**：113 分支 + 117 标签 = 242 refs；大量 M1–M5 中间分支、两个重点会话的 phase/release/evidence 分支/标签；易混淆、难维护、容易误用旧 SHA。
- **影响**：仓库可用性/可审计性下降；正是用户要求"整理整合 + 删原痕迹"的直接原因。
- **优先级**：P1（本次整合解决）。

### B7. 团队任务看板与产物的状态漂移（P2）
- **现象**：会话二 48 个共享任务：44 completed / 2 in_progress（task-13、task-45，实际产物已落地）/ 2 pending（task-37、task-46，Lead 集成已完成但未认领/关闭）。
- **影响**：看板不能真实反映完成度；属于流程治理问题。
- **优先级**：P2。

### B8. 会话/工作区残留物（P2）
- **现象**：`.tmp/`（解压会话、team 合同）、`handoff/` 大 zip 与解压副本、`capacity-archive-2026-11-14/`、多个 worktree、`datasets/`、`.venv` 等；其中部分被 `.gitignore` 忽略（不入库），但本地占用大（archive 1.4 GB、handoff zip 60 MB）。
- **影响**：磁盘/环境噪声；交接时易误用。
- **优先级**：P2。

### B9. 凭据卫生风险（P0 安全）
- **现象**：会话日志中出现明文 API key（SiliconFlow CN/US、DashScope、DeepSeek，多个 key），且会话日志保存在本机 `~/.dsh/sessions`；仓库交付包已做 secret 扫描（v7 verify-package PASS），但**会话日志与聊天记录中的 key 应视为已泄露**。
- **影响**：安全风险；需要轮换/吊销。
- **优先级**：P0（安全）。

### B10. 文档口径分裂（P1）
- **现象**：`README.md` 顶部仍以 2026-11-15 的 "feature line" 为主，`DELIVERY.md` 是 v1.2.1 快照口径，`docs/status/final-status.md` 是 2026-11-08 口径；而最终 mainline 已到 Phase-8C。多个历史文档未标注"历史"。
- **影响**：读者可能引用旧数字/旧能力边界。
- **优先级**：P1（需文档层级重构）。

### B11. 依赖/环境可复现性（P2）
- **现象**：Python 3.11/3.12 双环境；Zig 0.17.1 只在部分机器；Ghidra/JDK 用户级安装；Lima 单实例；macOS readelf/AppleDouble/umask 噪声。
- **影响**：换机器复跑成本高；CI 与本地差异。
- **优先级**：P2。

### B12. 测试耗时（P3）
- **现象**：全量 pytest 889–1035 s serial；release gate 968–1034 s；nightly 门槛高；flake 治理未自动执行。
- **优先级**：P3。

## 6.3 C 类：本次任务对应的交付/仓库问题

### C1. 两个会话的成果散落在多个分支/标签（P0，本次解决）
- 成果分布在 `workbench-v3`、`feature/universal-repair`、`feature/ai-binary-repair`、`feature/phase8b/8c`、`release/2026-11-14..16-*`、`coverage-audit-*`、多个 tag；用户要求收敛到**一个新分支**并删除原位置/痕迹。

### C2. 仓库缺少"总览型"交付文档（P1，本次解决）
- 现有文档是分阶段/分文件的；没有一个从项目目标 → 全部完成项 → 现状 → 剩余任务 → 解决方案的总文档。本次生成。

### C3. 仓库默认分支与最终成果不一致（P1）
- 见 B5；本次新分支提供唯一最终载体，但默认分支设置需要 GitHub 设置页/API（无 gh/token）。

### C4. 删除痕迹的边界（P1）
- 可以删除远端 refs（分支/标签）与本地中间物；**无法删除 Git 对象历史**（除非重写全仓历史/强制 GC，且会破坏 main）；GitHub 上旧 commit 在删除 ref 后仍可能通过 SHA 访问，直到平台 GC。本次将：创建干净整合分支、删除两会话 refs、本地完整备份、文档说明残余风险。

## 6.4 D 类：用户/流程层面的待办

- D1. 轮换会话中泄露的所有 API key（P0 安全）；
- D2. 决定最终主分支策略（是否把整合分支设为 GitHub 默认分支；需要 owner 操作或 token）；
- D3. 确认 hidden 语料保留人/轮换策略（当前仅 owner 本机 0700）；
- D4. 确认是否继续投入 live API 成本完成 60 次稳定性矩阵（P18/P23）；
- D5. 确认是否申请 self-hosted Lima runner（P1-13/B1）；
- D6. 确认 12 项非目标的季度复审 owner（2027-02-14 前）；
- D7. 确认是否对外发布/演示（v1.2.1 公开仓库、DeepWorks 比赛材料）与最新成果的口径一致性。

---

## 6.5 补充：会话二最终报告列出的 23 项未决问题（逐条映射）

> 来源：`s2-analysis.md` §5（对会话二最终报告、claims/LIMITATIONS、Phase-8B/8C 遗留项的整合）。"处置"列对应本文第 7 节方案编号。

| # | 问题 | 现状/证据 | 处理原则 | 对应方案 |
|---|---|---|---|---|
| 1 | 公开 benchmark 仅 2/24 verified | Phase-8C results：30 executed、2 verified、1 rejected、false_verified=0 | 不夸大：这是 deterministic fixture repair，不是通用能力 | A10/A11 + Phase-9/10 |
| 2 | hidden 0 candidate / 0 verified | hidden 8/8 executed、0 verified | 明确"hidden 泛化未成立"；不得当 pass | A10 + Phase-13/15 |
| 3 | 非 loop 0/6 | Path A 12 case × 2 模型；P3 triage 三例全失败 | 研究型非目标（NG-ai-leaf-only），按五步毕业路径推进 | A1 + Phase-10 |
| 4 | `heap-malloc` plan/ABI 冲突被撤回 | verifier 要求可派生 ABI block；该样本 branch_target_unknown / call_target_not_allowed / no_ret | 修 engine 的 plan 生成或 verifier 语义（**不放宽验证**） | A13 + Phase-11 |
| 5 | Phase-8A 两个 deterministic claim 被撤回（8B 已闭合） | 8A disagreements 2 → 8B V8B-01..07 confirmed、0 disagreement、2/2 verified | 已闭合；保留回归测试防复发 | A12 |
| 6 | G01–G30 真正语义能力缺失（G04/05/06/09–17） | readiness implemented 13 / partial 7 / missing 5 / not_run 1 / non_goal 4 | 以 blocker/next_action 为输入排期 | A4/A5/A6 + Phase-9/10 |
| 7 | "implemented 13" 易被误读为能力晋级 | 规则是 code+test(+artifact/ground truth) 的探针级工程证据 | 对外固定表述"探针级"；capability graduation 仍为 0 | B10 文档口径 |
| 8 | Provider 只 2 providers / 4 models | SiliconFlow intl 402、GLM-Z1 超时、DashScope 无 key；pooled 36/96=0.375，Wilson [0.285,0.475]；cost/seed null | 记录 not_satisfied + sha 证据；不外推 | A18 + Phase-15 |
| 9 | served-model 身份不匹配 | 请求 deepseek-chat 实际 deepseek-flash（identity_ok=false） | 6/12 只归因 served model，不计 requested-model | A18；模型 registry K-04 |
| 10 | non-loop 0/6、多 provider 统计缺失 | AI 路径非验收 owner；统计口径未建立 | 作为研究非目标，按五步毕业路径推进 | A11 + Phase-15 |
| 11 | self-hosted Lima nightly not_run | 无 self-hosted runner；job inert 保护 | 配置 runner 或长期 not_run + signoff | B1 |
| 12 | 浏览器证据分层 | Linux CI 无 Chromium 时显式 skip；本地 macOS Chrome 12/12 | 保留本地证据定位，不并入 CI 结论 | B4 |
| 13 | 平台限制（不可用能力） | 32-bit Mach-O 原生/PE external PoC/macho x86_64 外部 PoC 在 arm64 仅 Rosetta 函数级 | 显式 unavailable/not_run，不伪造 | A7/A25 |
| 14 | 12 项研究/平台非目标未实现 | claims 12 non_goals（含 owner/review 2027-02-14/productization/fallback） | 季度复审 + 五步毕业；coverage gate 未映射即失败 | 第 7.2 节 Phase-13/15 |
| 15 | claims CI 指针滞后（结构性） | claims latest_verified_ci=43744573286（f1ba37e）；最终 SHA 的 43748886046 在 evidence addendum | 双记录；或冻结窗口内再做 claims commit + 重 gate（换 SHA） | B2 |
| 16 | Evidence 后置/部分证据在本地分支 | marcx 一手证据只在本地 `backup/capacity-86587da`；86587da 非 mainline 祖先 | **本次已归档进整合分支**（artifacts/marcx-repair-2026-11-14 + marcx-capacity-gui）；其余 evidence tag 已合并 | C1 + 本次交付 |
| 17 | Lima 并发鲁棒性 | 外部 P16 工作负载与本地 gate 共用同一 Lima guest；C11 前有一次 false_verified=1 flake | 专用 runner/串行化纳入 CI 强制 | B1/B12 + Phase-11 |
| 18 | 外部并发写入导致证据失效 | operator 多次推进 mainline（阶段 6 曾 6 次；8A/8B/8C 均有） | 发布窗口冻结；freeze wrapper 已 fail-closed；按 worktree-safety 重 freeze | B2/B6 |
| 19 | Hidden 隔离非密码学 | 0700 私有 root、CI 不访问、只发 commitment/aggregate；同 UID/root 可读 | 明确风险；如需强隔离用独立账号/加密 | A21 |
| 20 | 外部样本 not_run；跨编译器未验证（仅 Zig 0.17.1） | 无本地 external corpus；无第二 Linux 编译器 | 提供外部语料/第二工具链再声明 | A20 + Phase-13 |
| 21 | Phase-8D / 9–16 未实施 | 各阶段 not_claimed | 从 Phase-8D（开放世界发现 + Acceptance 2.0）起步 | 第 7.2 节 |
| 22 | 历史完整性修正 | `artifacts/coverage-closure-2026-11-14/SHA256SUMS` 的 acceptance.json checksum 过期（8A 只改 checksum 行） | 已修正；后续 artifacts 由 gate 自动生成 SUMS | B3 |
| 23 | 证据分层易混淆 | 本地 gate vs CI vs nightly vs browser 证明范围不同 | release note/ci-run.json/claims ci_evidence schema v2 显式区分 | B4 |

## 6.6 补充：早期阶段（重点会话之前）的遗留问题

| 编号 | 问题 | 说明 | 对应方案 |
|---|---|---|---|
| E-1 | T4 sprintf 格式展开未实现 | v7 TASKS.md 标记 ❌ | A3 + Phase-10 |
| E-2 | T5 UAF/整数/循环未实现 | v7 TASKS.md 标记 ❌ | A5 + Phase-10 |
| E-3 | 32 位/大端/fat Mach-O 重写未实现 | 只检测/分析，不改写 | A7/A25 |
| E-4 | 堆/全局 sink 覆盖不足 | v5 起 heap 部分覆盖，global/struct 仍 analysis-only | A4 + Phase-9 |
| E-5 | 硬化 guest/KVM 隔离未接入 | T6 partial：Unicorn/native macOS，硬化 Linux guest 未接入 | B11 + Phase-11 |
| E-6 | Windows PE 原生运行未实现 | 仅 Unicorn 仿真；Windows 不是验收环境 | A7/A25 |
| E-7 | readelf 后端未替换 | 仍依赖 Linux GNU readelf（macOS 需 Homebrew readelf） | A24 |
| E-8 | F1 legacy ELF fail-open | v7 冻结源码未修；HANDOFF-TASKS F1 记录 | A23 + Phase-11 |
| E-9 | M4 verifier 与 Lead approver 同一操作者 | role-separated，非双人独立复核 | 治理：独立审批人（Phase-16） |
| E-10 | Gate 0 的 D1–D6 原文缺失 | 书面签到缺失（11-07 记录） | 治理：补档/声明 |
| E-11 | Windows DPAPI key 存储未验证 | v1.2.1-rc1 明确披露 | B11 |
| E-12 | 项目计划书.docx 归档缺失 | 历史材料未在归档中找到 | B8 归档 |
| E-13 | 公开 repo 与开发 repo 的关系 | 公开 repo 是 curated snapshot；部分 raw evidence 不在公开 repo | B10 文档口径 |

---


# 7. 对应解决方案与执行路线

> 原则：**先验证、后能力；先证据、后声明；任何补丁都必须可被独立验证器拒绝**。所有方案都保留"不可用即 not_run、不降 gate、不自动晋级"的红线。

## 7.1 总体策略：双轨并行 + 三闸门

- **能力轨**：Phase-8B（跨函数/别名/整数/字符串/UAF 语义）→ Phase-10（修复扩展）→ Phase-12（Planner 2.0）。
- **发现/治理轨**：Phase-8D（开放世界发现）→ Phase-13（持续发现）→ Phase-14（自主反思/实验）→ Phase-15/16（模型与验收 3.0、Release 2.0）。
- **三闸门**（每个新能力必须全部通过才能晋级）：
  1. **Ground Truth 闸门**：≥1 个独立真实样本（PoC + regression + reference fix）；
  2. **Independent Verifier 闸门**：从原始/候选字节独立重算 + ABI/oracle/scope 全过，false_verified=0；
  3. **Hidden/Regression 闸门**：hidden 变体上不退化为 0，且回归/语义保持通过。
- **证据分级**：`implemented`（有代码）→ `tested`（有测试）→ `fixture_verified`（独立验证）→ `benchmark_verified`（benchmark 范围）→ `externally_validated`（外部样本）→ `production_eligible`（发布门禁）。**只有后三级可以对外称"能力"**。

## 7.2 完整阶段路线图（Phase-8D → Phase-16）

> 来源：会话二最终路线图（用户/组长确认）与仓库内 `docs/operations/autonomy-roadmap-2026-11-16.md`、`docs/operations/phase8-roadmap-2026-11-16.md`。

### Phase-8D：Acceptance Intelligence 2.0 与开放世界发现基础（2–3 周）

| 任务 | 交付物 | 验收标准 |
|---|---|---|
| D-01 统一 Discovery Engine（知识/失败/差分/变异/蜕变/样本/验收七机制） | `app/services/discovery_engine.py` + registry + 证据 | 7 机制每种有 run/not_run + reason；新增至少 1 个真实可运行机制（如 mutation） |
| D-02 Gap Registry 动态化（lineage/dedup/priority） | 扩展 `gap_registry.py` + 优先级算法（严重度×可达性×修复成本） | Gap 记录可追溯到证据；无重复；优先级可解释 |
| D-03 Acceptance 2.0（模型自审计 5 能力） | static contract audit / positive-negative / mutation testing / differential / historical drift | 注入已知错配 100% 检出，recall/precision 保持 1.0 |
| D-04 未覆盖空间度量 | unknown-space 规则 + `undiscovered_space=not_measurable` | 不编造数字；out-of-universe 有界 |
| D-05 Phase-7 backlog 关闭 | P0-04/P0-08/P1-13 等 partial 项 | 每项有 artifact/证据 |

### Phase-9：Cross-function Semantic Intelligence（3–4 周）

| 任务 | 交付物 | 验收标准 |
|---|---|---|
| E-01 CFG / Call Graph 重建 | `app/services/analysis/cfg.py`（Capstone + Ghidra/angr 可选后端） | 对 10 个真实 fixture 重建 CFG，无崩溃；indirect target 显式 unresolved |
| E-02 跨函数数据流（参数/返回/全局） | reaching-definition + 调用约定传播 | 在 cross-function fixture 上定位 sink，当前引擎失败、新引擎成功 |
| E-03 指针别名/points-to | 保守 alias 分析 | 不产生错误别名（fail-closed）；unit + fixture 正负例 |
| E-04 全局/结构体容量推断 | 类型信息（DWARF/编译器符号）+ 保守上限 | malloc(24) for char[16] 的高估被修正或显式 limitation |
| E-05 UAF 生命周期 | malloc/free 配对 + 生命周期状态机 | 在 CWE-416 fixture 上给出 use-after-free 证据；修复由 Phase-10 消费 |
| E-06 路径敏感 | 条件分支枚举/谓词抽象 | 至少 1 个真实 case 只有路径敏感才能定位 |

### Phase-10：Integer / String / UAF Repair Expansion + 非 loop 突破（4–6 周）

| 任务 | 交付物 | 验收标准 |
|---|---|---|
| F-01 CWE-121 Behavior Contract | RepairSpec 增加 `failure_behavior`（exit code/stderr 精确消息）+ 允许 `exit/fputs` 的**受控** syscall/PLT 模板 | CWE-121 至少 1 个候选独立 verified（stdout/stderr/exit 精确匹配） |
| F-02 CWE-134 格式串 | 字段级 `PLAN_INVALID` 诊断 + 格式串修复策略（固定格式/边界） | 至少 1 个 PLAN 通过；否则明确 non_goal 并记录 |
| F-03 非 loop 通用化 | 符号解析器（fputs/exit/strlen 等 PLT 模板）+ selective whitelist + call-graph 约束 | 非 loop verified 从 0/6 提升到 ≥2/6（多模型、多二进制） |
| F-04 整数/字符串/UAF 修复矩阵 | 每类 ≥2 fixture（PoC+regression+reference fix） | 每类 ≥1 独立 verified；否则 not_run |
| F-05 60 次稳定性矩阵 | 冻结 profile + 断点续跑 + 成本预算 + 统计（Wilson CI） | 2 模型 × 10 case × 3 重复全部真实执行；结果可复现 |
| F-06 模型矩阵 5–6 模型（如可获得） | SiliconFlow 国际余额/新 provider key | 5–6 模型 exact identity；served-only 不计 requested |

### Phase-11：Independent Binary Verification 2.0（3–4 周）

| 任务 | 交付物 | 验收标准 |
|---|---|---|
| G-01 CaveABIBlock 完整出口语义 | ret/tail_jump/continuation_jump/noreturn + CFG/指令边界证据 | 4 类出口各有正/负测试；非法跳转 fail-closed |
| G-02 policy-issued Authorization Record | 绑定原始 ELF sha、plan hash、修改范围、old/new bytes、签发者 | 伪造/过期/越权授权被拒绝；记录可复现 |
| G-03 V4 漏洞消除 / V5 语义保持 | 行为差分 + 不变量 + 回归 + 副作用捕获 | 能拒绝"内存安全但行为改变"的补丁（至少 1 个负例） |
| G-04 函数返回级 errno / 寄存器 / 栈 / 控制流 trace | gdb/ptrace 探针（guest 内 gdb 可用） | N3–N6 有真实数据；不可用→not_run |
| G-05 符号执行/模糊回归 | 可选：angr/AFL++ 接入 independent verifier | 新 crash 可自动进入 regression/verifier |
| G-06 行为契约引擎 | 从 PoC 自动提取 expected/actual 断言 | 至少覆盖 stdout/stderr/exit/errno/文件副作用 |

### Phase-12：Autonomous Repair Planner 2.0（3–4 周）

| 任务 | 交付物 | 验收标准 |
|---|---|---|
| H-01 Planner 合同 | root cause → strategy → candidate plan，状态机强制 | 非法状态不可表示；plan 通过 schema+state machine |
| H-02 候选生命周期 | candidate→analysis_only→patch_candidate→verified→release_eligible，禁止跳级 | verified→release_eligible 需 evidence+independence |
| H-03 多候选/多函数规划 | 候选排序、回滚、冲突处理 | 至少 1 个多函数 case 的候选被正确选择/拒绝 |
| H-04 自动实验记录 | 每个决策可追溯到 Gap/Reflection | 无"无证据晋级" |

### Phase-13：Open-World Autonomous Discovery（4–6 周）

| 任务 | 交付物 | 验收标准 |
|---|---|---|
| I-01 外部知识扫描 | CVE/CWE/论文/补丁源接入（本地/离线优先） | 知识条目有来源/版本/许可；新知识触发候选 gap |
| I-02 真实二进制语料库 | CGC/CVE/公开样本 + 许可/哈希/污染审计 | 至少 20 个外部样本，污染审计 clean |
| I-03 Mutation/Metamorphic Discovery | 变异/蜕变测试生成器 | 发现的 gap 有证据；不自动晋级 |
| I-04 Sample-based Discovery | 外部样本驱动的能力缺口发现 | not_run 减少；候选有机器证据 |
| I-05 组合发现 | 能力维度交叉组合搜索 | 组合 gap 可复现 |

### Phase-14：Autonomous Reflection & Experimentation（4–6 周）

| 任务 | 交付物 | 验收标准 |
|---|---|---|
| J-01 Failure Analyzer / Hypothesis Generator | 失败分类 + 可证伪假设 | 12 问全有 answer/evidence/status |
| J-02 Experiment Runner | 自动排队/执行/预算/超时/复现 | 实验可复现；失败保留证据 |
| J-03 Result Analyzer / Improvement Planner | 统计显著性/效应量/回归 | 不显著不晋级；负结果保留 |
| J-04 Promotion Evaluator | 能力晋级/降级/撤回 | 双重门禁；可回滚 |

### Phase-15：Model & Acceptance Intelligence 3.0（3–4 周）

| 任务 | 交付物 | 验收标准 |
|---|---|---|
| K-01 Provider 矩阵 5–6 模型 | 多 provider exact identity + cost/seed | 完成矩阵或明确 not_satisfied + 证据 sha |
| K-02 Hidden Benchmark 扩展 | ≥20 hidden（≥16 runtime） | hidden 结果不泄漏；0 false_verified |
| K-03 Acceptance 自审计 2.0 | mutation/differential/historical drift | recall/precision 1.0；漂移报警 |
| K-04 Model registry/路由 | 按任务评价模型 | served-model-only 永不 verified |

### Phase-16：Autonomous Binary Repair Release 2.0（4–6 周）

| 任务 | 交付物 | 验收标准 |
|---|---|---|
| L-01 端到端自主闭环演示 | 发现→分析→规划→修复→独立验证→反思→实验→晋级 | 1 个真实未见样本完成全链路；证据包可审计 |
| L-02 Release Gate 2.0 | 能力晋级/hidden/回归/证据/成本门禁 | 13+ 项全绿；无 not_run 冒充 |
| L-03 文档/治理/合规 | 总览/边界/非目标/报告 | 对外声明与证据一致 |
| L-04 最终交付 | Release 2.0 tag/evidence/报告 | 可复现、可审计 |

## 7.3 逐项问题 → 解决方案映射

### A 类（修复能力）

| 问题 | 解决方案 | 验收标准 | 阶段 |
|---|---|---|---|
| A1 非 loop 0/6 | 符号解析器泛化（PLT 模板 fputs/exit/strlen）+ selective whitelist + call-graph 约束；RepairSpec 约束 failure_behavior；多模型矩阵 | 非 loop ≥2/6 独立 verified；多模型可复现 | Phase-10 |
| A2 CWE-121 Behavior Contract | RepairSpec 增加 `failure_behavior`（exit/stderr 精确）；受控 `exit/fputs` 调用模板；PoC expectations 进入 planner + gate 断言 | ≥1 个 CWE-121 候选独立 verified（stdout/stderr/exit 精确匹配） | Phase-10 |
| A3 CWE-134 | 字段级 PLAN_INVALID 诊断子类型；格式串修复策略（固定格式/边界）；或明确 non_goal | ≥1 个 plan 通过；否则记录 non_goal + 证据 | Phase-10 |
| A4 跨函数/别名/全局/结构体 | CFG/call graph + reaching-def + points-to + DWARF 类型；Phase-9 E-01..E-04 | cross-function fixture 上当前失败/新成功；不产生错误别名 | Phase-9 |
| A5 整数/字符串/UAF | 每类 ≥2 fixture + 分析器 + 修复策略；Phase-10 F-04 | 每类 ≥1 独立 verified | Phase-10 |
| A6 间接调用/路径敏感/并发 | CFG + indirect call 解析 + 路径枚举 + 并发模型 | ≥1 个真实 case 需要该能力才能解决 | Phase-9 |
| A7 格式/架构 | 写回器扩展（32-bit Mach-O/fat/大端/arm32/riscv/mips/ppc）；PE 原生运行环境；平台限制表 | 每项有 contract + measured + negative test；不可用 not_run | Phase-10/11 |
| A8 Planner/Candidate Manager | 状态机 + planner 合同 + candidate lifecycle + 回滚；Phase-12 | 非法状态不可表示；多候选可回滚 | Phase-12 |
| A9 多函数/whole-program | 多函数 runtime oracle + patch scope 治理；whole_image 永不 verified 的规则保持 | ≥1 个多函数 case 被独立验证；或明确 non_goal | Phase-12/13 |
| A10 Hidden 0 verified | 用 Phase-9/10 的真实能力提升 hidden 覆盖；hidden 只用于评估，不参与训练/调参；每次 release 记录 hidden aggregate | hidden ≥1 independently verified 且 false_verified=0；否则保持 hidden_available=false | Phase-13/15 |
| A11 AI 增量 | 只测 gate-blind 用例；真实 provider 多模型；记录 incremental coverage；负结果保留 | 在 baseline 失败的 case 上测出 AI 增量 ≥1，且独立验证 | Phase-10/15 |
| A12 CaveABIBlock/Authorization | G-01/G-02：完整出口语义 + policy-issued record | 4 类出口正负测试；伪造授权被拒 | Phase-11 |
| A13 Verifier 2.0 | G-03：行为差分 + 不变量 + 副作用；拒绝行为改变补丁 | ≥1 个"内存安全但行为改变"负例被 reject | Phase-11 |
| A14 Regression Engine | 自动回归用例生成 + 跨样本语义回归；G-06 | 新候选自动跑回归；回归失败→rejected | Phase-11 |
| A15 Fuzzing | guest 内 AFL++ campaign + 覆盖率反馈 + crash 去重最小化 + 自动进入 regression | ≥1 个新 crash 被发现并进入 verifier | Phase-13 |
| A16 N3–N6 / errno | guest 安装 gdb + ptrace 权限 + ret 断点探针；G-04 | 寄存器/栈/控制流/errno 真实数据；不可用 not_run | Phase-11 |
| A17 副作用等价 | stdout 签名 + fd offset/errno/buffered I/O 捕获；G-06 | ≥1 个 puts 副作用负例被 gate 拒绝 | Phase-11 |
| A18 Provider 矩阵 | 申请国际站余额/新 key；或多 provider 本地部署；K-01 | 5–6 模型 exact identity 或明确 not_satisfied + sha 证据 | Phase-15 |
| A19 60 次稳定性 | 断点续跑 + 成本预算 + 自动重试；F-05 | 60/60 真实执行；Wilson CI；可复现 | Phase-10 |
| A20 外部语料/第二编译器 | 本地 external corpus + 第二 Linux 编译器（clang/gcc）；I-02 | ≥20 外部样本 + 2 编译器变体 | Phase-13 |
| A21 Hidden 隔离 | 操作隔离 + 轮换策略 + 不宣称密码学；只公开 commitment/aggregate | 文档/审计明确边界；无 hidden 泄漏 | Phase-13 |
| A22 性能/容量 | 输入/可执行区限制文档化；并行测试但 gate 串行；性能基准 | release gate 时间可控；不牺牲串行正确性 | Phase-15 |
| A23 F1 fail-open | 在后续版本修复 legacy 路径：验证失败清空 candidate_available + 回归测试；v7 包内加 F1 说明/或重打 v8 | 回归测试覆盖失败/异常路径；v8 包重跑 | Phase-11 |
| A24 readelf | 替换为 LIEF/llvm-readelf 后端，保留 readelf 兼容 | macOS 默认环境测试通过；不再依赖外部 readelf | Phase-9 |
| A25 32-bit/fat/大端/PE | 写回器 + 运行时证据逐项实现；平台限制表 | 每项 contract + measured + negative | Phase-10/11 |
| A26 Authorization/Capability Promotion | 端到端晋级流程 + 双重门禁 + 自动降级；J-04/L-02 | 只有验证通过的能力可晋级；可回滚 | Phase-14/16 |
| A27 反思/实验执行器 | J-01..J-04：失败分析→假设→实验→结果→改进→晋级 | 12 问 + 自动执行器 + 负结果保留 | Phase-14 |
| A28 Hidden/public 版本治理 | hidden 轮换 + contamination + commitment 版本；K-02 | 无泄漏；contamination clean；版本可追溯 | Phase-15 |

### B 类（验证/治理）

| 问题 | 解决方案 | 验收标准 |
|---|---|---|
| B1 self-hosted nightly | 申请/部署 self-hosted Lima runner；或用 GitHub-hosted Linux + Lima（文档化平台差异）；保留 not_run signoff | nightly 真实运行一次并绑定 SHA；否则永久 not_run + signoff |
| B2 claims CI 口径 | claims 增加 `final_release_sha` 与 `gated_sha` 双字段；evidence-branch addendum 自动生成；发布说明明确"gated code CI vs final SHA CI" | 外部读者能一眼看到两个 SHA 的 CI；无虚假声明 |
| B3 CI 环境敏感 | CI 增加 toolchain 探测（Zig/clang）；artifact 再生成 job；失败重试/隔离；provenance 依赖版本化 | CI 在无 Zig 主机也绿；artifact 确定性 |
| B4 hosted vs 13 项 | 文档化"portable CI ≠ full gate"；hosted 增加可移植检查；平台测量本地保留 | 无"CI 13/13"虚假声明；gate 报告分层清晰 |
| B5 main 陈旧 | 整合分支创建后，把 GitHub 默认分支切到新分支（需 owner 操作）；或把 main fast-forward 到整合分支（force，需备份） | 默认分支显示最终成果；旧 main 保留备份 tag |
| B6 refs 膨胀 | 本次：删除两会话 refs（分支/标签）；本地 bundle 全量备份；保留 pre-session refs | 远端只剩必要 refs；备份可恢复 |
| B7 看板漂移 | 关闭 task-37/46、更新 task-13/45 状态；建立"产物落地即改状态"规则 | 48/48 状态与实际一致 |
| B8 残留物 | 清理本地 `.tmp/`、handoff 解压副本、capacity archive（归档到备份盘）；保留 zip + SHA | 工作区干净；关键产物可追溯 |
| B9 凭据 | **立即轮换**会话中所有 API key；扫描仓库/会话日志；加 pre-commit secret 扫描 + CI secret scanning | 所有旧 key 失效；无明文 key 入库 |
| B10 文档口径 | 建立文档层级：README（最新状态）→ STATUS（当前）→ LIMITATIONS（边界）→ phase docs（历史）；旧文档标注历史日期/版本 | 新读者不会被旧数字误导 |
| B11 环境复现 | 固化 requirements + toolchain 版本 + Docker/Lima 镜像 + 一键脚本 | 新机器可复现全量测试 |
| B12 测试耗时 | 测试分层（unit/integration/e2e）；gate 串行；CI 缓存；flake quarantine 自动执行 | release gate 时间可控且正确 |

### C/D 类（交付/流程）

| 问题 | 解决方案 |
|---|---|
| C1 成果散落 | 本次：创建整合分支（见第 8 节），推送 GitHub；删除两会话原 refs；本地 bundle 备份 |
| C2 缺总览文档 | 本次生成本文档 + 仓库内 `docs/consolidation/` 索引 |
| C3 默认分支 | 建议 owner 在 GitHub Settings 把新分支设为默认；或提供 token 由脚本 API 设置 |
| C4 删除边界 | 明确"删 ref 不等于删对象"；本地 bundle 永久备份；残余风险写入交付说明 |
| D1 key 轮换 | 立即执行（安全 P0） |
| D2 默认分支 | owner 决策 |
| D3 hidden 保留 | owner 决策 + 轮换计划 |
| D4 60 次成本 | 预算决策（live API 成本） |
| D5 self-hosted runner | 资源决策 |
| D6 非目标复审 | 指定 owner，2027-02-14 前复审 |
| D7 对外口径 | 用本文档 + LIMITATIONS 统一对外表述 |

## 7.4 建议的执行优先级与时间表

### 立即（0–2 周）
1. **安全**：轮换所有会话中出现的 API key；扫描仓库/日志；加 secret 扫描（P0）。
2. **交付**：完成本次整合分支 + 文档 + 远端 refs 清理 + 备份（本文档第 8 节）。
3. **文档**：README/STATUS 更新到最终 mainline；历史文档标注日期。
4. **流程**：关闭团队看板 pending/in_progress；记录 B7。

### 短期（2–6 周）
1. Phase-8D：Discovery Engine + Acceptance 2.0 + Gap Registry 动态化（D-01..D-05）。
2. Phase-9：CFG/call graph + 跨函数数据流 + alias（E-01..E-03）。
3. Phase-11 部分：CaveABIBlock 出口语义 + Authorization Record（G-01/G-02）——先于更多修复能力。
4. 60 次稳定性矩阵（F-05）+ 成本预算。
5. self-hosted Lima runner 方案（B1）。

### 中期（1–2 个季度）
1. Phase-10：CWE-121/134 + 非 loop + 整数/字符串/UAF 矩阵（F-01..F-04）。
2. Phase-11 完成：Verifier 2.0 + GDB trace + 副作用（G-03..G-06）。
3. Phase-12：Planner 2.0（H-01..H-04）。
4. Phase-13：开放世界发现 + 外部语料（I-01..I-05）。

### 长期（2–4 个季度）
1. Phase-14：自主反思/实验（J-01..J-04）。
2. Phase-15：模型/验收 3.0 + hidden 扩展（K-01..K-04）。
3. Phase-16：Release 2.0 全链路演示（L-01..L-04）。

## 7.5 红线与防作弊机制（必须保持）

1. **不降 gate**：任何新能力不得通过放宽验证/跳过测试/伪造 not_run 获得；
2. **不自动晋级**：`verified→release_eligible` 需 evidence+independence 双门禁；能力晋级需独立实验；
3. **不把 not_run 当 pass**：self-hosted nightly、国际矩阵、GDB、AFL、external corpus 等未运行项永久显式标注；
4. **不伪造证据**：CI run id/head_sha/conclusion 必须机器核对；provenance/evidence 强绑定；
5. **hidden 不泄漏**：hidden 语料不参与训练/调参，不进入公开报告；只公开 commitment/aggregate；
6. **模型只产生候选**：AI 评审不能提升失败 gate；served-model-only 不计 requested-model；
7. **负结果保留**：CWE-121/134、hidden 0、非 loop 0/6、AI 增量 0 等必须写入报告/LIMITATIONS。

## 7.6 资源与风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| API 余额/限流（SiliconFlow 402、GLM 超时） | 多模型矩阵/60 次无法完成 | 预算+多 provider+本地模型备选；记录 not_satisfied |
| 无 self-hosted Lima runner | nightly 只能 not_run | GitHub-hosted Linux + 平台差异文档；或申请 runner |
| 无 GDB/ptrace | N3–N6 无法实现 | 在 guest 内安装 gdb + 调整 ptrace_scope；或改用 QEMU 插件 |
| 测试耗时/成本 | 发布周期长 | 分层测试 + 缓存 + 串行 gate；nightly 预算 |
| 外部并发写入 mainline | 证据失效 | release_freeze 已 fail-closed；冻结窗口；worktree 隔离 |
| hidden 泄漏/污染 | 评估失真 | 操作隔离 + contamination 审计 + 轮换 |
| Git 痕迹无法彻底删除 | 用户期望落差 | 删除 refs + 本地 bundle + 文档说明；必要时 GitHub Support GC |

---


# 8. 本次仓库整合与交付（新分支 / 痕迹清理 / 仓库地址）

## 8.1 目标与方案

按用户要求："将两个会话（Linux 虚拟机验证漏洞修复-1、全类型二进制修复-1）中所有完成的任务整理整合后推送至 GitHub 仓库中一新分支内，并删除其原本在仓库中的所有位置与信息存放痕迹。"

本次采用的方案（可审计、可回滚）：

1. **新分支**：`final/consolidated-2026-11-16`，基于最终 mainline（Phase-8C）的 evidence tip `ec503e4`（= Phase-8C 发布 `4a7b235` + post-tag evidence addendum）。
2. **补齐散落证据**：把此前只存在于各 `release/*-evidence` 分支与本地 `backup/capacity-86587da` 分支、未进入 mainline 的 **51 个证据文件（3.9 MB）** 归档进新分支，包括：
   - `artifacts/marcx-repair-2026-11-14/`（marcx 一手证据：README、marcx-fixed、patch-record、poc-manifest、runtime-evidence、challenge-suite、verification-report、gui-success.png、reproduce.py、SHA256SUMS）与 `artifacts/marcx-capacity-gui-2026-11-14/`；
   - `artifacts/release-gate-2026-11-14/`、`...-11-15/`、`...-11-15-autonomy/`、`...-11-16/`、`...-11-16-phase8a/`、`...-11-16-phase8b/` 的 gate.json/freeze.json/ci-run.json/provenance 等；
   - 缺失的 release note：`docs/release-2026-11-15.md`、`docs/release-2026-11-15-autonomy.md`、`docs/release-2026-11-16-phase8a.md`、`docs/release-phase8b-final-evidence-2026-11-16.md`。
3. **整合文档**：新增 `docs/consolidation/`：
   - `PROJECT-MASTER-REPORT-2026-11-16.md`（本文档，项目总览/完成现状/剩余任务/解决方案）；
   - `session-1-linux-vm-analysis.md`、`session-2-all-types-analysis.md`（两个重点会话的逐事件分析，含 seq/commit/CI/证据）；
   - `project-history.md`（2026-10-15 → 11-13 的早期历史还原）；
   - `CONSOLIDATION-2026-11-16.md`（本次整合的执行记录、ref 映射、删除清单、备份与恢复方法）。
4. **删除原位置/痕迹**：删除两个会话产生的 **23 个远端分支 + 14 个远端标签**（见 8.3），保留 `main` 与 2026-11-13 之前的历史 refs；本地做完整 mirror 备份（见 8.5）。
5. **验证**：新分支可正常 checkout、文档可读、远端 refs 数量下降、备份可恢复。

## 8.2 新分支内容

- 分支名：`final/consolidated-2026-11-16`
- 起点：`ec503e4b1df53ad39fa836bd34d93a18564d78f9`（Phase-8C evidence tip；其历史包含两个会话的全部 commit：`3d5d0f0`、`72db891`、`aa45b36`、`a1755a5`、`090ad94`、`0aa9f54`、`956ee10`、`f65ed53`、`fd6ca41`、`a8934fe`、`2bfa112`、`bd9cbf6`、`227f45b`、`4a7b235` 等）
- 相对 mainline 的新增：
  - 51 个补归档证据文件；
  - `docs/consolidation/` 5 份文档；
  - 根目录 `CONSOLIDATION.md`（指向新分支与总报告）；
  -（可选）README 顶部一行指向 consolidation 的说明。
- 语义：**这是交付整合分支，不是被 gate 的 release SHA**；gated release SHA 仍是 `4a7b235`（`docs/status/claims.json` 与各 gate 证据不变）。新增文件均为 docs/evidence，不改代码、不改 claims、不改 gate 结果。

## 8.3 删除的原位置/痕迹清单（两个会话产生）

### 8.3.1 远端分支（23 个）

| 分支 | tip | 说明 |
|---|---|---|
| `handoff-v4-local` | 3d5d0f0 | v6.1 docs（会话一前段） |
| `feature/universal-repair` | 72db891 | v5 任意二进制 |
| `feature/ai-binary-repair` | a1755a5 | 两条 AI 路径 + P21–P24 |
| `feature/phase8b-verifier-semantics` | 227f45b | Phase-8B |
| `feature/phase8c-ground-truth-v2` | ceb2061 | Phase-8C |
| `coverage-audit-2026-11-14` | 956ee10 | 覆盖审计阶段 3 |
| `coverage-audit-2026-11-14-merged` | f65ed53 | 覆盖审计合并 |
| `release/2026-11-14-final` | fd6ca41 | 阶段 5 发布 |
| `release/2026-11-14-evidence` | 9cfaaa | 阶段 5 证据 |
| `release/2026-11-15-integration` | 2a468d7 | 集成 |
| `release/2026-11-15-final` | fd6ca41 | 阶段 5 发布 |
| `release/2026-11-15-evidence` | 028d709 | 阶段 5 证据 |
| `release/2026-11-16-final` | a8934fe | 阶段 6 发布 |
| `release/2026-11-16-evidence` | d6b41db | 阶段 6 证据 |
| `release/2026-11-15-autonomy-final` | 2bfa112 | Phase-7 |
| `release/2026-11-15-autonomy-evidence` | 37994eb | Phase-7 证据 |
| `release/2026-11-16-phase8a-final` | bd9cbf6 | Phase-8A |
| `release/2026-11-16-phase8a-evidence` | 0a095c5 | Phase-8A 证据 |
| `release/2026-11-16-phase8b-final` | 227f45b | Phase-8B |
| `release/2026-11-16-phase8b-evidence` | 528304a | Phase-8B 证据 |
| `release/2026-11-16-phase8c-final` | 4a7b235 | Phase-8C（最终 mainline） |
| `release/2026-11-16-phase8c-evidence` | ec503e4 | Phase-8C evidence tip |
| `workbench-v3` | 4a7b235 | 两个会话共同推进的 mainline（其历史/内容已在整合分支中） |

### 8.3.2 远端标签（14 个）

`release-2026-11-14`、`release-2026-11-14-evidence`、`release-2026-11-15`、`release-2026-11-15-evidence`、`release-2026-11-16`、`release-2026-11-16-evidence`、`release-2026-11-15-autonomy`、`release-2026-11-15-autonomy-evidence`、`release-2026-11-16-phase8a`、`release-2026-11-16-phase8a-evidence`、`release-2026-11-16-phase8b`、`release-2026-11-16-phase8b-evidence`、`release-2026-11-16-phase8c`、`release-2026-11-16-phase8c-evidence`

> 说明：这些 tag 指向的 commit 均已包含在整合分支历史中；tag 对应的证据文件已归档进整合分支 `artifacts/release-gate-*`（见 8.1）。

## 8.4 保留项（不删除）

- `main`（GitHub 默认分支，2026-11-12 前的历史；两会话未在其上直接推进；默认分支不可由普通 push 删除）；
- 2026-11-13 之前的历史 refs（M1–M5 角色分支、v1.2.1 发布线、集成分支等，共约 90 个分支 + 65 个标签）——它们不是两个重点会话的"原位置"，删除会丢失课程/公开交付历史；
- 本地：2 个 worktree（`binary-repair-gui`、`binary-repair`）、`backup/`（mirror + bundle + refs 清单）、`handoff/`、`capacity-archive-2026-11-14/` 等；
- 远端：新建的 `final/consolidated-2026-11-16` 分支。

## 8.5 本地完整备份与恢复

- **mirror 备份**：`backup/binary-repair-mirror-2026-11-16.git`（`git clone --mirror` 自 origin，129 MB，含全部 113 分支 / 79 个标签对象 / 11 个 pull refs 及全部 commit 对象）。
- **refs 清单**：`backup/remote-refs-2026-11-16.txt`（删除前 `git ls-remote origin` 的 242 行原始输出）。
- **本地 refs bundle**：`backup/local-refs-2026-11-16.bundle`（127 MB，git bundle create --all，含删除前本地全部分支/标签，包括只在本地存在过的 backup/capacity-86587da、handoff-v3-local、integration/release-2026-11-15、release/2026-11-14）。
- **恢复方法**（任选）：
  ```bash
  # 1) 从 mirror 恢复某个分支/标签到远端
  cd backup/binary-repair-mirror-2026-11-16.git
  git push git@github.com:chenfanaichifan/binary-repair.git refs/heads/workbench-v3:refs/heads/workbench-v3
  git push git@github.com:chenfanaichifan/binary-repair.git refs/tags/release-2026-11-16-phase8c:refs/tags/release-2026-11-16-phase8c
  # 2) 或把 mirror 作为远端直接 fetch/clone
  git clone backup/binary-repair-mirror-2026-11-16.git recovered-binary-repair
  ```
- **注意**：mirror 是**本地**备份，不上传 GitHub；请保留该目录（或另存到移动硬盘/云盘）。

## 8.6 执行结果（本次实做，2026-11-16）

| 项 | 结果 |
|---|---|
| 新分支 | `final/consolidated-2026-11-16`，首个 commit `4322a51`（父 `ec503e4`），已推送 GitHub |
| 整合内容 | 58 个文件变更：51 个补归档证据文件 + `docs/consolidation/` 5 份文档 + 根 `CONSOLIDATION.md` + README 顶部说明 |
| 删除远端分支 | **23/23 成功**（全部两个会话产生的分支，含 `workbench-v3`、`feature/universal-repair`、`feature/ai-binary-repair`、`feature/phase8b/8c`、`coverage-audit-*`、`release/2026-11-14..16-*`） |
| 删除远端标签 | **14/14 成功**（全部 11-14..16 的 release/evidence tag） |
| 远端 refs 数量 | 删除前 **242**（+新分支 1 = 243 行）→ 删除后 **192** 行；heads 113 → **91**；tag refs 117 行（79 unique）→ **89** 行（**65 unique**） |
| 会话相关远端 ref 残留 | **0**（`git ls-remote` 中已无 workbench-v3/phase8/universal/ai-binary/coverage-audit/release-2026-11-1x/autonomy/handoff-v4） |
| 本地清理 | 删除本地 23 个会话分支 + 14 个会话 tag + 4 个本地会话分支（`backup/capacity-86587da`、`handoff-v3-local`、`integration/release-2026-11-15`、`release/2026-11-14`）+ 移除 `worktree-feature-final`；本地仅保留 `final/consolidated-2026-11-16` 一个会话相关 ref |
| 本地剩余 | branches 102（91 remote + 本地 pre-session + 新分支）；tags 67（pre-session 历史） |
| 备份 | `backup/binary-repair-mirror-2026-11-16.git`（129 MB，remote 全量 mirror）；`backup/local-refs-2026-11-16.bundle`（127 MB，含删除前全部本地 refs）；`backup/remote-refs-2026-11-16.txt`（242 行删除前 refs 清单） |
| gated release SHA | 仍为 `4a7b2355ffc5225d013a777bc7d588abac58f944`（未改代码/claims/gate） |

## 8.7 验证与仓库地址

### 8.7.1 验证清单（实测）

| 检查 | 结果 |
|---|---|
| 新分支在 GitHub | `refs/heads/final/consolidated-2026-11-16` = `4322a51811463eedcfee98bae6e03ae48b6c911f` |
| 新分支历史包含两会话 commit | 是（`ec503e4` 祖先链包含 `3d5d0f0`、`72db891`、`aa45b36`、`a1755a5`、`090ad94`、`0aa9f54`、`956ee10`、`f65ed53`、`fd6ca41`、`a8934fe`、`2bfa112`、`bd9cbf6`、`227f45b`、`4a7b235`） |
| 补归档证据 | `artifacts/marcx-repair-2026-11-14/`（10 文件）、`artifacts/marcx-capacity-gui-2026-11-14/`、6 个 release-gate bundle、4 份 release note 均在树中 |
| 整合文档 | `docs/consolidation/` 5 份（总报告/两会话分析/早期历史/整合说明） |
| 远端 refs 清理 | 192 行；会话相关残留 0 |
| 备份完整性 | mirror 可用（`git for-each-ref` 203 refs、`workbench-v3`=4a7b235）；bundle 127 MB 可用 |
| 工作区 | `binary-repair-gui` 在 `final/consolidated-2026-11-16`，clean（仅 .venv 未跟踪） |

### 8.7.2 仓库地址

- **仓库**：`https://github.com/chenfanaichifan/binary-repair`
- **SSH**：`git@github.com:chenfanaichifan/binary-repair.git`
- **新分支**：`final/consolidated-2026-11-16`
- **克隆/切换**：

```bash
git clone git@github.com:chenfanaichifan/binary-repair.git
cd binary-repair
git checkout final/consolidated-2026-11-16
```

- **总报告（仓库内）**：`docs/consolidation/PROJECT-MASTER-REPORT-2026-11-16.md`
- **整合说明**：`CONSOLIDATION.md` / `docs/consolidation/CONSOLIDATION-2026-11-16.md`

## 8.8 残余风险与说明（必须知道）

1. **Git 对象不会因删除 ref 而立即消失**：两个会话的 commit 对象仍存在本地/远端对象库中，GitHub 可能在 GC 前通过 SHA 访问；真正"物理删除"需要 GitHub Support 或全仓历史重写（会破坏 main/历史），本次不做。本次删除的是**所有可达 ref（分支/标签）**，即"原来的位置"。
2. **CI run 链接**：删除分支后 GitHub Actions 的 run 记录仍在（按 run id 可访问），但对应分支页面会显示 branch deleted；这是预期行为。
3. **默认分支**：GitHub 默认分支仍是 `main`（旧历史）。建议在 GitHub Settings → Branches 把 `final/consolidated-2026-11-16` 设为默认（需要 owner 操作或 admin token；本机无 gh/token，未代做）。
4. **本地 worktree**：`binary-repair-gui` 现 checkout 到新分支；`worktree-feature-final`（feature/ai-binary-repair）与 `binary-repair`（member-5 旧树）仍在，可按需删除（本地）。
5. **会话日志**：`~/.dsh/sessions/...` 中的会话原始日志仍在（本次未删除，因为"包括已归档"的回顾需要它们；如需彻底清理可另行删除）。
6. **凭据**：会话中出现的 API key 应全部轮换（见 6.2 B9）。

---


# 附录

## 附录 A：本工作区全部会话清单（38 个，含 7 个已归档）

> 数据来源：`~/.dsh/storages/workspace.json`（工作区 sessionIds + archivedSessionIds）与各会话 projcache 元数据。会话文件位于 `~/.dsh/sessions/--Users-huageorge-Desktop-AI…--/<session-id>/session.v4.jsonl.zstd`。
> 另有重点会话派生的 teammate/子会话（s1 6 个、s2 8 个），未列入本表（它们属于对应重点会话的执行细节）。

| # | 日期 | 会话标题 | session id | 大小 | 归档 |
|---|---|---|---|---|---|
| 1 | 10-15 16:39 | M4 | session-4f9a2f7d-7a32-4dbb-b173-f2e0a19b4e7e | 5.3 MB | 是 |
| 2 | 10-15 17:32 | 研究想法与MVP定义指导 | session-4fbcfd05-f810-418d-9217-5126e92863d2 | 0.9 MB | 是 |
| 3 | 10-18 16:49 | M1、4、5、Lead | session-cb06ee4c-9f02-4f6a-ae1f-a8dec70eadaa | 23.5 MB |  |
| 4 | 10-22 16:56 |  | session-42f57a46-993e-4e6a-ab18-d2592e66333c | 0.0 MB |  |
| 5 | 10-22 16:57 |  | session-1edb1a82-1c98-4cdb-be98-473a7d9249a2 | 0.0 MB |  |
| 6 | 10-22 16:57 |  | session-2f54838b-4a96-4e84-b5df-9ea123bf6a10 | 0.0 MB |  |
| 7 | 10-22 16:57 |  | session-f48df004-7ad1-4d0d-9692-1caa99dc796f | 0.0 MB |  |
| 8 | 10-22 16:57 |  | session-ff9c020b-24f5-45e7-b28d-84fc87088f48 | 0.0 MB |  |
| 9 | 10-22 16:58 |  | session-a1cdccb9-13a9-4baf-9cce-bdb13ed9017b | 0.0 MB |  |
| 10 | 10-22 16:58 |  | session-ba1995bd-e93f-4c1a-9af4-fadef17bca20 | 0.0 MB |  |
| 11 | 10-22 16:58 |  | session-b67c86c7-be92-49ed-9275-89f7aa8c584a | 0.0 MB |  |
| 12 | 10-23 13:41 |  | session-3327ffaa-ba4a-40e1-a7f5-93c41a796974 | 0.0 MB |  |
| 13 | 10-23 13:41 |  | session-aff70696-52b9-4fd6-8fdf-8e47fe52002b | 0.0 MB |  |
| 14 | 10-23 13:41 |  | session-3d349441-1fae-4b87-81af-efe7d8ee7619 | 0.0 MB |  |
| 15 | 10-23 13:41 |  | session-729f766f-d482-4662-8234-ce87f32b30a3 | 0.0 MB |  |
| 16 | 10-23 13:41 |  | session-474688b9-b282-4c7f-8684-578e4d021092 | 0.0 MB |  |
| 17 | 11-05 22:03 | M1 | session-3342aabf-8de2-47b0-a406-cc28aee1e6b6 | 7.4 MB | 是 |
| 18 | 11-05 22:52 | Lead | session-07d5319d-849b-4010-ab03-56e75f073a93 | 1.0 MB | 是 |
| 19 | 11-06 16:05 | M1 partial 语义并入 canonical | session-e44273d9-2b8f-46e2-a134-08036408c95e | 0.8 MB | 是 |
| 20 | 11-06 16:10 | M1任务：partial 与 canonical 关系 | session-38221d41-2ec1-4cd6-ba33-2c31575baebd | 0.7 MB | 是 |
| 21 | 11-06 17:38 |  | session-caf358f3-d3b9-479b-a1ce-8c7808795dc4 | 0.0 MB |  |
| 22 | 11-06 18:00 | 查询GitHub上传地址及T8.3说明 | session-217a1378-36d1-4953-a06c-8055ee15a70c | 1.2 MB | 是 |
| 23 | 11-08 19:11 | 迁移项目成果至DeepWorks平台 | session-5a19b610-b3d6-4686-8878-f753735acef0 | 3.3 MB |  |
| 24 | 11-09 20:28 |  | session-a50c362f-1f66-425e-bac1-f099dfcb5085 | 0.0 MB |  |
| 25 | 11-09 20:47 |  | session-ad717231-eaa8-4239-bf0e-6d58301e2613 | 0.0 MB |  |
| 26 | 11-09 20:47 |  | session-c20f3715-dfd8-4d2d-b0ee-dec5f8e7781b | 0.0 MB |  |
| 27 | 11-11 22:20 | 计划服务未接通原因排查 | session-190e48d8-781e-4a0e-8a00-44509a99c6f3 | 15.2 MB |  |
| 28 | 11-12 19:55 |  | session-892c4d59-7434-453a-8f22-d727b1a13201 | 0.0 MB |  |
| 29 | 11-12 19:55 |  | session-1309dc6c-cabf-4be7-8daf-d183d878b454 | 0.0 MB |  |
| 30 | 11-12 19:55 | CGC 克隆用途与替代方案 | session-04d75281-29c2-4c30-b390-de7926582ef3 | 1.2 MB |  |
| 31 | 11-12 22:52 |  | session-5bdf6473-ebe6-4ebc-bd3c-806ae9f23485 | 0.0 MB |  |
| 32 | 11-12 22:52 |  | session-8152265e-ad2d-4dba-b1b2-880800559103 | 0.0 MB |  |
| 33 | 11-12 22:52 | 生成虚拟机任务压缩包 | session-7c2cc0ef-0a28-40a8-b85e-d535532fd395 | 4.0 MB |  |
| 34 | 11-12 23:00 | Fix CI and AI review milestone | session-336db26b-2de0-45d5-8a42-23312679a40b | 2.3 MB |  |
| 35 | 11-13 15:15 | **结论：v3 的内容层面可以通 | session-ce323436-b85b-4619-88ec-6773a916ad3e | 1.8 MB |  |
| 36 | 11-13 16:15 | Linux 虚拟机验证漏洞修复-1 | session-879cc62f-ff8b-476f-b06b-9e5f24ef1a28 | 16.6 MB |  |
| 37 | 11-14 15:12 | 全类型二进制修复-1 | session-b139b586-985b-475c-af5a-1ee7f0082668 | 13.6 MB |  |
| 38 | 11-16 08:06 | 项目会话回顾与任务汇总 | session-791a36c4-b1f8-40c3-bf76-2cc9aca07842 | 1.4 MB |  |

> 说明：空标题/0.0 MB 的会话是"打开后未发消息"的空会话（10-22/10-23/11-06/11-09/11-12），不影响项目结论；7 个已归档会话均已被本次回顾覆盖（M4、研究想法与MVP定义、M1、Lead、M1 partial、M1任务、查询GitHub/T8.3）。

## 附录 B：关键 commit / CI / tag 索引

### B.1 两个重点会话的关键 commit

| 阶段 | 分支 | commit | 说明 |
|---|---|---|---|
| v6.1 docs | handoff-v4-local | `3d5d0f0` | v6.1 交付证据补齐（11-13 16:44） |
| v5 任意二进制 | feature/universal-repair | `915f362` → `47465e0` → `f65c2dc` → `72db891` | 初始/补齐/最终 |
| 两条 AI 路径（第一代） | feature/ai-binary-repair | `abeab27` → `6d525ca` | ai_plan / ai_bytes |
| 两条 AI 路径（第二代） | feature/ai-binary-repair | `61287fd` → `aa45b36` | asm_roundtrip / binary_direct |
| PoC 差分/gate 盲区 | workbench-v3 | `455011f` / `60362a9` | 真实 provider 3/6 vs baseline 6/6 |
| 硬案例基准 | workbench-v3 | `0adcd68` | baseline 0/2、AI 1/2 |
| 公平性消融 | workbench-v3 | `eb1f0a4` / `853dd04` | target AI 6/10、blind 0 |
| 12 案/7 家族 | workbench-v3 | `bf5da88` / `ab679ef` | UAF/heap 探针 |
| Ghidra 工具链 | workbench-v3 | `6a12bb8` | JDK25 + Ghidra 12.2 |
| 4 模型矩阵 | workbench-v3 | `c3dae2f` | flash/v4-pro 6/12，Qwen 0/12 |
| Errno/Path B | workbench-v3 | `5f9dd77` | strace errno 代理、Path B 0 vs 0 |
| P0–P4 | workbench-v3 | `2739ead` | injection retry、auto symbols、ld_preload |
| 3/3 非 loop | workbench-v3 | `a8934fe` | 3 个非 loop AI VERIFIED |
| P5–P9 | workbench-v3 | `bd9cbf6` | native feedback、v2、4/6 |
| P10–P15 | workbench-v3 | `dad21c9` | assembly feedback、36 次 19/36、hidden CWE-476 |
| P16–P20 | workbench-v3 | `c5d87b5` | 6 verified/1 rejected/3 not_run |
| P16-R | workbench-v3 | `106d1cd` | 严格路径 0 verified |
| P16-R2 | workbench-v3 | `085fc38` | 真实 patch plan；ABI 仍 fail |
| P16-R3 | workbench-v3 | `f42e6c4` | PT_LOAD 映射；7 verified/1 rejected/2 missing |
| P21–P24（session1 终态） | feature/ai-binary-repair = workbench-v3 | `a1755a5` | 冻结 profile/artifact audit/smoke |
| marcx 修复（原始隔离） | backup/capacity-86587da | `86587da` | capacity 引擎 + 证据包（非 mainline 祖先；本次已归档） |
| gap 审计 | workbench-v3 / coverage-audit | `090ad94` | 66 gaps、marcx 21/21 |
| 覆盖收尾 | workbench-v3 | `0aa9f54` | target scope、legacy 收敛 |
| 全覆盖阶段 3 | workbench-v3 | `956ee10` / `725e7bb` | 67 gaps、205 cells |
| 阶段 4/5 | workbench-v3 | `f65ed53` / `640d08a` / `fd6ca41` | 68 gaps、240 cells、11/11→12/12 |
| 真实 CI + evidence | release/2026-11-16-final | `a8934fe` | 13/13 nightly + hosted CI |
| Phase-7 | release/2026-11-15-autonomy-final | `2bfa112` | Autonomy Foundation |
| Phase-8A | release/2026-11-16-phase8a-final | `bd9cbf6` | readiness/GT v1/verifier MVP |
| Phase-8B | release/2026-11-16-phase8b-final | `227f45b` | verifier semantics + 2 verified |
| Phase-8C（最终 mainline） | workbench-v3 / release/2026-11-16-phase8c-final | `4a7b235` | GT v2 / hidden / 13/13 |
| Phase-8C evidence tip | release/2026-11-16-phase8c-evidence | `ec503e4` | post-tag evidence addendum |

### B.2 关键 CI run 索引

| 阶段 | run id（结论） |
|---|---|
| v7 handoff 证据链 | 43390831537 = e1756a2 success |
| v5 任意二进制 | 43411767923 / 43412399232 / 43412905037 success |
| 第一代两条 AI 路径 | 43418024120 / 43418615884 / 43421560913 success |
| 第二代两条 AI 路径 | 43426508766 / 43427654178 success |
| PoC 差分/gate 盲区 | 43435227438 / 43436452584 success |
| 硬案例基准 | 43457857951 / 43458988294 success |
| 公平性消融 | 43555871445 / 43556499270 / 43559328831 success |
| 12 案/7 家族 | 43560207206 success |
| provider profiles | 43563347462 / 43565353034 success |
| Ghidra | 43570678371 success |
| 双模型矩阵 | 43573457659 success |
| Path A / 范式 A | 43579784063 / 43582808690 success |
| symbol resolver / 合并 | 43589156716 / 43589863303 / 43601736542 success |
| errno/Path B | 43608147997 success |
| P0–P4 | 43614759619 / 43616285244 success |
| 3/3 非 loop | 43628367481 / 43628367473 success |
| P5–P9 | 43687651300 / 43687651314 success |
| P10–P15 | 43695637933 / 43695637887 success |
| P16–P20 | 43703724955 / 43703724942 success |
| P16-R | 43707923361 / 43707923227 success |
| P16-R2 | 43713295997 / 43713296021 success |
| P16-R3 | 43723326346 / 43723326360 success |
| P21–P24 | 43729513475 / 43729513476 success |
| 阶段 7（真实 CI） | 43626323294 / 43628367481 / 43628367473 success |
| Phase-8A | 43687651314 / 43687651300 success |
| Phase-8B | 43718302033 / 43718302188 success |
| Phase-8C | 43744573286 / 43744573230 success（gated code SHA）；43748886046 / 43748886289 success（最终 release SHA） |

> 会话一分析的独立复核：45/45 CI run 经 GitHub API 核对 run id/head_sha/head_branch/conclusion 一致（全部 success）；s2 分析另按阶段核对了 8 组真实 CI run。

### B.3 关键 tag / evidence 分支（两个会话，共 14 个 tag + 23 个分支）

| tag | 指向（peeled） | 说明 |
|---|---|---|
| `release-2026-11-14` | cdeab74 | 12/12 gate（已归档为历史） |
| `release-2026-11-14-evidence` | 9cfaaa | 11-14 evidence bundle |
| `release-2026-11-15` | fd6ca41 | 12/12 最终 mainline |
| `release-2026-11-15-evidence` | 028d709 | 11-15 evidence bundle |
| `release-2026-11-16` | a8934fe | 13/13 + 真实 hosted CI |
| `release-2026-11-16-evidence` | d4aeee | 11-16 evidence bundle |
| `release-2026-11-15-autonomy` | 2bfa112 | Phase-7 |
| `release-2026-11-15-autonomy-evidence` | 37994eb | Phase-7 evidence |
| `release-2026-11-16-phase8a` | bd9cbf6 | Phase-8A |
| `release-2026-11-16-phase8a-evidence` | 0a095c5 | Phase-8A evidence |
| `release-2026-11-16-phase8b` | 227f45b | Phase-8B |
| `release-2026-11-16-phase8b-evidence` | 528304a | Phase-8B evidence |
| `release-2026-11-16-phase8c` | 4a7b235 | Phase-8C（最终 mainline） |
| `release-2026-11-16-phase8c-evidence` | ec503e4 | Phase-8C evidence |

## 附录 C：关键证据文件索引（仓库内）

| 证据 | 路径 |
|---|---|
| 最终发布 claims | `docs/status/claims.json` |
| 限制总表 | `docs/acceptance/LIMITATIONS.md`、`docs/limitations.md` |
| Phase-8C release note | `docs/release-2026-11-16-phase8c.md`、`docs/release-phase8c-final-evidence-2026-11-16.md` |
| Phase-8B release note | `docs/release-2026-11-16-phase8b.md`、`docs/release-phase8b-final-evidence-2026-11-16.md` |
| Phase-8A release note | `docs/release-2026-11-16-phase8a.md` |
| 能力缺口审计 | `artifacts/capability-gap-audit-2026-11-14/{coverage-matrix.json,gap-report.md,SHA256SUMS}` |
| 覆盖收尾验收 | `artifacts/coverage-closure-2026-11-14/acceptance.json` |
| Phase-8A | `artifacts/phase8-readiness-2026-11-16/`、`benchmark/phase8-v1/manifest.json`、`artifacts/phase8-verification-2026-11-16/` |
| Phase-8B | `artifacts/phase8b-baseline-2026-11-16/`、`artifacts/phase8b-benchmark-2026-11-16/results.json` |
| Phase-8C | `benchmark/phase8c/{manifest.json,results.json,hidden-commitment.json}`、`artifacts/phase8c-*/` |
| 17 份合同 | `contracts/*.schema.json`、`artifacts/contract-fixtures-2026-11-16/SHA256SUMS` |
| 验收模型审计 | `artifacts/acceptance-model-audit-2026-11-16/report.json` |
| 能力宇宙 | `artifacts/capability-universe-2026-11-16/dimension-registry.json` |
| Gap Registry | `artifacts/gap-registry-2026-11-16/{gaps.json,candidates.json}` |
| Reflection | `artifacts/autonomous-reflection-2026-11-16/reflection.json` |
| release gate 证据 | `artifacts/release-gate-2026-11-16-phase8c/`、`artifacts/release-gate-2026-11-16-phase8b/`、`artifacts/release-gate-2026-11-16-phase8a/`、`artifacts/release-gate-2026-11-16/`、`artifacts/release-gate-2026-11-15/`、`artifacts/release-gate-2026-11-15-autonomy/`、`artifacts/release-gate-2026-11-14/` |
| marcx 一手证据（本次归档） | `artifacts/marcx-repair-2026-11-14/`、`artifacts/marcx-capacity-gui-2026-11-14/` |
| 会话一 v7 检验 | 工作区 `handoff/final-verification-2026-11-13/FINAL-LINUX-VERIFICATION.md`、`audit-evidence.md`、`audit-claims.md` |
| 会话一 P16-R3 | `docs/acceptance/p16-r3-2026-11-16.md`、`artifacts/independent-verification-p16r3-2026-11-16/README.md` |
| 会话一冻结 profile | `experiments/p21-p16r3-658ff8c/profile.json`、`artifacts/p22-artifact-audit-2026-11-16/audit.json` |

## 附录 D：术语表

| 术语 | 含义 |
|---|---|
| **disposition / outcome** | 处置结论：`verified_patch` / `static_only_patch` / `analysis_only` / `unsupported` / `rejected` / `invalid`；验收引擎的 outcome：`success_within_scope` / `inconclusive` / `rejected` / `unsupported` / `error` / `cancelled` |
| **V0–V5** | 验证阶梯：V0 结构/契约、V1 编译、V2 接口/语义、V3 运行、V4 符号/模型级、V5 重放/可复现 |
| **gate** | 确定性验收引擎；AI 不能提升其结论 |
| **evidence profile** | `strict_template / emulated_instruction / native_poc / native_poc_rewrite` |
| **not_run / unavailable** | 不可用/未运行；永远不等于 pass |
| **false_verified** | 声称 verified 但独立验证不通过的数量；必须为 0 |
| **independent verifier** | 从原始/候选字节独立重算事实的验证器；不读生成器 verdict |
| **patch plan / patch-plan** | 补丁布局计划（write/insert/replace、cave、relocation、associated change、authorization） |
| **CaveABIBlock** | 代码洞的 ABI 证据块（入口/出口语义 ret/tail_jump/continuation_jump/noreturn、寄存器/栈约束） |
| **RepairSpec v1/v2** | 结构化修复规格（漏洞/程序上下文/安全不变量/修复/ABI/验证） |
| **Ground Truth v1/v2** | 基准样本契约（binary sha/format/arch/oracle/reference fix/expected behavior） |
| **hidden benchmark** | 私有评估语料；不参与训练/调参；只公开 commitment + aggregate |
| **capability universe** | 20 维 × 240 cells 的能力空间枚举；unknown=0 仅代表当前枚举 |
| **Gap Registry** | 统一缺口记录（candidate/open/blocked/non_goal/resolved/rejected） |
| **Reflection Engine** | 12 问反思；`verified=false` 恒成立 |
| **release gate 13/13** | 本地 frozen-tree nightly 的 13 项 required checks |
| **provenance / evidence branch** | 发布证据与分支/tag 强绑定；drift checker 校验 |
| **ready / implemented（readiness）** | 探针级工程证据（code+test+artifact），不是能力晋级 |
| **M1–M5** | 五名成员角色（不是里程碑） |
| **T8.3** | CWE-416 第二类样本任务；11-07 以 124 success_within_scope 收口 |
| **F1** | v7 交付件记录的 legacy ELF x86-64 fail-open 已知缺陷 |
| **12 non-goals** | 已产品化的研究/平台非目标（owner/复审 2027-02-14/毕业路径） |

