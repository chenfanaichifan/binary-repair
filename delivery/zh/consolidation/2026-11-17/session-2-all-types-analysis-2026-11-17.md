# 会话二考古：`b139b586`「全类型二进制修复-1」逐阶段与最终状态

> 角度 2 / 6。只读调查，未修改仓库、会话日志或任何 git 引用。
> 结论口径见文末「假设与判定方法」。

---

## 0. 会话元信息

| 项 | 值 | 证据 |
|---|---|---|
| session id | `session-b139b586-985b-475c-af5a-1ee7f0082668` | 目录名 |
| 日志文件 | `session.v4.jsonl.zstd`，15,267,674 B（解压 59,418,413 B / 18,457 行） | `ls -l`；`zstd -dc ... \| wc -lc` |
| 时间跨度 | 2026-11-14 15:12:55 → 2026-11-17 01:31:28（约 58.3 h，含两段长空档） | `time=1794640375276` / `1794850288509` |
| turn 数 | **16**（T11、T12 为 transport error 提前结束；T10、T16 由后台任务通知驱动，T12 由用户「请重试」驱动） | `turn/start`/`turn/end` 16 组 |
| 事件构成 | assistant/message 2168、tool/call 2377（bash 1717、job_output 264、wait_agent 95、send_message 92、team_task_* 83（create 48/update 17/get 12/list 6）、write 23、edit 15）、tool/result 2442、job 1717 对、team/task 154、team/member 16 | `index.tsv` 类型统计 |
| 标题演进 | 「修复二进制漏洞文件失败问题」(seq 17，LLM 生成) → 「全类型二进制修复」(seq 16659) → 「全类型二进制修复-1」(seq 16660，均为 user 改名，11-16 22:44) | `session/title` 事件 |
| 团队 | 具名成员 8 个：`guest-runtime`、`pipeline`、`gui-docs`、`audit-tools`、`heap-engine`、`gate-profiles`、`target-scope`、`legacy-convergence`；`spawn_teammate` 调用 10 次 | seq 460/470/480/1926/1931/1941/3578/3583 |
| 提交身份 | 本会话内所有 `git commit` 均带 `-c user.name="BinaryRepair" -c user.email="binaryrepair@local"` | calls2.tsv 中 commit 命令 |
| 并行车道 | 同一仓库另有 `operator（身份已脱敏）` 身份的 operator 车道（p5–p9 … p31–p34、M1–M4、整合轮），本会话多次明确称其为「operator 提交 / 外部 p31–p34 提交」 | seq=10786 @11-15 15:20；seq=18441 @11-17 01:26 |

**本会话在仓库中的落点**：主 worktree `binary-repair-gui`（= `binary-repair` 的 `allhands` worktree），分支 `workbench-v3`（mainline），另建 `.agents/worktrees/phase8d-open-world`、`phase8d-final-d37` 两个临时 worktree。会话结束时 mainline `workbench-v3` = **`d37bfad`**。

---

## 1. 人类指令清单（按 turn 去重）

会话共 170 条经过滤的 user/message，但其中约 130 条是 subagent 完成通知、后台 job 通知、`goal_round`、以及团队消息回灌。**真正的用户输入只有 13 条**，且形态高度一致：用户先自己写一份几万字的阶段路线图，粘贴进来当作本轮任务书。

| Turn | 时间 | 触发 seq | 输入形态 | 指令要点（原文摘要） | 产出阶段 |
|---|---|---|---|---|---|
| T1 | 11-14 15:14 | 8 | 134 字指令 + 附件路径 | `@…/artifacts/marcx 这是上传的二进制漏洞文件，为什么修复失败，请识别后解决所有问题，完成完整的修复功能` | marcx 容量混淆修复 |
| T2 | 11-14 18:34 | 1795 | 81 字指令 | 「请借鉴这一问题的发现，搜索全部种类的修复能力缺口 + 验收模型不匹配情况，自我发现并反思，做到所有可能的全覆盖。…最后推送仓库，并总结报告与问题」 | 66 项 gap 审计 |
| T3 | 11-14 19:39 | 3513 | 5,212 字报告粘贴 | 四类问题（仍开放/诚实非目标/已关闭防回归/根因流程）→ 要求 P0–P3 落地 | 缺口关闭 P0–P3 |
| T4 | 11-14 20:45 | 4104 | 6,089 字报告粘贴 | 0 open 之后的 6 类系统性差距（默认 whole-image、静态 mitigated、能力合同、非目标黑洞、provider 矩阵、meta-audit） | 六类差距工程化 |
| T5 | 11-14 22:24 | 5209 | 6,374 字报告粘贴 | 发布一致性/测量维度/研究型非目标/流程风险四类 | 发布治理 + provider 统计 |
| T6 | 11-14 23:40 | 6197 | 25,147 字报告粘贴（plan mode） | 冻结树 release gate 11/11 之后的全量剩余问题 | 12/12 冻结发布 |
| T7 | 11-15 01:28 | 7267 | 19,761 字「最终合并版」 | 距离「全覆盖」的全部剩余问题与解决方案 | 13/13 + 真实 GitHub CI |
| T8 | 11-15 03:05 | 8527 | 60,304 字技术路线 | 从 Release 12/12 到全能力覆盖、自主发现、自我反思 | **Phase-7 Autonomy Foundation** |
| T9 | 11-15 12:42 | 9454 | 63,091 字路线图 | 从 Autonomy Foundation 到 Repair Intelligence | **Phase-8A** |
| T10 | 11-15 15:24 | 10794 | 后台 job 通知 | （自动轮）Phase-8A 收尾 | — |
| T11 | 11-15 15:37 | 10824 | 64,038 字路线图 | 从 Phase-8A 到自主发现/反思/修复 | Phase-8A 重跑（16:04 TRANSPORT 失败） |
| T12 | 11-15 16:10 | 11207 | 「请重试继续项目」 | — | 16:12 再次 TRANSPORT 失败 |
| T13 | 11-15 16:30 | goal_round 11234 | goal 目标 | Phase-8B Independent Verification Semantic Closure | **Phase-8B** |
| T14 | 11-15 22:05 | 13923 | 62,760 字路线图 | 从 Phase-8B 到持续自主发现、自我反思与全范围修复 | **Phase-8C** |
| T15 | 11-16 22:44 | 16667 | 54,311 字方案 | 从 Phase-8C 到开放世界自主发现（D00–D10） | **Phase-8D** |
| T16 | 11-17 01:31 | 18449 | 后台 job 通知 | （自动轮）收尾确认 | — |

