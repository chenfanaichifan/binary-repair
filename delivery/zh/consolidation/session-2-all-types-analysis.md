# 会话深度分析：全类型二进制修复-1（session-b139b586）

> 分析对象：`.tmp/sessions/s2-alltypes.jsonl`（由 `~/.dsh/sessions/.../session-b139b586-985b-475c-af5a-1ee7f0082668/session.v4.jsonl.zstd` 解压，16 662 条事件，2026-11-14 15:12:55 → 2026-11-16 08:06:06，14 个 turn）
> 仓库核查：`binary-repair-gui`（只读）。分析时该工作树 HEAD = `ec503e4b1df53ad39fa836bd34d93a18564d78f9`（分支 `release/2026-11-16-phase8c-evidence`，工作树 clean）；`origin/workbench-v3` = `4a7b2355ffc5225d013a777bc7d588abac58f944`。
> 口径：数字优先取仓库内已提交证据（claims.json / gate.json / freeze.json / 审计产物 / git tag）；仅存在于会话报告而未在仓库复核的，标注「报告自述」。所有引用给出来源（seq / commit / 证据文件）。

---

## 0. 会话总览（关键数字）

| 项目 | 值 | 来源 |
|---|---|---|
| 事件数 | 16 662 | JSONL 统计 |
| 起止时间 | 2026-11-14 15:12:55 → 2026-11-16 08:06:06 | seq 首尾事件 |
| turn 数 | 14（其中 turn 11/12 因 DeepSeek transport error 中断，turn 13 由 goal resume 自动续跑） | turn/start、turn/end |
| 真人指令 | 12 条（`user/message` 且 `source.kind=user`） | seq 8/1795/3513/4104/5209/6197/7267/8527/9454/10824/11207/13923 |
| AI 正式文本报告 | 16 条（14 条实质报告） | assistant/message |
| 共享任务 | 48 个（44 completed / 2 in_progress / 2 pending） | team/task 终态 |
| 团队成员 | 8 个 teammate（spawn，fresh）+ Lead | team/member seq 460–3583 |
| goal | 19 次 goal/change，9 个 goal（7 个 create→complete，1 个 resume） | goal/change |
| 会话标题 | provider 标题「修复二进制漏洞文件失败问题」(seq 17)；用户改名「全类型二进制修复」/「全类型二进制修复-1」(seq 16659/16660) | session/title |
| 最终发布 | mainline `workbench-v3` = `4a7b2355…`；tag `release-2026-11-16-phase8c`（annotated）；evidence `release/2026-11-16-phase8c-evidence` = `ec503e4b…`（annotated tag `release-2026-11-16-phase8c-evidence`） | git tag/ref 实测 |

---

## 1. 时间线：12 条真人指令与 AI 交付阶段

### 1.1 真人指令（全部 12 条，按 seq）

| # | seq | 时间 | 指令要点 | 触发/对应的 AI 交付 |
|---|---|---|---|---|
| 1 | 8 | 11-14 15:14:06 | 上传 `@…/elf-challenge/artifacts/marcx`（134 字符）：「为什么修复失败，请识别后解决所有问题，完成完整的修复功能」 | turn 1：marcx 根因定位 + 新 capacity 引擎 + 真实验收（seq 1787 报告） |
| 2 | 1795 | 11-14 18:34:02 | 「借鉴这一问题的发现，搜索全部种类的修复能力缺口 + 验收模型不匹配情况，自我发现并反思，做到所有可能的全覆盖…最后推送仓库，并总结报告与问题」 | turn 2：66 项 gap 自发现审计 + 8 teammate 并行（seq 3505 报告） |
| 3 | 3513 | 11-14 19:39:47 | 5 212 字：按「仍开放/缓解—诚实非目标—已关闭防回归—根因与流程风险」四类给可执行方案（引用 66 gaps=51 closed/1 mitigated/3 open/11 non-goal） | turn 3：P0–P3 收尾（seq 4096 报告） |
| 4 | 4104 | 11-14 20:45:28 | 6 089 字：55 closed/0 open 后仍差 6 类系统性差距（默认策略、非目标产品化、provider 矩阵、静态审计 dynamic_unverified、审计的 meta-audit、能力合同统一） | turn 4：全覆盖阶段 3（seq 5201 报告） |
| 5 | 5209 | 11-14 22:24:34 | 6 374 字：四类剩余问题（发布一致性 P0-1、artifacts 滞后 P0-2、provider P1-1、nightly/CI P1-2、非目标 P2-1…） | turn 5：冻结树 release 闭环（seq 6184 报告） |
| 6 | 6197 | 11-14 23:40:44 | 25 147 字：12 项剩余问题，要求最终冻结 SHA 完整 nightly/--release-sha、CI 证据分离、provider 统计/identity、非目标路线图、meta-audit/invariant/stale-artifact 门禁 | turn 6：12/12 冻结发布（seq 7253 报告） |
| 7 | 7267 | 11-15 01:28:07 | 19 761 字：最终合并版剩余问题；基线 fd6ca41 / 12/12；要求 GitHub-hosted release-gate 真实 CI、claims ci_evidence schema v2、完整 provenance、evidence 分支强关联、universe 方法学 | turn 7：真实 CI + evidence 链（seq 8520 报告） |
| 8 | 8527 | 11-15 03:05:23 | 60 304 字总路线图：从 Release 12/12 到「全能力覆盖 + 自主发现 + 自我反思 + 持续进化」（G01–G11：能力宇宙、漏洞类型、跨函数语义、修复引擎、provider、验收模型、缺口发现 6 机制、反思 5 阶段…） | turn 8：Phase-7 Autonomy Foundation（seq 9441 报告） |
| 9 | 9454 | 11-15 12:42:42 | 63 091 字路线图 2：Autonomy Foundation 已完成 → Repair Intelligence；16 项 backlog、G01–G30 等 | turn 9：Phase-8A（seq 10786 报告） |
| 10 | 10824 | 11-15 15:37:10 | 64 038 字路线图 3：Phase-8A → 开放世界发现；分层 capability universe、Acceptance Taxonomy/Registry/自检、Ground Truth 四层语料、Binary Understanding、Independent Verifier 升级…（Phase-8B 指令） | turn 11/12 两次 transport error；turn 13 于 16:30 由 goal resume 续跑 → Phase-8B（seq 13910 报告） |
| 11 | 11207 | 11-15 16:10:35 | 「请重试继续项目」（7 字符） | turn 12 仍 transport error；goal `e5c675e3…` resume 后 turn 13 继续 |
| 12 | 13923 | 11-15 22:05:36 | 62 760 字路线图 4：Phase-8B → 持续自主发现；16 个一级能力域、Repair Planner、开放世界发现、Acceptance 自审计、Phase-8C 实施要求…（Phase-8C 指令） | turn 14：Phase-8C（seq 16654 报告） |

### 1.2 AI 交付阶段（按 turn，含 commit / gate / CI）

| turn | 起止 | 阶段 | 报告 seq | 关键 commit / 发布物 | gate / CI | 主要数字 |
|---|---|---|---|---|---|---|
| 1 | 11-14 15:14–16:01 | marcx 修复 | 1787 | `86587da`（42 文件 +9766/−143，16:00:33） | 本地确定性 gate（后 14/14） | patched sha `93e27f2f…`；28/28 guest 差分；16/16 挑战矩阵 |
| 2 | 18:34–19:37 | 66 项 gap 自发现审计 | 3505 | `090ad94`（19:35:28，push workbench-v3 + coverage-audit-2026-11-14） | 审计工具 + 回归 | 66 gaps=51 closed/1 mitigated/3 open/11 non-goal；marcx 21/21、heap 19/19 |
| 3 | 19:39–20:39 | P0–P3 覆盖收尾 | 4096 | `0aa9f54`（20:25，8 commits：5374eb2 target scope、c285397/ee02eef legacy、097a33b runtime capability、224a005/5b509f3 CI gate、0aa9f54） | `verify_coverage_gate.py --static-only/--local` exit 0 | 66 gaps=55 closed/0 open/11 non-goal；target-scoped heap 20/20 |
| 4 | 20:45–22:22 | 全覆盖阶段 3 | 5201 | `956ee10`（21:49，phase-3 独立证据分支）、`725e7bb`（22:20，合并主线） | `--release` 9/9 | 67 gaps=56/0/0/11；universe **205 cells**；provider 12-case 真实跑（6/12）；meta-audit 9 scenarios |
| 5 | 22:24–23:31 | 冻结树 release 闭环 | 6184 | 冻结树 `640d08a`（23:15），mainline `f65ed53`（23:30），`0522735`（local gate 等价树） | nightly **11/11** | 68 gaps=55/1/0/12；universe **240 cells**；meta-audit 15；invariants 9 packets；pytest 564.9 s；Lima 40.4 s |
| 6 | 23:40–11-15 01:13 | 最终 SHA 完整 gate + CI 证据分离 | 7253 | `fd6ca41`（00:52），tag `release-2026-11-15`；evidence `028d709` | nightly **12/12**（`028d709` gate.json 实测 12 checks、968.2 s、pytest 787.2 s） | fd6ca41 证据 bundle `artifacts/release-gate-2026-11-15/`；meta 18；provider 4 models/2 providers |
| 7 | 01:28–03:05 | 真实 GitHub CI + provenance/evidence 分支 | 8520 | `a8934fe`（02:45），tag `release-2026-11-16`；evidence 分支 tip `d6b41db`（tag `release-2026-11-16-evidence` → `d4aeee`） | nightly **13/13**（1034.6 s、pytest 849.8 s、Lima 47.1 s）；hosted CI 首次成功 | CI 43626323294（bb1ee2d）、final 43628367481 + Ubuntu 43628367473；meta 24 |
| 8 | 03:05–04:44 | **Phase-7 Autonomy Foundation** | 9441 | `2bfa112`（04:23）；tag `release-2026-11-15-autonomy`；evidence `37994eb` | nightly **13/13**（1092.1 s、pytest 906.3 s） | CI 43637263062 + Ubuntu 43637263068；6 contracts；20 dims/240 cells；acceptance AM01-20/43 cases；gap registry 64；reflection 91；meta 26 |
| 9 | 12:42–15:20 | **Phase-8A Repair Readiness** | 10786 | `bd9cbf6`（14:55，tree `c3edf88`）；tag `release-2026-11-16-phase8a`；evidence `0a095c5` | nightly **13/13**（834.5 s、pytest 703.0 s、Lima 39.4 s） | CI 43687651314 + Ubuntu 43687651300；G01–G30=13/7/5/1/4；GT v1 12 samples；verifier 8 checks；12 contracts；AM 24/52；meta 28 |
| 10 | 15:24:25–15:24:41 | CI 轮询收尾报告 | 10811 | — | 复核 CI 43687651314/43687651300 = success | — |
| 11/12 | 15:37–16:12 | 两次 DeepSeek transport error（turn 11/12 失败） | 11207 后 | — | — | goal `e5c675e3…` 于 16:30 resume |
| 13 | 16:30–21:50 | **Phase-8B Independent Verification** | 13910 | `227f45b`（21:18，tree `5a9b94c`）；tag `release-2026-11-16-phase8b`；evidence `528304a` | nightly **13/13**（1300.5 s、pytest 1105.6 s、Lima 47.1 s） | 2/2 independently verified（stack-strcpy 1bc66b2e…、heap-capacity 93e27f2f…）；false_verified=0、disagreements=0；13 contracts；AM 28/62；meta 30；CI final 43718302033 + Ubuntu 43718302188 |
| 14 | 22:05–11-16 03:18 | **Phase-8C Ground Truth v2 / Hidden / Integrity** | 16654 | `4a7b235`（11-16 02:48，tree `4bf5013`）；tag `release-2026-11-16-phase8c`；evidence tip `ec503e4`；集成基线 `a1755a5`（Phase-8C 在该 operator mainline 之上 19 commits） | nightly **13/13**（1438.6 s、pytest 1225.3 s、Lima 47.7 s） | public 32 样本（30 executed/2 unsupported/2 verified/1 rejected/false_verified 0）；hidden 8（0 verified）；17 contracts；CI final 43748886046 + Ubuntu 43748886289 |

