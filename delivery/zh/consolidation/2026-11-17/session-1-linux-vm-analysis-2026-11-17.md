# 01 · 会话一（session-879cc62f）逐阶段考古与最终卡点分析

- 会话 id：`session-879cc62f-ff8b-476f-b06b-9e5f24ef1a28`
- 标题（会话自带）：`Linux 虚拟机验证漏洞修复`（`session:879cc62f#seq=17 @11-13 16:16`）
- 时间：`2026-11-13 16:15:49` 创建 → `2026-11-17 00:46:14` 最后事件（`#seq=19987`），wall clock ≈ 80.5 h
- 规模：**19 989** 条事件；**36 个 turn**；2 654 tool/result、2 567 tool/call、310 user/message、87 compaction/prune、8 次 compaction
- 模型：`deepseek-account / deepseek-flash`，`reasoningEffort=max`（`#seq=12 @11-13 16:16`）
- 解析方法：`zstd -dc session.v4.jsonl.zstd > /tmp/rev01/s1.jsonl`（66.9 MB 明文），Python 分片流式统计；未修改任何会话文件。
- 证据指针约定：`s#seq @时间` 表示本会话事件序号与时间（Asia/Singapore，11-14 19:11 前记录为 +08:00 上海，之后为 +08:00 新加坡，同一时区）；`repo@<sha> path` 表示仓库提交证据。

---

## 1. 用户原始指令（去重、按 turn）

35 条"人味"消息中，**只有 15 条是用户本人下发的指令**，其余 20 条是用户把**外部组长（评审者）的技术长文**整段粘贴回来当输入。区分这两类很关键：后者的结论不能算"用户需求"，但它是本项目实际的需求驱动力。

### 1.1 用户本人指令（15 条，含 plan-mode 提交）

| # | turn | 时间 | 指令（原文摘要） | 性质 |
|---|---|---|---|---|
| U1 | 1 | 11-13 16:16 | 「需要 linux 虚拟机最后检验 @方法建议_…20261113(1).md」 | 验收 handoff v7 |
| U2 | 2 | 11-13 17:09 | 「请一次性实现修复任意二进制文件这一功能」 | 功能需求（v5） |
| U3 | 3 | 11-13 18:13 | 「请问…修复任意二进制文件…是否已经完成，若未完成，请继续完成，直到成功为止…最终返回百分百完成的成果，然后将所有成果推送仓库」 | 完成+推送（v5 收口） |
| U4 | 4 | 11-13 18:58 | 「请完成对任意二进制文件在二进制层面的直接修复…无需转换成汇编然后再反编译，最终形成两条 AI 自动修二进制文件的路径」 | 功能需求（v6 两条路径） |
| U5 | 6 | 11-13 20:06 | 「请重新审查这个项目我们最初所设定的目标」+ 重申两条路径定义（第一条：ELF→汇编→修复→装回；第二条：ELF→不转汇编→二进制层直接改） | 需求纠偏（促成 `asm_roundtrip`/`binary_direct`） |
| U6 | 10 | 11-13 22:23 | 「这是组长所有的反馈，我已打开所有权限，请直接代理我的电脑…保证百分百成功率…如果有实在没法解决的问题，请详细罗列」 | 授权+继续 |
| U7 | 15 | 11-14 13:08 | 「@方法建议… 组长的建议，请严格按顺序全部完成，继续突破」 | 按外部清单执行 |
| U8 | 16 | 11-14 13:27 | 「先将已完成所有成果推送仓库，而后沿用已经建立固定的网页让我先测试一下效果」 | 推送+固定 Web 入口（8124） |
| U9 | 19 | 11-14 14:59 | 提供 API key `[REDACTED]`，要求在 M2 Mac 上装 JDK+Ghidra 并跑通 | 环境/凭证 |
| U10 | 20 | 11-14 15:37 | 提供新 API key `[REDACTED]`，「请继续跑通所有任务，实现突破」 | 凭证 |
| U11 | 27 | 11-15 01:10 | 粘贴「最终目标推断、问题总表与完整解决方案」（26 KB） | 外部方案 |
| U12 | 28 | 11-15 12:32 | 粘贴「最新阶段综合评估 + 3/3 非 loop PASS 后的定位升级」（19 KB） | 外部方案 |
| U13 | 29 | 11-15 15:18 | 粘贴「P0–P4、P5–P9 诊断与路线」（14 KB） | 外部方案 |
| U14 | 30 | 11-15 17:11 | 粘贴「P0–P15 全面总结」（28 KB） | 外部方案 |
| U15 | 36 | 11-16 22:38 | 粘贴「下一阶段总体解决方案：以 OpenRouter 为统一入口、Ollama 本地、统一 LLM Gateway、独立 Verifier 为唯一验收权威」（24 KB，含 P31–P40 与 Phase-8C/8D 要求） | 外部方案（本会话最后一轮的任务书） |

> 说明：U11–U15 在会话里都是 `user/message`，但文体是外部评审文档（"我建议你…"），非用户口语；把它们计入"用户指令"会高估用户参与度。真正的**内生需求**只有 U1–U10。

另外有 4 个 turn（7、9、16、17…）是用户对后台任务失败/网页重启的**单点追问**，不含新需求；4 次 `/plan` 命令（`s#seq=1308/3302/6591/9776/14287/15380/16432/17312/18151/18474/18901`）把长文以 plan 模式提交。

### 1.2 被转贴的外部"组长"结论（关键约束来源）

`s#seq=5084 @11-13 19:42`、`#seq=6110 @21:05`、`#seq=6720 @22:30`、`#seq=7329 @23:40`、`#seq=7771 @11-14 11:47`、`#seq=8160 @12:48`、`#seq=8688 @13:31`、`#seq=8956 @14:07` 等，反复给出同一组判断，并被本会话接受为验收口径：

1. "100%"只能指**批准计划的完成度**，不能指"任意二进制修复"；
2. `asm_roundtrip` 仍属 B 家族（汇编级），**不等于**范式 A（反编译 C→LLM 补丁→二进制感知重编译）；
3. 增量必须用"确定性 baseline 修不了、AI 能修"的硬案例测，否则 coverage increment 恒为 0；
4. provider 必须校验 `resp.model == requested`（防"模型缩水"）。

---

## 2. 36 个 turn → 阶段总表（可核验交付）

