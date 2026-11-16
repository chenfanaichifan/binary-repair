# BinaryRepair 产品定位与边界（2026-11-17）

> 版本：v0.1（M3 产品化，P0-1 首增量）
> 状态：**内部产品定位文档**，用于对齐交付/演示/客户沟通口径；不是对外销售承诺。
> 事实来源：`docs/status/claims.json`、`docs/acceptance/LIMITATIONS.md`、`benchmark/phase8c/results.json`、`artifacts/phase8c-*/**`、`docs/consolidation/PROJECT-MASTER-REPORT-2026-11-16.md`。
> 冲突处理：本文件与 `claims.json` / `LIMITATIONS.md` 冲突时，**以后两者为准并立即修正本文件**。

## 0. 一句话定位

> **BinaryRepair = 有界二进制修复 + 可审计证据包。**
> 输入「一个已知漏洞点 + 一个二进制」，输出「一个 target 函数的候选补丁 + 可复现 PoC/回归差分 + 独立验证证据」，
> 拒绝时不产出字节、不伪造成功。**不是**任意二进制、任意漏洞、whole-program 的通用修复，也不是漏洞挖掘器。

**产品口径纪律（所有材料强制执行）**：

1. 任何产品/客户材料必须写明：**公开 benchmark 2/24 verified（8.3%）、hidden 0/8 verified**；
2. 禁止出现「任意二进制」「100% 修复」「通用修复」「保证安全」等表述；
3. 能力数字只能引用 `claims.json` / `LIMITATIONS.md` 已发布的数字，不得自行估算或外推；
4. 未运行项必须显式写 `not_run` + 原因，不得用「已完成」掩盖。

## 1. 客户与场景（ICP）

### 1.1 谁最需要（按痛点排序）

| # | 客户/场景 | 痛点 | 本产品能提供 | 不能提供 |
|---|---|---|---|---|
| 1 | **无源码 / 第三方二进制供应链**（采购的 COTS 组件、闭源 SDK、供应商不再维护的库） | 拿到 CVE 通告或渗透报告，但**没有源码无法重编译**，只能等厂商或整包替换 | 对已知 sink 的 target 函数做**有界候选补丁** + PoC 差分证据，供安全团队评审 | 全量供应链扫描、未知漏洞发现 |
| 2 | **遗留系统 / EOL 二进制**（工具链丢失、构建环境不可复现） | 有源码也编不出来；补丁窗口极短 | 直接对二进制做候选修复；证据包可用于变更评审 | 全程序等价证明、跨函数大改 |
| 3 | **CVE 应急修复 / 临时缓解**（明确 CVE + 明确 sink，要求小时级） | 厂商补丁未发布；需要先缓解 | 单函数/单 sink 的确定性修复尝试 + 证据；失败时给出 `analysis_only`/`unsupported` 结论 | SLA 级「一定修好」承诺 |
| 4 | **安全研究 / 合规审计 / 红队演练** | 需要可复现、可审计的修补证据链，而不是口头结论 | 证据包：original/candidate SHA256、patch plan、gate 检查表、独立验证器报告、PoC/回归结果、limitations、not_run | 形式化证明、第三方认证 |

### 1.2 明确不适用的场景（销售/试用前置过滤）

- **未知漏洞挖掘 / 扫描器用途**：detection 仅 **3/24（12.5%）**，定位/根因同为 3/24；本产品要求**用户给定目标函数/sink**，不做发现；
- **whole-program 证明 / 形式化等价**：验证范围是「一个函数 + 给定 PoC/回归用例」，见 LIMITATIONS §1/§9；
- **任意架构 / 任意容器**：矩阵外架构（arm32、riscv、mips、ppc、大端、32-bit Mach-O、fat Mach-O 回写）只分析不改写；
- **UAF、`sprintf` 格式串扩展、整数缺陷、循环缺陷、混淆/内联拷贝**：确定性引擎为 `analysis_only`（AI 路径仅有研究证据，非产品能力）；
- **多函数/整镜像自动修复**：一次候选只修 **一个 target 函数/sink**，其余仅报告为限制；
- **要求「修复后二进制可安全上生产」的合规签字**：LIMITATIONS §9 明确不做该声明；
- **需要独立二人复核的合规流程**：本交付的 M4 验证与 Lead 批准为同一操作者（角色分离，非独立双人复核，LIMITATIONS §4）。