> 说明：turn 8 的 goal（`e6815f47…`）create 于 11-15 03:05，complete 于 04:44；Phase-8A/B/C 的 goal 分别 create 于 seq 9632（12:46）、11005（15:46）、14144（22:10），均 complete。

---

## 2. 重点一：marcx 二进制修复失败的根因与修复

### 2.1 现象（用户上传样本，turn 1）

- 样本：`marcx`，ELF64 x86-64、静态链接、已 strip，713 160 B；SHA-256 = `72fb53cbac09f576e037f730b07a7850ce8e129fb8c9a72c2c707c121d54b0d5`。
- GUI 一键修复截图 14 项检查失败：`format failed supported=False`、`candidate.present failed candidate_bytes=0`、`candidate.identity.patched failed`、`patch.scope failed unsupported mode=unsupported`、`runtime.*` 全部 `not_run`。
- 结论（seq 1787 报告 + `artifacts/marcx-repair-2026-11-14/README.md`）：**不是 gate 误判，而是「修复能力缺口 + 验收模型不匹配」两病并发**。

### 2.2 根因（带代码位置，来自 marcx 证据 README）

1. 入口链路：GUI → `app/services/binary_review.py::run_direct_repair()`（约第 670 行）→ 旧字节引擎 `app/services/binary_repair_engine.py::repair_elf()`。
2. 旧引擎只识别 4 类形态：预审模板固定哈希（`KNOWN_STRICT`，第 27 行）、`sub rsp,N`+立即数 `edx` 栈读写、立即数 `memcpy` 长度、`strcpy/strcat` code cave。
3. marcx 缺陷：`render()` 的 `OP_SPAN` 分支把**输出缓冲区容量 `out_size` 的目标校验误写成输入数据池容量 `data_size`**（CWE-131/697 → CWE-787），且 `memcpy` 长度来自归档索引的**运行时值**（无立即数）→ 四类形态全不匹配 → fail-closed（`supported=False`、`mode=unsupported`、`patched=None`）。
4. 旧验收 gate：`app/services/binary_verification.py::build_verification()`（约第 148 行），运行时证据模型是 Unicorn 全 ELF 执行 + **栈哨兵** `runtime.no_overflow`（约第 337 行）；本缺陷是**堆越界 + 非恒定长度**，栈哨兵产不出用例 → `runtime.* = not_run`。
5. 该缺口此前已被记录为 non-goal：`app/services/repair_matrix.py` 第 186 行「heap, global and non-imported inline copy sinks」；`artifacts/fairness-ablation-2026-11-14/` 中 `hard-nonconst`/CWE121/heap-canary 家族确定性基线全部 0 通过。

### 2.3 修复设计（新引擎，seq 1787 报告 + patch-record.json 实测）

- 新文件 `app/services/repair/capacity.py`（35 083 B）：
  - `detect_capacity_confusion(data)`：在 `.text` 识别内联无符号范围校验块 `cmp Ra,Rb; jb FAIL; mov T,Ra; sub T,Rb; cmp T,Rl; jcc`；要求 `Rb` 来自 `[BASE+dst_disp]`、`Rl` 为内存加载运行时长度；按 `(函数起点, BASE, dst_disp)` 分组，同组 ≥3 个校验块、容量寄存器恰好 2 种取值且少数派唯一，并要求少数派寄存器在同一函数内还作为「另一个字段（源偏移）的容量」出现 → 证明它是输入大小变量而非写缓冲区容量。
  - `repair_capacity_confusion(data)`：对少数派块做**等长原地重写**（无 code cave、无段表修改）：`mov T, GOOD_CAP; sub T, dst; jb FAIL; cmp T, len; jae COPY`（用 `sub` 的 CF 替代被删的 `cmp`）；重写后 re-decode 逐条校验；`.rodata` 错误措辞对齐；白名单 diff，除记录区域外任何字节变化 fail-closed。
- 本样本唯一 site：vaddr `0x4020d9`（file offset 8409），16 B：
  - before：`39f3 720c 89df 29f7 39d7 0f83c4feffff`（`cmp ebx,esi; jb; mov edi,ebx; sub edi,esi; cmp edi,edx; jae`）
  - after：`4489e7 29f7 7209 39d7 0f83c5feffff 90`（`mov edi,r12d; sub edi,esi; jb; cmp edi,edx; jae; nop`）
  - `ebx = data_size` → `r12d = out_size`；兄弟分支 `literal`(0x401f97)/`fill`(0x40208a) 原本就用 r12d。
- `.rodata` 49 B（offset 538624，string_va 4732928）：`op[%u]: span destination outside the payload pool` → `op[%u]: span destination outside the output`（对齐兄弟分支措辞）。
- 修复后文件 `marcx-fixed`：**SHA-256 `93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2`**；只改 16 B `.text` + 49 B `.rodata`，长度/段表/入口不变。

### 2.4 验收与产品化（同 turn 落地）

- `app/services/unified_verification.py` 新增 required check **`patch.capacity`**：从原始/候选字节**重新推导**每个重写动作，不信任引擎报告；新增 `runtime.evidence/tier/contract`（由真实 PoC/回归差分提供）；无 manifest/runner → `not_run`（inconclusive，不给下载）。
- `app/services/guest_runner.py`：`find_guest_runner()`/`run_path()`，native Linux → qemu-user → Lima VM（`limactl`）顺序选择；`app/services/poc_runner.py`：manifest 支持逐用例 `files:[{name,base64}]` + `{tmp}` 替换，staging 目录，原/候选同路径顺序执行。
- 产品化接线：`repair_any` capacity 回退（`strategy="capacity"`）；`/api/binary/repair-review` 可选 `poc_manifest`（≤64 KiB，否则 422）；CLI `--poc`；GUI 一键修复面板 PoC manifest 选择器 + 只读 chips；`repair_matrix.py` 仅 ELF/x86-64 新增 `capacity` 策略与 `capacity_check_mismatch` sink 类。
- 测试/文档：`tests/test_capacity_repair.py`（12 729 B）、`test_binary_pipeline_capacity.py` 等 + 架构文档/README/CHANGELOG；报告自述「全量 1224 passed / 7 skipped / 0 failed，exit 0」（未在本次分析中重跑，标「报告自述」）。

### 2.5 修复证据（交付时 / 后续复验）

| 证据 | 值 | 来源 |
|---|---|---|
| 原始 SHA-256 | `72fb53cb…d54b0d5` | patch-record.json；仓库 fixture `fixtures/elf/vuln-capacity-confusion-x86_64.elf` 实测同值（713 160 B） |
| 修复后 SHA-256 | `93e27f2f…b033a2` | patch-record.json、verification-report.json |
| 确定性 gate | 14/14 required checks，`outcome=success_within_scope` | `artifacts/marcx-repair-2026-11-14/verification-report.json`（仅存于本地 backup 分支，见 2.6） |
| 关键 check | `patch.capacity: actions=1 sites=0x4020d9 registers=ebx->r12d`；`runtime.evidence: runner=limactl tier=emulated_run source=poc_manifest` | 同上 |
| 真实 guest 差分 | 28/28 case 期望一致（4 个 PoC：原始崩溃/候选 exit 1 且 stderr `span destination outside the output`；10 个回归：原/候选逐字节一致，含 `--help`/`--list`） | `runtime-evidence.json`（4 PoC + 20 regression 执行记录） |
| 挑战自带归档矩阵 | 16/16：8 例行为不变；5 例原崩溃→现拒绝；1 例原静默 1B 越界→现拒绝；`--list` 不变；`--dump-index` 原崩溃→现拒绝 | `challenge-suite.json` |
| GUI 端到端 | 浏览器真机上传 marcx+manifest → `decision.success=true`，检查表全绿、下载可用 | `gui-success.png`；报告 seq 1787 |
| 通用性 | 另一份不同 C 源码/不同寄存器分配（`rbp`→`r12d`）的合成样本同样被修复并在 guest 通过差分；仓库其余 20+ fixture 不误报 | 报告 seq 1787；`tests/test_capacity_repair.py` |
| 后续复验（phase-2） | review API 21/21 checks、`decision.success=true`、`profile=native_poc_rewrite`、补丁 sha `93e27f2f…` | `artifacts/coverage-closure-2026-11-14/acceptance.json`（marcx_review_api） |
| 基准复用 | `benchmark/phase8-v1` 与 `phase8c` 的样本 `heap-capacity-x86_64` 的 original/patched sha 即 `72fb53cb…`/`93e27f2f…`；Phase-8B 独立验证为 verified | manifest.json:958、results.json:353 |

### 2.6 证据存档状态（重要 caveat）

- marcx 修复代码以 `app/services/repair/capacity.py` 形式回到产品（审计文档 §3.1 称「隔离 commit 86587da 重新集成」），**但 `86587da` 不是 mainline `4a7b235` 的祖先**（`git merge-base --is-ancestor` 实测 false），是重新实现/重新落地的。
- `artifacts/marcx-repair-2026-11-14/` 整包（README、marcx-fixed、patch-record、poc-manifest、runtime-evidence、challenge-suite、verification-report、gui-success.png、reproduce.py、SHA256SUMS）**只存在于本地分支 `backup/capacity-86587da`**，不在任何 origin/mainline ref 上；仓库现行只保留 fixture 与 `fixtures/poc/marcx-capacity.json`。→ 若该本地分支丢失，上述一手证据将不可复现（建议 Lead 纳入归档/迁移）。