| turn | 时间窗 | 阶段目标 | 交付 commit / 产物 | 测试 | CI | 状态 |
|---:|---|---|---|---|---|---|
| 1 | 11-13 16:16–17:06 | handoff **v7** Linux VM 终检 | `BinaryRepair-Linux-Handoff-2026-11-13-v7.zip`（60 488 092 B，sha256 `2afeb6c8…fcc8`） | 950 collected / 943 passed / 7 skipped | 43390831537 = `e1756a2` | ✅ 完成（v6.1 `3d5d0f0` 判 superseded） |
| 2 | 17:09–18:08 | **v5 任意二进制修复**（i386 引擎+运行时+UI，3 子 Agent） | `915f362`（68 files，+8531/−316） | 1014 / 0 fail（mac+Linux） | 未触发（未 push） | ✅ 代码完成 |
| 3 | 18:13–18:58 | v5 收口 G1–G5 + 推送 | `47465e0`→`f65c2dc`→`72db891` | 1039 / 0 fail | 43412905037 | ✅ 推送 |
| 4 | 18:58–19:42 | **v6 两条 AI 直接二进制路径**（`ai_plan`/`ai_bytes`） | `abeab27`→`6d525ca` | 1118 / 0 fail | 43418615884 | ✅ 推送 |
| 5 | 19:42–20:06 | 按组长意见修正文案/证据口径 | `af8f674` | 1119 / 0 fail | 43421560913 | ✅ 推送 |
| 6 | 20:06–20:51 | 按用户 U5 重做为 **`asm_roundtrip` + `binary_direct`** | `61287fd`→`aa45b36` | 1128 / 0 fail | 43427654178 | ✅ 11 条正向证据 |
| 7/9 | 20:56 / 22:06 | 后台 GitHub 轮询器 403 限流答疑 | — | — | — | ✅ 无代码变更 |
| 8 | 21:05–21:56 | 真实 provider 首测 + gate 盲区 + PoC 差分进 gate | `60362a9`→`455011f` | 1133 / 0 fail | 43436452584 | ⚠️ 增量 0，盲区 4/5 |
| 10 | 22:23–22:27 | 只出「一次性执行计划」（W0–W6），无代码 | — | — | — | 📄 仅文档 |
| 11 | 22:30–23:28 | PoC/回归 gate、10k 鲁棒性、静态语法门禁、CI 证据核验 | `2fb9317`→`54b575f` | 1141 / 0 fail | 43451324919 | ✅ |
| 12 | 23:40–00:14 | 硬案例基准（2 案） | `4ee5e5d`→`0adcd68` | 1143 / 0 fail | 43458988294 | ✅ 增量 1（0/2→1/2） |
| 13 | 11-14 11:47–12:32 | 公平性消融 + 10 案 | `853dd04`→`eb1f0a4` | 1143 | 43556499270 | ✅ 消融：0/0/0 vs 6 |
| 14 | 12:48–13:08 | UAF 探针（第 11 案） | `24f8e2b`→`ab679ef` | 1143 | 43559328831 | ⚠️ UAF 0/1 |
| 15 | 13:08–13:19 | 扩到 12 案 / 7 家族（heap-canary） | `afb1e85`→`bf5da88` | 1143 | 43560207206 | ⚠️ 非 loop 0/6 |
| 16 | 13:27–13:31 | 推送 + 重启固定网页 8124 | `e5f731c` | — | 复用前次 | ✅ |
| 17 | 13:31–13:57 | 三 provider profile + 严格 model identity | `91e4706`→`afe4aee` | 1149 | 43563347462 | ✅ 探针证实缩水 |
| 18 | 14:07–14:21 | 多模型操作清单 | `4349a92`→`14971d9` | 1149 | 43565353034 | ✅ |
| 19 | 14:59–15:28 | **JDK25 + Ghidra 12.2 装上 M2**（无 sudo 方案） | `6a12bb8`→`c0dbd0d` | 1149 | 43570678371 | ✅ 三平台 key 全 401 |
| 20 | 15:37–16:04 | 有效 DeepSeek key → 2 模型 ×3 次 | `fd205dc` | 1149 | 43573457659 | ✅ loop 6/6，非 loop 0/6 |
| 21 | 16:10–17:25 | `86587da` 隔离 + Path A call 白名单 + 范式 A **loop** 闭环 | `148df69`→`d69c84b` | 1155 | 43579784063 | ✅ loop A 6/6 |
| 22 | 17:39–18:05 | **CWE121 非 loop 范式 A 闭环**（首个） | `fa80f50`→`12d05ec` | 1155 | 43582808690 | ✅ 2/2 PoC+4/4 reg |
| 23 | 18:27–19:24 | symbol_resolver 固化 + SiliconFlow 国际站 402 | `8dc9c85`→`6afe122` | 1160 | 43589156716 | ⚠️ key 有效但余额不足 |
| 24 | 19:34–20:28 | **4 模型真实矩阵**（CN 免费 key） | `c3dae2f` | 1161 | 无 CI（workflow 不覆盖 feature） | ✅ 6/6/0/0 |
| 25 | 20:30–22:01 | rebase→workbench FF 合并 + 修 CI | `7a5d21f`→`6cc51d3` | 1314 | 43601736542 | ✅ 合并 |
| 26 | 22:06–23:19 | errno 代理 + Path B context A/B + 符号黑名单 | `5f9dd77`→`c8af199` | 1518 | 43608147997 | ⚠️ A/B 0 vs 0 |
| 27 | 23:27–11-15 00:49 | P0–P4：ud2 归因、auto symbols、ld_preload errno | `f2392fd`→`2739ead` | 1626 | 43614759619/43616285244 | ⚠️ 非 loop 仍 0 |
| 28 | 01:10–03:01 | **3/3 非 loop AI VERIFIED**（cave relocation 根因） | `12945c3`→`a8934fe` | 1641 | 43628367481/473 | ✅ 转折点 |
| 29 | 11-15 12:32–15:10 | P5–P9：native feedback、RepairSpec v2、跨二进制 benchmark | `bd9cbf6` | 1954 | 43687651300/314 | ⚠️ 4/6，P9 partial |
| 30 | 15:18–16:54 | P10–P15：assembly feedback、**36 次稳定性**、v2 真链、8 二进制 7 CWE、hidden CWE-476 | `dad21c9` | 1966 | 43695637933/887 | ⚠️ 19/36=52.8% |
| 31 | 17:11–18:37 | P16–P20 | `c5d87b5` | 1966 | 43703724955/942 | ⚠️ 6/1/3；P18 not completed |
| 32 | 18:55–19:52 | P16-R–P20-R | `106d1cd` | 2041 | 43707923361/227 | ❌ 严格路径 0 verified |
| 33 | 20:03–20:38 | P16-R2–P20-R2 | `085fc38` | 2041 | 43713295997/021 | ⚠️ CWE-122 过 5 项，ABI 失败 |
| 34 | 21:01–22:33 | **P16-R3：PT_LOAD 统一映射 → 7/10 verified** | `f42e6c4` | 2044 | 43723326346/360 | ✅ 严格路径突破 |
| 35 | 22:42–23:39 | P21–P24：冻结 profile、artifact 审计、稳定 runner、统计工具 | `a1755a5` | 2048 | 43729513475/476 | ⚠️ 60-run 未跑 |
| 36 | 11-16 22:38–11-17 00:46 | **P31–P34：统一 LLM Gateway / OpenRouter+Ollama / 凭证 preflight / stability runner 加固** | `a0e6a24`(feature 线) + `e01fc9e`→`d37bfad`(workbench 线) + `a9db731`→`c0f9feb`(final 线) | 2411 / 0 fail | 43907136876/267 | ⚠️ P31/P34 完成，P32/P33 LIVE_NOT_RUN |

---

## 3. 分阶段详述

### 3.1 M1–M5 / 四成员：**本会话未执行，只是背景**