**要点**：用户从不做微观代码指令，而是「贴路线图 + 要求全覆盖 + 要求推送仓库 + 要求总结报告」。因此本会话的实质是**替用户把 5 份路线图逐项落地为可测量交付**，并反复自我限权（"no capability promotion"）。

---

## 2. 阶段考古

### 2.1 T1（11-14 15:14–16:01）marcx：从"修复失败"到 14/14

**目标**：解释并修好用户上传的 `marcx`（ELF64 x86-64、静态、strip、713,160 B）。

**根因裁定**（seq=1787 @16:01）：
1. GUI 一键修复 → `binary_review.py::run_direct_repair()` → 旧字节引擎 `repair_elf()`，只识别 4 类形态（预审模板固定哈希、`sub rsp,N`+立即数 `edx`、立即数 `memcpy`、`strcpy/strcat` code cave）；
2. `marcx` 缺陷是 `render()` 的 `OP_SPAN` 分支把**目标写容量 `out_size`** 校验误写成**输入池容量 `data_size`**（CWE-131/697→787），`memcpy` 长度是运行时值，无立即数 → 全部不匹配 → fail-closed；
3. 旧 gate 的运行时证据是 Unicorn 全 ELF 执行 + **栈哨兵**，对堆越界 + 非恒定长度产不出用例 → `runtime.*` 全 `not_run`。
证据：`binary-repair@d37bfad artifacts/marcx-repair-2026-11-14/README.md:10,:123`（14/14 `success_within_scope`）、`:122`（28/28 真实 guest 差分）、`:173-174`（28/28 与 16/16 的边界声明）。

**交付**：
- 新引擎 `app/services/repair/capacity.py`：识别「同函数 ≥3 个重复内联范围校验、少数派容量变量恰是输入大小变量」；等长原地重写（`mov T,out_size; sub T,dst; jb fail; cmp T,len; jae copy`，用 `sub` 的 CF 替代被删的 `cmp`）+ re-decode 校验 + 白名单字节 diff + `.rodata` 错误措辞对齐。对 marcx 只改 **16 B `.text` + 49 B `.rodata`**。
- gate 新增 required `patch.capacity`（从原始/候选字节**重新推导**），新增 `runtime.evidence/tier/contract`，无 manifest → 保持 `not_run`/`inconclusive`、不给下载。
- `guest_runner` 支持 native → qemu-user → Lima；`poc_runner` 支持 manifest 内嵌夹具（`files`+`{tmp}`）并在 guest 跑原/候选差分。
- 产品化接线：`repair_any` 回退、`/api/binary/repair-review` 的 `poc_manifest`（≤64 KiB）、CLI `--poc`、GUI 上传面板。
- 结果：**14/14 required checks**、**28/28** guest 差分、**16/16** 挑战归档矩阵、全量 **1224 passed / 7 skipped / 0 failed**（seq=1787 @16:01）。

**状态**：代码/测试已实现并验证（真实 Lima，`runner=limactl tier=emulated_run`）。

### 2.2 T2（11-14 18:34–19:37）66 项 gap 审计

**目标**：把 marcx 的个例升级为"可复现的自发现审计"。

**交付**：`scripts/audit_capability_coverage.py`（导入真实 matrix/pipeline/analyzer/runtime/gate/fixtures/PoC/claims 做有界动态探测）+ `artifacts/capability-gap-audit-2026-11-14/{coverage-matrix.json,gap-report.md}`。

| 指标 | 值 | 证据 |
|---|---|---|
| gap 总数 | 66 | seq=3505 @19:37 |
| 已关闭 | 51 | 同上 |
| 诚实缓解 mitigated | 1 | 同上 |
| 仍开放 | 3（0 high） | 同上 |
| 非目标 non-goal | 11 | 同上 |

同时补齐：capacity 策略重新集成（此前被隔离在 backup 分支）、heap 目标容量恢复（`malloc/calloc` 立即数 → 返回寄存器 → 目标数据流，`destination_kind=stack\|heap`）、动态 ELF code cave 从"扩程序头表压 `PT_INTERP`"改为 **PT_NOTE 就地重写**、四个证据 profile（`strict_template/emulated_instruction/native_poc/native_poc_rewrite`）、x86-64 `.plt.sec`/CET 导入解析、Lima virtiofs 旧视图可见性等待。

**推送**：`workbench-v3` 与 `coverage-audit-2026-11-14` → **`090ad94`**（seq=3505）。

**遗留（本会话自述）**：target 作用域/错误函数候选（medium，开放）。

### 2.3 T3（11-14 19:39–20:39）P0–P3 全落地，0 open

| 类别 | 结果 | 证据 |
|---|---|---|
| target/错误函数 | 关闭：`repair_any(target/require_target)` + `containers.resolve_function_scope` + 必选 `patch.target_scope`（每个 action 的 `site_va` 必须落在 `[va,end)`，scope 哈希进 `report_sha256`） | seq=4096 @20:39 |
| Mach-O x86_64 外部 PoC | 关闭为"实测平台限制"：`capabilities.probe()` 声明 `poc_available=False` + 原因，永不伪造 | 同上 |
| legacy 无 manifest 模型 | 关闭：pipeline 在 `repair_elf` 之前拦截 manifest 请求（`guard_pos=4507 < legacy_pos=8929`），legacy gate 收到 external PoC 追加必失败 `manifest.legacy_gate_unsupported` | 同上 |
| 11 项非目标 | 逐一映射到 `docs/acceptance/non-goals-2026-11-14.md` + `claims.json["non_goals"]`，coverage gate 未映射即失败 | 同上 |
| 防回归 | `scripts/verify_coverage_gate.py`（static CI + `--local`，`ALLOWED_OPEN=()`）+ CI coverage-gate job | 同上 |

**数字**：66 gaps → **55 closed / 0 open / 0 mitigated / 11 non-goal**；27/27 fixture、18 策略、2 capacity、0 budget skip；真实 Lima：marcx **21/21**、heap **19/19**、target-scoped heap **20/20**；CLI `--target heap_bad --require-target` → `verified=true`、输出 sha `ea222605…`。推送 **`0aa9f54`**。

### 2.4 T4（11-14 20:45–22:22）六类系统性差距