### 2.7 teammate 分工（首轮 8 人，seq 460–3583 spawn）

| task | 角色 | 交付 | 状态 |
|---|---|---|---|
| task-1 | Lead | `app/services/repair/capacity.py` 引擎 + 测试 + marcx/synthetic fixture（参考补丁 vaddr 0x4020d9、patched sha 93e27f2f…） | completed |
| task-2 | guest-runtime | `guest_runner.py` Lima runner + `poc_runner.py` `files`/`{tmp}` manifest + 原/候选差分 | completed |
| task-3 | pipeline | `repair_matrix` capacity 策略、`repair_any` 回退、unified gate `patch.capacity`、API/CLI `poc_manifest`、测试 | completed |
| task-4 | gui-docs | GUI manifest 选择器 + 架构/README/CHANGELOG | completed |
| task-5 | audit-tools | 能力缺口自发现审计工具 + 证据（后来的 `coverage_audit.py`/`scripts/audit_capability_coverage.py`） | completed |
| task-6 | heap-engine | heap 目标容量恢复（`malloc/calloc` 立即数→返回寄存器→复制目标数据流）+ fixture/oracle | completed |
| task-7 | gate-profiles | 验收模型显式化：4 个 evidence profile、no-input、cell/tier、rewrite 复验 | completed |
| task-8 | target-scope | P0 target 选择器 + `patch.target_scope` 归属门禁 + benchmark strict mode | completed |
| task-9 | legacy-convergence | P1 legacy gate manifest 写路径收敛（fail-closed backstop） | completed |

> 后续各阶段沿用同一 8 人团队（team/member 仅 8 条 spawn 记录），任务 owner 映射见 §6。

---

## 3. 重点二：66 项 gap 审计、覆盖矩阵与发布治理

### 3.1 审计方法（代码化、可复现）

- 工具：`app/services/coverage_audit.py` + `scripts/audit_capability_coverage.py`；导入真实 repair matrix / pipeline / analyzers / runtime selectors / gate builders / fixtures / PoC / claims，在有界预算内**探测真实 pipeline**，每次运行重新测量，无硬编码 gap 清单（gap-report.md 开头声明）。
- 产物：`artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json`（603 145 B）、`gap-report.md`（44 004 B）、`SHA256SUMS`；文档 `docs/acceptance/capability-gap-audit-2026-11-14.md`（421 行）。
- 回归门禁：`scripts/verify_coverage_gate.py`（`--static-only` CI 防漂移；`--local`/`--release` 动态验收）；CI `coverage-gate` job。
- 「两病」框架：① 修复能力缺口；② 验收模型不匹配（堆目标用栈预言机、runner 不可用被当 rejected、rewrite 不复核字节、legacy gate 不能消费 PoC…）。

### 3.2 gap 数字演进（逐阶段，含证据）

| 阶段 | 时间 / seq | gap 总数 | closed | mitigated | open | non-goal | 其他 | 提交/产物 |
|---|---|---|---|---|---|---|---|---|
| 首轮审计 | 11-14 19:37 (seq 3505) | 66 | 51 | 1 | 3（0 high） | 11 | 27/27 fixture、18 策略、2 capacity 探测 | `090ad94`；coverage-matrix+gap-report |
| 收尾 P0–P3 | 11-14 20:39 (seq 4096) | 66 | 55 | 0 | 0 | 11 | coverage gate static/local exit 0；open=[]；non-goals 11/11 | `0aa9f54` |
| 阶段 3 | 11-14 22:22 (seq 5201) | 67 | 56 | 0 | 0 | 11 | universe **205 cells** unknown=0；`--release` 9/9；meta 9 | `956ee10`/`725e7bb` |
| 阶段 4 | 11-14 23:31 (seq 6184) | 68 | 55 | 1 | 0 | 12 | universe **240 cells**；nightly 11/11；meta 15；invariants 9 packets | `640d08a`（gate）/`f65ed53`（mainline） |
| 阶段 5 | 11-15 01:13 (seq 7253) | 68 | 55 | 1 | 0 | 12 | nightly 12/12；static 62（44/6/11/1/0）；meta 18 | `fd6ca41`；`028d709` |
| 阶段 6 起（终态） | 11-15 03:05 起 | 68 | 55 | 1 | 0 | 12 | static 62；nightly 13/13；dynamic_unverified release=0 / static=6 | `a8934fe` 起各阶段 |

- 68 的组成（gap-report.md 实测）：open 0 / dynamic_unverified 0 / mitigated 1（host-dependent ELF x86_64 `native_run` 平台声明）/ closed 55 / non_goal 12；high-severity open 0。
- 静态视图（claims.audit_status.static）：62 gaps = closed 44 / open 0 / mitigated 1 / non_goal 11 / **dynamic_unverified 6** / high 0 → 静态不能放行 release，`--local` 要求 dynamic_unverified=0（实测 local open=[]、dynamic=0、universe unknown=0、cells=240）。
- 67→68、11→12 non-goal 的变化原因：主线 `5f9dd77` 新增 host-dependent `RG-external-poc::<doc>::macho/x86_64` non-goal（seq 6184 报告）。

### 3.3 覆盖矩阵 / 能力宇宙（240 cells）

- 终态：**240 cells，unknown=0**；三态分布 verified 36 / supported 51 / non_goal 129 / unavailable 24，全部有 reason（gap-report.md、gate.json `universe-unknown-zero` detail 实测）。
- 11 维度枚举：arch=4、bits=3、container=4、destination_kind=4、endian=2、evidence_profile=5、proof_scope=4、provider=2、runtime_tier=3、sink_class=7、strategy=5（gap-report.md）。
- 覆盖行：8 matrix cells / 5 sink classes / 18 strategy entries / 4 gate profiles / 24 evidence sources / 36 gate checks（gap-report.md；文档另一处记 34 gate checks，属版本差异）。
- Phase-7 起升级为 **20 维候选注册表**（D01–D20）+ old-11 维双向映射，`artifacts/capability-universe-2026-11-16/dimension-registry.json`；`undiscovered_space="not_measurable"`，12 个 bounded out-of-universe candidates（明确「不能证明维度已穷尽」）。

### 3.4 接受模型审计（Acceptance Intelligence）

| 时点 | 内容 | 证据 |
|---|---|---|
| Phase-7 | A01–A08 验收维度 + **AM01–AM20** 20 类 mismatch；纯函数 `AcceptanceModelMatcher`（fail-closed，served-only/unknown 永不冒充 requested verified）；**43-case** 矩阵，20/20 类全部检出 recall=precision=1.0 | `app/services/acceptance_models.py`；`artifacts/acceptance-model-audit-2026-11-16/report.json`；`scripts/audit_acceptance_models.py --check` |
| Phase-8A | 新增 AM21–AM24（repair-scope/semantic-scope/oracle-quality/benchmark-version）：52 cases / 24 classes | claims.phase8_readiness.contracts |
| Phase-8B | 新增 AM25–AM28：**62 cases / 28 classes**，recall/precision 1.0，`ok=true` | `artifacts/acceptance-model-audit-2026-11-16/report.json`（实测 case_count=62、mismatch_classes=AM01…AM28、recall=1.0、precision=1.0） |

### 3.5 meta-audit（对审计器自身的注入缺陷测试）

场景数演进（均为 recall/precision 1.0）：

| 场景数 | 时点/seq | 注入内容（新增举例） |
|---|---|---|
| 9 | 阶段 3，seq 5201 | 死 sink class、移除 gate check、未演练策略、manifest-route 签名 token 假阳性、伪造 gap/unmapped non-goal |
| 15 | 阶段 4，seq 6184 | target check 移除、rewrite 未复验、provider identity 不符、stale artifacts、inconclusive 下载、伪造 capability |
| 18 | 阶段 5，seq 7253 | release-evidence SHA 不符、缺 provenance、local-gate 冒充 CI |
| 24 | 阶段 6，seq 8520 | 更多证据/平台反例 |
| 26 | Phase-7，seq 9441 | 自主/验收合同类 |
| 28 | Phase-8A，seq 10786 | 8A 合同/验证类 |
| **30** | Phase-8B/8C | 最终 gate.json `meta-audit` detail：`recall=1.0 precision=1.0 scenarios=30` |

### 3.6 acceptance invariants（验收不变量引擎）

- `app/services/acceptance_invariants.py`：对 verified/rejected/not_run/target/rewrite/manifest-legacy/download/policy 规则 fail-closed；终态 gate detail：**packets_checked=9，limitations=12，violations=[]**（各阶段 gate.json）。
- 覆盖「inconclusive 不可下载」「not_run 不得当 rejected」「whole_image 不得 verified」「manifest-only 路径」等。

### 3.7 release gate / nightly（11→12→13 checks）

- 工具链：`scripts/release_gate.py`（分阶段 PR/nightly/release）、`scripts/release_freeze.py`（干净树 + HEAD==requested SHA + `origin/workbench-v3` pin + 失败关闭 + evidence bundle）、`--evidence-out` provenance JSON；`docs/operations/release-gate-2026-11-14.md` 定义分层/成本/flake。
- 计数演进：阶段 3 `--release` **9/9**（seq 5201）→ 阶段 4 nightly **11/11**（seq 6184）→ 阶段 5 nightly **12/12**（seq 7253）→ 阶段 6/7/8A/8B/8C nightly **13/13**（证据 bundle 实测）。
- 终态 13 个 required checks（gate.json id）：
  1. `release-tree-identity`（frozen SHA + clean tree + MATCH）
  2. `static-coverage-gate`
  3. `claims-measurement-diff`
  4. `acceptance-contract`（capacity=1/heap=1/target_scoped=1/controls=2）
  5. `local-coverage-gate`（open=[] dynamic=0 universe_unknown=0 cells=240）
  6. `meta-audit`
  7. `acceptance-invariants`
  8. `universe-unknown-zero`
  9. `provenance-complete`（builder/guest/subjects/limactl 2.3.0）
  10. `provider-matrix`（cases=12，target_strict_pass_rate=1.0，target_in_scope_rate=0.0）
  11. `provider-coverage`（rows=11，2 providers/4 models，identity_policy=True，cost/seed unavailable）
  12. `nightly-real-lima-acceptance`（runner=lima:limactl tier=emulated_run）
  13. `full-pytest`