会话里 `M1`–`M5` 全部出现在**读取既有文档/代码**的上下文（`s#seq=55/107/1376/1412/2079/2160/2696/4193`），例如 `M4 verifier and Lead approver are the same operator`、`M2-MERGE-REPORT.md`、`M5 provider shape: chat_json`。仓库侧对应证据：`repo@38dd93d docs(handoff): record four-member execution status, integrations and blocked items`（2026-11-16 12:17）、分支 `canonical/m1-m5-integration@3a107ab`、`m5/*`。

结论：**M1–M5 与"四成员"是 11-13 之前的历史里程碑**（handoff 线），本会话起点是它们的产物 v7 的终检；"四成员任务分配"是**另一个会话（791a）**的动作，不要记到本会话头上。

### 3.2 v4→v7 handoff 线（turn 1）

- v7 是把 v6 修好重打包：修 8 类问题（umask 002 导致 938/7/5 failed、3 个嵌套 `SHA256SUMS` 失配、2 处用户名/临时路径泄露、时间戳矛盾、patches 清单错、CGC 表述过度、2 个解压副本与 `.DS_Store`、中文名无 UTF-8 标志）。
- 终态：Linux VM（Ubuntu 24.04 arm64 + qemu-x86_64，全新解压+全新 venv）**950/943/7/0**；`run-smoke.sh` PASS；zip SHA256 + 2227 行 SHA256SUMS + 29/29 嵌套清单 + `verify-package` 全 PASS。
- 并行会话产出 v6.1（`3d5d0f0`、CI 43395652244），同环境复跑 **938/7/5 failed**，判 superseded 并归档。
- 残留风险（包内已记录）：F1 legacy ELF x86-64 验证失败仍可能返回候选（fail-open，冻结源码未改）；CGC `basic_messaging` replay 跨次不稳定（4 次中 1 次触发），降级 exploratory。
- 证据：`s#seq=1304 @11-13 17:06`。

### 3.3 v5「任意二进制修复」（turn 2–3）

- 一次性实现：统一入口 `/binary` + `/api/binary/{scan,repair,matrix}` + `scripts/repair_binary.py` 共用 `repair_any`，报告 schema v4；处置枚举 `verified_patch / static_only_patch / not_verified / analysis_only / unsupported / rejected / invalid`。
- 新增 i386 全链：`analyzer_i386`（cdecl push 参数、容量=帧顶−目标）、`cdecl_x86` guard 机器码、ELF32 `PT_LOAD` / PE32 `.brfix` 注入、`E8`/`FF15` 调用解析、Unicorn x86-32 运行时（tier `emulated_run`，engine `unicorn-i386`）。
- **消除历史 fail-open**：ELF x86-64 gate 失败不再保留可下载候选。
- turn 3 补齐 5 个缺口：动态 ELF32（PLT）、PE32 `FF15` 直调 IAT、i386 memcpy 立即数 64→16、ELF32 `extend-rx` fallback、fat Mach-O/大端输入显式 `analysis_only`/`unsupported`。
- 安全策略：**每候选只修一个函数/一个 sink**。
- 证据：`s#seq=3298 @11-13 18:08`、`s#seq=4180 @18:58`；提交 `repo@915f362`、`repo@72db891`。

### 3.4 v6 两条 AI 路径，再到产品口径的 `asm_roundtrip` / `binary_direct`（turn 4–6）

| 版本 | 路径 | 机制 | 结局 |
|---|---|---|---|
| v6 初版 | `ai_plan` | AI 只输出 `{sink_index, strategy}`，确定性 writer 写字节（AI 看不到原始字节） | 6 个 verified，但**候选 SHA256 与 v5 确定性 baseline 完全相同**，`same_candidate_as_deterministic=true` → 只证明链路，`coverage increment=0` |
| v6 初版 | `ai_bytes` | AI 直出机器码/就地字节，Capstone 白名单校验后写回 | 同上；新增 `buffer_match` 拒掉"单条 `ret`"空 guard |
| v6.2 | `asm_roundtrip` | Capstone 反汇编 → AI 改汇编 → 宿主 clang 汇编回机器码 → 注入新块 + 入口重定向（仅 ELF i386/x86_64/arm64） | 11 条正向证据（含 Mach-O native、PE arm64） |
| v6.2 | `binary_direct` | 原 `ai_bytes` 改名，不产汇编文本 | 同上 |

- turn 5 的三处纠偏（用户/组长共同要求）：把"100%"改写为"批准计划内确定性矩阵 100%"、把 v5 定性为"确定性引擎扩展而非 AI 修复证明"、把"PoC 失效判据未进 gate"写进 `LIMITATIONS.md` §11。
- 同时澄清一个假故障：macOS `test_static_routeb_bundle` 失败根因是**缺 GNU readelf**（只剩 objdump，views=1），装 Homebrew binutils 后解决；stock macOS 仍会复现，属环境依赖。
- 证据：`s#seq=5078/5337/6087 @11-13 19:42–20:51`；`repo@6d525ca`、`repo@af8f674`、`repo@aa45b36`。

### 3.5 从"堆验证设施"转向"测 AI 增量"（turn 8–15）

这是全会话方法论转折，外部评审连续 3 轮施压（"验证基础设施循环"）后被接受。

1. **turn 8 首次真实 provider**：6 任务（3 asm + 3 direct），AI **3/6** vs 确定性 **6/6**，**increment 0**；3 个失败原因如实记录（runtime gate 拒、注入块含 `call`、块尾 `mov` fall-through）。
2. **gate 盲区实验**：5 个"结构合法语义错"候选，**抓住 4 个**；残留 1 个 = `asm_roundtrip` 省略原 `puts` 副作用仍能过内存安全 gate。
3. **PoC 进 gate**：新增 `poc.original_fails` / `poc.candidate_passes`，函数级 runtime 差分；真实 native PoC manifest（`fixtures/poc/elf-x86_64-strcpy.json`，64/256 B 使原二进制 SIGSEGV）。
4. **turn 12 硬案例首个正增量**：`inline-byte-loop`（手写内联拷贝，无 `strcpy`，analyzer 看不见 sink）→ baseline `rejected`，AI 44 字节汇编 + `new-pt-load` 注入 → native PoC 原崩/候选 exit 0 → **baseline 0/2、AI 1/2、增量 1**；同时保留 `cwe121-unchecked-strcpy` 失败（AI 汇编含 `call`，被 leaf-only validator 拒）。
5. **turn 13 公平性消融**（本项目最规范的一次实验）：确定性盲跑 **0/10**、确定性+target/capacity 提示 **0/10**、AI 盲跑 **0/10**、AI+target `full`/`generic`/`none` 均 **6/10**（7 次重复稳定）。
   - 可声称：定位必要（盲跑 0）、生成能力真实（target-aware 确定性 0）、契约详细度效应 **0**。
   - 不可声称：6 个成功全是同一"内联字节拷贝循环"家族的 6 个变体（loop8/16/32/64、reverse），**不是 6 个独立硬案例**。