| 差距 | 处理 | 证据 |
|---|---|---|
| 默认 whole-image 不安全 | 无 target 且无 `allow_whole_image=True` → `analysis_only`（无候选/无下载）；whole-image 仅显式 opt-in 并记录 `target_policy=whole_image` | seq=5201 @22:22 |
| 静态审计把动态未验证当 mitigated | static 模式单列 `dynamic_unverified`（6 行），`--local` 要求 `dynamic_unverified=0` | 同上 |
| 能力合同不统一 | `runtime/capabilities.contract()` 单一真源；PE/32-bit Mach-O/Mach-O x86_64 外部 PoC 统一 `unavailable/not_run` | 同上 |
| 非目标黑洞 | 11 项带 affected cells、检测到时的行为、owner、复审日期、产品化条件、fallback | 同上 |
| provider 矩阵未跑全 | **12/12 case 真实 DeepSeek endpoint，253.7 s / 13 次调用；AI target verified 6/12（in-scope 9/12）**；deterministic target-strict 期望匹配 12/12 但 0 verified；请求 `deepseek-chat` 实际服务 `deepseek-flash`（`identity_ok=false` 如实记录）；cost/seed 不可得 → null | 同上 |
| 审计自身缺 meta-audit | `scripts/meta_audit.py` 注入已知缺陷 → recall 1.0 / precision 1.0 / 9 scenarios；`acceptance_invariants.py` fail-closed | 同上 |

**数字**：67 gaps = 56 closed / 0 open / 0 mitigated / 11 non-goal；capability universe **205 cells**（unknown=0；36 verified/51 supported/115 non_goal/3 unavailable）；release gate `--release` **9/9**。

### 2.5 T5（11-14 22:24–23:31）发布一致性 / 证据 / provider 维度

| 指标 | 值 | 证据 |
|---|---|---|
| Release gate（`--nightly --release-sha`） | exit 0，**11/11**，`violations=[]` | seq=6184 @23:31 |
| full pytest | 564.9 s serial 通过 | 同上 |
| 真实 Lima | 通过（`lima:limactl / emulated_run`，40.4 s） | 同上 |
| 审计终态 | **68 gaps = 55 closed + 1 mitigated + 12 non-goal + 0 open**；high=0 | 同上 |
| universe | **240 cells**，unknown 0（36 verified/51 supported/129 non_goal/24 unavailable） | 同上 |
| meta-audit | 15 scenarios，1.0/1.0 | 同上 |
| provider | **2 provider / 4 model** 完成 12-case：DeepSeek 官方 2 模型 exact identity 各 3 runs、6/12；SiliconFlow CN 2 个 Qwen 各 12 case、**0/12 verified**（能力结果，非通过）；SiliconFlow intl 被 HTTP 402 阻断；GLM-Z1 probe 超时；DashScope 无 key | 同上 |

**本会话关键的"诚实"动作**：把 Lead 自己那次 `provider-matrix`（请求 `deepseek-chat`、实跑 `deepseek-flash`）标记 `identity_ok=false`，只归因于 served model，不计入 requested-model coverage。

### 2.6 T6（11-14 23:40–11-15 01:13）12/12 冻结发布

- 最终 mainline **`fd6ca41`**（tree `93fb36a`），`release_freeze.py --mode nightly` → exit 0，**12/12**，gate 968.2 s，full pytest 787.2 s，真实 Lima 45.9 s，`mainline_unchanged=true`（seq=7253 @01:13）。
- 新增 `--evidence-out`（provenance JSON）与 `release_freeze.py`（干净树、SHA 校验、mainline 前后钉住、漂移 fail-closed）。
- **并发冻结治理实测**：`cdeab74` gate 12/12 通过但运行中 mainline 被外部推进 → freeze wrapper 正确 fail-closed（`mainline_unchanged=false`）；随后在静默窗口对 `fd6ca41` 重跑成功。
- 推送：mainline + release branches + evidence branch + tags。

### 2.7 T7（11-15 01:28–03:05）13/13 + 真实 GitHub CI 首次全绿

| 项 | 值 | 证据 |
|---|---|---|
| 冻结 SHA | **`a8934fe`**（tree `1bd4fcc`） | seq=8520 @03:05 |
| 本地 nightly gate | **13/13**，1034.6 s，`mainline_unchanged=true` | 同上 |
| full pytest | 849.8 s | 同上 |
| 真实 CI | `CI` run **43628367481** success（同一 SHA）+ `Ubuntu verification` **43628367473** success | 同上 |
| 浏览器 e2e | 本地 macOS Chrome **12/12**；CI hosted `browser-e2e` job success | 同上 |
| 证据分层 | 本地 frozen-tree gate（权威 host 测量）≠ GitHub-hosted portable CI ≠ self-hosted nightly（`not_run` + signoff）≠ browser | 同上 |

这一轮把"CI 证据"从口号变成可核对的 run id + 分层声明，是后续 8A/8B/8C/8D 的发布模板。

### 2.8 T8（11-15 03:05–04:44）Phase-7 Autonomy Foundation

- 冻结 **`2bfa112`**（tree `65a9df8`），nightly **13/13**，1092.1 s，full pytest 906.3 s（+101 个 phase-7 测试），CI **43637263062** success，Ubuntu **43637263068** success（seq=9441 @04:44）。
- 交付（用户 15 项 backlog：**8 implemented / 3 partial / 4 not_started**，`binary-repair@d37bfad docs/status/claims.json:465-560`）：
  - Acceptance Intelligence：A01–A08 维度 + **AM01–AM20 二十类 mismatch**，43-case 矩阵 **20/20 全检出，recall=precision=1.0**；
  - **20 维能力宇宙**：D01–D20 注册表 + old-11 维双向映射，**240/240 cells** 映射、unknown=0、12 个 out-of-universe candidates、`undiscovered_space="not_measurable"`；
  - 统一 Gap Registry + 发现器：**64 条记录** = 12 non-goal 迁移 + 1 mitigated + 51 candidates；六机制中 knowledge/failure_driven/differential 已跑，mutation/metamorphic/sample_based/knowledge_source_scan 未跑；
  - 反思：12 问题 / 91 记录 / 12 candidates / **verified_true=0**；
  - 6 份 JSON contract + 状态机 `repair_states.py`。

### 2.9 T9–T12（11-15 12:42–16:12）Phase-8A

- 冻结 **`bd9cbf6`**（tree `c3edf88`），nightly **13/13**，834.5 s，full pytest 703.0 s，Lima 39.4 s；CI **43687651314** success、Ubuntu **43687651300** success；tag `release-2026-11-16-phase8a` + evidence `0a095c5`（seq=10786 @15:20）。
- 交付：
  1. **Readiness 审计 G01–G30**（30 项，code/test/artifact 探针 + 硬证据规则）；
  2. **Ground-Truth Benchmark v1**（12 样本，确定性 runner）；
  3. **独立验证器 MVP**（`independent_verifier.py` / `verify_repair.py`）；
  4. 6 个新 JSON contract、4 类新 acceptance mismatch、非阻断 shadow checks。