- 各阶段 gate 实测（来自各 evidence 分支 `gate.json`）：

| evidence ref | gated SHA | checks | gate 耗时 | full pytest | Lima capture |
|---|---|---|---|---|---|
| `9cfaaaa`（release-2026-11-14-evidence） | `cdeab74`（旧候选） | 12/12 | 995.2 s | 838.0 s | 46.6 s |
| `028d709`（release-2026-11-15-evidence） | `fd6ca41` | 12/12 | 968.2 s | 787.2 s | 45.9 s |
| `d6b41db`（release-2026-11-16-evidence） | `a8934fe` | 13/13 | 1034.6 s | 849.8 s | 47.1 s |
| `37994eb`（autonomy-evidence） | `2bfa112` | 13/13 | 1092.1 s | 906.3 s | 47.1 s |
| `0a095c5`（phase8a-evidence） | `bd9cbf6` | 13/13 | 834.5 s | 703.0 s | 39.4 s |
| `528304a`（phase8b-evidence） | `227f45b` | 13/13 | 1300.5 s | 1105.6 s | 47.1 s |
| `ec503e4`（phase8c-evidence，当前 HEAD） | `4a7b235` | 13/13 | 1438.6 s | 1225.3 s | 47.7 s |

- `freeze.json` 终态（phase8c）：`frozen_sha==release_sha==4a7b235`、`clean_tree=true`、`mainline_sha_start==mainline_sha_end==4a7b235`、`mainline_unchanged=true`、`runner.kind=local-frozen-tree`、gate 命令与 SHA256SUMS 可复核。

### 3.8 CI（hosted 成功 / self-hosted not_run）

- 工作流：`.github/workflows/ci.yml`（jobs：`test`、`coverage-gate`、`release-gate-pr`、`release-gate-hosted`、`release-drift`、`browser-e2e`、`release-nightly-gate`）+ `.github/workflows/ubuntu-verify.yml`（「Ubuntu verification」）。
- `release-nightly-gate` 为 **inert**：GitHub Actions 条件为 vars.BINARYREPAIR_RELEASE_GATE == 'true'，且 runs-on: [self-hosted, lima]；各阶段证据均记 `not_run`，并有 signoff `docs/release/CI-SIGNOFF-2026-11-15.md`、`docs/operations/phase8c-ci-signoff.md`。
- 真实 GitHub-hosted run（全部 conclusion=success，head SHA 与阶段对应；记录于各 evidence 分支 `ci-run.json` / release addendum / docs）：

| 阶段 | CI run | head SHA | Ubuntu verification run |
|---|---|---|---|
| 阶段 6（首轮真实 CI） | 43626323294 | `bb1ee2d`（候选 X） | 43626323267 |
| 阶段 6（最终 SHA） | 43628367481 | `a8934fe` | 43628367473 |
| Phase-7 | 43637263062 | `2bfa112` | 43637263068 |
| Phase-8A | 43687651314 | `bd9cbf6` | 43687651300 |
| Phase-8B（claims 记录 code SHA） | 43703724955 | `c5d87b5` | 43703724942 |
| Phase-8B（最终 SHA） | 43718302033 | `227f45b` | 43718302188 |
| Phase-8C（claims 记录 gated code SHA） | 43744573286 | `f1ba37e` | 43744573230 |
| Phase-8C（最终 SHA） | 43748886046 | `4a7b235` | 43748886289 |

- browser e2e：本地 macOS Chrome 157.0.8103.51 **12/12**（`artifacts/browser-e2e-2026-11-14/summary.json`；报告 seq 7253）；Linux CI 显式 skip，明确「skip 不是 pass、不是 release 证据」。
- CI 证据分层：本地 frozen-tree gate（权威 host 测量）≠ GitHub-hosted portable CI ≠ self-hosted nightly ≠ browser；claims `ci_evidence` schema v2 强制区分，历史 SHA 冒充 fail-closed。

### 3.9 claims / provenance / evidence 分支与 tag 体系

- `docs/status/claims.json`（46 708 B，889 行）：`audit_status`（release/static 双视图 + artifacts sha256）、`provider_coverage`、`release_evidence`（procedure/artifact_dir/evidence_branch/evidence_tag/ci_status/hosted_ci_run_id…/not_run[]）、`ci_evidence`（schema v2：gated_sha/evidence_branch/evidence_tag/hosted_ci/ubuntu_verification/self_hosted_nightly）、各 phase block（autonomy_foundation/phase8_readiness/phase8b_verifier_semantics/phase8c_ground_truth，均含 `not_claimed`）。
- provenance：`scripts/build_ci_evidence.py`、`verify_provenance.py`、`verify_evidence_branch.py`（gated SHA 是 mainline 祖先、仅 evidence/docs 路径变更、bundle SHA 钉住、SUMS 校验）、`release_drift_check.py`（drift=0）、`verify_ci_evidence.py --online`。
- 分支/tag 体系（git 实测，annotated tag）：

| tag | 指向 | 说明 |
|---|---|---|
| `release-2026-11-14` | `cdeab74` | 旧候选（曾 gate 12/12，mainline 漂移后保留为历史） |
| `release-2026-11-14-evidence` | `9cfaaaa` | 该候选 evidence bundle |
| `release-2026-11-15` | `fd6ca41` | 阶段 5 冻结发布 |
| `release-2026-11-15-evidence` | `028d709` | 对应证据 |
| `release-2026-11-16` | `a8934fe` | 阶段 6 冻结发布 |
| `release-2026-11-16-evidence` | `d4aeee` | 对应证据（branch tip `d6b41db` 含 final-SHA CI 记录） |
| `release-2026-11-15-autonomy` | `2bfa112` | Phase-7 |
| `release-2026-11-15-autonomy-evidence` | `37994eb` | Phase-7 证据 |
| `release-2026-11-16-phase8a` | `bd9cbf6` | Phase-8A |
| `release-2026-11-16-phase8a-evidence` | `0a095c5` | Phase-8A 证据 |
| `release-2026-11-16-phase8b` | `227f45b` | Phase-8B |
| `release-2026-11-16-phase8b-evidence` | `528304a` | Phase-8B 证据 |
| `release-2026-11-16-phase8c` | `4a7b235` | Phase-8C（当前 mainline） |
| `release-2026-11-16-phase8c-evidence` | `ec503e4` | Phase-8C 证据（当前 HEAD） |

- 对应发布分支：`origin/release/2026-11-{14,15,16}-final`、`…-evidence`、`…-autonomy-final/-evidence`、`…-phase8{a,b,c}-final/-evidence`（实测 SHA 见 §7.1）。
- 设计原则：**发布 tag/mainline = 被 gate 的树**；release note/evidence bundle 后置在 evidence 分支（`phase8c` 的 mainline 只保留 gate 目录 + 代码，最终 addendum 在 evidence 分支）。

---

## 4. 重点三：Phase-7 / 8A / 8B / 8C 逐阶段

### 4.1 Phase-7 — Autonomy Foundation（11-15 03:05–04:44）

- **目标**（goal seq 8541）：在已验证 mainline `a8934fe` 上实现「自主能力智能基础」：统一状态机 + JSON 合同、AcceptanceModelRegistry/Matcher、20 维能力宇宙、统一 Gap Registry + 6 机制发现器、Reflection/Experiment Planner、统一审计入口、CI 强化、路线图。
- **交付物与真实数字**（claims.autonomy_foundation 实测）：
  - 状态机 `app/services/repair_states.py`（verified→release_eligible 强制 evidence+independence 双门）；
  - 6 份 JSON 合同：`contracts/{capability,gap,acceptance,repair,evidence,reflection}.schema.json`（6 valid + 6 invalid fixtures）；
  - 20 维注册表 + **240 cells** 映射、`unknown_within_universe=0`、out-of-universe 12 candidates、`undiscovered_space=not_measurable`；
  - Acceptance Intelligence：AM01–AM20、**43-case**、recall/precision 1.0；
  - Gap Registry **64 条** = 12 non-goal 迁移 + 1 mitigated + 51 candidates；6 机制中 knowledge/failure_driven/differential 实跑，mutation/metamorphic/sample_based/knowledge_source_scan 显式 `not_run + reason`；
  - Reflection **91 records** = 12 candidates / 73 analysis_only / 6 not_run，`verified_true_count=0`、`auto_upgrade_verified=false`；
  - 统一审计 `scripts/autonomous_repair_audit.py --mode full` = **7/7 checks passed**，`not_run=[]`；
  - 用户 15 项 backlog：**8 implemented / 3 partial（P0-04/P0-08/P1-13）/ 4 not_started（P1-09~P1-12）**；
  - 新增 phase-7 测试 101 个（报告自述）；路线图文档 `docs/operations/autonomy-roadmap-2026-11-16.md`、边界文档 `docs/acceptance/autonomous-intelligence-2026-11-16.md`。
- **发布**：`2bfa112`（tree `65a9df8`，04:23）；tag `release-2026-11-15-autonomy`；evidence `37994eb`；本地 nightly 13/13（1092.1 s、pytest 906.3 s）；CI 43637263062 + Ubuntu 43637263068 success；self-hosted nightly not_run。
- **遗留**：P1-09~P1-12 not_started（跨函数 data-flow/alias、Integer/String/UAF 测试矩阵、Repair Planner 完整状态机、独立 Binary Integrity/Semantic Verifier）；P0-04 partial（outside-universe 仅 12 bounded，未建立外部知识扫描/语料/变异）；P0-08 partial（模型身份审计仅在 acceptance matcher）；P1-13 partial（self-hosted nightly not_run）；**不新增漏洞修复能力、不升级 verified**。

### 4.2 Phase-8A — Repair Readiness（11-15 12:42–15:20）