## 2. 产品承诺（可交付的最小单元）

**一次修复交付 = 1 个 target 函数/sink 的候选补丁 + 可复现 PoC/回归差分 + 可审计证据包。**

| 交付字段 | 内容 | 生成方式 |
|---|---|---|
| disposition | `verified_patch` / `static_only_patch`(opt-in, 未验证) / `analysis_only` / `unsupported` / `rejected` / `invalid` | 确定性统一 gate（唯一验收权威） |
| candidate bytes | 仅当 gate 通过且独立验证器复核通过才可下载 | `repair_any` + writer |
| patch plan | 布局、cave、关联变更（容量消息等）、ABI block | 引擎生成、独立验证器重放校验 |
| PoC / 回归差分 | original fails / candidate passes + 回归用例输出一致 | `poc_runner`（guest/Lima/Unicorn 按平台） |
| 独立验证报告 | 9 项 required checks（身份、重解析、动作重放、scope、关联变更授权、cave 可执行/重定向、relocation、ABI、oracle） | `app/services/independent_verifier.py`（不读生成器 verdict） |
| 证据索引 | 每个文件的 SHA256（original/candidate/plan/report/results） | `scripts/run_repair_benchmark.py` 同构证据布局 |
| limitations + not_run | 本用例的限制、未运行项及原因 | 引擎 + 验证器 + 宿主探测 |

**三条不可协商的产品行为（由代码强制，不是营销话术）**：

1. **失败/不确定不产出可下载字节**：无 PoC/无运行时证据时 fail-closed（`not_run`/`inconclusive`），不 success、不下载；
2. **生成器永不自证**：确定性 gate 通过后，仍须独立验证器 `verified`；否则记 `false_verified`（必须为 0）并撤回声明；
3. **deterministic 路径无网络、无 API key**：产品演示与默认 CLI 不调用任何模型；AI 仅是可选的候选生成器，且永不拥有验收权。

## 3. 能力矩阵与 SLO

### 3.1 能力矩阵（当前真实边界）

| 输入族 | 支持级别 | 处置上限 | 可对客户承诺的内容 |
|---|---|---|---|
| ELF x86-64 / i386 / arm64 | 解析+改写 | `verified_patch`（gate+独立验证+oracle 通过时） | 「可尝试 target 级修复；结果以证据包为准」 |
| PE x86-64 / i386 / arm64 | 解析；x86-64/i386 改写 | 同上（PE 运行时证据为 Unicorn 指令级仿真，非 Windows 内核运行） | 同上，须注明仿真证据层级 |
| Mach-O thin little-endian x86-64 / arm64 | 解析+改写 | 同上；**仅 macOS 原生证据**，Linux 上 `not_verified` | 同上，须注明宿主平台 |
| ELF32 / PE32 i386 | 解析+改写 | 同上；32-bit cdecl push 参数模型，fail-closed | 同上 |
| fat Mach-O / 32-bit Mach-O / arm32 / riscv / mips / ppc / big-endian | 仅检测/分析 | `unsupported`（不回写） | 「不修复，仅报告」 |
| 非 ELF/PE/Mach-O（无法识别容器） | — | `invalid` | 「输入不被接受」 |
| 拷贝类 stack sink：`strcpy`/`strcat`/`stpcpy` guard；常量长度 `memcpy`/`memmove`/syscall 钳位 | 确定性模板 | `verified_patch` 可达 | 同上 |
| capacity-check 重复内联校验（marcx 类）等长原地重写 + `.rodata` 消息 | 确定性模板 | `verified_patch` 可达 | 同上 |
| 同函数 immediate heap 目标（`malloc/calloc` 立即数→目标） | 确定性模板 | `verified_patch` 可达；错误容量由运行时 oracle 拒绝 | 同上 |
| 全局目标 / 结构体成员容量 / 动态大小 / 跨函数别名 / 跨函数分配 | `analysis_only` | `analysis_only` | 「只分析、不给补丁」 |
| `sprintf` / UAF / 整数 / 循环 / 混淆内联拷贝 | `analysis_only`（AI 研究证据 ≠ 产品能力） | `analysis_only` | 「当前不修复」 |
| whole-image（无 target 声明） | 显式 opt-in | 标签 `target_policy=whole_image`，**永不声明 target 修复** | 「非 target 修复，不做归属声明」 |

