# 会话深度分析：Linux 虚拟机验证漏洞修复-1（session-879cc62f）

- 分析对象：.tmp/sessions/s1-linuxvm.jsonl（19,358 个事件，一行一个 JSON）
- 会话时间：2026-11-13 16:15:49 → 2026-11-15 23:39:48（35 个 turn；最后一条用户指令 seq 18911 @ 11-15 22:42:49，最后一份正式报告 seq 19352 @ 11-15 23:39:48；11-16 08:05–08:06 仅有 session/end-seed 与标题事件）
- 真人指令：33 条（user/message 且 source.kind=user）；AI 正式报告：35 条（assistant/message 含 text）
- 会话标题演变：seq 14 fallback「需要linux虚拟机最后检验 @方法」→ seq 17 provider「Linux 虚拟机验证漏洞修复」→ seq 19356 user「Linux 虚拟机验证漏洞修复-1」
- 时间均为本机 +08:00（由事件 time 字段 epoch ms 转换）
- 分析限制：仓库只读、未做任何 git 写操作；本机未重跑 pytest/基准/LLM 调用；CI 结论已用 GitHub API 独立复核（见附录 A），其余测试数字来自会话报告与仓库内证据文件

## 0. 证据口径与核验方法

1. 用 Python 直接解析 19,358 个事件，抽取 33 条真人 user/message、35 条 assistant/message、10 个共享任务（team/task 事件 30 条含多版本）、12 个 team/member 事件、8 次 todo/write、4 次 goal/change、1 次 deliverables/presented。
2. 读取仓库内独立证据文件：handoff/final-verification-2026-11-13/FINAL-LINUX-VERIFICATION.md（248 行）、audit-evidence.md（437 行）、audit-claims.md（525 行）；worktree-feature-final/docs/acceptance/*.md；docs/status/claims.json；worktree-feature-final/experiments/p21-p16r3-658ff8c/profile.json；artifacts/p22-artifact-audit-2026-11-16/audit.json；artifacts/independent-verification-p16r3-2026-11-16/README.md 等。
3. 用 GitHub REST API 逐条复核会话中引用的 45 个 CI run（run id、head_sha、head_branch、conclusion），45/45 全部为 success 且 SHA/分支与报告一致；用 git cat-file 确认会话引用的 28 个 commit 全部存在于本地工作树（见附录 A）。
4. 未重放/未重跑的部分在 §8「未核实事项」逐条标注。

## 1. 时间线：33 条真人指令与 AI 阶段交付

| # | user seq | 时间(+08) | 用户指令目标（概括） | AI 交付（assistant seq / 阶段编号 / commit / CI） |
|---|---|---|---|---|
| 1 | 8 | 11-13 16:16 | 要求做「Linux 虚拟机最后检验」，附 方法建议_大模型二进制漏洞修复Agent_20261113(1).md | seq 1304 @17:06：v6→v7 最终检验与交付（v7 zip sha 2afeb6c8…；CI 43390831537=e1756a2 success） |
| 2 | 1318 | 17:09 | 「请一次性实现修复任意二进制文件这一功能」 | seq 3298 @18:08：v5 首个实现 commit 915f362（feature/universal-repair；68 files +8531/−316；macOS/Linux 1014 tests） |
| 3 | 3312 | 18:13 | 追问「任意二进制修复」是否已完成，未完成则继续，完成后推送仓库 | seq 4180 @18:58：v5 收口 72db891；CI 43412905037 success；双平台 1039 tests |
| 4 | 4187 | 18:58 | 要求实现「二进制层面直接修复、不转汇编/反编译」两条 AI 路径 | seq 5078 @19:42：两条 AI 直接二进制路径 6d525ca（功能提交 abeab27）；CI 43418024120/43418615884；1118 tests |
| 5 | 5084 | 19:42 | 组长分析：v5 证据核对 + 定位「B 家族/未测 AI 增量」+ 要求再次确认跑通并推送 | seq 5337 @20:06：逐条更正文案（100% 限定为批准计划）、readelf 机制、SHA256 复核脚本；af8f674；CI 43421560913；1119 tests |
| 6 | 5343 | 20:06 | 重申两条路径定义（汇编往返 / 直接二进制），要求核查并重做 | seq 6087 @20:51：按定义重做为 asm_roundtrip + binary_direct，aa45b36；CI 43426508766/43427654178；1128 tests；11 条脚本化正向证据 |
| 7 | 6110 | 21:05 | 组长分析（asm_roundtrip 校验器天花板、gate 盲区、真实 LLM 增量）+ 要求完成并推送 | seq 6571 @21:56：PoC 差分进 gate、gate 盲区 4/5 抓住、真实 provider 3/6 vs baseline 6/6（增量 0）；455011f；CI 43435227438/43436452584；1133 tests |
| 8 | 6601 | 22:23 | 组长全部反馈：任意二进制修复仍未完成；授权代理电脑、下载工具、一次性解决 | seq 6699 @22:27：产出《任意二进制修复一次性执行计划》（W0–W6/验收标准/不可承诺清单） |
| 9 | 6720 | 22:30 | 组长补充（「任意二进制修复」是领域开放难题）+ 要求按计划执行到底 | seq 7322 @23:28：真实 PoC+回归 gate（poc_runner.py）、任意输入鲁棒性、语法门禁、CI 证据核验；54b575f；CI 43449603578/43451324919；1141 tests |
| 10 | 7329 | 23:40 | 组长：验证基础设施循环已足够，下一轮只做「硬案例 AI 增量基准」 | seq 7764 @00:14：硬案例基准 2 案（baseline 0/2，AI 1/2，增量 1）；0adcd68；CI 43457857951/43458988294；1143 tests |
| 11 | 7771 | 11-14 11:47 | 组长核对增量 1 的限定并给出消融/扩样本要求 | seq 8153 @12:32：公平性消融 + 10 案硬案例（target AI 6/10，blind 0，baseline target-aware 0，契约效应 0）；eb1f0a4；CI 43555871445/43556499270 |
| 12 | 8160 | 12:48 | 组长：6 成功全是 loop 家族，要求家族多样性 | seq 8353 @13:08：UAF/heap 探针（12 案/7 家族），loop 6/6、非 loop 0/6；ab679ef；CI 43559328831 |
| 13 | 8359 | 13:08 | 「组长的建议，请严格按顺序全部完成，继续突破」（附方法建议文件） | seq 8473 @13:19：12 案/7 家族定稿，成败分布与 gate 支持说明；bf5da88；CI 43560207206 |
| 14 | 8480 | 13:27 | 要求先推送成果，再用已搭好的固定网页测试 | seq 8682 @13:31：e5f731c 推送 + 8124 端口固定网页重启（原 token/数据目录） |
| 15 | 8688 | 13:31 | 组长：多模型 provider 防缩水、UAF/heap 测量基础设施、能力边界 | seq 8949 @13:57：DeepSeek/SiliconFlow/DashScope profiles + 严格 model identity；afe4aee；CI 43563347462；1149 tests |
| 16 | 8956 | 14:07 | 组长：竞赛平台调研 + 多模型/防缩水；要求完成 | seq 9116 @14:21：多模型操作清单、身份探针证据（deepseek-chat→deepseek-flash 不一致）；14971d9；CI 43565353034 |
| 17 | 9123 | 14:59 | 提供 API key，要求在 M2 Mac 安装 JDK+Ghidra（附步骤） | seq 9541 @15:28：Temurin JDK 25.0.5 + Ghidra 12.2 用户级安装、自建 macOS arm64 decompiler、headless 反编译 PASS；c0dbd0d；CI 43570678371 |
| 18 | 9548 | 15:37 | 提供新 key，要求继续跑通所有任务 | seq 9773 @16:04：DeepSeek 官方有效 key，2 模型×12 案×3 重复（各 6/12，loop 6/6、非 loop 0/6）；fd205dc；CI 43573457659 |
| 19 | 9786 | 16:10 | 组长 5 个问题：86587da 隔离、非 loop 路径 A/B、范式 A、4–6 模型、固定网页环境 | seq 10847 @17:25：worktree 隔离 86587da；Path A call 白名单实测无效；范式 A loop 函数级闭环 PASS；d69c84b；CI 43579784063 |
| 20 | 10860 | 17:39 | 组长 5 个问题：Patcherex2 符号/stub、call-graph 导出、4–6 模型、86587da 决策、puts 副作用 | seq 11245 @18:05：CWE121 非 loop A 闭环 PASS（2/2 PoC+4/4 regression）；callee context 导出；capacity 暂不合并；stdout_signature gate；12d05ec；CI 43582808690 |
| 21 | 11252 | 18:27 | 组长 4 个问题：SiliconFlow key、符号解析器、errno/stdout、capacity 截止 | seq 11748 @19:24：symbol_resolver 固化、国际 key 402 余额阻断、6afe122；CI 43589156716/43589863303；1160 tests |
| 22 | 11755 | 19:34 | 组长：SiliconFlow 中国站免费模型路径、capacity 归档、strlen 模板 | seq 12053 @20:28：4 模型真实矩阵完成（flash 6/12、v4-pro 6/12、Qwen3-8B 0/12、Qwen2.5-7B 0/12）；c3dae2f（无 CI） |
| 23 | 12060 | 20:30 | 组长：feature/workbench 分叉与 CI、4 模型结论、errno、符号解析 | seq 12593 @22:01：feature rebase + fast-forward 合并 workbench-v3，CI 43601736542 @7a5d21f success；6cc51d3；本地 1314 tests |
| 24 | 12600 | 22:06 | 组长：errno 运行时捕获、符号分层、Path B A/B、验证边界文档 | seq 13239 @23:19：strace errno 代理、Path B A/B 0 vs 0、符号黑名单、docs/limitations.md；c8af199；CI 43608147997；1518 tests |
| 25 | 13252 | 23:27 | 组长给出 P0–P4 详细执行指南（Path B 注入、malloc 白名单、LD_PRELOAD errno、泛化、白皮书） | seq 14284 @11-15 00:49：P0–P4 执行（注入 retry、auto symbols、动态符号、ld_preload、非 loop 0 新增、文档）；2739ead；CI 43614759619/43616285244；1626 tests |
| 26 | 14297 | 11-15 01:10 | 组长长文：项目最终目标判断、问题总表、完整解决方案（P0–P4 收口） | seq 15377 @03:01：3/3 非 loop AI VERIFIED PASS（hard-multicall/sprintf/nonconst，含 SHA256）；cave relocation 修复、RepairSpec、CFG-aware ABI；a8934fe；CI 43628367481/43628367473；1641 tests |
| 27 | 15390 | 12:32 | 组长：P5–P9 任务书（Native feedback、RepairSpec v2、benchmark 扩展、模型资格、验证/证据） | seq 16429 @15:10：P5 native feedback retry、P6 v2、P7 4/6 verified（CWE122 未见二进制）、P8 2/6 vs 2/6、P9 evidence 部分；bd9cbf6；CI 43687651300/43687651314；1954 tests |
| 28 | 16442 | 15:18 | 组长：P10–P15 任务书（汇编诊断反馈、36 次稳定性、v2 集成、跨二进制扩展、native trace、更强验证） | seq 17305 @16:54：P10 CWE-787 VERIFIED、P11 36 次 19/36（52.8%）、P12 v2 真实 trace、P13 8 二进制/7 CWE + hidden CWE-476 VERIFIED、P14 N1/N2、P15 mutation plan；dad21c9；CI 43695637933/43695637887；1966 tests |
| 29 | 17312 | 17:11 | 组长：P16–P20 任务书（统一独立验证器、CWE-121/134、48 次稳定性、N3–N6、fuzzing） | seq 17763 @18:37：P16 6 verified/1 rejected/3 not_run；P17 失败保留；P18 未完成；P19 partial；P20 partial；c5d87b5；CI 43703724955/43703724942 |
| 30 | 17770 | 18:55 | 组长：P16-R–P20-R 返工要求（先可信验证器，再语义与可重复性） | seq 18148 @19:52：P16-R 0 verified/8 rejected/2 not_run（暴露 patch-plan/ABI/scope 问题）；P17–P20 仍失败/未完成；106d1cd；CI 43707923361/43707923227；2041 tests |
| 31 | 18161 | 20:03 | 组长：P16-R2 起（PT_LOAD mapping、CaveABIBlock、authorization） | seq 18471 @20:38：真实 patch plan 进入验证器；CWE122 通过 layout/action/scope/oracle/independence 但 ABI 失败（no_ret/branch_target_unknown）；严格路径 0 verified；085fc38；CI 43713295997/43713296021 |
| 32 | 18484 | 21:01 | 组长：先完成 P16-R3（PT_LOAD 映射、CaveABIBlock、Authorization Record）再谈其余 | seq 18898 @22:33：P16-R3 严格验证 7/10 verified（+1 rejected +2 ARTIFACT_MISSING）；CaveABIBlock 出口语义/真实授权/两条缺失 artifact 仍未完成；f42e6c4；CI 43723326346/43723326360；2044 tests |
| 33 | 18911 | 22:42 | 组长：P21–P30 路线（P21 冻结、P22 artifact、P23 60 次、P24 统计；P25–P30 并行工程线） | seq 19352 @23:39：P21 冻结 profile（source 658ff8c）、P22 审计 8 recovered/2 missing、P23 独立验证 runner+1 次 smoke、P24 统计工具；完整 60 次未完成、P25–P30 未实现；a1755a5；CI 43729513475/43729513476；2048 tests |

说明：35 个 turn 中有 2 个不是真人指令触发的 turn（seq 6092 @20:56 与 seq 6576 @22:06），分别对应 AI 对旧版 GitHub API 轮询器 403 限流的说明（assistant seq 6103、6588），不影响交付结论。

阶段编号对应关系：v6/v7 交付件检验（#1）→ v5「修复任意二进制」（#2–#5）→ 两条 AI 直接二进制路径（#4–#6，先 ai_plan/ai_bytes 后重做为 asm_roundtrip/binary_direct）→ 验证基础设施（#7–#9）→ 硬案例 AI 增量与公平性消融（#10–#13）→ 多模型/Glidra/范式 A（#15–#24）→ P0–P4（#25–#26）→ P5–P9（#27）→ P10–P15（#28）→ P16–P20 系列（#29–#32）→ P21–P24（#33）。

## 2. 重点一：Linux VM 最终检验（v6 → v7，seq 8–1304）

### 2.1 起点与执行链

- 用户指令 seq 8 @16:16:05；AI 开工时 v6 交付件已存在（handoff/BinaryRepair-Linux-Handoff-2026-11-13-v6.zip，sha256 da5f4fda…ba357，60,204,619 B，zip mtime 16:17:39）。
- 权威环境：Linux VM Ubuntu 24.04.5 LTS arm64（Lima 2.3.0，4 vCPU / 5.8 GiB，QEMU 8.2.2，clang 18.1.3，GNU readelf 2.42），x86-64 动态执行走 qemu/binfmt。
- 检验链：宿主重算 zip 哈希/unzip -t/29 个嵌套 SHA256SUMS/MANIFEST/文本路径扫描 → VM 全新解压 → 按 02-Linux运行手册装工具链 → ./setup-linux.sh（全新 venv，pip 在线安装 40 个包）→ ./run-baseline.sh -rs（全量 pytest + JUnit）→ ./run-smoke.sh --allow-native → 独立运行时抽查（L2 native ELF / L3 CGC replay×3 / 负向对照）→ GitHub API 复核 CI。
- 交付：seq 1304 @17:06:29 报告 v7 可交付；deliverables/presented（seq 1299）给出 v7 zip 与 FINAL-LINUX-VERIFICATION.md 两个文件。

### 2.2 v6 问题清单（两轮独立审计 + 最终报告合并，P0=0）

| 级别 | 编号 | 问题 | 证据（审计原文/文件） | v7 处置 |
|---|---|---|---|---|
| P0 | — | 无阻断项：未发现证据伪造、关键缺件、凭据泄漏、静态/模拟证据冒充原生证据 | audit-evidence「P0=0」；audit-claims「P0=0」 | — |
| P1 | P1-1 | VERSION created_at 16:20 / MANIFEST created_at 16:25，均晚于 zip 封包 16:17:39 且互相矛盾（不可能时间） | audit-evidence P1-1 | 统一取真实构建时间，早于 zip mtime；host 校验通过 |
| P1 | P1-2 | 3 个嵌套 SHA256SUMS 失配：evidence/v4-macos 1/4 OK（自指行写成空文件哈希）、artifacts-v4 26/28、artifacts-old 10/12 | audit-evidence P1-2 | 按实际字节全部重算，另修 1 个 fixture 级清单；29/29 通过 |
| P1 | P1-3 | 2 个历史日志文本泄露真实用户名 huageorge 与 /private/var 私有临时路径 | audit-evidence P1-3 | 脱敏为 <user>/<tmp>；文本 0 命中 |
| P1 | P1-4 | handoff/ 根目录存在 2 个当前包解压副本 + .DS_Store，违反「只交付一个 zip」 | audit-evidence P1-4 | v6 归档为 -superseded；删除副本与 .DS_Store；README 指向唯一当前包 |
| P1 | P1-5 | patches/git-info.txt 的 parent 写成 ef90544（实际 3eac4e6）；patches/README.md commit subject 张冠李戴 | audit-evidence P1-5 | 修正 parent/subject 与 BASELINE 措辞 |
| P1 | P1-6 | v6 Linux 计数依赖未记录的 umask 022；VM 登录 shell 默认 umask 002 时 950 中 938 passed/7 skipped/5 failed（5 例 tests/test_guest_executor.py） | claims-auditor P1-4；根因 workers/executor/self_test.py:44-45 mkdir 受 umask 影响 + workers/executor/run_job.py:214-216 拒绝 group-writable 包根 | v7 顶层 run-baseline.sh/run-smoke.sh 先 umask 022（与 Ubuntu CI 一致）并写入手册；复验 943/7/0 |
| P1 | P1-7 | CGC「patched」来源未说明（易误读为引擎修复+PoC 验收）；basic_messaging 差分被当稳定证据 | claims-auditor P1-1/P1-3；datasets/cgc-linux-src/CMakeLists.txt:88,101,147 证明 *_patched 为上游 -DPATCHED 源码构建 | 明确披露上游构建、非引擎产物、非 V0–V5；Palindrome 作 canonical，basic_messaging 降级 exploratory-only、不作 gate |
| P1 | P1-8 | legacy ELF x86-64 验证失败时仍返回候选并报 supported=True（潜在 fail-open） | claims-auditor P1-2；app/services/binary_pipeline.py:195/207-216/279-287 + scripts/repair_binary.py:43-55 | 冻结源码不改；HANDOFF-TASKS.md F1（201-217 行）记录复现步骤、影响、必需修复与回归测试要求 |
| P2 | 7 项 | 包内 pytest.log 无汇总行；junit hostname 明文；MANIFEST 计数口径未注明；in-tree 历史文档旧口径；archive 体积 1.4GB 与 README 列表不符；Windows PE 原生/32 位/大端/fat Mach-O/heap/sprintf/UAF 等仍为 HANDOFF 任务；readelf 仍为外部依赖而非 LIEF/llvm-readelf 后端 | FINAL-LINUX-VERIFICATION.md §4 P2；audit-evidence P2=9；audit-claims P2=9 | 记录为不影响本次交付的建议项 |

补充：audit-evidence 判定「有条件可交付（Conditional PASS）：P0=0，P1=5，P2=9」；audit-claims 判定「功能声称—实现—测试三者基本一致，无 P0，P1=4，P2=9」。两轮审计均在 v7 上复验了处置。

### 2.3 Linux VM 权威验收结果（v7）

| 检查项 | 结果 | 证据 |
|---|---|---|
| zip SHA256 与 .sha256 | 2afeb6c8c0908acfcf0fb83328d75a2c5254dc7656f2ef43105cf3f89a42fcc8，双源一致（60,488,092 B） | handoff/BinaryRepair-Linux-Handoff-2026-11-13-v7.zip.sha256；FINAL §3.1 |
| unzip -t / 条目 | 无错误；2,228 个文件条目、0 目录、解压 157 MB | FINAL §3.1 |
| 顶层 SHA256SUMS | 2,227/2,227 OK、0 失败；行数恰为全部文件减自身 | FINAL §3.1 |
| 29 个嵌套 SHA256SUMS | 29/29 通过（v6 为 26/29，3 个失配已修复） | FINAL §3.1 |
| verify-package.sh | PASS（checksums + secret hygiene） | FINAL §3.1 |
| MANIFEST 计数 | files=2,226 / bytes=157,757,081 / by_top_level 六项与实际一致 | FINAL §3.1 |
| VERSION/MANIFEST 时间戳 | created_at=2026-11-13T16:58:23+08:00，早于 zip mtime 16:58:31，二者一致 | FINAL §3.1 |
| 禁止项/文本路径扫描 | 0 命中：__pycache__/.venv/.git/.DS_Store/.env/var 密钥/浏览器 profile；用户名/本机临时路径 0 命中 | FINAL §3.1 |
| zip 中文文件名与可执行位 | UTF-8 标志已置；解压后 90 个可执行文件，与 v6 一致 | FINAL §3.1 |
| setup / 环境安装 | ./setup-linux.sh 全新 venv，pip 在线安装 40 个包；apt 代理对 ports.ubuntu.com 返回 502，改为直连执行并如实记录 | FINAL §2 |
| 全量 pytest（全新解压+全新 venv） | 950 collected / 943 passed / 7 skipped / 0 failed，69.861 s（host lima-binaryrepair，ts 2026-11-13T17:00:01+08:00） | FINAL §3.2；evidence/v7/vm-console.log |
| 7 个 skip 归因 | 1 个 BINARYREPAIR_CANDIDATE_ELF 可选测试 + 4 个 test_repair_macho_native.py + 2 个 test_binary_pipeline_v4.py 的 Mach-O 正向用例；逐项核对为平台真实限制，无「为通过而 skip」 | FINAL §3.2；audit-claims §2.1 |
| run-smoke.sh --allow-native | PASS: all smoke checks（6 个 section 全过；仅 native ELF run 因 VM 为 arm64 按设计 SKIP） | FINAL §3.3 |
| arm64 平台说明 | VM 为 Ubuntu 24.04 arm64；x86-64 动态执行走 qemu-user；Unicorn/Mach-O 证据分别按平台门控 | FINAL §3.3/§9.1；FINAL §3.4 |
| 全量测试 umask 对照 | v6 原样（VM 默认 umask 002）= 938/7/5 failed；显式 umask 022 = 943/7/0；v7 = 943/7/0（不依赖外部 shell 状态） | FINAL §3.6 |
| CI 证据链 | run 43390831537 = e1756a2 / workbench-v3 / success；check-run annotations 独立给出 943 passed / 7 skipped / 0 failed / 950 total；上游绿色 run 43256887551 注解 889/1/0/890；历史失败 run 43248544193 的 failed_test 与包内 run.json 一致 | FINAL §3.5；GitHub API 复核（附录 A） |
| 包内 macOS junit | 950/946/4/0（host HuadeMacBook-Pro.local，ts 2026-11-13T16:04:51+08:00；4 skip 均为平台门控） | FINAL §3.5 |
| Mach-O 原生（claims-auditor 本机复跑） | x86_64 原版 64B SIGSEGV(-11)、arm64 原版 SIGBUS(-10)；两架构 patched 均 exit 0 / 输出截断 15；v7 已将文档措辞精确为 x86_64 SIGSEGV / arm64 SIGBUS | FINAL §3.5；audit-claims 摘要第 6 点 |

### 2.4 独立运行时抽查（v7 解压树）

L2 · native ELF（qemu-x86_64）：

| 输入 | vuln.elf | vuln-strict-fixed.elf |
|---|---|---|
| 0 / 1 / 16 字节 | exit 0，回显 + 256 字节栈内容（可观测越界） | exit 0，精确回显 |
| 17 / 32 字节 | exit 0（故意不拒绝，越界） | exit 1 + input too long (max 16 bytes) |

L3 · CGC POV replay（exploratory；3 次重复/3 attempts）：

| 变体 | 权威验收脚本内结果 | 独立复跑（VM 内，同一解压树） |
|---|---|---|
| Palindrome vulnerable | 3/3 cb_signal=11 | 3/3 cb_signal=11 |
| Palindrome_patched | 3/3 cb_exit=0 | 3/3 cb_exit=0 |
| basic_messaging vulnerable | 0/9（9 次尝试均 cb_exit=0） | 独立 shell/近邻脚本复跑 >20 次均 cb_signal=11（含负载/顺序/脚本化隔离对照） |
| basic_messaging_patched | 3/3 cb_exit=0 | 3/3 cb_exit=0 |

结论：Palindrome 的 POV 差分稳定可复现（canonical）；basic_messaging 的差分真实但对运行上下文敏感（脚本化验收侧不稳定），v7 已降级为 exploratory-only、不作 gate，并把「使 replay 确定化」列为后续任务；同时显式说明 *_patched 是上游 -DPATCHED 源码构建，不是本引擎修复产物。

负向对照（audit-claims 实测）：

| 输入 | 结果 |
|---|---|
| PE i386（mov [esp+k],reg 参数形态） | candidate=None / status=unsupported |
| 无模式 PE / 无模式 Mach-O | candidate=None / unsupported |
| 未知字节 / 空输入 / 畸形 MZ / >20 MiB | invalid / unsupported，无候选 |
| 截断输入（5 个正例夹具的 6 种截断前缀） | 实测 0 候选；测试自身只断言「不抛异常/若给候选必须过 gate」，未直接断言「无候选」（P2 弱点） |
| gate 语义 | 无运行时证据时 runtime.evidence=not_run、tier=static_only、success=False/outcome=inconclusive；legacy ELF gate 在 runtime 缺失时 NOT_RUN；not_verified/unsupported 不计成功（唯一例外是 P1-8 legacy fail-open 潜在路径） |

### 2.5 独立审计 teammate 结论

| 审计 | spawn 证据 | 任务 | 报告与结论 |
|---|---|---|---|
| evidence-auditor（id 7945b4e0…） | team/member seq 212/214 @16:20；task-1 | 审核 v6 证据链与外层一致性（只读、不用 VM、不跑全量 pytest） | handoff/final-verification-2026-11-13/audit-evidence.md（437 行，35,716 B，16:31 交付 seq 453/454）。结论：有条件可交付（Conditional PASS）：P0=0，P1=5，P2=9；关键实测：zip/SHA256SUMS/MANIFEST/CI API 字段 7/7 一致、两份 junit 计数与 pytest 进度一致、Linux 7 skip = 1+4+2、zip 无禁用内容 |
| claims-auditor（id 8a5d3b4e…） | team/member seq 217/219 @16:20；task-2 | 审核 v6 功能声称与测试语义（只读、不用 VM、不跑全量 pytest） | handoff/final-verification-2026-11-13/audit-claims.md（525 行，16:55 交付 seq 1055/1056）。结论：P0=0，P1=4，P2=9；关键：负向对照全部 fail-closed；gate 语义 fail-closed（除 P1-2 潜在路径）；Mach-O native 本机复现（SIGSEGV -11 / SIGBUS -10）；CGC replay 为真实 qemu 执行且返回码顺序不会把 patched 崩溃/超时误判成功；对照方法建议 §4.1/4.2 属「部分符合、差距诚实标注」 |

claims-auditor 的中途发现直接改变了 v7 验收口径（会话内 seq 743/832/951）：CGC basic_messaging 在 16:35 的 fresh run 3/3 未触发、v7 脚本化 9/9 未触发，而手动复跑 10/10–16/16 触发；据此把 basic_messaging 降级为 exploratory，并把「patched 来源归属」「fail-open」「umask 根因」「脚本化上下文敏感」列入 v7 处置。

### 2.6 最终交付物与证据目录

- 最终交付：handoff/BinaryRepair-Linux-Handoff-2026-11-13-v7.zip（sha256 2afeb6c8…42fcc8，60,488,092 B）+ .sha256；v6/v6.1 已归档 -superseded；handoff/README.md 指向 v7。
- 最终报告：handoff/final-verification-2026-11-13/FINAL-LINUX-VERIFICATION.md（248 行，含复现命令与证据索引）。
- 证据目录：handoff/final-verification-2026-11-13/ 下 evidence/v7（host-verification.log、vm-console.log、acceptance/ 的 JUnit/pytest/smoke/CGC/环境原始文件）、evidence/v7-rc、evidence/v61-reference、evidence/v6-vm、evidence/vm-console-firstattempt.log、host-zip.sha256、scripts/build-v7.py、scripts/verify-linux-vm.sh、scripts/verify-host.sh。
- 复现命令（报告 §7）：shasum -a 256 -c …v7.zip.sha256；scripts/verify-host.sh；limactl shell binaryrepair -- bash scripts/verify-linux-vm.sh BinaryRepair-Linux-Handoff-2026-11-13-v7。
- 并行 v6.1：检验期间另一会话产出 v6.1（docs commit 3d5d0f0 + CI 43395652244 + Mach-O 证据），但同样在 fresh VM 下 938/7/5 failed，且仍有嵌套清单失配、用户名泄露、时间戳矛盾、无 umask 归一化，结论为「不发送」，已归档为 -superseded。

## 3. 重点二：「修复任意二进制」（v5）与「两条 AI 直接二进制修复路径」

### 3.1 v5：统一任意二进制修复入口（feature/universal-repair）

| 项 | 内容 |
|---|---|
| 首个实现 commit | 915f362「feat(binary): universal repair entry with 32-bit x86 support」（68 files，+8531/−316；未 push、未触发 CI；macOS 1014 tests / Linux VM 1014 tests，报告 seq 3298） |
| 最终 commit / 分支 | 72db891（docs 提交）；feature/universal-repair 与 workbench-v3 均指向 72db891；main 未动（8869b07） |
| 提交谱系 | 47465e0 → f65c2dc → 72db891；CI run 43411767923(47465e0)/43412399232(f65c2dc)/43412905037(72db891) 均 success（API 复核） |
| 本地验收（最终代码） | macOS 13.5 arm64 / Python 3.11.8：1039 tests，0 failed，0 errors，4 skipped（162.8 s）；Linux VM Ubuntu 24.04 arm64 / Python 3.12.3：1039 tests，0 failed，0 errors，7 skipped（178.4 s） |
| 功能范围（矩阵） | ELF/PE/Mach-O × x86_64/arm64 + ELF32/PE32 i386；sink：unbounded_copy（strcpy/strcat/stpcpy，guard）与 immediate_length/memcpy_length/syscall_length/checked_copy（immediate 钳位）；矩阵单一事实源 app/services/repair_matrix.py |
| 处置语义（schema v4） | verified_patch / static_only_patch（必须显式 opt-in、verified=false、绝不算 success）/ not_verified / analysis_only / unsupported / rejected / invalid；消除历史 ELF x86-64 gate 失败仍返回候选的 fail-open |
| 新增能力 | i386 analyzer（cdecl push 参数、容量=帧顶−目标）、cdecl_x86 guard 机器码、ELF32 PT_LOAD / PE32 .brfix 注入、E8/FF15 调用解析、Unicorn x86-32 运行时证据（emulated_run / unicorn-i386） |
| 新增夹具（engine-i386 task-3/6） | ELF32 i386：fixtures/elf/vuln-strcpy-x86.elf（sha256 a7395468…ad0d，3,955,228 B）；PE32 i386：fixtures/pe/vuln-strcpy-x86.exe（5c801c45…4634，847,872 B）；高级覆盖：vuln-strcpy-x86-dyn.elf（de051d8a…80c8，3,405,212 B）、vuln-strcpy-x86-iat.exe（59351c0b…471a，847,872 B）、vuln-memcpy-x86.elf（0bbe1c86…，3,930,224 B） |
| i386 关键证据 | 两夹具 capacity=16 的 strcpy sink；patched 在 0/1/15/16/17/64 字节输入下 canary 全部完整且输出 ≤15，原版 16/17/64 越界；gate success_within_scope、tier emulated_run；API 实测 200/verified=true/verified_patch |
| 验收文档/证据 | docs/acceptance/binary-universal-v5-2026-11-13.md；docs/reference/binary-repair-engine.md；docs/acceptance/LIMITATIONS.md；artifacts/binary-universal-v5-2026-11-13（11 个正向夹具的 scan/repair JSON、baseline 运行证据、macOS/Linux JUnit、SHA256SUMS；verify_evidence.py：11 fixtures/110 sources/38 files PASS） |
| 边界声明 | 「100%」仅指批准计划 G1–G5 与确定性矩阵完成，不指任意二进制/任意漏洞；arm32/riscv/mips/ppc/大端/fat Mach-O 重写/heap/global/sprintf/UAF/整数/循环 仍 fail-closed；Unicorn 为函数级指令模拟，不是原生内核运行；每候选只修一个函数 |

API/CLI/UI：POST /api/binary/scan（schema v4）、POST /api/binary/repair（verified/static-only/422）、GET /api/binary/matrix；CLI scripts/repair_binary.py 单文件 + --batch + --allow-static-only；/binary 中文页面（拖拽→扫描→修复→处置徽章→仅 delivery.download_allowed 才允许下载）与侧栏入口；i18n en 覆盖。

### 3.2 两条 AI 直接二进制修复路径（两代实现）

| 代 | 路径 | 流程 | 提交/CI | 测试/证据 |
|---|---|---|---|---|
| 第一代（seq 5078） | ai_plan | 模型只接收有界分析元数据包（无原始字节），只输出 {sink_index, strategy}，由确定性 writer 生成 guard/立即数钳位 | 功能 abeab27；6d525ca；CI 43418024120(abeab27)/43418615884(6d525ca) success | 1118 tests；docs/architecture/ai-binary-repair-paths.md；artifacts/ai-direct-binary-2026-11-13（第一代时 6 条正向记录，第二代扩充为 11 条） |
| 第一代 | ai_bytes | 模型直出机器码 code_hex（guard）或同长度就地字节编辑（immediate）；Capstone 完整解码、指令白名单、拒绝 syscall/特权/间接跳转/块外分支；writer 注入/重定向 | 同上 | 28 项 AI 规划 + 35 项 validator + 13 项 UI + 1 项脚本化证据 |
| 第二代（seq 6087，按用户定义重做） | asm_roundtrip（路径一） | ELF → Capstone 反汇编目标函数为汇编文本 → AI 返回修复汇编 → 宿主 clang 汇编回机器码 → 注入新可执行块 + 入口重定向 → 输出 patched ELF。支持 ELF i386/x86_64/arm64；PE/Mach-O 返回 422 | 功能 61287fd；aa45b36；CI 43426508766(61287fd)/43427654178(aa45b36) success；本地 macOS 1128 / Linux VM 1128 tests | 11 个脚本化正向 verified 记录（macOS；Linux 9 个，Mach-O native 跳过）：ELF i386/x86_64/arm64 × asm，PE x86-64/arm64、ELF i386/x86_64/arm64、ELF i386 memcpy、Mach-O x86-64/arm64 native gate；负向 no-op ret 被 gate 拒绝 |
| 第二代 | binary_direct（路径二） | 不生成汇编文本、不反编译 C；AI 直出机器码 guard 字节或同长度就地字节编辑 → 严格 validator → writer → 确定性 gate | 同上 | 同上；verify_evidence.py：12 fixtures/132 sources/两个 bundle PASS |
| 安全关键点 | 共享 finish_candidate() reparse/runtime/gate；AI 永远不能把失败/不完整 gate 提升为 success；新增 runtime buffer_match（结构合法但单条 ret 的空 guard 被拒） | 全部路径共用 | — | — |
| 产品面 | GET /api/binary/ai-paths；POST /api/binary/ai-repair（path=asm_roundtrip 或 binary_direct，200/422/503）；CLI scripts/repair_binary.py --ai-path；/binary 页面两卡（binary-ai-run-asm / binary-ai-run-direct，独立文件选择、共享 best-effort、每卡下载受 delivery.download_allowed 控制） | 全部路径共用 | — | — |

验收结论（seq 6103）：aa45b36 为两条产品路径最终提交，feature/ai-binary-repair 与 workbench-v3 同一提交，main 未动；macOS 1128 tests、Linux VM 1128 tests；证据 SHA256 校验 PASS。同时明确边界：路径一仅 ELF 三架构且依赖宿主 clang；路径二仍在确定性矩阵内；脚本化证据的 AI 是 deterministic stand-in，不代表真实 LLM 修复质量、也没有测出 AI 增量；范式 A（反编译 C→LLM 补丁→二进制感知重编译）不在本次范围。

### 3.3 与这两条路径直接相关的后续验证（承接重点三）

- 真实 provider 实验（seq 6571，455011f，CI 43435227438/43436452584）：3 个 asm_roundtrip + 3 个 binary_direct；AI verified 3/6，无 AI baseline 6/6，coverage increment 0；失败案例诚实记录（asm x86-64 被 runtime gate 拒；direct PE x86-64 注入块含禁止 call；direct PE arm64 以 mov fall-through 结尾）。证据 artifacts/ai-real-provider-2026-11-13/（不存 key/prompt/响应）。
- PoC 差分进 gate（同上）：poc.original_fails / poc.candidate_passes 成为 gate 判据（函数级 runtime 差分，不是 guest/kernel PoC replay）；tests/test_poc_gate.py。
- gate 盲区实验（同上）：4/5 抓住（空 ret、错误目标地址、缺 NUL、无关字节修改），1 个残留（asm 正确拷贝但省略原 puts 副作用）；证据 artifacts/gate-blind-spots-2026-11-13/。
- 硬案例基准（seq 7764，0adcd68）：baseline 0/2、AI 1/2（inline-byte-loop native PoC verified；CWE121 因 call 被 leaf-only validator 拒而失败）；证据 artifacts/hard-case-benchmark-2026-11-13/summary.json。
- 公平性消融（seq 8153/8353，eb1f0a4/ab679ef）：10 案；baseline blind 0；baseline target-aware 0；AI blind 0；AI target×(full/generic/none)=6/6/6（7 次重复稳定 6/10；contract_specificity_effect=0；localization_effect=6）；证据 artifacts/fairness-ablation-2026-11-14/aggregate.json。
- 12 案/7 家族扩展（seq 8473/8949，bf5da88/afe4aee）：loop 6/6；CWE121/multicall/sprintf/nonconst/UAF-noinput/heap-canary 全 0；新增 UAF no-input（stdout_hex、空 regression）与 heap-canary（无 native crash，用 guard 可观察行为）gate 支持。
- 多模型矩阵（seq 9773/12053/12593）：12 案 × 3 重复，native PoC 在 Linux VM；4 个真实模型：deepseek-flash 6/12、deepseek-v4-pro 6/12、Qwen/Qwen3-8B 0/12、Qwen/Qwen2.5-7B-Instruct 0/12；identity 全部 exact；证据 artifacts/multi-model-matrix-cn-2026-11-14/README.md、artifacts/multi-model-matrix-2026-11-14/aggregate.json。

## 4. 重点三：P0–P24 各阶段状态与证据

| 阶段 | 定义/目标 | 结果与状态 | 关键证据 | commit / CI |
|---|---|---|---|---|
| P0 | Path B AI 汇编注入瓶颈（hard-multicall no_candidate） | 完成「黑盒破除」：真实错误是 forbidden assembly construct: ud2，不是符号/空间；新增 typed injection.error_class/token/stage + candidate.no_candidate_reason + 一次 validator-feedback retry（不自动改写 ud2）；注入成功（new-pt-load、81 B、2 call relocations），native gate 从 no_candidate 变 fail（模型语义） | artifacts/path-b-injection-retry-2026-11-14/；injection 相关测试 | 2739ead / CI 43614759619 |
| P0b | Route A 自动符号解析 | 完成：available_symbols() 从 ELF .symtab/.dynsym + .plt/.plt.sec 提取；GOT/PLT 重名取唯一可执行地址；route_a_patch.py 默认自动符号；CWE121 无显式 --symbols 仍解析 printLine，产物 SHA 与旧版一致 463a9758… | artifacts/route-a-auto-symbols-2026-11-14/ | 2739ead |
| P1 | 动态依赖白名单（malloc/free） | 完成：malloc/calloc/realloc/free 仅在目标 ELF 实测存在时允许，否则 blocked；fork/execve/system/popen/dlopen 绝对拒绝；CWE121 无 malloc 继续 blocked；CWE416 解析 malloc/free 并参考 UAF 修复 PASS（参考锁，不计 AI） | artifacts/dynamic-symbols-2026-11-14/；artifacts/generalization-uaf-2026-11-14/ | 2739ead |
| P2 | errno 精确探针 | 完成（有限）：errno_probe=ld_preload 编译 runtime/errno_dumper.c，对 native dynamic ELF 捕获进程退出前 TLS errno，对比精确值；CI 断言 errno_probe=ld_preload、errno_signature=matched；边界=进程退出级，不是函数返回级；静态/qemu 报 not_run 不伪造 | docs/acceptance/feature-p0-p4-2026-11-15.md；poc_runner/unified_verification 测试 | 2739ead |
| P3 | AI 非 loop 泛化 | 未达标：3 例 triage（hard-multicall 注入成功/native fail；hard-sprintf 未注入/assembly_assemble 拒 ^；hard-nonconst 注入成功/native fail），AI 新增非 loop verified = 0；另 CWE416 参考修复 PASS | artifacts/generalization-2026-11-14/ | 2739ead |
| P4 | 工程化收尾（文档/白皮书/setup.sh/run_matrix.sh/claims） | 完成：docs/limitations.md、docs/whitepaper-2026-11-14.md、docs/acceptance/feature-p0-p4-2026-11-15.md、setup.sh、run_matrix.sh、README 状态指针、claims/CHANGELOG | 同左；1626 tests，0 failed，8 skipped | 2739ead / CI 43614759619、43616285244 |
| P5 | Native Semantic Feedback Retry | 完成：真实 DeepSeek flash hard-sprintf 首轮无 RepairSpec native 失败 → 分类 candidate_crash/retryable → 反馈 planner → 第二轮 RepairSpec+assembly → native PASS；两轮候选与失败证据全部保留；仅反馈可观测字段（stdout/stderr/exit/signal/ABI）、timeout 不重试、硬上限 3 | artifacts/native-feedback-2026-11-15/；tests/test_native_feedback.py | bd9cbf6 / CI 43687651300、43687651314 |
| P6 | RepairSpec v2 | 完成解析与校验（嵌套 schema：vulnerability/program_context/security_invariants/repair/abi/verification；v1 兼容；target/地址 scope/allowed calls/ABI/capacity/strategy 白名单校验；非法 fail-closed）；诚实说明：本轮成功实验仍以 v1 plan 为主，v2 未有大规模真实模型证据 | tests/test_repair_spec_v2.py；docs/acceptance/p5-p9 | bd9cbf6 |
| P7 | 跨二进制、跨 CWE Benchmark | 完成首版：4 个独立二进制、3 类 CWE（CWE-121/122/787）+3 个原 hard case；DeepSeek flash 4/6 verified（hard-multicall/sprintf/nonconst + cwe122-heap-copy 未见二进制 verified）；CWE121 SECURITY_FAILED、CWE787 ASSEMBLY_REJECTED（绝对分支 ^） | fixtures/repair-benchmark/；artifacts/repair-benchmark-2026-11-15/ | bd9cbf6 |
| P8 | Model Qualification | 完成：同 6 case、同 planner/ABI/retry/gate；deepseek-flash 2/6、deepseek-v4-pro 2/6，且两者成功 case 不完全相同；结论=不能只看总分、要看 per-stage funnel | artifacts/model-qualification-2026-11-15/ | bd9cbf6 |
| P9 | Evidence Bundle / 稳定性 | 部分完成：repair_evidence.py（schema v2、SHA256SUMS、check 防篡改、tests）；但计划中的 3 次重复跨二进制稳定性实验未完成，只能标 partial | artifacts/repair-evidence 相关；docs/acceptance/p5-p9 | bd9cbf6 |
| P10 | Assembly Diagnostic Feedback | 完成并验证：assembly_policy/assembly_diagnostics/assembly_feedback（绝对分支、directive、forbidden token、调用白名单、行号/列号/token 结构化诊断）；不自动改写模型汇编；最多两轮反馈；CWE-787 从 ^ → native VERIFIED | artifacts/assembly-feedback-2026-11-16/ | dad21c9 / CI 43695637933、43695637887 |
| P11 | 36 次独立稳定性实验 | 完成：2 模型 × 6 case × 3 次独立进程/独立 out/独立 bundle = 36/36；19/36 verified（R_verified=0.528；flash 12/18、v4-pro 7/18；per-case：cwe122 6/6、cwe787 6/6、hard-nonconst 3/6、hard-multicall 2/6、hard-sprintf 2/6、cwe121 0/6） | artifacts/stability-2026-11-16/；tests/test_stability_matrix.py | dad21c9 |
| P12 | RepairSpec v2 真实集成 | 部分完成：DeepSeek flash 在 CWE-787 上返回 schema_version=2 的 plan 并完成 plan→validation→assembly→ABI→injection→native→VERIFIED；记录 plan_sha256/assembly_sha256/candidate_sha256/evidence links；但仅 1 个真实 case | artifacts/repair-spec-v2-2026-11-16/ | dad21c9 |
| P13 | Benchmark 扩展 | 完成：新增 CWE-125/190/476/134 四个 fixture（vuln.c/build.sh/build.json/original.elf/reference_fix.c/defect.json/PoC/regression/dev-hidden split）；总计 8 个独立二进制、7 类 CWE；结果 CWE-125 VERIFIED、CWE-190 VERIFIED、hidden CWE-476 VERIFIED、CWE-134 PLAN_INVALID | artifacts/repair-benchmark-expansion-2026-11-16/ | dad21c9 |
| P14 | Native Trace（N1–N6） | 部分：native_trace.py 完成 N1（exit/signal/stdout/stderr）与 N2（PoC/regression 行为差异）；N3+（寄存器/栈/内存/控制流/函数返回 errno）因 guest 无 gdb 明确 not_run，不伪造 | app/services/native_trace.py；tests/test_native_trace.py | dad21c9 |
| P15 | 更强验证与 fuzz | 部分：复用 independent_verifier、新增确定性 mutation plan 生成器（固定 seed/count/可复现输入）与测试；无 AFL campaign、无符号执行、未把 independent verifier 接入全部 benchmark | scripts/fuzz_repair_benchmark.py；tests/test_fuzz_repair_benchmark.py | dad21c9 |
| P16 | 统一独立验证器 | 部分：verify_repair_benchmark.py + independent verifier 显式 allow_resize/append；10 条候选记录 6 verified / 1 rejected / 3 not_run（not_run 因所选 run 目录缺 candidate artifact）；未达 8/8 全部纳入 | artifacts/independent-verification-2026-11-16/ | c5d87b5 / CI 43703724955、43703724942 |
| P17 | 解决 CWE-121 / CWE-134 | 失败（负结果保留）：CWE-121 仍 SECURITY_FAILED（candidate stdout=""、exit=0，PoC 要求 exit 1+精确 stderr）；CWE-134 仍 PLAN_INVALID；未降低 gate 强行置绿 | docs/acceptance/p16-p20-2026-11-16.md | c5d87b5 |
| P18 | 扩展稳定性实验（48/60 次） | 未完成：仍只有 P11 的 36 次；新 benchmark 为 10 case，完整矩阵应为 2×10×3=60；报告明确不能把 P11 当 P18 结果 | docs/acceptance/p16-p20 | c5d87b5 |
| P19 | N3–N6 Native Trace | 部分/环境阻塞：guest strace available、gdb not available；N1/N2 已实现，N3–N6 未运行、不伪造 | app/services/native_trace.py | c5d87b5 |
| P20 | 真正的 Fuzzing | 部分：仅确定性 mutation plan + 测试；无 AFL/AFL++ campaign、coverage feedback、crash/hang 去重、符号执行 | scripts/fuzz_repair_benchmark.py | c5d87b5 |
| P16-R | 返工：统一验证链 | 失败/部分：真实 patch plan 进入 verifier 后 10 条记录 0 verified / 8 rejected / 2 not_run；失败原因已具体化：自动 patch plan 的 header_update 缺 authorization_ref、cave ABI block 推导错误（no_ret/stack_misaligned_before_call）、target scope 组合检查、候选 artifact 缺失 | docs/acceptance（p16-r 相关）；artifacts/independent-verification-2026-11-16/ | 106d1cd / CI 43707923361、43707923227 |
| P16-R2 | 返工 2：真实 patch-plan builder | 部分：不再从候选 diff 伪造 patch plan，改用 binary_pipeline.build_patch_plan；CWE-122 上 layout-plan/action-replay/target-scope/runtime-oracle/independence 五项通过，但 ABI 仍失败（symbol_function no_ret / branch_target_unknown；cave ABI block 未走统一 PT_LOAD VA/file-offset 映射）；严格路径仍 0 verified | docs/acceptance/p16-r2-2026-11-16.md | 085fc38 / CI 43713295997、43713296021 |
| P16-R3 | 返工 3：PT_LOAD 映射 + artifact 状态 | 部分/实质突破：新增 app/services/elf_mapping.py（只通过 PT_LOAD 做 VA↔file-offset 映射，显式状态 MAPPED_FILE_BACKED/MAPPED_MEMORY_ONLY/OUTSIDE_PT_LOAD/AMBIGUOUS_SEGMENT/INVALID_FILE_RANGE/INVALID_ALIGNMENT）；verification_semantics.derive_abi_blocks 先 PT_LOAD 后 section；benchmark verifier 使用真实 build_patch_plan、单独输出 ARTIFACT_MISSING。10 条记录：7 independently verified / 1 rejected（CWE-121）/ 2 ARTIFACT_MISSING（CWE-787、CWE-134）；CWE-122 同时通过 layout-plan/action-replay/target-scope/abi/runtime-oracle/independence（真实严格结果，不是 allow-resize 宽松路径）。仍未完成：CaveABIBlock 出口语义（tail_jump/continuation/noreturn）、policy-issued Authorization Record（当前仍是静态引用）、两条缺失 artifact 未恢复。状态 PARTIAL，严格验证 7/10 verified | docs/acceptance/p16-r3-2026-11-16.md；artifacts/independent-verification-p16r3-2026-11-16/README.md | f42e6c4 / CI 43723326346、43723326360；2044 tests / 0 failed / 9 skipped / 929.8 s |
| P21 | 冻结 P16-R3 实验基线 | 完成：scripts/freeze_experiment.py；experiments/p21-p16r3-658ff8c/profile.json（profile_id p21-p16r3-658ff8c，source_commit 658ff8c，verifier_profile P16R3_PLAN_AWARE，authorization_profile STATIC_REFERENCE_ONLY，semantic_trace NOT_RUN，fuzzing NOT_RUN，tests 2044，含 benchmark/verifier/verification_semantics/patch_plan/verification/repairspec/p16r3 七个 hash）；镜像证据 artifacts/p21-p16r3-profile-2026-11-16/。说明：冻结 commit 含 P16-R3 代码与 P21/P22 工具，不是纯 f42e6c4；明确标注不是 policy-issued authorization | experiments/p21-p16r3-658ff8c/profile.json | a1755a5 / CI 43729513475、43729513476 |
| P22 | 10 个 case 的 artifact 审计 | 完成：scripts/audit_artifacts.py；结果 8 RECOVERED_HISTORICAL / 2 ARTIFACT_MISSING_CONFIRMED（cwe787-index-write、cwe134-format-string）；未用新候选替换历史 artifact | artifacts/p22-artifact-audit-2026-11-16/audit.json | a1755a5 |
| P23 | 稳定性 runner 改用独立 verifier | 部分：run_stability_matrix.py 读取冻结 profile、每次 run 写 run-manifest.json、候选验证走独立 verifier（区分 verified/PLAN_INVALID/NO_CANDIDATE/ARTIFACT_MISSING/NOT_RUN）；--smoke/--experiment-id/--profile；单次 smoke（hard-multicall，deepseek-flash）结果 PLAN_INVALID；完整 60 次矩阵启动后因 live provider 延迟过高在第一个 case 后停止；partial 记录明确标注「不是 60-run 结果」 | artifacts/p23-smoke-2026-11-16/README.md；artifacts/p23-stability-partial-2026-11-16/README.md | a1755a5 |
| P24 | 统计工具 | 部分：scripts/summarize_stability.py + tests（test_experiment_profile.py/test_artifact_audit.py/test_stability_summary.py），可区分 ARTIFACT_MISSING 与模型失败、计算 R_verified/R_robustness、按模型/case 聚合；因 60 次矩阵未完成，无正式 P24 全量报告 | scripts/summarize_stability.py | a1755a5；2048 tests / 0 failed / 9 skipped / 889.2 s |
| P25–P30 | CaveABIBlock 出口语义 / policy-issued Authorization Record / CWE-121 Behavior Contract / CWE-134 字段级诊断 / GDB N3–N6 / AFL++ campaign | 全部未实现：P25/P26 需要新 verifier profile（不污染 P21 冻结基线）；P27/P28 需专门模型运行与诊断；P29 环境无 GDB；P30 无真实 AFL campaign | docs/acceptance/p21-p24-2026-11-16.md §P25-P30 | a1755a5 |

P16-R3 的 7 条严格 verified：hard-multicall、hard-sprintf、hard-nonconst、cwe122-heap-copy、cwe125-oob-read、cwe190-integer-overflow、cwe476-null-deref；rejected：cwe121-unchecked-strcpy；ARTIFACT_MISSING：cwe787-index-write、cwe134-format-string。

## 5. 未完成任务、失败/负结果、阻塞、风险与遗留问题（逐条）

### A. 交付件/环境层

A1. **F1 legacy ELF x86-64 fail-open（v7 冻结源码未修）**
- 现象：验证失败/异常时 binary_pipeline.py:195/207-216/279-287 仍保留 candidate_available 并返回候选，repair_binary CLI 报 supported=true。
- 根因：历史 ELF 路径只在 gate 失败时改 status=not_verified，未清 candidate_available、未 return None；与 unified_verification「not_verified/static_only 不得作为 success」原则相悖。
- 当时建议：v7 不改冻结源码，以 HANDOFF-TASKS F1 记录复现步骤、影响、必需修复与回归测试要求；对外写明「存在已知 F1 例外」。
- 后续：v5 分支已消除该历史 fail-open（seq 3298/4180 报告），但 v7 冻结交付件仍带该已知缺陷（属版本冻结问题，不是修复失败）。

A2. **CGC basic_messaging POV replay 对运行上下文敏感**
- 现象：脚本化验收 4 次运行中 3 次未触发（v6 3/3、v7-rc 9/9、v7-final 9/9 均未触发），1 次触发（v6.1 参照 3/3）；独立 shell/近邻脚本复跑 20+ 次均触发。
- 根因：残余解释为 qemu-user 下堆/ASLR/时序随机性；已排除脚本化重定向/命令替换、前置 pytest/smoke 状态、4x CPU 负载、Palindrome 先行顺序等确定性因素（claims-auditor 7 组对照）。
- 当时建议：降级为 exploratory-only、不作 gate；把「使 replay 确定化（显式 fd/时序处理或固定随机源）」列为后续任务；v7 已披露 *_patched 为上游 -DPATCHED 构建、非引擎产物。

A3. **v6 Linux 计数不可按 runbook 稳定复现（umask）**
- 现象：VM 默认 umask 002 时 938/7/5（5 例 test_guest_executor.py 失败）。
- 根因：workers/executor/self_test.py:44-45 mkdir 受外部 umask 影响 → 包根 0775 → run_job.py:214-216 拒绝 group-writable 包根。
- 建议：v7 已做 run-baseline/run-smoke 的 umask 022 归一化并写入手册；审计另建议 self_test 显式 chmod 0755，避免再依赖外部 umask（未采纳/后续）。

A4. **readelf 外部依赖未替换**
- 现象：仍依赖 Linux GNU readelf；macOS 缺 readelf 时 test_static_routeb_bundle 会失败（本机装 Homebrew GNU readelf 2.47 解决，不是替换后端/弱化测试）。
- 建议：按方法建议 §9.3 替换为 LIEF/llvm-readelf 后端（至会话结束仍未做）。

A5. **Windows PE 原生运行、32 位 Mach-O、大端、fat Mach-O 重写等环境/能力缺口**
- v7 P2 与 LIMITATIONS 明确：Windows PE 原生运行、32 位/fat Mach-O、堆/全局/sprintf/UAF/整数/循环等仍为 HANDOFF 任务；fat Mach-O 只分析不回写。

### B. 验证能力/证据层

B1. **gate 未内建 PoC 失效判据（v7 时点）**
- 现象：PoC 失效证据只在测试层（Mach-O 原生崩溃差分、PE/AArch64 emulated canary、ELF x86-64 Unicorn sentinel），不是 gate 判据。
- 后续：0adcd68 起 poc.original_fails/poc.candidate_passes 进入 gate（函数级 runtime 差分）；但完整 guest/kernel PoC replay 仍未实现（PE、32-bit Mach-O、跨架构、非可信上传文件）。

B2. **gate 残留语义盲区（puts/stdout 副作用）**
- 现象：asm_roundtrip 重写整函数后省略原 puts，内存安全通过，但 stdout/副作用未被比较；gate 盲区实验 4/5 抓住、1 残留。
- 后续：12d05ec 起 poc_runner 增加 stdout_signature，unified_verification 增加 required poc.native.stdout_signature；heap-canary 早退候选被归为 regression；但无 PoC 的 asm 路径仍可能省略 puts 通过内存 gate（明确记录为限制）。

B3. **副作用等价只做到「可抓的 I/O + exit + stdout + errno 代理」**
- stdout 签名、strace syscall errno 代理、LD_PRELOAD 进程退出级 TLS errno；函数返回瞬间 errno、堆内部布局、fd offset、锁、locale、资源泄漏、全程序等价均未覆盖（docs/limitations.md）。
- 建议：ptrace/GDB 断点方案（函数 ret 处捕获精确 errno）仍为后续；环境无 GDB 是 P19/P29 的阻塞。

B4. **MoC：独立验证器的严格性反复暴露为「验证工程问题」而非模型失败**
- 现象：P16 宽松 allow-resize 路径 6 verified；P16-R 严格路径 0 verified（8 rejected）；P16-R2 0 verified（CWE122 五项通过但 ABI 失败）；P16-R3 修 PT_LOAD 后 7 verified。
- 根因：不同模块对「补丁位于哪里、允许改什么、代码块如何退出、ABI 应如何分析」未共享同一套可验证事实（cave/PT_LOAD/section 映射、authorization、target scope）。
- 遗留：CaveABIBlock 的 tail-jump/continuation/noreturn 出口语义、policy-issued Authorization Record、两条 ARTIFACT_MISSING 恢复。

### C. AI 能力/非 loop / 模型层

C1. **AI 真实增量早期为零，后经硬案例基准首次测到 1**
- 现象：真实 provider 6 任务 3/6 verified vs baseline 6/6，coverage increment 0（全部夹具 baseline 可修）；硬案例基准 baseline 0/2、AI 1/2（inline-byte-loop）。
- 根因：夹具可被确定性引擎修复，无法测增量；需要「baseline 明确失败、AI 可尝试」的 gate-blind 用例。
- 后续：公平性消融把定位与生成能力分开（target-aware deterministic 0/10，AI target 6/10，blind 0/10，契约详细度效应 0）；但 6 个成功全是内联 loop 家族，案例非独立、单/少模型，不构成泛化结论。

C2. **非 loop 家族 0/6 的根因链**
- 早期：leaf-only assembly 禁 call → 无法调用 printLine/exit/strlen 等。
- Path A（放宽 call 白名单）实测无效（0/6 不变）；heap-canary 出现「PoC 过但短输入 stdout regression 失败」。
- 范式 A（函数级替换）先 loop 闭环，再用 CWE121（人工审查 br_fail syscall helper）跑通非 loop A；接着 symbol_resolver（纯函数模板/syscall 模板/动态 PLT 白名单/黑名单）把人工 helper 固化为可复用层；CWE121 非 loop PASS（2/2 PoC+4/4 regression，fixed SHA 463a9758…）。
- 遗留：通用符号解析仍非任意 libc（fputs 仅 stderr 降级、未知语义 fail-closed）；CWE121 公开 case 在后续 P11/P17 又反复失败（0/6、SECURITY_FAILED，行为契约未满足）；CWE134 一直 PLAN_INVALID。

C3. **3/3 非 loop AI VERIFIED（seq 15377，a8934fe）**
- 成果：hard-multicall / hard-sprintf / hard-nonconst 三例 AI VERIFIED（候选 SHA aab33ae…/ea83b59…/2e12599…），满足 overflow PoC（原崩溃、候选 exit 0）、regression、ABI 静态检查 ok=true fatal=0、run manifest VERIFIED:1，非 reference fix/人工候选。
- 根因修复：cave relocation 把 call 写到错误文件位置（VA 落在 .tbss 虚拟范围，旧代码按 section 映射把 .tbss file offset 当 cave offset → call e8 00 00 00 00）；改为 cave VA 优先按 PT_LOAD program header 映射、再 fallback section；加 RepairSpec 规划约束和 CFG-aware ABI 检查。
- 边界：3 例来自同一 hard-case binary；模型 A/B 显示 v4-pro 0/3（ABI fatal/plan 空/非法 call 0x0）→ 模型能力仍是变量。

C4. **多模型结论**
- 4 个真实模型：flash/v4-pro 6/12（loop 6/6、非 loop 0/6）；Qwen3-8B / Qwen2.5-7B（CN 免费）0/12。结论：非 loop 不能靠换小模型解决，根因仍是 leaf-only/符号缺口；4 模型只验证 loop 家族稳健性，不改变根因。
- 遗留：5–6 模型未扩；GLM-Z1 单点 probe 超时；免费池限流/402 阻断过矩阵。

C5. **模型结果随机性**
- P8/P11：同代码同 case 不同 run 成功集合不同；P11 36 次 19/36（52.8%）；P23 smoke 单次 PLAN_INVALID；P16-R3 严格验证的 7 条来自历史 run（未重跑）。
- 建议：完整 60 次矩阵、多模型、独立样本、置信区间仍缺；不能用单次/旧 run 结果外推。

### D. 凭据/环境/Git/流程层

D1. **API key 多次无效/受限**
- SiliconFlow .cn key：HTTP 401 code 30014 Token is invalid；国际站 key：/v1/models 200 且 identity 通过，但 benchmark 全部 402 余额不足；DashScope/DeepSeek 对该 key 也 401；DeepSeek 官方有效 key 仅 2 个模型。
- 处理：坚持不伪造结果，identity probe 严格校验 resp.model==requested；最终用 CN 免费模型完成 4 模型矩阵。

D2. **86587da（capacity-check 并行提交）的隔离与处置**
- 隔离：worktree-capacity-check（/Users/.../worktree-capacity-check）+ backup/capacity-86587da；capacity 目标测试 71 passed/4 skipped；未 merge/push。
- 后续：11755 建议导出 patch 清空 stash、删除 worktree 保留 backup；12593/13239 执行：capacity 144K + coverage 310K patch 归档到 ../capacity-archive-2026-11-14/，worktree 删除，coverage-audit 分支独立推送，stash 清空；86587da 工作最终未合入 feature（按「暂不合并」决策）。

D3. **多会话并发导致的 Git 分叉**
- 现象：主工作区 binary-repair-gui 被并行 coverage/capacity 工作流切到 coverage-audit-2026-11-14；workbench-v3 被推进到 090ad94，与 feature c3dae2f 分叉；feature push 不触发 CI（workflow 只在 workbench-v3/PR/main 触发）。
- 处理：最终验证固定在 worktree-feature-final/；feature rebase 到 origin/workbench-v3 后 fast-forward 合并 workbench-v3（6cc51d3 收尾），CI 43601736542 @7a5d21f success；CI 暴露并修复两个环境相关测试问题（ELF x86_64 runtime tier 接受 native_run/emulated_run；Mach-O Rosetta capability 测试显式模拟 engine ready）。
- 遗留风险：主工作区仍保留 coverage 分支（未切回），依赖 worktree 隔离作为长期工作方式。

D4. **本机 macOS readelf / AppleDouble / umask 等环境噪声**
- macOS 缺 GNU readelf → test_static_routeb_bundle 失败（装 Homebrew readelf 解决，非代码修复）；macOS 传输产生 ._* AppleDouble 导致首次 Linux 跑 203 failures（清理后 canonical）；Linux VM 需 umask 022。均已在验收文档注明为环境问题。

### E. 阶段实验缺口（P18/P19/P20/P23/P24/P25–P30）

E1. **P18 60 次稳定性实验未执行**：唯一正式稳定性数据仍是 P11 的 36 次 19/36；新 benchmark 10 case → 应为 2×10×3=60；报告明确不能把 P11 当 P18。建议：用新的 experiment ID 从完整 60 次重新开始，冻结 profile 后再跑，禁止用旧 run 补齐。
E2. **P23 完整 60 次矩阵未完成**：runner 已用独立 verifier 且 smoke 跑通（hard-multicall PLAN_INVALID）；完整矩阵启动后因 live provider 延迟过高在第一个 case 后停止，partial 记录明确不是 60-run。
E3. **P19/P29 N3–N6 被环境阻塞**：Linux guest strace available、gdb not available；寄存器/栈/内存/控制流/函数返回 errno 未实现（不伪造）。建议：先在 Linux guest 内安装/启用 gdb 并解决 ptrace 权限、stripped 目标断点定位问题，再实现 N3–N6。
E4. **P20/P30 fuzzing 未完成**：只有确定性 mutation plan、固定 seed、可复现输入；无 AFL/AFL++ campaign、coverage feedback、crash/hang 去重、符号执行。建议：在统一验证与稳定性成立后再做真实 AFL++ campaign，并把新 crash 纳入 regression/独立验证器。
E5. **P24 无全量统计报告**：工具已建立但无正式矩阵结果。
E6. **P25/P26/P27/P28 未实现**：CaveABIBlock 完整出口语义、policy-issued Authorization Record、CWE-121 Behavior Contract、CWE-134 字段级诊断。
E7. **P16 系未达 10/10**：7 verified + 1 rejected + 2 artifact missing；两条缺失 artifact 未恢复/未替换。

### F. 声明纪律与「不能声称」

F1. 「任意二进制修复 100%」不可承诺（用户/组长多次强调）；v5 的 100% 只指批准计划 G1–G5 与确定性矩阵完成度。
F2. 脚本化 AI 证据用 deterministic stand-in，不代表真实 LLM 修复质量；真实 provider 实验为 exploratory、不是 CI 门禁。
F3. 真实增量早期为零；后续 3/3、hidden CWE-476 等成功样本小、模型/随机性依赖明显，不能外推。
F4. 无形式化安全保证、无全程序等价、无真实 PoC 完备性。

## 6. 该会话 spawn 的 teammate 名单、任务与结果

共 6 个 teammate（team/member 事件 12 条 = 6 人 × provisioning/active），10 个共享任务（task-1…task-10，全部 completed）。

| teammate | spawn 证据 | 任务（写范围/内容） | 结果与证据 |
|---|---|---|---|
| evidence-auditor（id 7945b4e0…） | team/member seq 212/214 @16:20 | task-1：审核 v6 交付件证据链与外层一致性（只读；不许改交付件/不用 VM） | audit-evidence.md（437 行，35,716 B）；Conditional PASS：P0=0/P1=5/P2=9；zip sha、SHA256SUMS 2227/2227、MANIFEST、29 个嵌套清单、CI API 7/7 字段、两份 junit、Linux 7 skip=1+4+2、GitHub 注解 943/7/0/950 全部实测一致；交付消息 seq 453/454 @16:31 |
| claims-auditor（id 8a5d3b4e…） | team/member seq 217/219 @16:20 | task-2：审核 v6 功能声称与测试语义（只读；不用 VM/不跑全量 pytest） | audit-claims.md（525 行）；P0=0/P1=4/P2=9；7 skip 归因精确、负向对照 fail-closed、Mach-O native 本机复现（SIGSEGV -11/SIGBUS -10）、CGC replay 真实 qemu 且返回码顺序安全、gate 语义 fail-closed（除 P1-2 潜在路径）；中途发现 CGC basic_messaging 脚本化不可稳定触发并推动 v7 降级；交付消息 seq 743/832/951/1055/1056 |
| engine-i386（id 74dba8e8…） | team/member seq 1803/1805 @17:26 | task-3：i386 引擎（analyzer/guards/writer/ELF32-PE32 注入）+ 夹具；task-6：高级夹具（动态 ELF32、PE32 FF15、i386 memcpy immediate、ELF32 extend-rx） | task-3：analyzer_i386.py、guards_i386.py、writer/code_cave/pe_repair/containers 扩展、2 个夹具与测试；必做 49 passed、回归 sweep 133 passed/2 skipped；task-6：3 个新夹具（sha 见 §3.1）+ extend-rx 单测，必做 61 passed；交付 seq 1948/2378/2389、3770/3783 |
| runtime-i386（id 09a5ff9d…） | team/member seq 1808/1810 @17:26 | task-4：i386 Unicorn 运行时证据；task-7：长度感知 Unicorn 模型（memcpy immediate verified） | task-4：emulated.py +268/−49，tier=emulated_run/engine=unicorn-i386；13 passed，两夹具 repair(verify=True) → patched/gate pass；task-7：长度感知（i386 cdecl [esp+12]、SysV rdx、Win64 r8、AArch64 x2；memcpy 家族 output_len=None），17 项测试（含三 ABI 合成验证）；交付 seq 2352/2353/2420/2435、3807/3814 |
| product-ui（id fd089f4b…） | team/member seq 1813/1815 @17:26 | task-5：/binary 页面与前端测试；task-9：两条 AI 路径 UI（第一代 ai_plan/ai_bytes）；task-10：改为产品两条路径 asm_roundtrip/binary_direct | task-5：binary.html/js/css、base.html 侧栏、i18n；10 passed + UI 回归 111 passed；task-9：13 passed（含 200/422/503 契约）；task-10：两卡/新 testid/新文案，11 用例重写并通过；交付 seq 2101/2102、4461/4501/4512、5846/5862 |
| ai-patch-engine（id 1c3a0043…） | team/member seq 4316/4318 @19:02 | task-8：AI 路径二机器码/就地字节补丁校验器 | 新增 app/services/ai_patch_validation.py（690 行）+ tests/test_ai_patch_validation.py（453 行，35 个测试）；apply_ai_patch fail-closed、Capstone 完整解码/白名单/黑名单/分支目标块内/同长度 before 匹配；35 passed in 4.71s；端到端与 Lead 的 ai_repair 联调 verified_patch；风险已上报（仅结构安全、语义归 gate、Mach-O 注入未单测）；交付 seq 4666/4668 |

共享任务状态：task-1…task-10 全部 completed；其中 task-3/6 同属 engine-i386，task-4/7 同属 runtime-i386，task-5/9/10 同属 product-ui；任务写范围互不重叠（Lead 明确写范围，符合团队并行约束）。团队流程要点：审计员只写各自报告文件；实现 teammate 不 commit/branch/push，由 Lead 统一提交；teammate 间发现契约问题通过 send_message 澄清（如 runtime-i386 与 engine-i386 的 FF15 期望值 0x40100E 旧快照争议，经复核为测试自身早期错误）。

## 7. 该会话最终仓库状态与最终能力声明

### 7.1 会话结束时（11-15 23:39）状态

| 项 | 状态 | 证据 |
|---|---|---|
| 分支/提交 | feature/ai-binary-repair = workbench-v3 = a1755a5（「feat(p21-p24): frozen profile, artifact audit, independent stability runner and smoke evidence」）；main = 8869b07 未动 | seq 19352；GitHub API run 43729513475/43729513476 head_sha=a1755a5 head_branch=workbench-v3 success；git ls-remote 当前 feature/ai-binary-repair=a1755a5 |
| CI | 43729513475（Ubuntu verification）与 43729513476（CI）均 success（API 复核） | 附录 A |
| 测试 | 2048 tests / 0 failed / 0 errors / 9 skipped / 889.2 s（本机 macOS） | seq 19352；v5 acceptance 文档同数字 |
| 工作区 | 干净，仅 .venv 未跟踪；最终验证在 worktree-feature-final/ | seq 19352 |
| 关键冻结产物 | experiments/p21-p16r3-658ff8c/profile.json（P16R3_PLAN_AWARE / STATIC_REFERENCE_ONLY / NOT_RUN / 2044 tests）；artifacts/p21-p16r3-profile-2026-11-16/；artifacts/p22-artifact-audit-2026-11-16/；artifacts/p23-smoke-2026-11-16/；artifacts/p23-stability-partial-2026-11-16/；artifacts/independent-verification-p16r3-2026-11-16/ | 会话内与仓库内文件（已确认存在） |
| 会话后状态（不在本会话范围） | 远端 workbench-v3 现为 4a7b2355（release/2026-11-16-phase8c-final，Phase-8C 最终）；release/2026-11-16-phase8c-evidence 为 ec503e4；a1755a5 是 ec503e4 的祖先；main 仍 8869b07 | team/BRIEF.md；git ls-remote（refs/heads/workbench-v3=4a7b2355、refs/heads/release/2026-11-16-phase8c-evidence=ec503e4）；本地 git merge-base 验证 a1755a5 是 ec503e4 祖先 |

### 7.2 最终能力声明（会话末尾口径）

可以声称：
1. 存在真实的二进制修复闭环：ELF/PE/Mach-O 解析 → 修复计划/汇编 → 注入 → ABI 检查 → native PoC/regression → 独立验证器 → 证据 bundle。
2. P11 有 36 次真实独立稳定性实验，19/36 VERIFIED（≈52.8%，2 模型 × 6 case × 3 重复，每 run 独立进程/目录/证据）。
3. P12 有 1 个真实 RepairSpec v2 → native VERIFIED 的完整 trace（CWE-787）。
4. P13 有 hidden CWE-476 VERIFIED（未见二进制）；benchmark 已到 8 个二进制、7 类 CWE。
5. P16-R3 有 7 条严格 plan-aware 独立验证（hard-multicall/hard-sprintf/hard-nonconst/cwe122/cwe125/cwe190/cwe476）；CWE-122 同时通过 layout/action/scope/ABI/oracle/independence。
6. CWE-121 非 loop 范式 A 单函数闭环曾 PASS（2/2 PoC + 4/4 regression，fixed SHA 463a9758…）；符号解析器/纯函数模板/syscall 模板/动态 PLT 白名单有可复用实现与测试。
7. 4 模型真实矩阵完成（2 大模型 6/12，2 小模型 0/12），identity 全部 exact；防模型缩水机制生效。
8. 2048 tests / CI 双 workflow 通过。

不能声称：
1. 通用任意二进制修复、任意漏洞修复或确定性成功率。
2. P16 已完成 10/10 VERIFIED；严格路径已全部可信（还缺 CaveABIBlock 出口语义与 policy-issued Authorization Record）。
3. CWE-121/CWE-134 已修复（前者 SECURITY_FAILED/Behavior Contract 未满足，后者 PLAN_INVALID）。
4. 60 次稳定性实验已完成（P18/P23 均未完成；只有 P11 的 36 次）。
5. N3–N6 native trace 已实现（只有 N1/N2，无 GDB）。
6. AFL++ fuzzing 已完成（只有确定性 mutation plan）。
7. 跨模型稳定、跨架构（arm32/riscv/mips/ppc/大端/32 位/fat Mach-O）、PIE/stripped/static 普遍支持。
8. 形式化安全保证、全程序等价、无新漏洞、函数返回级 errno 精确等价。
9. 完整 PoC 级证明：PoC 判据是函数级 runtime 差分 + 原生 PoC manifest 子集，不是所有路径的 guest/kernel replay。
10. 「AI 增量已普遍证明」：P0–P4 之前真实增量曾为 0；后续 3/3、hidden CWE-476、P16-R3 7/10 等样本小、随机性明显，不可外推。

## 8. 未核实事项（诚实标注）

1. 本机未重跑任何 pytest/基准/LLM 调用；1626/1641/1954/1966/2041/2044/2048 等测试数字来自会话报告与仓库 JUnit/acceptance 文档，未独立复算。
2. LLM 真实调用结果（3/6、6/12、19/36、7/10 candidate 状态等）来自会话 artifact（artifacts/*）与报告，未重放（需 provider key + Linux VM + 历史 run 目录）。
3. 45 个 CI run 的元数据（run id/head_sha/head_branch/conclusion）已用 GitHub API 逐条复核，但未核对 CI artifacts 内容与 check-run annotations 原文（除审计报告引用的 v7 注解数字）。
4. P22 audit.json 引用的 /tmp/p7final-flash 等临时 candidate 路径在分析机上不一定仍然存在；本次只确认 audit.json/README 存在与内容，未验证 /tmp 下候选文件本体。
5. Phase-8A/8B/8C（11-16 之后）的细节不在本会话范围；本报告只按 BRIEF.md 与远端 refs 记录 workbench-v3=4a7b2355/release phase8c evidence=ec503e4，未展开其内容。
6. 会话中出现的 API key 未做任何复验/使用；报告只记录其被平台拒绝的事实（401/402）。
7. SiliconFlow/DeepSeek provider 的 4 模型 identity/矩阵结果未在本机复现，仅引用 artifacts 与报告。
8. v6/v6.1/v7 zip 的包内文件内容未重新校验（只读了 .sha256、FINAL 报告与审计报告；zip 本体未重算哈希）。

## 附录 A：独立复核记录

### A.1 CI run 复核（GitHub API，45/45 success）

| 阶段 | run id（head_sha） |
|---|---|
| v7 handoff 证据链 | 43390831537 (e1756a2) |
| v5 universal repair | 43411767923 (47465e0)、43412399232 (f65c2dc)、43412905037 (72db891) |
| 第一代两条 AI 路径 | 43418024120 (abeab27)、43418615884 (6d525ca)、43421560913 (af8f674) |
| 重做 asm_roundtrip/binary_direct | 43426508766 (61287fd)、43427654178 (aa45b36) |
| PoC 差分/gate 盲区 | 43435227438 (60362a9)、43436452584 (455011f) |
| native PoC + 静态门禁 | 43449603578 (2fb9317)、43451324919 (54b575f) |
| 硬案例基准 | 43457857951 (4ee5e5d)、43458988294 (0adcd68) |
| 公平性消融 | 43555871445 (853dd04)、43556499270 (eb1f0a4)、43559328831 (24f8e2b) |
| 12 案/7 家族 | 43560207206 (afb1e85) |
| provider profiles | 43563347462 (91e4706)、43565353034 (4349a92) |
| Ghidra 工具链 | 43570678371 (6a12bb8) |
| 双模型矩阵 | 43573457659 (fd205dc) |
| Path A / 范式 A loop | 43579784063 (148df69) |
| CWE121 非 loop A | 43582808690 (fa80f50) |
| symbol resolver / 合并前 | 43589156716 (8dc9c85)、43589863303 (6afe122) |
| feature→workbench 合并 | 43601736542 (7a5d21f) |
| errno/Path B 对照 | 43608147997 (5f9dd77) |
| P0–P4 | 43614759619 (f2392fd)、43616285244 (2739ead) |
| 3/3 非 loop | 43628367481、43628367473 (a8934fe) |
| P5–P9 | 43687651300、43687651314 (bd9cbf6) |
| P10–P15 | 43695637933、43695637887 (dad21c9) |
| P16–P20 | 43703724955、43703724942 (c5d87b5) |
| P16-R | 43707923361、43707923227 (106d1cd) |
| P16-R2 | 43713295997、43713296021 (085fc38) |
| P16-R3 | 43723326346、43723326360 (f42e6c4) |
| P21–P24 | 43729513475、43729513476 (a1755a5) |

复核字段：head_sha 与报告一致；head_branch 均为 workbench-v3；conclusion 均为 success。

### A.2 commit 存在性（git cat-file，全部存在）

a1755a5、f42e6c4、12945c3、bd9cbf6、dad21c9、c5d87b5、106d1cd、085fc38、2739ead、c8af199、6cc51d3、12d05ec、6afe122、c3dae2f、d69c84b、14971d9、afe4aee、bf5da88、ab679ef、eb1f0a4、0adcd68、54b575f、455011f、aa45b36、6d525ca、72db891、915f362、e1756a2（在 worktree-feature-final 仓库中逐一 git cat-file -t = commit）。

### A.3 关键证据路径存在性（已确认）

- handoff/BinaryRepair-Linux-Handoff-2026-11-13-v7.zip + .sha256；handoff/final-verification-2026-11-13/{FINAL-LINUX-VERIFICATION.md, audit-evidence.md, audit-claims.md, evidence/, scripts/}
- worktree-feature-final/docs/acceptance/{binary-universal-v5-2026-11-13.md, ai-binary-repair-2026-11-13.md, feature-p0-p4-2026-11-15.md, p5-p9-2026-11-15.md, p10-p15-2026-11-16.md, p16-p20-2026-11-16.md, p16-r2-2026-11-16.md, p16-r3-2026-11-16.md, p21-p24-2026-11-16.md, LIMITATIONS.md}
- worktree-feature-final/{app/services/elf_mapping.py, app/services/native_trace.py, app/services/repair_spec.py, app/services/repair/abi.py, scripts/freeze_experiment.py, scripts/audit_artifacts.py, scripts/run_stability_matrix.py, scripts/summarize_stability.py}
- worktree-feature-final/experiments/p21-p16r3-658ff8c/profile.json
- worktree-feature-final/artifacts/{independent-verification-p16r3-2026-11-16/README.md, p22-artifact-audit-2026-11-16/audit.json, p23-smoke-2026-11-16/README.md, p23-stability-partial-2026-11-16/README.md, binary-universal-v5-2026-11-13/, ai-direct-binary-2026-11-13/, hard-case-benchmark-2026-11-13/summary.json, fairness-ablation-2026-11-14/aggregate.json, multi-model-matrix-cn-2026-11-14/README.md, paradigm-a-cwe121-2026-11-14/README.md}

## 附录 B：会话关键统计

- 事件总数 19,358；tool/call 2,500；tool/result 2,587；assistant/message 2,300（其中 35 条含正式 text 报告）；user/message 297（其中 33 条 source.kind=user）；turn/start 35、turn/end 35；team/task 30（10 个任务、多版本）；team/member 12（6 人）。
- goal/change 4 次：goal-b84c2a26（v5 全部剩余缺口，seq 3429 创建 @18:17:38，seq 4175 complete @18:58:39）；goal-9915435f（两条 AI 直接二进制路径，seq 4263 创建 @19:01:51，seq 5073 complete @19:41:53）。
- todo/write 8 次；deliverables/presented 1 次（seq 1299 @17:06:19，v7 zip + FINAL-LINUX-VERIFICATION.md）。
- 用户提供过的第三方 key：SiliconFlow CN/US、DashScope、DeepSeek 等（会话内明文出现）；分析中未复验、未使用，仅记录平台响应（401/402）。