- **目标**（goal seq 9632，基线 `2bfa112`）：(1) 30 项 G01–G30 可复现 readiness 审计（code/test/artifact/ground-truth/verifier 证据、blocker、next action，禁止无证据 implemented）；(2) Ground-Truth Benchmark v1（12 真实 fixture）；(3) 独立验证器 MVP；(4) 合同/验收/meta 扩展。
- **交付物与真实数字**（claims.phase8_readiness 实测）：
  - Readiness：**30 项 = implemented 13 / partial 7 / missing 5 / not_run 1 / non_goal 4**，`capability_claims=0`；G29 hidden benchmark 为 `not_run`（`hidden_available=false`）；产物 `artifacts/phase8-readiness-2026-11-16/readiness.json`（summary.total=30）；文档 `docs/acceptance/phase8-readiness-2026-11-16.md`；
  - Ground Truth v1：`benchmark/phase8-v1/manifest.json`，**12 samples**（dev 8 / validation 4），hidden_available=false；
  - Benchmark 结果（`artifacts/phase8-benchmark-2026-11-16/results.json` 实测 summary）：12/12 executed、detected 4、candidate 2、deterministic_verified 2、**independently_verified 0**、**false_verified 0**、**verification_disagreements 2**、deterministic_claim_withdrawn 2；
  - Independent Verifier MVP：`app/services/independent_verifier.py` + `scripts/verify_repair.py`；**8 项从原始/候选字节独立重算**（identity/container reparse/byte action replay/target scope/ABI/独立 runtime oracle/evidence completeness/independence），selftest **11/11**，generator verdict 永不读取；
  - Contracts **12** 份（新增 binary-target/vulnerability-finding/root-cause/verification/benchmark-sample/patch-candidate）；Acceptance AM21–AM24（**52 cases/24 classes**）；meta-audit **28**；统一审计 7 required + 3 advisory shadow passed。
- **发布**：`bd9cbf6`（tree `c3edf88`，14:55）；tag `release-2026-11-16-phase8a`；evidence `0a095c5`（ci-run.json 记录 13/13、failed 0/skipped 0/unavailable 0）；本地 nightly 13/13（834.5 s、pytest 703.0 s、Lima 39.4 s）；CI 43687651314 + Ubuntu 43687651300 success。
- **遗留**：真正的修复能力仍未实现（G09 跨函数 dataflow、G10/G11 alias/global/struct、G12 integer、G13 string（仅探针级）、G14 UAF、G15 间接调用、G16 路径敏感、G17 并发；G04/G05/G06 组合/变异/变形发现缺失）；**2 个 deterministic claim 被独立验证器撤回**（resized guard candidate 与 cave-bearing capacity candidate：等长重写/动作范围/ABI/oracle metadata 语义不一致）→ 真实 engine/verifier 语义 gap；无 hidden benchmark；无真实独立修复验证（independently_verified=0）；mainline 上的 `artifacts/release-gate-2026-11-16-phase8a/` 是早期 `3ec09b1` 的中间 bundle（实测 gate frozen_sha=3ec09b1），权威 `bd9cbf6` bundle 在 evidence 分支；`artifacts/coverage-closure-2026-11-14/SHA256SUMS` acceptance.json 旧 checksum 属 integrity correction（只改 checksum 行）。

### 4.3 Phase-8B — Independent Verification Semantic Closure（11-15 15:37–21:50）

- **目标**（goal seq 11005，基线 `bd9cbf6`）：B1 baseline/audit 根因分析两个 disagreement；B2 语义设计与裁决；B3 patch-plan/verification 合同；B4 布局感知独立验证器；B5/B6/B7 pipeline plan/gate + benchmark 独立验证；B8 ABI/oracle 负例；B9/B10 集成/CI/claims/gate/evidence/tag。
- **交付物与真实数字**：
  - B1/B2：`artifacts/phase8b-baseline-2026-11-16/`（baseline audit、verifier gap registry）；7 个 gap 全部 confirmed：V8B-01 oracle CLI 未注入 `run_poc`；V8B-02 resolved target scope 未交换（stack confirmed；heap 已有 va_range 不适用）；V8B-03 长度变化被 blanket reject（stack confirmed；heap refuted）；V8B-04 capacity `.rodata` message action 未建模；V8B-05 无 ABI evidence 派生；V8B-06 缺 patch-plan 合同；V8B-07 runner 未保存/交换 candidate/plan/report；**未观察到 candidate 本身缺陷**，失败来自 verifier 语义与证据交换；文档 `docs/acceptance/phase8b-disagreement-analysis.md`、`docs/operations/phase8b-{implementation-plan,test-plan}.md`；
  - 验证器：新增 `app/services/verification_semantics.py`；`patch-plan` 的 write/insert/replace 从原始字节**独立重放**并逐字节等于 candidate；支持 code cave/appended segment/call redirect/header update/relocation；target scope 用全部 raw changed ranges；associated change 需 `authorization_ref`；ABI 无法派生 → `not_run`；verifier 自己执行 `poc_runner.run_poc`；resized 无 plan → `not_run`；`whole_image` 永不 verified；required checks **9**、selftest **19**（macOS native 1 skip）；
  - 合同：新增 `contracts/patch-plan.schema.json`（总计 **13**）；Acceptance AM25–AM28（**62 cases/28 classes**）；meta-audit **30**；
  - 真实运行 `artifacts/phase8b-benchmark-2026-11-16/results.json`（实测 summary）：samples 12、executed 12、candidate_produced 2、**independently_verified 2**、false_verified 0、**verification_disagreements 0**、oracle `limactl`/`emulated_run`；verified samples：`stack-strcpy-x86_64`（candidate `1bc66b2e…`）、`heap-capacity-x86_64`（candidate `93e27f2f…`）；其余 10 个 analysis-only；
  - 测试：verifier selftest 19；B1 测试 11 passed；verifier/semantics 69 passed 1 skipped；pipeline/benchmark targeted 57 passed；contracts/acceptance/meta 73 passed（报告自述）。
- **发布**：`227f45b`（tree `5a9b94c`，21:18）；tag `release-2026-11-16-phase8b`；evidence `528304a`（含 `docs/release-phase8b-final-evidence-2026-11-16.md`）；本地 nightly 13/13（1300.5 s、pytest 1105.6 s）；最终 SHA CI 43718302033 + Ubuntu 43718302188 success；claims 引用 code SHA `c5d87b5` 的 CI 43703724955/43703724942（两段证据都真实存在，分开记录）。
- **遗留**：只 2/12 候选独立验证，10 个 analysis-only；非任意二进制/任意漏洞/whole-program 证明；hidden benchmark 未完成；Phase-8C 未实施；Lima 并发导致两次 gate 尝试瞬时失败（guest 空闲重跑通过）；claims CI 指针滞后为结构性限制。

### 4.4 Phase-8C — Ground Truth v2 / Hidden Benchmark / Integrity（11-15 22:05–11-16 03:18）

- **目标**（goal seq 14144，基线 `227f45b`）：C1 baseline/hidden readiness audit（不改生产代码）→ C2 GT v2 合同/迁移（4 新 schema，17 total）→ C3 公开语料（≥28 样本）→ C4 私有 hidden corpus + commitment → C5 污染审计 → C6 runner v2 → C7 外部摄入 → C8/C9 变体/跨架构 → C10 语义回归 → C11 Lima 串行化 → C12/C14 evidence/gate/release。
- **交付物与真实数字**（claims.phase8c_ground_truth 实测）：
  - **C1 baseline**：status `ok_rebaselined`；原 baseline `227f45b`，集成 mainline `a1755a5`（operator P21–P24）；v1 迁移无损（12 samples）；Phase-8B 两个候选复现一致（2/2）；3 个 warning blockers：B-P8B-EVIDENCE-BINDING（8B 证据绑定 c5d87b5，不得复用）、B-TOOLCHAIN-ZIG（无 Zig 时 C4 受限）、B-GATE-COUNT；flake 记录（f42 一次性 false_verified，C11 锁后两次 serialized repeat 未复现）；
  - **C2 Ground Truth v2**：4 新合同（ground-truth-sample-v2/benchmark-manifest-v2/hidden-benchmark-commitment/benchmark-results-v2）→ **17 contracts total**，旧 13 未变；12 个 v1 样本无损迁移（id/hash/split/target/oracle/reference/evidence 均不变）；
  - **C3 公开语料**：`benchmark/phase8c/manifest.json`（sha256 `d46f06bf…`）**32 samples** = 28 core（12 迁移 + 6 hard-case + 6 repair-benchmark + 4 跨架构 analysis-only）+ **4 个 Zig 编译/优化变体**（-O2/-O3/-Os/static/dynamic/strip）；**24 runtime-oracle / 8 analysis-only**；dev 18 / validation 14；`PROVENANCE.json` + `SHA256SUMS`；
  - **C4 hidden**：`benchmark/phase8c/hidden-commitment.json`，commitment `eaec60aadd42388efb725a668b887465268c78fd257ec4622ac56eac571bae12`（file sha `3ebf2901…`），**8 samples = 6 runtime + 2 analysis-only**；私有语料在 `~/.binaryrepair/phase8c-hidden`（0700，不提交），仓库只有 opaque commitment + aggregate；初始 hidden 有 1 个与 public 变体字节相同 → 已重新生成；
  - **C5 污染审计**：public verdict clean、hidden verdict clean、0 unresolved overlaps（`artifacts/phase8c-contamination-2026-11-16/`）；
  - **C6/C10 runner v2**：`app/services/benchmark_runner.py` + `semantic_regression.py`；分层检测/根因/定位/策略/候选/独立验证/回归指标；显式分母，`not_run/blocked/unsupported/analysis_only` 单列；零分母为 null 而非伪造 0；文档 `docs/operations/phase8c-benchmark-runner.md`；
  - **C11 Lima 锁**：`app/services/guest_coordinator.py` flock lease + 进程内重入锁 + 有界超时 + `blocked` 状态 + attempt evidence；`run_path`/`run_poc` Lima 路径全串行（直接 `limactl` 探测不受覆盖）；
  - **公开 benchmark 实测**（`benchmark/phase8c/results.json` aggregate + claims）：32 samples、**30 executed / 2 unsupported**（variant-cwe122-O2-stripped、variant-cwe125-Os-static-stripped 目标函数范围无法解析）、0 not_run/blocked/invalid；3 次验证尝试：**2 verified / 1 rejected / false_verified=0**；1 个 deterministic claim（`heap-malloc`）被独立 verifier ABI 拒绝后撤回（`branch_target_unknown`、`call_target_not_allowed`、`no_ret`）——记录在 `disagreements.json`，不计通过；eligible repair cases **24**，verified repair rate **2/24=0.0833**；detection/root-cause/localization 各 3/24；analysis-only detection 6/8；**2 次 serialized repeat 结果完全一致**（`a477ea3c…`），但不声明无条件稳定；
  - **hidden benchmark 实测**：8/8 executed；**0 candidates / 0 independently verified / 0 rejected / 0 false_verified**；aggregate sha `18f7e39a…`；不声明 hidden 泛化；
  - **C7/C13 外部摄入/质量**：external ingestion `not_run`（无本地 external corpus）；full quality audit `ok` + 1 个 warning（public manifest 不内联 hidden commitment——避免 manifest↔commitment 循环依赖，刻意设计）；
  - contracts 17；C12/C14：evidence bundle `artifacts/phase8c-release-2026-11-16/`（runner_check 23/23）、release note、LIMITATIONS、claims、CI shadow checks、gate/evidence/tag。