- 实测：12 样本全部执行，4 detected、2 candidate、2 deterministic verified，但**独立验证 0 verified / 10 unknown / 2 disagreement**（`artifacts/phase8-benchmark-2026-11-16/results.json`）→ 直接引出 Phase-8B。
- **T11/T12 中断**：`turn/end` reason = `{'kind':'error','error':{'message':'DeepSeek Messages transport failed','code':'TRANSPORT'}}`（seq=11200 @16:04、seq=11226 @16:12）。两次都是模型侧传输失败，不是工具循环；用户 16:10 发「请重试继续项目」拉起 T12，T12 又在 16:12 失败，T13 于 16:30 由 goal_round 重新拉起。

### 2.10 T13（11-15 16:30–21:50）Phase-8B：验证器语义闭合

- 冻结 **`227f45b`**，tag `release-2026-11-16-phase8b`，evidence `528304a9`，nightly **13/13**，CI **43718302033** / Ubuntu **43718302188**（seq=13910 @21:50）。
- B1/B2 审计：两个 `verification_disagreement` 确定性复现（candidate sha 与 8A 完全一致），**7 条根因全部 confirmed**：V8B-01 oracle CLI 未注入 `run_poc`；V8B-02 target scope 未交换（stack confirmed，heap 已有 va_range 不适用）；V8B-03 长度变化被 blanket reject（stack confirmed / heap refuted）；V8B-04 capacity `.rodata` message action 未建模；V8B-05 无 ABI evidence 派生；V8B-06 缺 patch-plan 合同；V8B-07 runner 未保存/交换 candidate/plan/report。
- **关键结论**：两个样本都没有 candidate 本身缺陷，失败来自 verifier 语义与证据交换；B1 保存的候选**当时不是 verified claim**。
- 实现 `verification_semantics.py` + 改造 `independent_verifier.py`/`verify_repair.py`：patch-plan 的 `write/insert/replace` 从原始字节独立重放、必须逐字节等于 candidate；支持 code cave / appended segment / call redirect / header update / relocation；target scope 用全部 raw changed ranges；associated change 必须带 `authorization_ref`。
- 结果：**2 个真实 deterministic 候选独立验证为 verified**（`stack-strcpy-x86_64`、`heap-capacity-x86_64`），`false_verified=0`、`disagreement=0`，oracle 实跑 `runner=limactl tier=emulated_run`。
- 期间在 `docs/limitations.md` 引用并锁定外部 36-run 稳定性结论（19/36，见 §4.4），并补 P16 独立验证覆盖说明（seq=12590）。

### 2.11 T14（11-15 22:05–11-16 03:18）Phase-8C：Ground Truth v2 + Hidden Benchmark

- 冻结 **`4a7b2355`**（tree `4bf5013`），tag `release-2026-11-16-phase8c`，evidence `ec503e4b`，nightly **13/13**，CI **43748886046** / Ubuntu **43748886289**；post-tag：provenance ok、evidence 8/8、`drift=0`、CI evidence online ok（seq=16654 @03:18）。
- 交付：Ground Truth v2（contracts **17**，v1 12 样本 12/12 无损迁移、旧 13 contract 未改写）；公开语料 **32 样本**（28 core：12 迁移 + 6 hard-case + 6 repair-benchmark + 4 跨架构 analysis-only；4 个 Zig `-O2/-O3/-Os`+static/dynamic+strip 变体；**24 runtime / 8 analysis-only**；dev 18 / validation 14）；私有 hidden **8 样本**（6 runtime + 2 analysis-only，私有语料在 `[PRIVATE_CORPUS_PATH]`，仓库只提交 commitment `eaec60aa…`）；C11 Lima `flock` 串行化；C12/C14 证据链/claims/LIMITATIONS/CI shadow。
- **真实结果**：32 样本 30 executed / 2 unsupported / 0 not_run；3 次独立验证尝试 **2 verified / 1 rejected**，`false_verified=0`；**1 个 deterministic claim 被独立 verifier 撤回**（`heap-malloc`：`branch_target_unknown`、`call_target_not_allowed`、`no_ret`），记入 `disagreements.json` 而非当通过；**24 个 eligible repair cases → verified rate = 2/24 = 0.0833**；detection/root-cause/localization 各 3/24（`binary-repair@d37bfad docs/status/claims.json:780,:808,:812`）。
- **loop-guard 命中**：T14 step 310（**seq=16505 @11-16 03:02**）收到「You are repeating the exact same tool call with identical arguments」提醒——当时正用连续 `job_output` 轮询一个长跑 gate（`sleep 720` + `job_output`×3）。收到提醒后下一步改为 `bash`，**自行恢复，未陷入死循环**。与 session-1 的终局循环同源（轮询同一 job），但本会话有恢复。

### 2.12 T15（11-16 22:44–11-17 01:26）Phase-8D：开放世界

- 结构：D00–D10，工作目录 `.agents/worktrees/phase8d-open-world`（后 `phase8d-final-d37`）。
- Phase-8D 自身集成点：**`996060d`**（tag `release-2026-11-17-phase8d`，evidence `bdd3f840`，CI **43905664704** / Ubuntu **43905664754**）。
- 最终 mainline：**`d37bfad`**（tree `2708ad2`），tag `release-2026-11-17-phase8d-final`，final evidence **`a1d7150`**；nightly **13/13**、`require` 策略、`mainline_unchanged=true`、CI **43907137267** / Ubuntu **43907136876**、post-tag `drift=0`、evidence checker 8/8、provenance ok（seq=18441 @01:26）。
- 最终 gate 原始报文（`binary-repair@a1d7150 artifacts/release-gate-2026-11-17-phase8d-final/gate.json`）：`ok=true`、`exit_code=0`、`status_counts={passed:13, failed:0, skipped:0, unavailable:0}`、`violations=[]`、`frozen_matches_release=true`、`clean_tree=true`、`elapsed_ms=1250277`（≈20.8 min）、`full-pytest passed in 1064207 ms`、`nightly-real-lima-acceptance ... tier=emulated_run 50.1 s`；`not_run=[github_actions, international_provider_matrix, self_hosted_nightly_lima_capture]`；`mitigated_residual=[RG-runtime-evidence::elf/x86_64/64/little::native_run]`。

**D00–D10 实测**（`binary-repair@d37bfad docs/status/claims.json:890-1050` + seq=18441）：