补充约束（必须随矩阵一起出现）：
- **一次一个函数**：其他漏洞函数只报告为限制，不补丁；
- **容量语义**：容量 = 帧几何（`frame_top - destination`）或显式 `_chk`/立即数，不是 DWARF 对象大小；非帧顶缓冲可能被**高估**；
- **输入上限**：通用入口 ≤ 20 MiB（超限直接拒绝）；
- **平台差异**：Mach-O x86_64 外部 PoC 在 arm64 宿主不可用；PE/32-bit Mach-O 外部 PoC 不可用；这些情形按 `not_run`/不可用记录，永不伪造。

### 3.2 SLO：只承诺流程与证据，不承诺修复成功率

> **重要**：修复成功率实测为 **2/24 = 8.3%**（公开 benchmark），**hidden 0/8**。因此本产品**不提供**「修复成功」SLO；
> 只对可被代码强制、可被审计的**流程 SLO** 负责。

| SLO 项 | 承诺 | 强制点 | 状态 |
|---|---|---|---|
| 处置完整性 | 100% 的请求输出至少一个显式 disposition（无静默成功、无静默失败） | 统一 gate 返回枚举；`not_run` 必带原因 | 已实现（代码） |
| 验收独立性 | 任何 `verified` 必须来自独立验证器 `decision=verified`；生成器 verdict 不被接受 | `independent_verifier` + `false_verified` 断言 | 已实现（代码） |
| fail-closed | 无 PoC/运行时证据 → 不 success、不产出可下载字节 | 证据 profile gate | 已实现（代码） |
| 证据完整性 | 每次修复产出 original/candidate SHA256、patch plan、检查表、验证器报告、limitations、not_run | 报告与证据 bundle 结构 | 已实现（代码） |
| 演示可复现 | 确定性演示路径**无 API key、无外网**；失败显式 | `scripts/product/demo_repair.py` + `tools/product/run-demo.sh` | 本任务实现并验收 |
| 演示时长 | 3 个 fixture 的 demo 在 10 分钟内跑完（目标；以实测记录为准） | `run-demo.sh` 输出 elapsed | 待实测记录（`artifacts/m3-product-2026-11-17/`） |
| 修复成功率 | **不承诺**；按 benchmark 报告当前 2/24、hidden 0/8 | — | 明确不承诺 |

## 4. 不可承诺清单（逐条引用，禁止改写）

### 4.1 当前 phase 的 `not_claimed`（`claims.json.phase8c_ground_truth.not_claimed`，原文）

- `hidden material availability or distribution`
- `hidden generalisation or independently verified hidden repairs`
- `new vulnerability-repair capability`
- `automatic upgrade or capability promotion`
- `arbitrary binary/vulnerability/whole-program repair`
- `cross-compiler verification with a second toolchain`
- `Phase-8D open-world discovery or Acceptance 2.0`
- `Phase-9-16 semantic/repair/reflection expansion`

### 4.2 `LIMITATIONS.md` 中与产品承诺直接相关的条目（原文摘引）