- **发布**：`4a7b235`（tree `4bf5013`，11-16 02:48）；tag `release-2026-11-16-phase8c`；evidence tip `ec503e4`（tag `release-2026-11-16-phase8c-evidence`）；本地 nightly 13/13（1438.6 s、pytest 1225.3 s、Lima 47.7 s）；最终 SHA CI 43748886046 + Ubuntu 43748886289 success；claims 记录 gated code SHA `f1ba37e` 的 CI 43744573286/43744573230；integration mainline `a1755a5`（Phase-8C 在该 operator 主线之上 19 commits，diff 166 files/+75 300/−119）。
- **CI 三轮真实失败（已修复，非重跑覆盖）**：① C3 builder 在无 Zig 主机把 toolchain/source-digest provenance 差异误判为 committed corpus 篡改；② C4 hidden builder 无 Zig 时先报 `not_run` 而非 insecure root `violation`；③ claims/docs 变更后 capability/gap/provider/reflection 确定性 artifacts 过期。
- **遗留**：hidden 0 verified（确定性引擎在 hidden 变体上 0 候选）；公开仅 2/24 verified（仍为目标 scope 下的 deterministic fixture repair）；`heap-malloc` 暴露真实 engine/plan-vs-verifier ABI 冲突；一次性 C1 flake 保留为 documented warning；hidden 隔离是操作隔离（0700）非密码学保护；public manifest `hidden_commitment=null`（质量 1 warning）；无跨编译器（仅 Zig 0.17.1）；Phase-8D/9–16 未实施未声明。

---

## 5. 未完成任务与问题清单（根因 / 现状 / 建议）

> 来源：各阶段最终报告（seq 3505–16654）、`docs/acceptance/LIMITATIONS.md`（第 21–23 节 + Phase-8A/8B/8C 段）、claims `not_claimed`、非目标路线图。标注「推断」的为我基于证据的判断。

| # | 问题 | 根因 | 现状 / 证据 | 建议后续动作 |
|---|---|---|---|---|
| 1 | Phase-7/8A/8B/8C **均未新增漏洞修复能力、未升级任何 verified** | 阶段目标定义为基础设施/证据/验收，不含算法能力 | claims 各 phase block `new_vulnerability_repair_capability_this_phase=false`、`auto_upgrade_verified_this_phase=false`；LIMITATIONS 三段首句 | 下一阶段只做「能提升真实修复率」的算法工作（跨函数语义/规划/独立验证） |
| 2 | 公开 benchmark 仅 **2/24** verified repair | 确定性引擎只覆盖 capacity-check rewrite 与同函数 heap 立即数容量两类；其余 22 例无候选 | Phase-8C claims public_benchmark.verified_repair_rate=0.0833；8B 10/12 analysis-only | 先解决 `heap-malloc` 的 plan/ABI 语义冲突，再扩展跨函数 dataflow |
| 3 | hidden benchmark **0 候选 / 0 verified** | 确定性引擎在 hidden 变体（不同编译器/优化/路径）上不泛化 | claims hidden_benchmark：executed 8、verified 0、false_verified 0 | 视为真实覆盖缺口，不解释为 pass；Phase-8D 受控 hidden 迭代 |
| 4 | `heap-malloc` 真实 engine/plan-vs-verifier ABI 冲突被撤回 | verifier 要求可派生 ABI block；该样本 plan 与实际分支目标/调用目标/ret 状态不一致（branch_target_unknown / call_target_not_allowed / no_ret） | Phase-8C 报告 + `disagreements.json`；确定性 claim withdrawn 1 | 修 engine 的 plan 生成或 verifier 语义（不放宽验证） |
| 5 | Phase-8A 两个 deterministic claim 被撤回（Phase-8B 已闭合） | oracle CLI 未注入、resolved scope 未交换、长度变化 blanket reject、`.rodata` message action 未建模、ABI 未派生、缺 patch-plan、runner 未交换证据 | 8A：disagreements 2；8B：V8B-01~07 confirmed、disagreements 0、2/2 verified | 已闭合；保留回归测试防复发 |
| 6 | G01–G30 中真正语义能力缺失（G04/G05/G06/G09–G17） | 组合/变异/变形发现未实现；跨函数 dataflow、alias/global/struct、integer、string（仅探针）、UAF、间接调用、路径敏感、并发未达 M3/M4 | Phase-8A readiness：implemented 13 / partial 7 / missing 5 / not_run 1 / non_goal 4；claims `not_claimed` | 以 readiness 的 blocker/next_action 为输入排期 |
| 7 | Readiness 的「implemented 13」易被误读为能力晋级 | 规则是 code+test(+artifact/ground truth) 的**探针级工程证据** | readiness 文档明确「不是能力晋级」；G29 hidden `not_run` | 对外表述固定为「探针级」，capability graduation 仍为 0 |
| 8 | Provider 维度只 2 providers / 4 models | SiliconFlow intl HTTP 402、GLM-Z1 探测超时、DashScope 无 key | claims.provider_coverage：not_satisfied、blocked_reasons；pooled AI-target 36/96=0.375（Wilson 95% CI [0.285,0.475]）；cost/seed null | 配置 5–6 模型国际矩阵；统计扩展到置信区间之外 |
| 9 | served-model 身份不匹配 | Lead run 请求 deepseek-chat 实际服务 deepseek-flash（identity_ok=false） | 6/12 只归因 served model，不计 requested-model coverage | 选支持 exact identity 的 endpoint 复跑 |
| 10 | non-loop AI verified **0/6**；多 provider 统计缺失 | AI 路径非验收 owner（leaf/allowlist 校验器）；统计口径未建立 | claims non_goals（NG-ai-leaf-only）；LIMITATIONS §16/17 | 作为研究非目标按五步毕业路径推进 |
| 11 | self-hosted Lima nightly **not_run** | 无 self-hosted runner；job 被 `vars.BINARYREPAIR_RELEASE_GATE` inert 保护 | 各阶段 `ci-run.json` self_hosted_nightly=not_run + signoff | 配置 self-hosted runner 或明确长期不声明 |
| 12 | 浏览器证据分层 | Linux CI 无 Chromium 时显式 skip；本地 macOS Chrome 12/12 | `artifacts/browser-e2e-2026-11-14/summary.json`；Phase-8C claims `not_claimed` | 保留本地证据定位，不并入 CI 结论 |
| 13 | 平台限制（不可用能力） | 32-bit Mach-O 原生执行不可用；PE 外部 PoC 不可用；arm64 宿主上 macho/x86_64 外部 PoC 仅 Rosetta 函数级 | `docs/acceptance/platform-limits-2026-11-15.md`；contract/claims 显式 unavailable/not_run | 保持 not_run，不伪造；需要时换宿主 |
| 14 | 12 项研究/平台非目标未实现 | 能力/规模/证明范围限制；已产品化治理 | claims.non_goals 12 项（含 EG-cases-target-not-analyzed、NG-ai-leaf-only×2、NG-non-goal-1~5、RG-external-poc×4），均带 owner/review_by(2027-02-14)/productization criteria/fallback；coverage gate 未映射即失败 | 季度复审 + 五步毕业（fixture→runtime oracle→evidence profile→gate check→claims） |
| 15 | claims CI 指针滞后（结构性） | 写完 claims 提交后树变化→再跑 CI 会产生新 SHA；不能自引用自身 run ID | claims `latest_verified_ci`=43744573286（SHA f1ba37e）；最终 SHA 的 43748886046 记录在 evidence 分支 addendum | 保持双记录；或在冻结窗口内再做 claims commit + 重 gate（会换 SHA） |
| 16 | Evidence 后置 / 部分证据在本地分支 | 设计上 release note + bundle 放 evidence 分支；marcx 一手证据只在本地 `backup/capacity-86587da` | `git merge-base` 实测 `86587da` 非 mainline 祖先；`artifacts/marcx-repair-2026-11-14/` 不在 origin/mainline | **优先归档 marcx 证据包**；确认所有 evidence tag 可推送/可校验 |
| 17 | Lima 并发鲁棒性 | 外部 P16 工作负载与本地 gate 共用同一 Lima guest；C11 前有一次 false_verified=1 的 flake | 8B 两次 gate 瞬时失败后 guest 空闲重跑通过；8C 两次 serialized repeat 一致；flake 仍为 documented warning | 专用 runner/串行化纳入 CI 强制 |
| 18 | 外部并发写入导致证据失效风险 | operator 多次推进 mainline（阶段 6 曾 6 次；8A/8B/8C 均有） | freeze wrapper 记录 `mainline_unchanged`；任何后续 mainline commit 使该证据失效 | 发布窗口冻结；按 `docs/operations/worktree-safety.md` 重 freeze |
| 19 | Hidden 隔离非密码学 | 0700 私有 root、CI 不访问、只发 commitment/aggregate；同 UID/root 可读 | Phase-8C 报告/LIMITATIONS | 明确风险；如需强隔离用独立账号/加密 |
| 20 | 外部样本摄入 `not_run`；跨编译器未验证（仅 Zig 0.17.1） | 无本地 external corpus；无第二 Linux 编译器 | claims external_ingestion=not_run；cross_compiler_verified=false | 提供外部语料/第二工具链再声明 |
| 21 | Phase-8D / Phase-9–16 未实施 | 未进入排期 | 各阶段 `not_claimed` 明确 | 从 Phase-8D（开放世界发现 + Acceptance 2.0）起步 |
| 22 | 历史完整性修正 | `artifacts/coverage-closure-2026-11-14/SHA256SUMS` 的 acceptance.json checksum 过期 | Phase-8A 只改 checksum 行（f4aa…→43e3…），未改内容 | 已修正；后续 artifacts 由 gate 自动生成 SUMS |
| 23 | 证据分层易混淆（本地 gate vs CI vs nightly vs browser） | 各层证明范围不同 | release note/ci-run.json/claims ci_evidence schema v2 显式区分；`ci_status=portable_hosted_success_self_hosted_not_run` | 保持分层表述，不合并 |

---

## 6. 该会话 team/task（48 个任务）状态汇总

### 6.1 总体

- 48 个任务：**completed 44 / in_progress 2 / pending 2**（team/task 终态实测）。
- owner 分布（按 ownerId 映射到 teammate 名）：