| 工作流 | 交付 | 真实结果 |
|---|---|---|
| D00 | Phase-8C 基线冻结记录 | 8C release/tree/evidence/gate/CI 事实、8B 2/2 复现、原 refs 被 consolidation 删除的事实全部记录 |
| D01 | **297-unit / 20 维**能力宇宙 | 240 声明 cell + 32 public + 2 hidden aggregate + 3 analysis prototype；**2 independently verified、0 generalized、0 promoted**；catalog 外 `unmeasurable/null` |
| D02 | Gap Registry | **8/8 审计缺口全部 open**（acceptance 2、discovery 1、governance 1、hidden_evidence 1、isolation 1、reflection 1、verifier_root_cause 1）；未因代码修改而关闭 |
| D03 | Acceptance 2.0 | L0–L7 八层、18 cases、**14/14 声明 mutation 被检出**、0 false accept、0 false reject（fixtures）、2 inconclusive + 2 not_run 保留 |
| D04 | heap-malloc ABI 根因 | 主因 `generator_plan_incorrect` + `abi_proof_insufficient`；贡献因素 `verifier_rule_incorrect`；**候选仍 rejected，规则未放宽** |
| D05 | hidden 阶段归因 | 6/6 runtime 执行；first blocking stage **`detection_missed` 6/6**；0 candidates、0 verified；仅匿名聚合公开 |
| D06 | CWE 5.0 / Schema 8.0 | **984 entries / 232 mapped candidates / 15 new / 752 unmapped**；无 support claim |
| D07 | metamorphic + input mutation | 4 编译器变体、2 engine differences、2 not_run/unsupported、11/11 input mutations 执行；机制 registry 6/7 有真实证据；**sample_based 仍 not_run** |
| D08 | 实验/证据 bundle | 10 条实验记录，全部 `promotion_effect=none`，`verified_true=0` |
| D09 | hidden 隔离审计 | 操作隔离通过；same-UID/root 可读仍是明确限制，**不是密码学隔离** |
| D10 | promotion gate | **4/4 transition 全部 denied**、`promoted_count=0` |

新增 3 个 contract（总数 **20**，valid 20/20、invalid 20/20）；CI/静态审计新增 **11 个 Phase-8D shadow checks**（完整 autonomous audit 30 checks / 23 shadow）。

**并发冲突（本会话自述、未掩盖）**：第一次在 `996060d` 上跑 gate 时外部 mainline 推进到 `d37bfad` → `mainline_unchanged=false`，该次记录保留为显式 offline 证据；随后在 `d37bfad` 上以 `require` 重跑 13/13，最终以 d37 为准。

### 2.13 T16（11-17 01:31，4 秒）收尾

由 `sleep 420` 的陈旧后台 job 通知触发（seq=18449）。模型识别为"早先等待 gate 的轮询进程"，只做最终状态确认，**未重复执行**，turn 正常 `completed`（seq=18452）。会话结束状态干净：工作树 clean（gate 记录 `clean_tree=true`），无未推送提交。

---

## 3. 全类型二进制矩阵（8 cell）

声明矩阵（`binary-repair@d37bfad docs/status/claims.json` `declared_matrix`）：**ELF i386/x86_64/arm64 + PE i386/x86_64/arm64 + Mach-O x86_64/arm64（仅小端 thin）**。产物 `artifacts/binary-universal-v5-2026-11-13/`（scan/repair/baseline 各 8 组 + 4 组负例）。

| cell | repairable | strategies | runtime tier | 真实证据 |
|---|---|---|---|---|
| elf/i386 | true | immediate, guard | emulated_run | `scan-elf-i386.json`、`repair-elf-i386.json`（`strcpy`@0x33e9a，cave 0xda000） |
| elf/x86_64 | true | strict-template, immediate, guard | emulated_run | `repair-elf-x86_64-strict.json`（syscall_length 256→16）×2 |
| elf/arm64 | true | immediate, guard | emulated_run | `repair-elf-arm64.json`（`strcpy`@0x10352a8，cave 0x100003ef0 邻域） |
| pe/i386 | true | immediate, guard | emulated_run | `repair-pe-i386.json` + `repair-pe-i386-iat.json`（IAT 变体） |
| pe/x86_64 | true | immediate, guard | emulated_run | `repair-pe-x86_64.json`（cave 0x1400d1000） |
| pe/arm64 | true | immediate, guard | emulated_run | `repair-pe-arm64.json`（cave 0x1400e5000） |
| macho/x86_64 | true | immediate, guard | **native_run** | `repair-macho-x86_64.json`（cave 0x100003f2a） |
| macho/arm64 | true | immediate, guard | **native_run** | `repair-macho-arm64.json`（cave 0x100003ef0） |

负例：`negative-unknown-bytes`（`invalid`，`download_allowed=false`）、`negative-pe-no-pattern`、`negative-pe-i386-no-sink`、`negative-macho-no-pattern`（均 `analysis_only`、无候选）。

**口径澄清**：该 8-cell 矩阵是 11-13 的 v5 产物（**不是本会话生成**）。本会话对它的贡献是：把 matrix 变成 audit 的输入真值（T2「matrix truth / strategy honesty」提交 `0d2c7c5`）、补 `.plt.sec`/CET 导入解析（此前动态 ELF 0 sink）、把 Mach-O x86_64 外部 PoC 明确降级为 `unavailable/not_run`、把 PE/32-bit Mach-O 统一进 capability contract。运行时层级始终是 **ELF/PE = 模拟执行，只有 Mach-O 在 macOS 上是 native_run**；PE 从未在真实 Windows 上执行——这一点在 v5 负例与 `docs/acceptance/platform-limits-2026-11-15.md` 中均有声明。

---

## 4. AI 两条路径、真实 provider、benchmark、稳定性、独立验证器

### 4.1 两条产品 AI 路径（`product_paths`，非本会话首创，本会话接线与限权）

| 路径 | 机制 | 支持范围 | 证据 |
|---|---|---|---|
| `asm_roundtrip` | 反汇编目标函数 → 模型改汇编 → `clang` 汇编回机器码 → 注入 + 函数入口重定向 | **仅 ELF i386/x86_64/arm64**，需 host `clang` | `binary-repair@d37bfad docs/acceptance/ai-binary-repair-2026-11-13.md:11,:14,:220` |
| `binary_direct` | 模型直接产出机器码字节或等长字节编辑 → Capstone/白名单/注入校验器 fail-closed 约束 → 写回 | ELF/PE/Mach-O | 同上 `:14` |

两条路径终点都是**确定性 runtime/gate**；AI 从不做验收判定（`ai_effect=none`，见 `acceptance.json` 中 marcx review API 的 `decision`）。`source_roundtrip` 明确标注 `not implemented`（研究路径）。

### 4.2 真实 provider 矩阵（本会话 T4 实跑）