6. **turn 14/15 家族扩到 12 案 / 7 家族**：新增 UAF no-input（`stdout_hex` + 空 regression，原始残留 `04050a`）与 heap-canary（同分配块 guard 破坏 → 原进程 exit 1 / `HEAP GUARD CORRUPT`）。结果 **loop 6/6，非 loop 0/6**（CWE121、multicall、sprintf、nonconst、UAF、heap 全 0）。
7. **turn 14 的关键负结果**：尝试改模型名仍返回同一 `deepseek-flash` → 证明当时 provider 是"单模型 endpoint"，无视 `model` 参数。这直接催生 turn 17 的严格身份校验。

### 3.6 凭证与环境：从"不可执行"到"4 模型矩阵"（turn 17–25）

| 阶段 | 事件 | 结果 |
|---|---|---|
| turn 17 | 加 SiliconFlow / DashScope profile + `model_identity_ok` + `BINARYREPAIR_STRICT_MODEL_IDENTITY` | 探针：`deepseek:deepseek-chat` → 实际 `deepseek-flash`，`identity_mismatch`；`deepseek-flash` → ok |
| turn 19 | 用户给的 key 在 SiliconFlow/DashScope/DeepSeek **全部 401** | 未跑矩阵（不伪造） |
| turn 19 | JDK 25.0.5 + Ghidra 12.2 用户级免 sudo 安装；官方 zip **缺 macOS arm64 原生 decompiler**，用自带 gradle `buildNatives` 构建成功（1m11s）；headless 反编译 `vuln_copy` PASS（122 chars, entry `0102bab4`） | 范式 A 前置条件就绪 |
| turn 20 | 有效 DeepSeek key（存在 `var/assistant.key` 0600，git-ignored）→ 2 模型 ×3 次 ×12 案 | flash 6/12、v4-pro 6/12，identity 100% |
| turn 23 | SiliconFlow **国际站** key 有效（`/v1/models` 200、identity 三模型全对），但 benchmark 全 **402 余额不足** | 4–6 模型被余额阻断 |
| turn 24 | 换 **中国站免费** key（`.cn` 端点） | **4 模型真实矩阵**：flash 6/12、v4-pro 6/12、Qwen3-8B **0/12**、Qwen2.5-7B **0/12**；GLM-Z1 identity probe 超时未纳入 |
| turn 25 | feature rebase → workbench **fast-forward** 合并 | `6cc51d3`，CI 43601736542 green；同时修 2 个环境相关测试（x86_64 native tier、Mach-O Rosetta） |

`deepseek-v4-pro` 在 turn 28 之后的 ABI 管线里反而 **0/3**（ABI fatal / plan 空 / 非法 `call 0x0`），即"Pro 不一定更强"，这是后话。

### 3.7 范式 A：从 loop 到非 loop，再到 3/3（turn 21–28）

1. **turn 21 loop A 闭环**：Ghidra 导 C → 归一化 → DeepSeek 生成修复 C → **Patcherex2 0.2.14 `ModifyFunctionPatch`** 回填 → 六用例 oracle：未改 C roundtrip **6/6 PASS**、LLM 修复 C **6/6 PASS**。
   - 同期 Path A（放宽 call 白名单）**没有**把非 loop 拉起来（0/6），`heap-canary` 出现"安全 PoC 过、短输入 stdout regression 失败"的部分信号。
2. **turn 22 首个非 loop A 闭环（CWE121）**：目标 ELF 根本没有 `fputs/exit/strlen` import，改用**人工审查的 syscall helper `br_fail()`**（x86-64 `write`+`exit`）+ `symbols={"printLine":0x401380}` → `status=pass`，**2/2 PoC + 4/4 regression**，fixed sha256 `463a9758…636f`。
3. **turn 23 把 helper 固化为 `routeb/symbol_resolver.py`**：已有符号复用 / 补丁自定义跳过 / `write|exit` 注入 syscall stub / 未知语义（如 `strlen`）**fail closed**；CLI `--resolve-gaps`。
4. **turn 24–26 模板扩容与黑名单**：纯函数模板 `strlen/memcpy/memset/strcat/atoi`；`fputs(x,stderr)→br_fputs`；`malloc/calloc/realloc/free` 改为**动态依赖白名单**（目标 ELF 有 PLT 才放行）；`fork/execve/system/popen/dlopen` **绝对拒绝**。
5. **turn 27 `ud2` 归因**：`hard-multicall` 的 `no_candidate` 真因不是符号/空间，而是 assembly validator 拒 `ud2`；改为 typed 归因 + 一次 validator-feedback 重试（**不自动改写 `ud2`**）→ 注入成功（`new-pt-load`、81 B、2 个 call relocation），native gate 从 `no_candidate` 变 `fail`。
6. **turn 28 三连破（3/3 非 loop AI VERIFIED）**：四个真实工程根因被逐个拆掉：
   - **cave relocation 用 section 映射而非 PT_LOAD**：cave VA `0x10cf000` 落在 `.tbss` 虚拟范围，写入被映射到 NOBITS 位置，真正执行的 cave 里两个 call 仍是 `e8 00 00 00 00`（call next instruction）；
   - **缺结构化 RepairSpec 时模型不写边界检查**（只"复制+canary"）；
   - **`hard-sprintf` 的 `^` 是绝对地址标签**（`jne 0x102cc32` + `0x102cc32:`），assembler 拒绝；
   - **ABI 检查器是线性栈跟踪**，把两个等价 epilogue 误报 `rsp_not_restored` → 改 **CFG-aware worklist**。
   结果：`hard-multicall` `aab33ae…5b84`、`hard-sprintf` `ea83b59…0583`、`hard-nonconst` `2e12599…a2b3` 全部 AI VERIFIED（overflow PoC 原崩/候选 exit 0、regression `hi\n` 保持、ABI `ok=true fatal=0`）。

### 3.8 P5–P24：从"能修 3 例"到"可测量、可审计"（turn 29–35）