| owner | 角色 | completed | in_progress | pending |
|---|---|---|---|---|
| Lead（session-b139b586…） | 主控 | 1（task-1） | 0 | 0 |
| guest-runtime（3d314401…） | Lima guest / PoC manifest / capability probe | 4 | 0 | 0 |
| pipeline（71d269a3…） | pipeline / unified gate / provider 矩阵 / benchmark | 9 | 0 | 0 |
| gui-docs（d1dd544f…） | GUI / docs / CI 证据 / reflection / verifier MVP | 7 | 0 | 0 |
| audit-tools（9438bd56…） | 审计工具 / gap registry / acceptance / Phase-8 审计 | 9 | **2** | 0 |
| heap-engine（6e1a16d0…） | heap 容量引擎 / hidden corpus | 2 | 0 | 0 |
| gate-profiles（b0ce1dc7…） | 验收 profile | 1 | 0 | 0 |
| target-scope（ca467c26…） | target scope / safe default / runner v2 | 3 | 0 | 0 |
| legacy-convergence（df27de2c…） | legacy 收敛 / 合同 / 治理 | 8 | 0 | 0 |
| （unowned） | Lead 集成任务 | 0 | 0 | **2** |

### 6.2 48 个任务全表

| task | owner | status | subject |
|---|---|---|---|
| task-1 | Lead | completed | Capacity-confusion repair engine (Lead) |
| task-2 | guest-runtime | completed | Guest runtime + PoC manifest file fixtures |
| task-3 | pipeline | completed | Pipeline + unified gate + API/CLI capacity integration |
| task-4 | gui-docs | completed | GUI manifest upload + docs for capacity repair |
| task-5 | audit-tools | completed | Capability-gap self-discovery audit tool + evidence |
| task-6 | heap-engine | completed | Heap destination capacity recovery + fixture/oracle |
| task-7 | gate-profiles | completed | Acceptance-model harmonization: profiles, no-input, cell/tier, rewrite checks |
| task-8 | target-scope | completed | P0 target selector + patch ownership gate + benchmark strict mode |
| task-9 | legacy-convergence | completed | P1 legacy gate manifest write-path convergence |
| task-10 | guest-runtime | completed | P2 runtime capability probe + Mach-O x86_64 honesty + matrix payload |
| task-11 | audit-tools | completed | P3 non-goal mapping + coverage regression gate + audit detector closure |
| task-12 | target-scope | completed | P0 safe default whole-image policy + target/allow plumbing |
| task-13 | audit-tools | **in_progress** | P0/P1/P2 audit dynamic_unverified + universe/meta-audit + invariants + non-goal productization |
| task-14 | guest-runtime | completed | P0 unified capability contract + platform-limit negative tests |
| task-15 | pipeline | completed | P1 real 12-case provider matrix + target-strict measurement evidence |
| task-16 | gui-docs | completed | P2 release/nightly gate + cost layering + worktree safety docs |
| task-17 | pipeline | completed | P1 provider coverage: reproducible builder + statistics + identity policy + docs + tests |
| task-18 | audit-tools | completed | P2/P3 self-audit closure: meta-audit 18 scenarios + capability contract checker + roadmap id gate |
| task-19 | gui-docs | completed | P0/P1/P3 CI evidence separation: release-sha + evidence upload, serial/language checks, ops docs, browser e2e evidence |
| task-20 | legacy-convergence | completed | P3 language compliance fix + P2 non-goal roadmap document (12/12 ids) |
| task-21 | pipeline | completed | P1 provider HTTP/identity evidence + AI failure classification |
| task-22 | audit-tools | completed | Universe methodology artifact/checker + meta-audit 22 + release-claims gate checks |
| task-23 | gui-docs | completed | CI hosted release gate + drift checker + evidence-branch verifier/ops docs |
| task-24 | legacy-convergence | completed | Non-goal/flake/platform/compliance governance artifacts + checkers |
| task-25 | audit-tools | completed | Acceptance Intelligence: 20 mismatch classes + matcher + audit + meta-audit acceptance scenarios |
| task-26 | pipeline | completed | 20-dimension universe registry + unified Gap Registry + six-mechanism discovery adapters |
| task-27 | gui-docs | completed | Reflection Engine + Experiment Planner + unified autonomous_repair_audit + CI/docs |
| task-28 | legacy-convergence | completed | Canonical repair/capability state machine + six JSON contracts + autonomy roadmap |
| task-29 | audit-tools | completed | Phase-8A: 30-item G01-G30 repair readiness audit + artifact + docs |
| task-30 | pipeline | completed | Phase-8A: Ground-Truth Benchmark v1 manifest/builder + deterministic repair benchmark runner |
| task-31 | gui-docs | completed | Phase-8A: Independent Verifier MVP + unified audit shadow checks |
| task-32 | legacy-convergence | completed | Phase-8A: 6 contracts + AM21-AM24 acceptance + meta 28 + phase-8 roadmap |
| task-33 | audit-tools | completed | Phase-8B B1/B2: verifier disagreement baseline audit + root-cause/semantics docs |
| task-34 | legacy-convergence | completed | Phase-8B B3/B9: patch-plan/verification contracts + AM25-AM28 acceptance/meta |
| task-35 | gui-docs | completed | Phase-8B B4/B8: layout-aware independent verifier + ABI/oracle + negative tests |
| task-36 | pipeline | completed | Phase-8B B5/B6/B7: pipeline patch plan/gate + benchmark independent verification |
| task-37 | unowned | **pending** | Phase-8B B9/B10: integration, CI/claims, final gate/evidence/tag/report |
| task-38 | legacy-convergence | completed | Phase-8B follow-up: acceptance contract AM01-AM28 alignment |
| task-39 | audit-tools | completed | Phase-8C C1: baseline & hidden benchmark readiness audit |
| task-40 | legacy-convergence | completed | Phase-8C C2: Ground Truth v2 contracts + migration/checker |
| task-41 | guest-runtime | completed | Phase-8C C11: Lima guest coordination and serialization |
| task-42 | pipeline | completed | Phase-8C C3/C8/C9: public corpus v2 + variants + cross-arch |
| task-43 | heap-engine | completed | Phase-8C C4: private hidden corpus + commitment |
| task-44 | target-scope | completed | Phase-8C C6/C10: benchmark runner v2 + semantic regression |
| task-45 | audit-tools | **in_progress** | Phase-8C C5/C7/C13: contamination, external ingestion, quality audit |
| task-46 | unowned | **pending** | Phase-8C C12/C14: integration, evidence, CI and release |
| task-47 | pipeline | completed | Phase-8C C3 fix: SUMS ownership with C4/C6 auxiliary artifacts |
| task-48 | audit-tools | completed | Phase-8C C1 final rebind to a1755a5 and flake record |

### 6.3 pending / in_progress 的原因（含证据与推断）

| 任务 | 板上状态 | 创建/变更 | 原因 |
|---|---|---|---|
| task-13（audit-tools） | in_progress | 20:46 创建 pending → 20:47 in_progress（seq 4141/4168），之后再无状态变更 | 内容（dynamic_unverified 状态、universe/meta-audit、invariants、非目标产品化）实际由 Lead 在阶段 3/4/5 直接实现并发布（seq 5201/6184/7253 报告、`0aa9f54`/`956ee10`/`f65ed53`），**板面未回写 completed**；属任务板记账滞后（推断） |
| task-45（audit-tools） | in_progress | 22:21 创建 pending → 22:41 in_progress（seq 14305/14541），之后再无变更 | C5 污染审计、C13 质量审计在最终树已完成（public/hidden clean、quality ok），C7 external ingestion 显式 not_run；Lead 在 turn 14 直接完成并写 claims（phase8c claims），**任务未回写**（推断） |
| task-37（unowned） | pending | 15:49 创建（seq 11055） | 描述即「Lead 集成、claims/docs、CI shadow、全量验证、final gate/evidence/tag/report」；Lead 直接在 mainline 完成 8B 集成与发布（`227f45b`/`528304a`），**从未 claim**，故终态 pending |
| task-46（unowned） | pending | 22:47 创建（seq 14608） | 描述即「Lead integration, evidence/provenance, CI shadow, frozen-tree gate…」，Lead 直接完成 8C 集成与发布（`4a7b235`/`ec503e4`），**从未 claim** |

> 说明：48 个任务中 44 个由 8 个 teammate 完成；Lead 只正式 claim 过 task-1（首轮核心引擎），其余 Lead 工作走「不建板 / 不 claim」的直做模式，这就是 2 个 pending（Lead 集成类）+ 2 个 in_progress（被 Lead 接管的审计类，未回写）的全部来源。

---

## 7. 该会话最终仓库状态与能力边界

### 7.1 仓库状态（分析时实测，只读）

- 主工作树 `binary-repair-gui`：HEAD = `ec503e4b1df53ad39fa836bd34d93a18564d78f9`（分支 `release/2026-11-16-phase8c-evidence`，2026-11-16 03:17:00 +0800，「phase-8C evidence: remove stale Phase-8A gate dir」），`git status` clean。
- mainline `origin/workbench-v3` = **`4a7b2355ffc5225d013a777bc7d588abac58f944`**（2026-11-16 02:48:52 +0800，tree `4bf501314b6469328d0256031990bfc402ce6677`）；`origin/release/2026-11-16-phase8c-final` 同 SHA。
- 其他 worktree：`worktree-feature-final` = `a1755a5`（`feature/ai-binary-repair`，behind origin/workbench-v3 19）；`binary-repair` = `221e47c`（`member-5-deepseek-schema`，旧）。
- 分支（origin 关键 ref 实测）：`release/2026-11-14-final`=fd6ca41、`release/2026-11-14-evidence`=9cfaaaa、`release/2026-11-15-final`=fd6ca41、`release/2026-11-15-evidence`=028d709、`release/2026-11-16-final`=a8934fe、`release/2026-11-16-evidence`=d6b41db、`release/2026-11-15-autonomy-final`=2bfa112、`…-autonomy-evidence`=37994eb、`…-phase8a-final`=bd9cbf6、`…-phase8a-evidence`=0a095c5、`…-phase8b-final`=227f45b、`…-phase8b-evidence`=528304a、`…-phase8c-final`=4a7b235、`…-phase8c-evidence`=ec503e4；另有 `feature/phase8c-ground-truth-v2`=4a7b235、`feature/phase8b-verifier-semantics`=227f45b、`feature/phase8-repair-readiness`=bd9cbf6、`feature/autonomy-foundation`=2bfa112 等。
- 14 个 release tag（含 evidence tag）全部存在且为 annotated tag，映射见 §3.9。
- 代码形态：`app/services/repair/capacity.py`（35 KB）、`app/services/independent_verifier.py`、`app/services/verification_semantics.py`、`app/services/benchmark_runner.py`、`app/services/guest_coordinator.py`、`app/services/acceptance_models.py`、`app/services/repair_states.py`、`app/services/coverage_audit.py` 等；`contracts/` 17 份 schema；`scripts/` 含 audit/verify/release/freeze/provider/universe/reflection/runner 等 20+ 校验脚本；`tests/` 206 个文件；`benchmark/phase8-v1` 与 `benchmark/phase8c`。