- 12/12 case、真实 DeepSeek endpoint、253.7 s / 13 次调用；AI target verified **6/12**（in-scope 9/12）；deterministic target-strict 期望匹配 12/12 但 **0 verified**（这些属 AI/非目标类）。
- **模型身份问题**：请求 `deepseek-chat`，实际服务 `deepseek-flash` → `identity_ok=false`，只按 served model 归因（seq=5201 @22:22；`binary-repair@d37bfad docs/status/claims.json:391-400`）。
- 后续 provider coverage（T5/T6 固化）：**2 provider / 4 model** 完成 12-case（`deepseek-flash`、`deepseek-v4-pro`、`Qwen/Qwen3-8B`、`Qwen/Qwen2.5-7B-Instruct`）；pooled AI-target **36/96 = 0.375**，Wilson 95% CI **[0.285, 0.475]**，inconclusive 60；国际 5–6 模型矩阵 **not_satisfied**（SiliconFlow intl HTTP 402、GLM-Z1 超时、DashScope 无 key）；`cost`/`seed` 不可得 → null。

### 4.3 跨二进制 benchmark（外部车道产出，本会话引用/门禁化）

- `artifacts/repair-benchmark-2026-11-15`：4 个二进制、CWE-121/122/787，DeepSeek flash **4/6 verified**（`hard-multicall/hard-sprintf/hard-nonconst/cwe122-heap-copy` 通过；`cwe121-unchecked-strcpy` SECURITY_FAILED、`cwe787-index-write` ASSEMBLY_REJECTED）——`README.md:6`。
- `artifacts/repair-benchmark-expansion-2026-11-16`：扩到 **8 个二进制、7 个 CWE 类**；新增 CWE-125/190 dev VERIFIED、CWE-476 hidden **VERIFIED**（首个 hidden-split AI verified）、CWE-134 `PLAN_INVALID`（负结果保留）——`README.md:15`。
- 谁做的：这两个 benchmark 的提交是 `ca6f5d8`(p5-p9)、`d4263f9`(p10-p15) 等 **operator operator 车道**；本会话只在 Phase-8A 起把它纳入 gate 与 claims。

### 4.4 36 次稳定性（**不是本会话的产物**）

`artifacts/stability-2026-11-16/`：**36 次独立运行 = 2 模型 × 6 case × 3 repeats**，verified **19/36 = 0.528**；deepseek-flash 12/18、deepseek-v4-pro 7/18；per-case：`cwe122-heap-copy 6/6`、`cwe787-index-write 6/6`、`hard-nonconst 3/6`、`hard-multicall 2/6`、`hard-sprintf 2/6`、`cwe121-unchecked-strcpy 0/6`（`README.md:3,:11,:19`）。

**归属**：该产物由提交 `d4263f9`（11-15 16:19，author operator）"feat(p10-p15): assembly feedback, **36-run stability**, v2 trace and benchmark expansion" 引入，属并行 operator 车道。本会话在 T13 把它写进 `docs/limitations.md` 并明确「这是 stochastic evidence，不是确定性泛化」（seq=12590 @11-15 18:20 的 diff）。p31–p34 车道后续把 stability runner 硬化，但 **live 60-run matrix 仍 `NOT_RUN`**（`docs/acceptance/p31-p34-2026-11-16.md:72`）。

### 4.5 独立验证器（本会话 8A→8B 的主线）

| 阶段 | 能力 | 真实数字 |
|---|---|---|
| 8A MVP | 9 required checks + 19 selftest；不读 generator verdict | 12 样本：2 deterministic verified、**独立验证 0 verified / 10 unknown / 2 disagreement** |
| 8B 语义闭合 | patch-plan 字节级重放、raw changed ranges 定 scope、ABI 派生 unavailable→not_run | **2 verified**（stack-strcpy、heap-capacity）、false_verified=0、disagreement=0；28 类 mismatch、62 audit cases、30 meta-audit scenarios（claims:637-700） |
| 8C | 撤销机制 | 公开 32 样本 2 verified / 1 rejected，**1 deterministic claim 被撤回**（heap-malloc）；verified rate 2/24 |
| 8D | 归因 + 晋级门 | heap-malloc 仍 rejected（根因在 generator plan，不在 verifier）；promotion 4/4 denied |

**这条链是本项目最重要的方法论资产**：verified 只能由独立验证器给，generator gate 不算；disagreement 必须显式保留并可撤回。

---

## 5. P31–P34 与 Phase-8D 的归属（任务点名问题）

### 5.1 P31–P34：**不是本会话完成**

| 证据 | 内容 |
|---|---|
| 提交作者/时间 | `e01fc9e` 11-16 23:30、`13d3c1d` 00:05、`b896f1b` 00:06、`d37bfad` 00:23，author 均为 `operator（身份已脱敏）`（`git log --format='%h %ad %an %s'`） |
| 工作目录 | `worktree-p31-ci`（detached HEAD=d37bfad）、`worktree-p31-final`（=c0f9feb），均非本会话的 `.agents/worktrees/phase8d-*` |
| 本会话自述 | 「`d37bfad` 是 `996060d` 的后代，额外包含**外部 p31–p34 provider/stability 提交**」（seq=18441 @01:26） |
| 内容（离线实现） | `app/services/llm_gateway/`（base/client/credentials/errors/usage + Mock/OpenRouter/Ollama providers）、`scripts/run_model_preflight.py`、`scripts/run_stability_matrix.py` 硬化（`PLAN_INVALID`/`NO_CANDIDATE`/`ARTIFACT_MISSING`/`VERIFIER_ERROR`/`TIMEOUT` 分离、timeout 捕获、checkpoint/resume） |
| 诚实边界 | **真实 OpenRouter/Ollama 调用 `NOT_RUN`；live 60-run matrix `NOT_RUN`；keychain/GitHub-Secret 校验 `NOT_RUN`**（`docs/acceptance/p31-p34-2026-11-16.md:7,:40,:71,:72`）；全量 2411 tests / 0 failed / 9 skipped（`:65`，离线） |

本会话与它的唯一接触：T15 末尾 mainline 被推到 `d37bfad`，本会话把最终 gate 重跑到该 SHA 并发布 `release/2026-11-17-phase8d-final`。**因此不能把 P31–P34 的交付计到本会话头上，也不能把 llm_gateway 的真实联网能力算作已验证。**

### 5.2 Phase-8D：**是本会话完成**

- `d1b73bf`（11-16 23:32，feat phase-8D）、`78edb97`（23:50，CI 修复）、`996060d`（11-17 00:16，evidence refs）均为本会话 `BinaryRepair` 身份提交，工作目录 `.agents/worktrees/phase8d-open-world`。
- 12 个 `artifacts/phase8d-*-2026-11-17/` 产物 + `docs/release-2026-11-17-phase8d.md`，D00–D10 全有实测数字（见 §2.12）。
- 最终 gate 在 `phase8d-final-d37` worktree 以 `require` 策略跑出 13/13。