- §1：`V4 is a typed symbolic claim over the target function. It is not binary-level symbolic execution and not a whole-program proof.` … `the binary-level claim is not made.`
- §2：`Coverage is a bounded fixture/matrix, not arbitrary binaries`；`this is still not evidence that arbitrary binaries, other architectures, other compilers, stripped production binaries, or client binaries work.`
- §4：`The verification row and approval row were signed by the same operator. This is role-separated, not independent two-person review.`
- §6：`V5 is build/replay reproducibility. It does not prove repaired behaviour.`
- §8：`This is a course/MVP deliverable, not a supported commercial vulnerability remediation service.`
- §9（节选）：`it is still not universal vulnerability repair`；`a candidate repairs one function per run`；`report v4 dispositions are bounded claims: no whole-program proof, no arbitrary-vulnerability discovery, no claim that a repaired binary is safe for production use.`
- §12（AI）：`The two AI direct-binary paths prove protocol/validator/writeback/gate integration with a scripted client.` … `no AI increment is measured`；`Real-LLM quality, a gate-blind increment suite and PoC-based evaluation remain future work; AI never owns acceptance.`
- §19：`it does not prove full side-effect equivalence (buffered I/O, errno, libc state); no-PoC assembly paths remain a known blind spot.`
- §21：`Global destinations, dynamic sizes, pointer+offset aliases and cross-function allocations stay analysis-only.`；`the legacy quick-repair gate refuses external PoC evidence`；`Mach-O x86_64 external PoC remains unavailable on an arm64 host; PE and 32-bit Mach-O external PoC are unavailable by design.`

### 4.3 `claims.json.explicitly_unimplemented` 中必须对客户明示的项（原文摘引）

- `sprintf/format-expansion, UAF/lifetime and integer/loop deterministic repair templates (no deterministic engine; AI path research only, non-loop AI verified 0/6)`
- `whole-program proof: verification is scoped to the supplied PoC/regression cases and the one repaired function, not the whole binary`
- `external-PoC replay for PE and 32-bit Mach-O; Mach-O x86_64 external PoC on arm64 hosts (native function-level Unicorn/emulation remains the only tier there)`
- `global destination and struct-member bounds inference`
- `multi-provider/multi-model statistics and independent-case confidence intervals; target/PoC/contract product API; puts side-effect gate`
- `register/stack native trace (gdb unavailable)` / `AFL/fuzzing campaign`

### 4.4 未运行（not_run）清单（产品材料必须显式列出）

| 项 | 状态 | 原因 |
|---|---|---|
| self-hosted Lima nightly | `not_run` | 无 self-hosted runner；仅有本机 frozen-tree nightly gate（`claims.json.ci_evidence.self_hosted_nightly`） |
| 国际 5–6 模型矩阵 | `not_run`（blocked） | SiliconFlow 国际余额不足 HTTP 402；无第 5 provider key |
| external ingestion（外部语料/数据集） | `not_run` | 未提供本地外部语料；CI 不做网络摄取 |
| hidden 泛化 | `not_run` | hidden 私有材料不下发；仅发布 opaque commitment + aggregate（0/8 verified） |
| GDB / 原生 register-stack trace | `not_run` | `gdb unavailable` |
| AFL / fuzzing campaign | `not_run` | 未开展 |
| Phase-8D / 13–16 自主化设施 | `not_run`（降级） | 组长决议：能力与产品优先 |

## 5. 与竞品/替代方案的定位差异

> 说明：以下为**公开定位层面的事实差异**，**未做同类产品实测对比（not_run）**；不构成竞品评测，不贬低任何方案。
> 任何销售材料不得编造竞品价格/性能数据。

| 替代方案 | 公开事实 | 与本产品的差异 | 本产品的劣势（诚实） |
|---|---|---|---|
| 手工反汇编 + 专家打补丁 | 由安全专家在 Ghidra/IDA 中定位并改写指令 | 我们把「有界缺陷类」的定位/改写/验收/证据流水线化；证据可复现、可审计 | 专家能处理更复杂/未知缺陷；我们只覆盖矩阵内缺陷类，且仍需人工评审候选 |
| 源码级修复（厂商补丁 / 重编译） | 有源码时最可靠、可全量测试 | 我们面向**无源码**场景；有源码时不应替代源码修复 | 无源码修复无法做全量回归；证据只覆盖给定 PoC/回归 |
| angr（开源符号执行框架） | 面向符号执行/程序分析的通用框架 | 我们不把符号执行作为产品能力；我们的验收是确定性 gate + 独立验证器 + PoC 差分 | 分析深度远不及专用符号执行；detection 仅 3/24，不能当扫描器 |
| Patcherex2（二进制重写框架） | 提供二进制重写/重汇编能力 | 我们内置「缺陷类→补丁模板→gate→证据」的端到端链路，且失败 fail-closed | 重写覆盖面远小于通用重写框架；矩阵外只分析 |
| Ghidra 工作流（脚本/插件） | 分析平台 + 可扩展脚本 | 我们要求显式 target 与 PoC/回归，并输出可审计证据包 | 灵活性与交互分析能力不如 Ghidra；我们是流水线不是平台 |
| 商业二进制热补丁 / 虚拟补丁（WAF、运行期内存补丁） | 通常运行期生效（内存/网络层），不改变磁盘二进制 | 我们产出**离线候选字节 + 可复现差分 + 证据包**，可进入客户变更评审 | 无商业产品实测数据；无运行期防护/虚拟补丁能力；不承诺生产可用 |