| 阶段 | 关键新增 | 硬数字 | 诚实边界 |
|---|---|---|---|
| P5 | Native semantic feedback retry | `hard-sprintf` 首轮 fail → 反馈 → 二轮 PASS，两轮产物都保留，重试硬上限 3 | 只反馈 exit/signal/stdout/stderr/ABI，无寄存器/栈 diff；timeout 不重试 |
| P6 | RepairSpec v2（`vulnerability/program_context/security_invariants/repair/abi/verification`），v1 兼容 | 解析/校验完成 | 真实成功实验仍以 v1 为主，"v2 落地"≠"v2 已证明" |
| P7 | 跨二进制跨 CWE benchmark（4 二进制 / 3 CWE） | **4/6**，其中 `cwe122-heap-copy` 是**未见二进制** VERIFIED | CWE-121 security fail、CWE-787 assembly rejected |
| P8 | `run_model_qualification.py` | flash 2/6、v4-pro 2/6，**成功集合不同** | 小样本，随机性明显 |
| P9 | `repair_evidence.py`（bundle v2 + SHA256SUMS + tamper check） | 单次可复现 | **3 次重复稳定性实验未做** → P9 = partial |
| P10 | assembly policy + diagnostics + feedback（带行列号的 typed 诊断） | CWE-787 改本地标签后 **native VERIFIED** | 反馈重试最多 2 轮，不自动改写模型汇编 |
| P11 | **36 次独立稳定性**（2 模型×6 案×3 次） | **19/36 = 52.8%**；flash 12/18、v4-pro 7/18；CWE-122/CWE-787 **6/6**、CWE-121 **0/6** | 单一 hard-case binary 家族，非跨二进制 |
| P12 | RepairSpec v2 真链（plan→assembly→ABI→injection→PoC→VERIFIED） | CWE-787 完整走通，产 `plan/assembly/candidate_sha256` | 只 1 个 case |
| P13 | 扩到 **8 二进制 / 10 案 / 7 CWE** + dev/hidden split | 首次 **hidden CWE-476 VERIFIED**；CWE-125/190 dev VERIFIED；CWE-134 PLAN_INVALID | hidden 只有 1 例成功，不能外推 |
| P14 | `native_trace.py` N1–N6 结构 | N1/N2 实现 | Linux guest `gdb: not available` → N3–N6 `not_run` |
| P15 | 确定性 mutation plan 生成器（固定 seed/count） | 有测试 | **无 AFL campaign、无符号执行** |
| P16 | `verify_repair_benchmark.py` 独立验证 | 6 verified / 1 rejected / 3 not_run | 非 8/8；not_run 来自 artifact 缺失 |
| P16-R | 支持 resize patch plan | **0 verified / 8 rejected / 2 not_run** | 暴露 4 类真缺陷：`authorization_ref` 缺失、cave ABI 推导错、target scope 组合失败、artifact 缺失 |
| P16-R2 | 用真实 `build_patch_plan`，不伪造授权 | CWE-122 过 layout/action/scope/oracle/independence 五项 | 仍 `abi failed: no_ret / branch_target_unknown` |
| **P16-R3** | **`elf_mapping.py`：只经 PT_LOAD 做 VA↔offset 映射**（6 种状态分类）+ cave ABI block 走 PT_LOAD | **7 verified / 1 rejected / 2 ARTIFACT_MISSING**；CWE-122 六项全过 | 未完成：`CaveABIBlock` 的 tail_jump/continuation 出口语义、policy-issued Authorization Record |
| P21 | `freeze_experiment.py` 冻结 profile | `p21-p16r3-658ff8c`：`verifier_profile=P16R3_PLAN_AWARE`、`authorization_profile=STATIC_REFERENCE_ONLY`、`semantic_trace=NOT_RUN`、`fuzzing=NOT_RUN` | 冻结的是 `658ff8c`（含 P21/P22 脚本），非纯 `f42e6c4` |
| P22 | `audit_artifacts.py` | **8 RECOVERED_HISTORICAL / 2 ARTIFACT_MISSING**（CWE-787、CWE-134） | 不用新候选替换历史 artifact |
| P23 | stability runner 改走独立 verifier + `run-manifest.json` | smoke 1 例（`hard-multicall`→`PLAN_INVALID`）；完整 60 次**启动后在第一个 case 后因 live provider 延迟被停** | partial 明确标注"这不是 60-run 结果" |
| P24 | `summarize_stability.py`（`R_verified`/`R_robustness`/status counts） | 工具+测试完成 | 无完整矩阵 → 无正式报告 |
| P25–P30 | — | — | 全部未实现，原因：P25/P26 需新 verifier profile（不污染 P21 冻结）、P27/P28 需专项模型运行、P29 无 GDB、P30 无 AFL |

### 3.9 P31–P34（turn 36，最后一轮）

- 组织方式：一次 `collab_fanout` 派出 **6 个子 Agent**（`s#seq=19382 @11-16 22:38`，子会话 `51d2fd7c/6850f239/bfdd3a3d/978ac2c0/628458cf/4c44ab6e`）。
- 新增 `app/services/llm_gateway/`：`base.py`（统一 request/result/model identity）、`client.py`（`LLMGateway.generate()`、provider 选择、严格身份、`gateway_from_env`）、`providers/{openrouter,ollama,mock}.py`、`credentials.py`、`errors.py`、`usage.py`；接入 `assistant_llm.py`、`binaryrepair_ai/{settings,client}.py`、`ai_binary_repair.py`，保留旧 `chat_json`/`client_from_env()` 兼容路径。
- `scripts/run_model_preflight.py` 实测：Mock → `CONFIGURED`；OpenRouter 无 key → `BLOCKED` + `ConfigurationError`。
- `scripts/run_stability_matrix.py` 加固：终态只认 independent verifier（不用 `candidate.gate`），区分 `verified/PLAN_INVALID/NO_CANDIDATE/ARTIFACT_MISSING/VERIFIER_ERROR/TIMEOUT`，捕获 `subprocess.TimeoutExpired`，记录 `expected/started/completed/eligible_runs`，原子写 `checkpoint.json`，支持 `--resume/--fresh`。
- 测试：`test_llm_gateway_integration.py` 9 passed、`test_llm_gateway_credentials.py` 15 passed（`httpx.MockTransport`，无真实网络）、`test_stability_matrix_hardening.py` 6 passed；workbench 全量 **2411 / 0 failed / 0 error / 9 skipped / 1015.7 s**。
- 真实调用状态：**OpenRouter live = NOT_RUN、Ollama live = NOT_RUN**（无 key、无 Ollama 服务）；**P35 60-run = NOT RUN/BLOCKED**；**P36–P40 = NOT STARTED**（CaveABIBlock / Authorization / CWE-121 / CWE-134 / GDB+AFL++）。
- 证据：`s#seq=19985 @11-17 00:46`（完整最终报告，4 844 字符）。

---

## 4. 明确完成项（代码/测试/证据三证齐全）