---

## 6. 最终状态（会话结束时刻）

### 6.1 引用与发布对象

| ref | SHA | 说明 | 证据 |
|---|---|---|---|
| `workbench-v3`（mainline） | **`d37bfad81f39c2bfa3fc90babed7301d6244446d`** | 被 gate 的最终树（tree `2708ad2`） | seq=18441；gate.json `release_sha` |
| `release/2026-11-17-phase8d-final` | d37bfad | final release branch | 同上 |
| tag `release-2026-11-17-phase8d-final` | d37bfad | annotated | 同上 |
| `release/2026-11-17-phase8d-final-evidence` + tag | **`a1d7150f06fa71612096d6a5b8f033d707f7a3bf`** | 最终 gate/CI 证据提交 | 同上 |
| `phase8d-open-world` | `996060d0b47374e9ad69e4fee5a3de4a11d164c1` | Phase-8D-only 集成 | 同上 |
| `release/2026-11-17-phase8d-evidence` + tag | `bdd3f840…` | 8D-only 证据 | 同上 |
| tag `release-2026-11-17-phase8d` | 996060d | 8D-only release | 同上 |
| `phase8d-frozen-phase8c-release` / `-evidence` | `4a7b2355` / `ec503e4b` | 8C 冻结快照 | 同上 |

> 远端实核（2026-11-17 08:5x，`git ls-remote`）：`workbench-v3`=d37bfad、`release/2026-11-17-phase8d-final`=d37bfad、`…-final-evidence`=a1d7150；annotated tag `release-2026-11-17-phase8d`→996060d、`…-phase8d-evidence`→bdd3f840、`…-phase8d-final`→d37bfad、`…-final-evidence`→a1d7150，与会话结束陈述一致。

### 6.2 结束时的"完成 / 未完成"清单

**已完成并有真实证据**
1. marcx 容量混淆修复闭环：14/14 gate、28/28 guest 差分、16/16 挑战矩阵、补丁 `93e27f2f…`。
2. 能力缺口审计：68 gaps = 55 closed + 1 mitigated + 12 non-goal + 0 open；universe 240 cells / unknown 0（static 视图为 62 gaps：44 closed + 1 mitigated + 11 non-goal + 6 dynamic_unverified，gate 两种模式都校验）。
3. 发布治理：连续 8 次 release/nightly gate 全过（11/11 → 12/12 → 13/13 ×6：a8934fe、2bfa112、bd9cbf6、227f45b、4a7b2355、d37bfad），每次都有本地 nightly + GitHub-hosted CI + evidence branch + tag + `drift=0`。
4. Phase-7/8A/8B/8C/8D 五个阶段全部落地，且**每一次都声明 0 capability promotion**。
5. 独立验证器闭环：2 个真实样本独立 verified、1 个 deterministic claim 被撤销、false_verified=0。
6. Phase-8D D00–D10 全交付：297 units、8/8 gaps open、14/14 mutation、hidden 6/6 `detection_missed`、promotion 0/4。

**未完成 / not_run（会话自述，非我推断）**
| 项 | 状态 | 证据 |
|---|---|---|
| hidden 泛化 | **0 verified**（6/6 执行但 first blocking = detection_missed，0 candidates） | claims:918；seq=18441 |
| heap-malloc | **仍 rejected**，根因 `generator_plan_incorrect` + `abi_proof_insufficient`；规则未放宽 | claims `heap_malloc` |
| 能力晋级 | **0 generalized / 0 promoted**，promotion gate 4/4 denied | claims:912,:1000 |
| sample_based 发现 / 外部样本 ingestion | `not_run` | seq=18441 |
| 第二 Linux 编译器（跨编译器验证） | 无，只有 Zig 0.17.1 | claims `cross_compiler_verified=false` |
| 国际 provider 矩阵 | `not_satisfied`（HTTP 402 等） | claims:374 |
| self-hosted Lima nightly（CI 内） | `not_run` + signoff | gate.json `not_run` |
| 真实 OpenRouter/Ollama 调用 | `NOT_RUN`（p31 车道） | p31 doc:71 |
| live 60-run stability matrix | `NOT_RUN` | p31 doc:72 |
| Acceptance 2.0 的 correct-but-new-layout False Reject | 未充分测量；2 inconclusive + 2 not_run | seq=18441 |
| hidden 隔离 | 仅操作隔离（root 0700），same-UID/root 可读，无密码学隔离声明 | seq=18441 |

### 6.3 会话层面的收尾问题（不是代码问题）

1. **无未推送提交**：mainline/release/evidence/tag 全部推送；gate 记录 `clean_tree=true`。T15 结束后工作树干净。
2. **两次 transport error**（T11 @16:04、T12 @16:12）导致 Phase-8A 的续写中断；用户 16:10 发「请重试继续项目」、goal_round 16:30 重新拉起 T13，最终结果不受影响（8A 已在 T9 发布，T13 做的是 8B）。
3. **一次 loop-guard 命中**（T14 seq=16505 @11-16 03:02），原因是用 `job_output` 轮询长 gate；已自行恢复。**这与 session-1 的终局死循环同源，值得 Lead 在总结里作为"长 gate 轮询"模式风险统一处理。**
4. **本会话两次改写 title**（seq 16659/16660），"全类型二进制修复-1" 是用户手动命名，不是系统生成。

### 6.4 任务要求的"删除原位置痕迹"相关事实（供 06 号使用，不执行）

- 本会话产生的 11-14/11-15/11-16 系列 tag（`release-2026-11-14*`、`release-2026-11-15*`、`release-2026-11-16*`、`release-2026-11-16-phase8a/8b/8c*`）**已不在本地 tag 列表**，只剩 `phase8d*`（`git tag -l`）；与整合轮提交 `fb807e2`「record execution results of the ref cleanup (23 branches + 14 tags deleted)」一致。
- 但本会话的最终 refs（`release/2026-11-17-phase8d-final*`、`phase8d-open-world`、tag `release-2026-11-17-phase8d*`）**仍在**，且是"会话痕迹"的主要残留。

---

## 7. 交叉发现（给 04/05/06 号，超出本会话但强相关）