**与 AI 编码/修复工具的关系**：AI 在本产品中是**候选生成器**（`asm_roundtrip` / `binary_direct`），验收权属于确定性 gate 与独立验证器；
当前 AI 证据为：3/3 非 loop 硬案例仅单模型（deepseek-flash；同 12-case 非 loop 合计 3/6，v4-pro 0/3），4 模型 pooled 36/96（Wilson 95% CI [0.285, 0.475]），
**不构成通用 AI 修复能力声明**；AI 增量未被测量（LIMITATIONS §12）。

## 6. 数字口径速查（所有材料引用同一组）

| 指标 | 值 | 来源 |
|---|---|---|
| 公开 benchmark verified | **2/24 = 8.3%**（eligible repair cases 24） | `benchmark/phase8c/results.json`、`claims.json.phase8c_ground_truth.public_benchmark` |
| 公开 benchmark detection / root-cause / localization | **3/24 (12.5%)** 各 | 同上 |
| 公开样本总规模 | 32（30 executed / 2 unsupported；dev 18 / validation 14；24 runtime-oracle + 8 analysis-only） | 同上 |
| false_verified（公开） | **0**；1 个 deterministic claim 被独立验证器拒绝并撤回（heap-malloc） | 同上 |
| hidden verified | **0/8**（8/8 executed；0 candidate；0 false_verified；hidden_available=false） | `claims.json.phase8c_ground_truth.hidden_benchmark` |
| 非 loop AI 硬案例 | 3/3（单模型 deepseek-flash；12-case 非 loop 合计 3/6；v4-pro 0/3） | 组长复核 §1.5.2、`claims.json` |
| AI 模型矩阵 | 4 模型 / 2 provider；pooled AI-target 36/96 = 0.375（CI [0.285, 0.475]） | `claims.json.provider_coverage.ai_target_pooled` |
| 确定性 target-strict baseline | 0/12 verified（12/12 期望匹配） | 同上 |
| 验证权威 | 确定性统一 gate + 独立验证器（9 项 required checks）；不是 whole-program/形式化证明 | `claims.json.phase8b_verifier_semantics` |
| 运行时证据层级 | native Linux / macOS、qemu、Lima、Unicorn 指令级仿真（非内核运行） | `claims.json`、LIMITATIONS §9 |

## 7. 口径纪律检查清单（发布前逐条打勾）

- [ ] 文中出现「公开 2/24（8.3%）」与「hidden 0/8」；
- [ ] 无「任意二进制 / 100% / 通用修复 / 保证安全」字样；
- [ ] 所有 not_run 项显式列出并带原因；
- [ ] 能力描述与 `claims.json` / `LIMITATIONS.md` 逐条一致（发现冲突先修文档并报 Lead）；
- [ ] 未使用未经验证的市场/竞品数据；
- [ ] 客户可见材料不含任何 API key、内部路径或未脱敏凭据（用 `tools/handoff/scan-secrets.sh` 复核）。

---

变更记录：
- 2026-11-17 v0.1：初稿（M3 P0-1）。事实口径锁定至 Phase-8C；产品化设计（demo/报告模板/部署/试用）见同目录其余文档。