| 项 | 证据 |
|---|---|
| handoff v7 终检通过（943 passed，包完整性 2227/2227） | `s#seq=1304`；`handoff/BinaryRepair-Linux-Handoff-2026-11-13-v7.zip` |
| v5 确定性矩阵（ELF/PE/Mach-O × x86_64/arm64 + ELF32/PE32 i386）+ 每候选单函数 | `repo@72db891`；`docs/acceptance/binary-universal-v5-2026-11-13.md` |
| 两条产品路径 `asm_roundtrip` / `binary_direct`（11 条正向 verified 证据） | `repo@aa45b36`；`artifacts/ai-direct-binary-2026-11-13/` |
| 真实 PoC + regression 进 gate（native 执行，非谓词） | `repo@54b575f`；`app/services/poc_runner.py`、`fixtures/poc/*.json` |
| 任意输入鲁棒性（500+ 变异输入全返回显式 disposition；修掉 `ELFParseError` 未捕获 bug） | `repo@54b575f`；`tests/test_input_robustness.py` |
| 静态语法门禁（BOM-aware AST/JSON/JS/HTML/shell，579→675 checked / 0 failures） | `scripts/check_static_syntax.py` |
| CI 证据自动核验 + `docs/status/claims.json` | `scripts/verify_ci_evidence.py` |
| 公平性消融（受控实验，7 次重复） | `artifacts/fairness-ablation-2026-11-14/aggregate.json` |
| 12 案 / 7 家族 benchmark（含 UAF no-input、heap-canary 的可观察行为 oracle） | `fixtures/hard-cases/cases.json` |
| JDK25 + Ghidra 12.2 在 M2 可用（含 arm64 原生 decompiler 自建） | `artifacts/ghidra-macos-2026-11-14/`、`scripts/install_ghidra_macos.sh` |
| 范式 A **loop** 闭环 6/6、**非 loop CWE121** 2/2 PoC+4/4 reg | `artifacts/paradigm-a-loop-2026-11-14/`、`artifacts/paradigm-a-cwe121-2026-11-14/` |
| `symbol_resolver`（纯函数模板 + syscall stub + 动态依赖白名单 + 危险调用绝对拒绝） | `repo@c8af199`、`repo@2739ead`；`routeb/symbol_resolver.py` |
| 3/3 非 loop AI VERIFIED（cave relocation PT_LOAD 修复 + RepairSpec + CFG-aware ABI） | `repo@a8934fe`；`artifacts/ai-repair-planning-2026-11-15/` |
| 36 次独立稳定性实测 19/36 | `artifacts/stability-2026-11-16/` |
| hidden CWE-476 AI VERIFIED（首个 hidden 成功） | `artifacts/repair-benchmark-expansion-2026-11-16/` |
| 独立 verifier 严格 7/10（PT_LOAD 统一映射） | `repo@f42e6c4`；`artifacts/independent-verification-p16r3-2026-11-16/` |
| P21 冻结 profile / P22 artifact 审计 8+2 | `experiments/p21-p16r3-658ff8c/profile.json`、`artifacts/p22-artifact-audit-2026-11-16/audit.json` |
| P31 统一 Gateway / P34 runner 加固（离线可测） | `repo@d37bfad`；`app/services/llm_gateway/`、`artifacts/p31-p34-2026-11-16/` |

---

## 5. 失败与负结果（全部被保留，未删改）

| # | 负结果 | 量化 | 证据 |
|---|---|---|---|
| N1 | 真实 provider 首测无增量 | AI 3/6 vs 确定性 6/6，increment **0** | `s#seq=6087 @11-13 20:51` |
| N2 | gate 语义盲区残留 1 个 | 4/5 抓住；`asm_roundtrip` 省略 `puts` 仍过内存安全 gate | `s#seq=6087` |
| N3 | `cwe121` 在 assembly 路径硬失败 | leaf-only validator 拒 `call`（`forbidden assembly construct: call`） | `s#seq=7764 @11-14 00:14` |
| N4 | 单模型 endpoint 无视 `model` | `deepseek-chat` → 实返 `deepseek-flash`，`identity_mismatch` | `s#seq=8949 @11-14 13:57` |
| N5 | 三平台 key 全 401 | SiliconFlow/DashScope/DeepSeek 均 401 | `s#seq=9541 @15:28` |
| N6 | SiliconFlow 国际站 402 | identity 3 模型全对，benchmark 全 `30001 balance insufficient`；免费小模型同样 402 | `s#seq=11748 @19:24` |
| N7 | Path A（放宽 call 白名单）无效 | 非 loop 仍 **0/6**；`heap-canary` 安全 PoC 过但 stdout regression fail | `s#seq=10847 @17:25` |
| N8 | Path B callee-context A/B 无提升 | 无 context 0/1、有 context 0/1（`accepted` 但 `no_candidate`） | `s#seq=13239 @23:19` |
| N9 | 小模型全挂 | Qwen3-8B 0/12、Qwen2.5-7B 0/12（真实免费调用，非 402） | `s#seq=12053 @20:28` |
| N10 | `deepseek-v4-pro` 在 ABI 管线退化 | RepairSpec+ABI 下 flash 3/3、**v4-pro 0/3**（ABI fatal、plan 空、非法 `call 0x0`） | `s#seq=15377 @11-15 03:01` |
| N11 | CWE-121 稳定失败 | 36 次里 **0/6**；真因 = candidate `stdout=""`+`exit 0`，而 PoC 契约要求 `exit 1`+精确 stderr | `s#seq=17305 @16:54`、`#seq=18898 @22:33` |
| N12 | CWE-134 规划层失败 | `PLAN_INVALID`（v2 一致性检查不过），多轮规范化未解决 | `s#seq=18471 @20:38` |
| N13 | P16-R 严格路径归零 | 0 verified / 8 rejected / 2 not_run | `s#seq=18148 @19:52` |
| N14 | 60 次稳定性从未完成 | P23 启动后第一个 case 后因 provider 延迟被停；P18/P18-R/P18-R2/P35 连续 4 轮 `NOT COMPLETED` | `s#seq=19352 @23:39`、`#seq=19985` |
| N15 | N3–N6 native trace 全程不可用 | Linux guest `gdb: not available`，只有 strace | 同上 |
| N16 | OpenRouter/Ollama 真实调用从未发生 | `LIVE NOT_RUN`（无 key / 无服务） | `s#seq=19985` |
| N17 | workbench 首次合并时 CI 失败 | 修掉 2 个环境相关测试：ELF x86_64 native tier 与 cell 声明不一致、Mach-O Rosetta 未模拟 engine ready | `s#seq=12593 @11-14 22:01` |
| N18 | 固定网页 token 明文外泄风险 | 8124 端口 URL 里带 `?token=[REDACTED]`，被写进对话与多份报告 | `s#seq=8682 @11-14 13:31` |

---

## 6. 未完成项（会话自述 + 我的核验）

| 项 | 会话自述状态 | 核验 |
|---|---|---|
| 范式 A 通用化（任意函数/跨二进制） | 只 loop 闭环 + CWE121 单点 | 一致；`route_a_patch.py` 依赖 auto symbols + 审查过的 glue |
| CWE-121 / CWE-134 | FAILED / negative retained | 一致；P27/P28 标 FAILED |
| 60 次稳定性矩阵 | NOT COMPLETED（P18/P35） | 一致；仅有 36 次（19/36）与 P23 partial |
| CaveABIBlock 完整出口语义 | NOT IMPLEMENTED（P25/P36） | 一致 |
| policy-issued Authorization Record | NOT IMPLEMENTED（P26/P37）；现为 `STATIC_REFERENCE_ONLY` | 一致 |
| GDB N3–N6 / AFL++ campaign | BLOCKED / NOT STARTED（P29/P30/P40） | 一致 |
| OpenRouter / Ollama live | LIVE NOT_RUN（P32/P33/P35） | 一致；preflight 仅 Mock + 无 key BLOCKED |
| target/PoC/contract 产品化 | 仍在 `scripts/run_hard_benchmark.py`，API/UI 仍要求 analyzer sink | 一致（turn 12/13/14 反复列为缺口） |
| 完整副作用等价（errno TLS/fd offset/malloc 内部状态/locale/锁） | 仅 stdout + 可选 syscall-errno / 进程退出 errno | 一致；`docs/limitations.md` |
| Phase-8C / Phase-8D | **本会话完全未执行** | 会话中 8C/8D 只出现在用户 turn 36 的输入文档里（`s#seq=19363`），无任何执行事件 |
| `final/consolidated-2026-11-16` 更新到 P31–P34 | 尝试失败，未强推 | 见 §7.3 |

---

## 7. 最后 turn 36 的"重复工具调用"卡点解剖