### 7.2 能声称（有已提交证据、可复现命令）

1. **marcx 这一类缺陷已被修复并可验证**：ELF64 x86-64、重复内联范围校验块「容量变量用错」类（容量为寄存器分配形态）；marcx 原始 `72fb53cb…` → 修复后 `93e27f2f…`（16 B `.text` + 49 B `.rodata`）；真实 Lima guest PoC/回归差分 28/28 一致；挑战归档矩阵 16/16；通用合成样本（rbp→r12d）同样修复且 guest 通过；20+ 其他 fixture 不误报。（一手证据包当前仅在本地 backup 分支，见 §2.6）
2. **两个 deterministic fixture 修复被独立验证**（Phase-8B，可复算）：`stack-strcpy-x86_64`（candidate `1bc66b2e…`）与 `heap-capacity-x86_64`（candidate `93e27f2f…`）；`artifacts/phase8b-benchmark-2026-11-16/results.json`：12 executed、2 candidates、**2 independently verified**、**false_verified=0**、**verification_disagreements=0**，oracle 真实执行 `limactl`/`emulated_run`。范围声明：目标 scope 内的 deterministic fixture repair + 函数级 PoC 差分，不是整程序证明。
3. **公开 benchmark（Phase-8C）**：32 samples、24 runtime-oracle/8 analysis-only、dev 18/validation 14；30 executed、2 unsupported、0 not_run/blocked/invalid；2 verified / 1 rejected；**published false_verified=0**；verified repair rate 2/24=0.0833；detection/root-cause/localization 3/24；2 次 serialized repeat 结果一致（不声明无条件稳定）。
4. **hidden benchmark 已真实执行**：8 samples（6 runtime + 2 analysis-only）全执行、commitment `eaec60aa…`（file `3ebf2901…`）、**0 candidates / 0 verified / 0 false_verified**；hidden 泛化能力**未**成立（这是覆盖缺口，不是 pass）。
5. **能力审计状态**：68 gaps（55 closed / 1 mitigated / 0 open / 12 non-goal；high=0；dynamic=0）；静态视图 62（44/6/11/1/0）；**240 cells、unknown=0**（36 verified/51 supported/129 non_goal/24 unavailable）；meta-audit **30 scenarios recall/precision 1.0**；invariants **9 packets / 12 limitations / 0 violations**；12 项非目标 12/12 产品化映射（owner/复审 2027-02-14/产品化条件/兜底）。
6. **发布门禁**：最终 SHA `4a7b235` 上本地 frozen-tree nightly **13/13 required checks passed、0 failed/skipped/unavailable、violations=[]**；`frozen_sha==release_sha`、clean tree、`mainline_unchanged=true`；gate 命令与 SHA256SUMS 可复核；`release_freeze.py` 在 mainline 漂移时 fail-closed。
7. **CI 证据**：GitHub-hosted `CI` 与 `Ubuntu verification` 在最终 SHA 上均 success（43748886046 / 43748886289）；此前各阶段同样有成功 run（§3.8）；browser e2e 本地 macOS Chrome 12/12；**self-hosted Lima nightly 全程 not_run，未冒充**。
8. **证据链**：claims/provenance/evidence 分支/tag 体系完整；`verify_provenance`、`verify_evidence_branch`（8/8 checks）、`release_drift_check`（drift=0）、`verify_ci_evidence --online` 均在最终发布通过；证据分层（本地 gate / hosted CI / self-hosted nightly / browser）显式。

### 7.3 不能声称（明确边界）

1. 不能声称任意二进制、任意漏洞类、whole-program 或生产安全能力——只有 2 个 deterministic fixture repair 被独立验证。
2. 不能声称 hidden 泛化：hidden 0 候选、0 verified、0 false_verified。
3. 不能声称 Phase-7/8A/8B/8C 新增了漏洞修复能力或发生了能力晋级（claims 各 phase `false`；capability graduation 仍为 0）。
4. 不能声称跨函数语义/alias/global/struct/integer/UAF/间接调用/路径敏感/并发已具备（G09–G17 缺失或 partial）。
5. 不能声称 5–6 模型国际 provider 矩阵满足（2 providers/4 models；402/超时/无 key）；不能把 served-model 数据当 requested-model 证据。
6. 不能声称 self-hosted Lima nightly 已运行；不能把 Linux CI 的 browser skip 当 pass。
7. 不能声称 PE/32-bit Mach-O/arm64 宿主上 macho x86_64 的外部 PoC 可用（显式 unavailable/not_run）。
8. 不能声称 cross-compiler 验证（仅 Zig 0.17.1）、external ingestion（not_run）、errno 运行时捕获（gate 仍 stdout+regression）。
9. 不能把 `0 open` 或 `13/13` 等价于「所有可能全覆盖」：240 cells 是 11 维枚举结果，方法学文档明确不能证明维度已穷尽（`undiscovered_space=not_measurable`）。
10. 不能复用旧 SHA 的 CI/证据：claims 的历史 CI（43744573286 @ f1ba37e）与最终 SHA（43748886046 @ 4a7b235）分开记录，不互相冒充。
11. 不能声明无条件稳定性：一次性 flake 仅为 documented warning；Lima 并发会影响 reference-host 测量。

### 7.4 关键复现命令（来自 release note / 各阶段报告）

```bash
cd binary-repair-gui
.venv/bin/python scripts/audit_capability_coverage.py --out artifacts/capability-gap-audit-2026-11-14
.venv/bin/python scripts/verify_coverage_gate.py --static-only
.venv/bin/python scripts/verify_coverage_gate.py --local
.venv/bin/python scripts/release_freeze.py --mode nightly --sha 4a7b2355ffc5225d013a777bc7d588abac58f944 --json
.venv/bin/python scripts/run_repair_benchmark.py --verifier auto --claim-policy withdraw
.venv/bin/python scripts/verify_repair.py --selftest
.venv/bin/python scripts/check_contract_schemas.py --check
.venv/bin/python scripts/audit_acceptance_models.py --check
.venv/bin/python scripts/meta_audit.py
.venv/bin/python scripts/autonomous_repair_audit.py --mode full --json
.venv/bin/python scripts/release_drift_check.py --tag release-2026-11-16-phase8c
.venv/bin/python scripts/verify_evidence_branch.py --gated-sha 4a7b2355ffc5225d013a777bc7d588abac58f944 \
  --evidence-ref release/2026-11-16-phase8c-evidence --json
```

### 7.5 证据索引（本报告引用到的核心来源）

- 会话：`.tmp/sessions/s2-alltypes.jsonl`（seq 8/1795/1787/3505/4096/5201/6184/7253/8520/9441/10786/10811/13910/16654 等）。
- 发布身份：`docs/status/claims.json`；`docs/release-2026-11-16-phase8c.md`；`docs/release-phase8c-final-evidence-2026-11-16.md`（evidence 分支）；`docs/release-phase8b-final-evidence-2026-11-16.md`；`docs/release-2026-11-16.md`。
- 限制：`docs/acceptance/LIMITATIONS.md`（§21–23 + Phase-8A/8B/8C 段）；`docs/acceptance/platform-limits-2026-11-15.md`；`docs/acceptance/non-goal-roadmap-2026-11-14.md`。
- 审计：`artifacts/capability-gap-audit-2026-11-14/{coverage-matrix.json,gap-report.md,SHA256SUMS}`；`docs/acceptance/capability-gap-audit-2026-11-14.md`。
- 验收：`artifacts/coverage-closure-2026-11-14/acceptance.json`（marcx 21/21、heap 19/19、target-scoped 20/20、safe-default 对照）。
- 阶段：`artifacts/{phase8-readiness-2026-11-16,phase8-benchmark-2026-11-16,phase8-verification-2026-11-16,phase8b-baseline-2026-11-16,phase8b-benchmark-2026-11-16,phase8c-baseline-2026-11-16,phase8c-benchmark-2026-11-16,phase8c-contamination-2026-11-16,phase8c-quality-2026-11-16,phase8c-hidden-2026-11-16,phase8c-release-2026-11-16,acceptance-model-audit-2026-11-16,capability-universe-2026-11-16,gap-registry-2026-11-16,autonomous-reflection-2026-11-16}`。
- Gate 证据：各 evidence 分支 `artifacts/release-gate-*/{gate.json,freeze.json,README.md,SHA256SUMS}`。
- marcx 一手证据：本地分支 `backup/capacity-86587da` 的 `artifacts/marcx-repair-2026-11-14/`（不在 origin）；`fixtures/elf/vuln-capacity-confusion-x86_64.elf`（sha256 实测 `72fb53cb…`）、`fixtures/poc/marcx-capacity.json`。

### 7.6 未核实/仅报告自述项

- turn 1「全量 1224 passed / 7 skipped / 0 failed」、Phase-7「新增 101 个 phase-7 测试」、Phase-8B 各 targeted 测试数量（69/57/73 等）：本次分析未重跑测试，仅记录报告自述。
- 浏览器 e2e「12/12、35.0 s」：证据 `summary.json` 存在（Chrome 157.0.8103.51），本次未逐条复核 runs 数量。
- 「`--release` 9/9」「nightly 11/11」为各阶段报告自述；仓库现存的 `2026-11-14-evidence` bundle 记录的是 cdeab74 的 12-check gate（995.2 s），11/11 版本的 bundle 已被后续覆盖，故标「报告自述 + 证据历史被覆盖」。
- operator 侧调用细节（如 deepseek 服务端 identity 实际值）：来自 artifacts/provider-coverage-2026-11-14 记录。

---

## 8. 一句话总结

该会话把「一个样本修不好」升级为「可审计的修复能力 + 显式验收模型 + 可复现发布证据链」：marcx 的 capacity-check mismatch 已修复（patched `93e27f2f…`、真实 guest 28/28），66→68 项 gap 收敛为 0 open/1 mitigated/12 产品化非目标/240 cells unknown=0，最终 mainline `4a7b235` 本地 nightly 13/13 + 真实 hosted CI 双绿 + evidence 分支/tag 体系完整；但真正的新修复能力并未增加——公开 benchmark 仅 2/24 verified、hidden 0 verified、Phase-8D/9–16 未实施，所有边界均已写入 claims/LIMITATIONS，没有用「0 open + 13/13」掩盖能力缺口。