1. **`final/consolidated-2026-11-16`（c0f9feb）不包含 Phase-8D**：`git merge-base --is-ancestor d37bfad c0f9feb` = NO；`git ls-tree -r c0f9feb | grep -c artifacts/phase8d` = **0**；而 d37bfad 包含 consolidation 文档（4322a51/fb807e2/8d4ba1c/503b226）、M1–M4、Phase-8D、p31–p34 全部。c0f9feb = f1bb1f4 + 重新应用的 p31（`a9db731`，与 `e01fc9e` 不同 SHA）。**若交付基线选 c0f9feb 会整体丢失 Phase-8D（117 文件 / 76,688 行）**；应选 `d37bfad`。
2. **`binary-repair-gui` 主 worktree 处于不一致脏状态**：HEAD=c0f9feb，`git status --short` 41 项——`app/services/llm_gateway/*` 与 `artifacts/p31-p34-2026-11-16/`、`docs/acceptance/p31-p34-2026-11-16.md`、`scripts/run_model_preflight.py` 被 staged 删除（`D `），同时 `app/services/llm_gateway/` 又有 untracked 副本；`ai_binary_repair.py`/`assistant_llm.py`/`binary_pipeline.py`/`code_cave.py`/`agent.js`/`agent.html` 有未提交修改。文件 mtime 集中在 11-16 22:40–23:10。**这不是本会话的提交**（本会话在 `.agents/worktrees/phase8d-*` 工作），更像整合轮/门户轮遗留的半完成 revert。交付前必须先裁定并清理。
3. **claims 的 CI 指针滞后**：`docs/status/claims.json` 的 `ci_evidence.gated_sha = 78edb97` / `latest_verified_ci.run_id=43900916188`，而最终发布是 `d37bfad`（CI 43907137267）。本会话以 evidence addendum 显式说明两次都是真实运行、不冒充（seq=18441 §4.8），但**机器可读字段仍指旧 SHA**，是治理债。

---

## 8. 假设与判定方法

- **事件指针格式**：`session:b139b586#seq=NNNN @MM-DD HH:MM`。seq 取自 JSONL 的 `seq` 字段；时间为 `time`（epoch ms）换算到 **UTC+8**。日志内运行时上下文在 11-16 02:56 之前写 `Asia/Shanghai`、之后写 `Asia/Singapore`，两者同为 UTC+8，不影响换算。
- **作者归属法**：以 git 作者身份为主判据——本会话所有 commit 命令显式 `-c user.name="BinaryRepair"`，故 `author=BinaryRepair` 的 86 个提交视为本会话产出；`author=operator` 的提交视为并行 operator 车道（p5–p9/p10–p15/p16/p21–p24/p31–p34/M1–M4/整合轮）。旁证：本会话在 T9/T15 明确称这些为"operator 提交""外部 p31–p34 提交"。**该判定不是密码学证明**：若另一会话也曾使用 BinaryRepair 身份，则归属会重叠；目前未发现反例。
- **"代码/测试已实现并验证"** 只用于有真实执行证据（gate 报文、Lima 差分、CI run id、pytest 输出）的项；仅文档/claims 声明的一律标注"仅文档/声明"。
- 未核实项：`final/consolidated-2026-11-16` 的创建者会话、`binary-repair-gui` 脏状态的具体操作者、`640d08a`（T5 提到的中间冻结树）是否仍在对象库——这三项均标"未核实"。

---

## 交接给 Lead

1. **本会话 = 项目的"测量与治理"主线**：它没有新增漏洞修复能力（每阶段自述 `0 capability promotion`），但把"什么算修好了"从一句口号变成了可执行门禁：独立验证器 + patch-plan 字节重放 + Acceptance 2.0（L0–L7）+ 30 scenarios meta-audit + 13 项 frozen-tree gate。总结报告应把这条线与"能力线"分开写，否则会把治理成果误读为修复能力。
2. **最终可交付的 mainline 是 `d37bfad`，不是 `final/consolidated-2026-11-16`（c0f9feb）**。后者缺失整个 Phase-8D（117 文件 / 76,688 行，`git merge-base --is-ancestor d37bfad c0f9feb` = NO）。GitHub 交付基线必须用 d37bfad（或其后代），否则"整合两个会话"会丢掉最后一阶段。
3. **最硬的一组数字**（可直接引用）：68 gaps = 55 closed + 1 mitigated + 12 non-goal + 0 open；240 cells / unknown 0；marcx 14/14 + 28/28 + 16/16；8B 2 verified / 0 false verified；8C 2/24 = 0.0833 且撤回 1 个 deterministic claim；8D 297 units / 8 个 gap 全 open / hidden 6/6 detection_missed / promotion 0/4；最终 gate 13/13、drift=0。
4. **P31–P34 不属于本会话**，且其真实联网能力是 `NOT_RUN`（OpenRouter/Ollama/live 60-run 全未跑）。若最终报告把"统一 LLM gateway/OpenRouter/Ollama"写成已验证能力，就是虚报。它们的提交时间是 11-16 23:30–11-17 00:23，author `operator`，在 `worktree-p31-ci`。
5. **"36 次稳定性 19/36" 也不是本会话产物**，来自 p10–p15 的 `d4263f9`；本会话只是把它写进 `docs/limitations.md` 并限定为 stochastic。引用时必须写清来源，否则会被当成 Phase-8 的成果。
6. **全类型矩阵是 8 个 cell（ELF×3 + PE×3 + Mach-O×2），不是"任意二进制"**；真实运行层级只有 Mach-O 是 native，ELF/PE 全是模拟执行，PE 从未在 Windows 上跑。`asm_roundtrip` 仅 ELF 三架构，`source_roundtrip` 未实现。总结里必须保留这层限定。
7. **交付前的两个仓库级 blocker**：(a) `binary-repair-gui` 主 worktree 41 项脏状态（p31 被 staged 删除 + 未提交改动，mtime 11-16 22:40–23:10），必须裁定后清理再提交；(b) `claims.json` 的 `ci_evidence.gated_sha`/`latest_verified_ci` 仍指 `78edb97`/run 43900916188，而最终发布是 `d37bfad`/43907137267——机器可读字段需要一次 evidence 更新或显式注记。
8. **会话本身干净收尾**：16 turns、无未推送提交、T16 只做确认未重复执行。唯一异常是 T11/T12 两次 `TRANSPORT` 中断（模型传输，不是死循环）与 T14 一次 loop-guard 命中（`job_output` 轮询长 gate，已自行恢复）。**这与 session-1 的终局死循环同源**，建议 Lead 在总结的"问题与方案"里合并为一条：长 gate 轮询应改为事件通知/一次性等待，而不是连续 `job_output`。
9. **不确定性**：①作者归属法基于提交身份，若其他会话也用 `BinaryRepair` 身份则会有重叠（未发现反例）；②`binary-repair-gui` 脏状态与 `final/consolidated` 的创建者未核实；③T5 提到的中间冻结树 `640d08a` 未在最终历史中定位；④会话日志里 `240 cells`/`297 units` 的口径差异（声明 cell vs unit）应以 `claims.json` 的 `phase8d_open_world.capability_universe` 为准，不要混用。