### 7.1 现象与量化

用户观察到的"循环"**不是模型自己空转重复同一条命令**，而是三段叠加的长等待：

| 指标 | 数值 | 证据 |
|---|---|---|
| turn 36 时长 | 22:38:42 → 00:46:14（**2 h 07 m**） | `s#seq=19359`、`#seq=19987` |
| tool/call 总数 | 67（bash 55、job_output 11、collab_fanout 1） | 统计 |
| 其中 job_output 阻塞时长 | 23:15→00:45 ≈ **90 min** | 见下表 |
| 全会话 job_output 阻塞总时长 | **≈ 1 499 min（25 h）**，占 80.5 h wall clock 的 ~31% | 逐条配对计算 |
| 完全相同参数的重复调用 | 2 对：`19570→19579`（job `bash-b6f347aa`）、`19953→19960`（job `bash-3a95be9b`） | `s#seq=19570/19579/19953/19960` |
| 反复"in_progress"输出 | job `bash-3a95be9b94f24972` 是 80 次迭代的 GitHub API 轮询循环，每 20 s 打印 `43907137267 in_progress / 43907136876 completed success` | `s#seq=19947/19954/19962` |
| 框架级"重复调用"告警 | 全会话 **5 次**：`#seq=3117 @11-13 18:00`、`#seq=15928 @11-15 13:41`、`#seq=17566 @17:42`、`#seq=18012 @19:47`、**`#seq=19967 @11-17 00:45`** | `user/message` 原文"That is repeating the exact same tool call with identical arguments" |
| turn 内重复度最高 | **turn 2**：273 calls、39 次重复、单条命令重复 **13 次**（反复 `pytest` 同一组用例） | 统计 |

### 7.2 卡住时正在做什么

- 正在等**两个 CI workflow 收尾**：`43907136876`（已 completed success）与 `43907137267`（长时间 in_progress），这是 P31–P34 的最终门禁。
- 等待期间模型把 `job_output(wait=true, timeout_ms=1800000)`（30 min）当轮询用；由于后台 job 是 `for i in $(seq 1 80); do curl …` 的轮询脚本，job 未结束前 `job_output` 只能返回 `(no new output) [status: running]`，于是出现"调用→无新输出→再调用"的外观。
- `00:45:47` 框架发出第 5 次重复告警（step 66）后，模型**换了命令**（`git fetch/status/rev-list` + GitHub API 取最近 3 个 run），循环即被打断；`00:45:57` 做最后一次 push 尝试；`00:46:14` turn 正常 `completed`。

**结论：这不是"模型死循环"，而是"把长轮询当同步等待"的效率缺陷 + 一个 CI run 特别慢（>20 min）**。会话是**正常结束**的（`turn/end reason=completed`），并且输出了完整的 4 844 字符最终报告（`s#seq=19985`）。

### 7.3 结束时真正失败的最后一个动作

```
s#seq=19978 @00:45:57  bash:
  git -C worktree-p31-ci merge-base --is-ancestor c0f9feb HEAD; echo anc=$?
  git push origin HEAD:final/consolidated-2026-11-16
s#seq=19981 @00:46:01  结果: "anc=1" + "hint: … fast-forwards" ← 非快进，push 被拒
```

模型在推理里明确写了"Not ancestor; don't force"（`s#seq=19985` 的 reasoning 段），最终报告写 `final/consolidated-2026-11-16 = c0f9feb（未强推，保留原分流）`。**这是正确的处置**（不强推历史分支），但留下一个真实的分叉：

### 7.4 三条并存的历史线（当前仓库实测）

| 线 | 头 | 时间 | 内容 | 上游 |
|---|---|---|---|---|
| `workbench-v3` = `feature/ai-binary-repair` = `release/2026-11-17-phase8d-final` | **`d37bfad`** | 11-17 00:24 | `e01fc9e`(P31–P34 cherry-pick) → 3 个 artifact/junit 提交 | ✅ 已 push |
| `final/consolidated-2026-11-16` | **`c0f9feb`** | 11-17 00:05 | `a9db731`(P31–P34) → provider coverage + full-suite | ✅ 已 push（但**不含** `996060d` 的 Phase-8D 提交） |
| feature-final 工作树 | **`a0e6a24`（孤儿）** | 11-16 23:30 | P31–P34 原始提交 | ❌ **无任何 ref 指向**，仅靠 `worktree-feature-final` 的 detached HEAD 保活 |

实测命令与结果：
```
git merge-base --is-ancestor 996060d c0f9feb → 1   # Phase-8D 提交不在 final 线
git merge-base --is-ancestor c0f9feb  d37bfad → 1   # final 线不是 workbench 线的祖先（故 push 被拒）
git for-each-ref --points-at a0e6a24 → 空           # 孤儿提交
```

### 7.5 并发真相：会话二在同一时刻推进同一分支

`d37bfad` 的父链是 `e01fc9e → 996060d docs(phase-8D)`（**996060d 时间戳 11-17 00:16:10，发生在 turn 36 进行中**），说明**另一个会话在 00:16 把 Phase-8D 提交推到 workbench-v3**，而 turn 36 在 00:24 在其上叠了 P31–P34 的 3 个提交。也就是说：

- 会话一**没有实现** Phase-8C/8D（只在 `s#seq=19363` 收到"之后还要完成 Phase-8C/8D"的指令）；
- 会话一最终的 `d37bfad` 是**骑在会话二的 Phase-8D 提交之上**的；
- 01:25:46 的 tag `release-2026-11-17-phase8d-final`（`19a91bc` → `d37bfad`）是**会话一结束 39 分钟后**由别的会话打的。

> 汇总时务必把这三件事分开归属，否则会把 Phase-8D 记到会话一，或把 tag 记到 P31–P34。

---

## 8. 未提交 / 未推送 / 未收尾产物清单

| # | 项 | 状态 | 风险 | 建议 |
|---|---|---|---|---|
| R1 | `a0e6a24`（feature 线 P31–P34 原始提交） | **孤儿提交，无 ref** | 一旦 `worktree-feature-final` 被 remove/prune，该提交不可达（内容虽已 cherry-pick 为 `e01fc9e`，但提交与 message 丢失） | 建 `backup/p31-p34-feature-a0e6a24` 分支或打 tag 固化 |
| R2 | `worktree-feature-final` | **detached HEAD**（`a0e6a24`） | 误操作 `git checkout` 后难找回 | 同上 |
| R3 | `worktree-p31-ci` | **detached HEAD**（`d37bfad`），工作树干净 | 无本地分支跟踪，`git pull` 语义缺失 | `git switch -c p31-ci-final d37bfad` 或保持并文档化 |
| R4 | `final/consolidated-2026-11-16` | 落后 workbench 线 3 个提交且**分叉**（缺 Phase-8D） | 两条"最终线"内容不同，验收时报哪个都可能被质疑 | 明确"唯一交付线 = workbench-v3"，或重建 final = d37bfad（需 force，须授权） |
| R5 | P35–P40 | 完全未执行 | 用户 turn 36 的任务书要求 P31–P40；只完成 P31–P34 | 在总报告里以 `BLOCKED/NOT_RUN` 明示 |
| R6 | OpenRouter/Ollama 真实凭证 | 未配置 | P32/P33 永远是 `LIVE_NOT_RUN` | 配 key 后先跑 `run_model_preflight.py` |
| R7 | 8124 固定网页 token | 明文出现在会话与多份报告 | 局域网内可复用 | 轮换 `var/lan.token`，历史报告脱敏 |
| R8 | 用户两次粘贴的 API key | 已进入会话日志（`s#seq=9123`、`#seq=9548`） | 凭证泄露面 | 全部标记 `[REDACTED]`，提示用户吊销/轮换 |
| R9 | `worktree-p31-final` | 在 `final/consolidated-2026-11-16`（`c0f9feb`）上 | 与 R4 同源 | 随 R4 一并处置 |
| R10 | 主仓 `binary-repair/` 工作树 | 停在 `member-5-deepseek-schema @221e47c` | 与当前交付线无关，易误判 | 文档化"该目录不是当前交付线" |

---

## 9. 逐阶段"目标 → 产出 → 判定"的一句话总结

1. **v7 handoff**：目标=可交付包；产出=943 passed + 2227/2227 清单；判定=**完成**。
2. **v5 任意二进制**：目标=任意输入有确定性结论；产出=i386 全链 + 7 种 disposition；判定=**完成（限确定性矩阵）**。
3. **v6 两条 AI 路径**：目标=AI 进生成回路；产出=6 条 verified 但候选与确定性相同；判定=**链路完成、增量未证明**。
4. **asm_roundtrip / binary_direct**：目标=按用户定义的两条路径；产出=11 条正向证据；判定=**完成（B 家族）**。
5. **硬案例 + 公平性消融**：目标=证明增量；产出=0/0/0 vs 6/10、增量 1；判定=**成立但单家族**。
6. **多模型矩阵**：目标=4–6 模型；产出=4 模型真实（6/6/0/0）；判定=**完成，且证明换模型救不了非 loop**。
7. **范式 A**：目标=C 级修复；产出=loop 6/6、CWE121 2/2+4/4、非 loop 3/3；判定=**单函数级成立，非通用**。
8. **P5–P24**：目标=可测量可审计；产出=36 次 19/36、hidden CWE-476、7/10 严格验证；判定=**测量体系完成，能力仍 53%**。
9. **P31–P34**：目标=统一调用层 + runner 加固；产出=Gateway + 4 adapter + preflight + checkpoint；判定=**离线完成、live 全未跑**。

---

## 交接给 Lead

1. **会话一是"v7 终检 → v5 → v6 两条路径 → 硬案例基准 → 范式 A → P5–P24 → P31–P34"的单线推进**，共 36 turn、19 989 事件、几乎每 turn 至少一个可核验交付 commit（§2 表列出 40+ 个 sha，从 `915f362` 到 `d37bfad`）。最有价值的三个转折点：`0adcd68`（首个硬案例增量 1）、`a8934fe`（3/3 非 loop AI VERIFIED）、`f42e6c4`（PT_LOAD 统一映射 → 严格验证 7/10）。
2. **"最后陷入重复工具调用循环"需修正表述**：会话**正常结束**（`turn/end reason=completed`，`s#seq=19987`）并输出了完整 4 844 字符报告（`s#seq=19985`）。真实问题是"把 30 min `job_output` 当轮询用"，turn 36 因此耗 2 h 07 m，其中 ~90 min 在等 CI；框架在 `#seq=19967` 发出第 5 次重复告警后模型才换命令。全会话 job_output 阻塞累计 ~25 h（占 80.5 h 的 31%）——这是**流程缺陷，不是模型死循环**。
3. **最后一个动作失败**：`00:45:57` 试图 `push HEAD:final/consolidated-2026-11-16` 被非快进拒绝（`anc=1`），模型选择不强推。因此**当前存在两条并存的"最终线"**：`workbench-v3 = d37bfad`（含 Phase-8D + P31–P34）与 `final/consolidated-2026-11-16 = c0f9feb`（含 P31–P34，但**不含** Phase-8D 的 `996060d/d1b73bf`）。汇总时必须点明，否则"最终状态"会自相矛盾。
4. **Phase-8C/8D 不属于会话一**：8C/8D 只出现在用户 turn 36 粘贴的指令里（`s#seq=19363`），会话一无任何执行事件；`d37bfad` 的父提交 `996060d docs(phase-8D)` 是**另一会话在 11-17 00:16（turn 36 进行中）推进**的。tag `release-2026-11-17-phase8d-final`（`19a91bc`→`d37bfad`）打于 01:25:46，晚于会话一结束 39 min，**也不是会话一做的**。
5. **真实完成度（可对外口径）**：确定性矩阵 100%（批准计划内）；AI 修复 = 12 案中 loop 6/6 + 非 loop 0/6（P11 口径 19/36=52.8%）；范式 A = 单函数 loop 6/6 + CWE121 2/2 + 三个非 loop 3/3，**不是通用**；严格独立验证 = **7/10**；hidden 成功 = **1 例**（CWE-476）。
6. **硬负结果一个都不能丢**：CWE-121 `0/6`（真因是 Behavior Contract：candidate `exit 0`/空 stdout vs 契约 `exit 1`+精确 stderr）、CWE-134 恒 `PLAN_INVALID`、UAF/heap 探针 0/1、Path B callee-context A/B **0 vs 0**、`deepseek-v4-pro` 在 ABI 管线 **0/3**、Qwen 小模型 **0/12**、SiliconFlow 国际站 **402**、三平台 key **401**。
7. **未收尾的三处 Git 隐患（交付前必须处理）**：`a0e6a24` 是**无 ref 的孤儿提交**（仅靠 detached worktree 保活）；`worktree-feature-final`/`worktree-p31-ci` 都是 detached HEAD；`final/consolidated-2026-11-16` 与 workbench 线**分叉**。建议在推送新分支前先 `git branch backup/p31-p34-a0e6a24 a0e6a24`（或打 tag）固化，再决定 final 线是否重建。
8. **P31–P34 只是"离线完成"**：`OpenRouter live = NOT_RUN`、`Ollama live = NOT_RUN`、`P35 60-run = NOT RUN`、`P36–P40 = NOT STARTED`。CI green（43907136876/267）+ 2411 tests 只能证明工程可跑，**不能**当作修复能力或 60-run 结论。
9. **凭证卫生**：用户两次在对话里粘贴 API key（`s#seq=9123`、`#seq=9548`），8124 网页 token 也明文写进多份报告（`s#seq=8682`）。总报告必须全部 `[REDACTED]`，并建议吊销/轮换这些凭证。
10. **不确定性**：① 各 turn 的 test 计数（1014→2411）来自会话自述，我只在仓库侧交叉验证了 `d37bfad`、`c0f9feb`、`a0e6a24` 的存在与树内容，**未逐 commit 复跑 pytest**；② `artifacts/*` 目录的实际内容与 SHA256SUMS 未逐项重算（属 04 号报告职责）；③ CI run 状态取自会话内的 GitHub API 输出，未在本次复查中重新请求 GitHub。
