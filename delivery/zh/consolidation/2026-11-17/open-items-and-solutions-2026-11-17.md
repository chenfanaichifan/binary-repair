# 05 · 未完成任务与问题清单（P0/P1/P2）＋分级解决方案

- 生成时间：2026-11-17 09:20（Asia/Singapore）
- 角色：第 5/6 号协作子 Agent（问题清单与解决方案）
- 基线对象：`final/consolidated-2026-11-16`=c0f9feb、`workbench-v3`/`release/2026-11-17-phase8d-final`=d37bfad、`release/2026-11-17-phase8d-final-evidence`=a1d7150、`phase8d-open-world`=996060d、`release/2026-11-17-phase8d-evidence`=bdd3f84
- 路径简写：**WT8D** = `binary-repair-gui/.agents/worktrees/phase8d-final-d37`（a1d7150，含 Phase-8D 全部产物）；**GUI** = `binary-repair-gui`（当前在 final/consolidated-2026-11-16，工作树脏，见 P0-6）

## 0. 口径与分级（先读，避免误读）

| 项 | 定义 |
|---|---|
| 状态 S1 | 代码/测试已实现并验证（有可复现命令或证据 JSON） |
| 状态 S2 | 仅有文档/声明（含 runbook、设计稿、claims 文字） |
| 状态 S3 | 部分实现（offline/mock/单架构/单一样本成立，live 或多架构未成立） |
| 状态 S4 | 未开始 / not_run（无代码或无真实执行；**not_run ≠ pass**） |
| P0 | 阻塞本次交付/签核：安全、单一交付 SHA、核心能力上限、备份可恢复性、工作树完整性 |
| P1 | 能力或验证缺口：不阻塞"诚实的交付"，但阻塞任何"通用修复/晋级"声明 |
| P2 | 治理/债务：口径漂移、CI/默认分支、refs、备份文档、平台边界、测试耗时 |
| 证据 | 一律给 `文件:行`、`git show <sha>:文件`、或 `session:<id前缀>#seq=NNNN @时间`；无法核实的写「未核实」 |

**本报告不复制旧报告数字**：下表所有数字均来自 2026-11-17 对仓库/会话/guest 的实测或当期 claims/artifacts。

## 1. 执行摘要（12 条）

1. **项目仍是有界修复，不是通用修复**：public 2/24（8.33%）、hidden runtime 0/6、`false_verified=0`、1 个 deterministic claim 被独立验证器撤回（heap-malloc）。证据：`WT8D/docs/status/claims.json#phase8c_ground_truth`、`WT8D/artifacts/phase8d-baseline-2026-11-17/baseline.json`。
2. **hidden 0 的根因已定位到"检测"而非"修复"**：6/6 runtime 样本 `first_blocking_stage=detection`、`no_candidate_reason=detection_missed`；后续阶段全部 not_reached。证据：`WT8D/docs/operations/phase8d-hidden-stage-attribution.md:47-58`。
3. **但 D05 的归因叙述有一处字段语义错误**：文中称"引擎报告 detected=true/repairable=true 却 0 findings"，而这两个字段实际是"容器格式识别/矩阵单元支持"，不是漏洞检测；真实检测在 `detection=bool(findings)`。结论（0 findings）仍成立，"自相矛盾"的说法需修正。证据：`WT8D/app/services/binary_pipeline.py:286-287`、`WT8D/app/services/benchmark_runner.py:846,850`。
4. **Phase-8D 交付了 297 单元能力宇宙、8 条 open audit gap（2 critical/6 high）、Acceptance 2.0（18 案/14 变异全检出）、promotion gate（4 评估全拒）**，但**本阶段没有新增任何修复能力**，`generalized=0`、`promoted=0`。证据：`WT8D/artifacts/phase8d-gap-registry-2026-11-17/gaps.json`、`WT8D/artifacts/phase8d-promotion-2026-11-17/README.md`。
5. **P31–P34 只完成 offline 部分**：gateway/adapters/preflight/stability runner 有代码与离线测试（2411 tests/0 fail/9 skip）；OpenRouter/Ollama 真实调用、Keychain/GitHub Secret、60-run 全部 `NOT_RUN`。证据：`WT8D/docs/acceptance/p31-p34-2026-11-16.md:6,53,71-72`；实测 `run_model_preflight --provider openrouter` → exit 2 / BLOCKED。
6. **P35–P40 未开始**（P35 60-run、P36 CaveABI 出口、P37 授权记录、P38 CWE-121、P39 CWE-134、P40 GDB+AFL++）；会话一收尾时明确记录，且 `final` 分支未更新。证据：`session:879cc62f#seq=19985 @2026-11-17 00:46`。
7. **CWE-121/134 只有"确定性替身"证据**：M1 用固定参考汇编/脚本化 `%s` 修复打穿 Native gate 与独立验证器，但**没有 live 模型调用**，不能算 AI 能力提升（3/6 未变 4/6）。证据：`WT8D/docs/operations/m1-2026-11-16.md:153-161`（§8 Claim boundary）。
8. **交付分支已再次分叉**：`final/consolidated-2026-11-16`（c0f9feb）与 `d37bfad` 互不包含（final 独有 2 个 P31 提交，d37 独有 7 个 Phase-8D/P31-workbench 提交）；P31 代码两份内容一致（关键路径 diff 为空），但 provider-coverage/junit 是两棵树各自再生成。证据：实测 `git rev-list --count`、`git diff a9db731 e01fc9e -- app/services/llm_gateway ...` 为空。
9. **交付工作树处于半提交/破坏态（本次新发现，最危险）**：GUI 工作树有 41 项改动；`app/services/llm_gateway/{__init__,base,client,providers/*}.py`、`scripts/run_model_preflight.py`、3 个 P31 测试与 P31 文档被**暂存删除**，磁盘上只剩 credentials/errors/usage；同时存在**任何分支都没有的**未提交修复：writer 的 phdr 槽位修复（+76/−36）、`suggest_repair_targets`（+138）、GUI agent.js（+140）。证据：`git -C binary-repair-gui status --short`、`git diff d37bfad -- <file>`。
10. **备份不覆盖当前交付链**：mirror 的 `final/consolidated-2026-11-16`=f1bb1f4（不是 c0f9feb），`d37bfad` 对象不存在；bundle 实际 SHA256=89a649… 而文档写 4129db…。证据：实测 `git -C backup/… cat-file -t d37bfad` → fatal；`shasum backup/local-refs-2026-11-16.bundle`。
11. **凭据仍未轮换**：4 个槽位（K1 SiliconFlow CN、K2 SiliconFlow Intl、K3 DashScope、K4 DeepSeek，含 GUI key store）列为 COMPROMISED，runbook 已写，执行 `blocked_by=owner`；会话日志目录 0700，但明文 key 已进入会话历史。证据：`WT8D/docs/operations/security-key-rotation-2026-11-17.md` §1。
12. **CI/默认分支仍不成立**：远端 HEAD=main=8869b07（陈旧）；自托管 Lima job 默认 inert（需 repo variable）；`claims.latest_verified_ci` 指向 78edb97/workbench-v3（run 43900916188），final/d37 的 tip 无 CI 记录。证据：实测 `git ls-remote --symref`、`WT8D/.github/workflows/ci.yml:353-366`、claims。

## 2. 本期实测基线（可复核）

| 指标 | 值 | 证据/命令 |
|---|---|---|
| public benchmark | 2/24 verified（8.33%），30 executed，1 rejected，1 withdrawn，false_verified=0 | `WT8D/docs/status/claims.json#phase8c_ground_truth.public_benchmark` |
| hidden benchmark | 8 样本=6 runtime+2 analysis；0 candidate、0 verified；detection_missed=6 | `WT8D/artifacts/phase8d-hidden-attribution-2026-11-17/aggregate.json` |
| 能力宇宙 | 297 units；independently_verified=2；generalized=0；promoted=0；not_applicable=131 | `WT8D/artifacts/phase8d-capability-universe-2026-11-17/registry.json` |
| Phase-8D gaps | 8 open（critical 2：AUDIT-07/08；high 6）；0 promoted | `WT8D/artifacts/phase8d-gap-registry-2026-11-17/gaps.json` |
| Acceptance 2.0 | 18 案、18 matched、false_accept=0、false_reject=0、mutation 14/14、not_run 2、inconclusive 2 | `WT8D/artifacts/phase8d-acceptance-2-2026-11-17/report.json` |
| promotion gate | 4 评估 / 4 denied（含 hidden_verified=0 导致 generalized 拒绝） | `WT8D/artifacts/phase8d-promotion-2026-11-17/README.md` |
| D07 发现 | 4 变体（2 执行、2 stripped 不支持）、11 输入变异全执行、2 处引擎能力差异 | `WT8D/artifacts/phase8d-discovery-2026-11-17/README.md` |
| 外部知识 | CWE 5.0：984 条、232 映射候选、support_claimed=false | claims `phase8d_open_world.external_knowledge` |
| 发布门禁 | d37bfad：nightly 13/13 passed、0 failed、exit 0、1,250s；full pytest 1,064s | `WT8D/artifacts/release-gate-2026-11-17-phase8d-final/gate.json` |
| 全量测试 | 2411 tests / 0 failed / 0 errors / 9 skipped / 1015.7s | `WT8D/artifacts/binary-universal-v5-2026-11-13/macos-junit.xml` |
| 稳定性（历史） | 36 次 19/36=52.8%（flash 12/18、v4-pro 7/18；cwe121 0/6） | `WT8D/artifacts/stability-2026-11-16/README.md` |
| provider 统计 | 4 模型/2 provider、96 case-run、36 verified、Wilson [0.285,0.475]；intl 402 | claims `provider_coverage` |
| 远端 refs | 97 heads / 101 tag 行（含 `^{}`）；HEAD→main 8869b07 | `git ls-remote origin` |
| 分支关系 | final 独有 2 提交（a9db731,c0f9feb）；d37 独有 7 提交（含 Phase-8D） | `git rev-list --count final..d37` / `d37..final` |
| guest 工具链 | gdb=MISSING、afl-fuzz=MISSING、zig=MISSING；clang/gcc/readelf/qemu-x86_64 存在；guest aarch64 | 实测 `limactl shell binaryrepair -- command -v` |
| 私密语料根 | 存在且 mode 0700（路径不公开） | 实测 `ls -ld`（只读） |
| preflight | mock→CONFIGURED/exit 0；openrouter 无 key→BLOCKED/exit 2（实测） | `WT8D/scripts/run_model_preflight.py` |

## 3. 优先级总表（27 项）

| ID | 问题（一句话） | 状态 | 级别 | 旧编号 | 关键证据 |
|---|---|---|---|---|---|
| P0-1 | 4 个 provider 凭据未轮换，会话日志含明文 | S3（清单+扫描完成，轮换未做） | P0 | B9/D1 | security-key-rotation §1 |
| P0-2 | 无单一交付 SHA：final 与 d37 分叉、main 陈旧 | S3 | P0 | C1/B5 | 实测 rev-list / ls-remote |
| P0-3 | hidden 0/6，全部卡在 detection | S3（已归因，未修复） | P0 | A10/AUDIT-01 | hidden attribution:47-58 |
| P0-4 | CWE-121/134 只有确定性替身；非 loop 剩余 3 例仍 0 | S3 | P0 | A1/A2/A3 | m1-2026-11-16.md:153-161 |
| P0-5 | 备份不覆盖 c0f9feb/d37bfad，异地缺失 | S3 | P0 | B8/C4 | mirror/bundle 实测 |
| P0-6 | GUI 工作树半提交：暂存删除 gateway/P31 测试，且有未提交 writer 修复 | S4（危险态） | P0 | 新增 | git status 41 项 |
| P1-1 | D04：planner 把整函数声明为 abi_block；verifier 不解析内存间接调用/尾跳 | S3（已分类，未修） | P1 | A12/AUDIT-02 | phase8d-heap-abi-analysis.md:15,89-107 |
| P1-2 | P36 CaveABI 出口语义只覆盖 ret | S3 | P1 | A12/G-01 | claims explicitly_unimplemented |
| P1-3 | P37 授权仍是 STATIC_REFERENCE_ONLY，无签名授权记录 | S4 | P1 | A12/G-02 | p21 profile |
| P1-4 | Verifier 2.0 语义保持 + false-reject/规则变异套件缺失 | S3（Acceptance 2.0 只部分覆盖） | P1 | A13/A14/AUDIT-04/05 | acceptance-2 report |
| P1-5 | UAF/整数/heap-canary/字符串 修复矩阵 0 覆盖 | S4（多数 not_run） | P1 | A5/A15 | non_goals/claims |
| P1-6 | P35 60-run、P32/P33 live、5–6 模型矩阵未完成 | S4 | P1 | A18/A19 | p31-p34:53,71-72 |
| P1-7 | 跨函数/别名/全局/结构体容量：M2 只读原型未接入 | S3 | P1 | A4/A6 | m2-analysis-api.md（DRAFT） |
| P1-8 | 发现机制 7 缺 2（sample_based、knowledge_source_scan），mutation/metamorphic 仅部分 | S3 | P1 | A20/AUDIT-03 | discovery README |
| P1-9 | P40 GDB N3–N6 + AFL++ 未运行（guest 无 gdb/afl） | S4 | P1 | A15/A16 | guest 实测 |
| P1-10 | GUI 真实 LLM 联调缺失：无 provider UI、无 live e2e | S3 | P1 | 新增（A2/A3 产品面） | templates 无 openrouter/ollama |
| P1-11 | promotion/reflection 未闭环：gate 有，人工审批/实验执行无 | S3 | P1 | A26/A27/AUDIT-06/07 | promotion README / reflection claims |
| P2-1 | 文档/门户口径漂移（2301 vs 2411、240 vs 297、0 open vs 8 open） | S3 | P2 | B10 | results-portal/data/overview.json |
| P2-2 | CI 分层与默认分支：self-hosted inert、tip 无 CI、claims 指针过期 | S3 | P2 | B1/B2/B4/B5 | ci.yml:353-366 |
| P2-3 | refs 仍 198 行 + 两套 P31 + 3 个 post-final/* 旧分支 | S3 | P2 | B6/C4 | ls-remote |
| P2-4 | 备份文档与实物不一致（SHA/refs 数） | S3 | P2 | B8 | backup doc §1 |
| P2-5 | hidden 隔离仅操作层（同 UID 可读） | S3（审计已做） | P2 | A21/AUDIT-08 | isolation README |
| P2-6 | 反思 101 条/12 决策，无执行器 | S4 | P2 | A27/AUDIT-06 | reflection claims |
| P2-7 | 平台/格式边界与 readelf 依赖未解 | S4 | P2 | A7/A24/A25 | LIMITATIONS §9 |
| P2-8 | 全量测试 1015s；无性能基线 | S3 | P2 | A22/B12 | junit |
| P2-9 | 工作区残留（.tmp/handoff archive/capacity）+ portal 未入库 | S3 | P2 | B8/C2 | ls / git check-ignore |
| P2-10 | gateway 生产化缺口：无 routing/queue/限流/成本；preflight 默认 model=mock-model | S3 | P2 | 新增 | run_model_preflight.py:25-26 |

---

## 4. P0 详述（交付/签核阻塞）

### P0-1 凭据轮换未执行（安全，owner 阻塞）

- **问题**：4 个槽位（K1 SiliconFlow CN、K2 SiliconFlow Intl、K3 DashScope、K4 DeepSeek）视为已泄露；K4 的 GUI `var/assistant.key` 审计时曾存在 55B。仓库/文档/脚本扫描干净（12 条均为测试假 key），泄漏面是会话历史+本机 key store。
- **证据**：`WT8D/docs/operations/security-key-rotation-2026-11-17.md` §1 K1–K4；`WT8D/docs/operations/handoff-readiness-2026-11-17.md:24`（item 9 PARTIAL）。
- **影响**：任何"交付签核"都不成立；旧 key 可被用于消耗账户或复现实验数据污染。
- **根因**：key 曾以明文贴入会话；GUI 只支持单一 DeepSeek key store，无 Keychain 集成；agent 无 provider 管理权限。
- **方案**：
  1. owner 在 4 个控制台先吊销再新建（runbook §2 已给逐步命令与验证方式）；
  2. GUI key store 迁移到 macOS Keychain（`security add-generic-password`），`assistant_key_store.py` 增加 keychain 后端并保持文件后端兼容；
  3. 在 `tools/handoff/scan-secrets.sh` 与 CI 增加 pre-commit/secret-scan（`WT8D/docs/operations/ci-security-proposal-2026-11-17.md` 已有提案）；
  4. 对 `handoff/archive`（约 1.5GB）做一次离线文本扫描（当前 not_run），只保留 masked 结果。
- **验收**：4 个旧 key 全部 401/失效；新 key 仅存在于控制台/本机 0600 存储；`git grep -nE 'sk-[A-Za-z0-9]{20,}'` 在跟踪文件中 0 命中；GUI 重启后 assistant 可调用且 key 不出现在页面/日志。
- **依赖/工作量**：owner 控制台操作 1–2h；Keychain 集成 0.5–1d；archive 扫描 0.5d。

### P0-2 单一交付 SHA 缺失（final 与 d37 分叉）

- **问题**：`final/consolidated-2026-11-16`=c0f9feb 只含 P31 offline + M1–M4；Phase-8D 全部在 d37bfad/a1d7150。两线互不包含（final 独有 2，d37 独有 7）。用户要求的"新分支"没有明确基线。
- **证据**：实测 `git rev-list --count final/consolidated-2026-11-16..d37bfad`=7、反向=2；`git diff a9db731 e01fc9e -- app/services/llm_gateway app/services/assistant_llm.py scripts/run_model_preflight.py scripts/run_stability_matrix.py tests/test_llm_gateway_*.py tests/test_stability_matrix_hardening.py` 为空（P31 代码同源）。
- **影响**：任何 push/删除 refs 都可能让"最终成果"落在不含 Phase-8D 的树，或让 Phase-8D 缺 P31 文档；CI/备份/门户各自指向不同 SHA。
- **根因**：11-16 整合后又在 workbench 上做了 P31 + Phase-8D，final 未 fast-forward（c0f9feb 不是 d37bfad 祖先，push 被拒，见 `session:879cc62f#seq=19978-19981`）。
- **方案**（Lead 执行，顺序不可乱）：
  1. 以 d37bfad 为基线建 `final/consolidated-2026-11-17`（它已含 P31 代码、M1–M4、Phase-8D、13/13 gate；`worktree-p31-ci` 是干净的 d37bfad checkout，可直接作工作树）；
  2. 只从 c0f9feb 取"两棵树各自再生成"的 5 个文件中的**文档差异**（`docs/acceptance/p31-p34-2026-11-16.md` 的 full-suite 行），artifact 不 cherry-pick；
  3. 在新分支上重新生成 `artifacts/provider-coverage-2026-11-14/` 与 junit（`scripts/build_provider_coverage.py --write`；junit 由全量 pytest 产出），使 source_digest 与合并后树一致；
  4. 打 tag `final-2026-11-17` + evidence 分支，记录 gate JSON 的 frozen/release SHA。
- **验收**：新分支 `git merge-base --is-ancestor d37bfad HEAD` 与 `--is-ancestor 4a7b235 HEAD` 均 0；全量 pytest 2411/0/9；release gate 13/13；provider-coverage `--check` 通过；只有 1 个交付 SHA 被写进 README/门户/备份。
- **依赖/工作量**：0.5–1d（含重跑 gate 约 21 分钟 + 全量测试约 17 分钟）。

### P0-3 hidden 泛化 0/6：卡在 detection，且归因字段语义需修正

- **问题**：6 个 runtime hidden 样本全部 `detection_missed`，0 findings、0 candidate；parse 与 target-scope 已观察到，后续阶段 not_reached。
- **证据**：`WT8D/docs/operations/phase8d-hidden-stage-attribution.md:47-58`；`WT8D/artifacts/phase8d-hidden-attribution-2026-11-17/aggregate.json`。
- **影响**：这是当前最硬的边界——"公开 fixture 能修 ≠ hidden 能修"；任何泛化/晋级声明被此阻断（promotion gate 已因此拒绝 generalized）。
- **根因（分层，含一条需修正的叙述）**：
  1. **真实根因待证**：hidden 为 Zig 变体/不同优化/可能 stripped；D07 已实测 stripped 变体 `target could not be resolved to a unique function with a determinable end address`（2/4 变体 unsupported），与 hidden 的 detection 失败高度同源（假设，需 private 阶段计数验证）。
  2. **叙述错误**：D05 文档称引擎"claimed detected=true/repairable=true"却 0 findings；实际 `universal.detected`=容器格式识别、`repairable`=矩阵单元存在（`WT8D/app/services/binary_pipeline.py:286-287`），真实检测是 `bool(findings)`（`WT8D/app/services/benchmark_runner.py:846,850`）。0 findings 的事实不变，但"引擎自相矛盾"的结论不成立。
- **方案**：
  1. 修字段语义：把 `universal.detected/repairable` 改名为 `format_detected/matrix_supported`（保留旧键一个版本做兼容），新增 `finding_count`；更新 D05 文档与 `tests/test_phase8d_hidden_attribution.py`，断言"detected 不等于有 finding"。
  2. 先在公开集复现 hidden 失败：把 D07 的 4 个编译器变体扩到 8 个（-O0/-O2/-Os × stripped/not），要求 detector 在每个变体上给出 sink 或明确 reason；当前 2 个 stripped 变体就是最小复现。
  3. 修 stripped 目标解析（P1-7 的 callgraph 前置）：线性 sweep + 符号 size + 函数边界投票，输出"唯一函数+可定 end"；失败必须 `function_boundary_unknown` 而非静默 0 findings。
  4. 扩检测模板：识别内联/无 PLT 的拷贝（`rep movs`、向量 mov 循环、`__memcpy_chk`），每条模板配正/负 fixture；负例必须保持 0 findings。
  5. 私有阶段计数（detection/root_cause/localization/strategy/candidate）随 hidden lane 输出，公开只发 counts（沿用 D05 的隐私校验器）。
- **验收**：hidden runtime detection ≥1（目标 6/6 有明确 stage 结论，≥1 candidate）；public 2/24 不下降；false_verified 仍 0；`run_phase8d_hidden_attribution.py --check` 通过；公开产物无 per-sample 字段。
- **依赖/工作量**：3–6 周（2 人），依赖 P1-7 的 callgraph 最小版；先做 (1)(2) 可在 2–3 天内给出"是否同源"的结论。

### P0-4 非 loop 剩余 3 例仍 0；CWE-121/134 只有确定性替身

- **问题**：非 loop 3/6（单模型 flash；v4-pro 0/3）自 a8934fe 后无新增；CWE-121 public、UAF-noinput、heap-canary 仍 0；M1 的 CWE-121/134 成功均为 reference/scripted stand-in，`no live model call`。
- **证据**：`WT8D/docs/operations/m1-2026-11-16.md:153-161`（可声称/不可声称）；`WT8D/artifacts/stability-2026-11-16/README.md`（cwe121 0/6）；claims `explicitly_unimplemented` 仍写 "non-loop AI verified 0/6"（与 3/6 口径冲突，见 P2-1）。
- **影响**：P38/P39 的验收标准（AI 候选 + 精确行为契约）未满足；对外只能称"协议/管道验证"。
- **根因**：leaf-only 限制被 M1 的受控调用模板部分打破，但**没有用 live 模型验证模型能否使用这些模板**；CWE-134 的 live plan 仍可能 PLAN_INVALID；UAF/heap-canary 缺检测与生命周期分析，不属于"再跑一次模型"能解决。
- **方案**：
  1. CWE-121 live 复跑：用 M1 的 `failure_behavior` + controlled_calls 提示，跑 6 次（同一 profile，记录 model identity），验收 ≥1 次独立 verified 且 stdout/stderr/exit 精确匹配；0/6 则如实发布负结果并关闭 P38。
  2. CWE-134 live 复跑：1 个 plan + PoC，验收 plan_valid 且 `%s` 行为正确；否则把"格式串 AI 规划"降级为 non_goal 并注明。
  3. UAF/heap-canary 不在本项硬推：转入 P1-5（先检测/分析，后修复）。
  4. 成本闸门：先 `run_model_preflight` + 预算上限（如 ≤120 次调用），失败即停，不重试 key。
- **验收**：新增 `artifacts/live-cwe121-134-2026-11-1x/`（manifest 含 requested/served model、identity_ok、独立验证状态）；报告明确"AI 3/6 → 3/6 或 4/6"。
- **依赖/工作量**：需 owner 授权 key 与预算；执行 0.5–1d，分析 0.5d。

### P0-5 备份不覆盖当前交付链，异地副本缺失

- **问题**：mirror（117M/203 refs）的 final 分支=f1bb1f4，不含 c0f9feb；`d37bfad` 对象不存在；bundle 的 final ref 也是 f1bb1f4；文档写的 bundle SHA256=4129db… 与实际 89a649… 不符；异地副本仍 `blocked_by=user:offsite_path`。
- **证据**：实测 `git -C backup/binary-repair-mirror-2026-11-16.git cat-file -t d37bfad`→fatal、`rev-parse refs/heads/final/...`=f1bb1f4；`shasum -a256 backup/local-refs-2026-11-16.bundle`=89a649…；`WT8D/docs/operations/backup-2026-11-17.md` §1。
- **影响**：一旦按用户要求删除会话 refs 或强推分支，P31/Phase-8D 的提交对象在本地镜像里没有冗余；恢复演练会恢复到 11-16 中午。
- **根因**：备份在 11-16 12:20 冻结，之后又产生 8+ 提交与 6 个新 ref；M4 已发现"mirror/bundle predate final branch"，但只写了 runbook。
- **方案**：
  1. 在 P0-2 的新分支定稿后重建：`git clone --mirror` 到 `backup/binary-repair-mirror-2026-11-17.git`；`git bundle create backup/local-refs-2026-11-17.bundle --all`；`git ls-remote origin > backup/remote-refs-2026-11-17.txt`；
  2. 生成 `SHA256SUMS`（含 mirror 目录用 `git fsck` 校验、bundle 用 `git bundle verify`）；
  3. 立即做一次恢复演练到空目录，断言新分支/`d37bfad`/`4a7b235` 三个对象可检出；
  4. owner 提供异地路径后 `tools/handoff/offsite-backup.sh <path>` + `verify-offsite-backup.sh`。
- **验收**：`git -C mirror cat-file -t <新分支SHA>` 成功；bundle verify "complete history"；异地 SHA256SUMS 29+ 文件全 OK；恢复出的树文件数与源一致。
- **依赖/工作量**：1–2h + 异地路径（user）。

### P0-6 交付工作树半提交/破坏态 + 未提交的 writer 修复（本次新发现）

- **问题**：`GUI` 工作树 41 项改动：10 个 `llm_gateway` 文件 + 3 个 P31 测试 + `scripts/run_model_preflight.py` + P31 文档被**暂存删除**（磁盘上只剩 credentials/errors/usage，`import app.services.llm_gateway` 变成 namespace package，`create_gateway` 不可导入）；同时有**任何分支都没有**的未提交改动：
  - `app/services/code_cave.py`（+76/−36）：修复 phdr 槽位被写进 `.rodata` 的 2026-11-16 回归（`--list` 丢 `format_case` 行/分隔线，gate 仍通过）；
  - `app/services/binary_pipeline.py`（+138）：`suggest_repair_targets()` 只读建议；
  - `app/static/js/agent.js`（+140）与 `agent.html`：问答/向导与缓存版本号。
- **证据**：`git -C GUI status --short`（41 行）；`git -C GUI diff d37bfad -- app/services/code_cave.py` 等；`git -C GUI diff --cached --stat`（30 文件 −2681 行）；实测 `cd GUI && .venv/bin/python -c "import app.services.llm_gateway as g; print(g.__file__)"`→`None`。
- **影响**：① 若 Lead 在此工作树直接 `git commit -am`，会把 gateway/P31 测试删掉，交付树不可运行；② 若忽略未提交改动，就会丢掉**能避免静默破坏 `.rodata` 的 writer 修复**——这正是一类 gate 未拦住的 false-accept，直接动摇 `false_verified=0` 的置信度；③ 后续任何依赖该工作树的测试/演示都可能结果失真。
- **根因**：P31 实现在 `worktree-p31-ci` 重做后，旧工作树的"替换式"改动只做了一半（暂存删除旧文件、未 add 新文件）；writer 修复与 GUI 改动没有落到任何分支就切走了。
- **方案**：
  1. **不要在 GUI 工作树提交**；先保全现场：`git -C GUI diff > review/2026-11-17/artifacts/gui-wip-unstaged.patch`、`git -C GUI diff --cached > .../gui-wip-staged.patch`、`git -C GUI status > .../gui-wip-status.txt`（由 Lead 执行，本报告只读）；
  2. 从 d37bfad 新建干净 worktree `wt-final-2026-11-17`；
  3. 只把 3 个"独有改动"按补丁重放：`git apply` 后逐个审阅；staged 删除**不重放**（新分支的 gateway 来自 d37bfad，完整）；
  4. 为 code_cave 修复加回归测试：构造 phdr 表后紧邻 `.rodata` 的 ELF，patch 后断言 `.rodata` 字节不变、`--list` 输出含 `format_case` 与分隔线；
  5. 全量 pytest + release gate 通过后，把该修复单独成一个提交（信息写清回归与影响面）。
- **验收**：干净 worktree `git status` 空；2411 tests 0 fail；新回归测试在旧 writer 上失败、新 writer 上通过；gateway 可 `from app.services.llm_gateway import create_gateway`；`--list` 输出完整。
- **依赖/工作量**：0.5–1d；风险：补丁可能依赖 GUI 树的其他未提交改动，需要逐块核对。

---

## 5. P1 详述（能力/验证缺口）

### P1-1 D04 heap-malloc ABI 根因闭环（AUDIT-8D-02）

- **问题**：候选被独立验证器以 `branch_target_unknown / call_target_not_allowed / no_ret` 拒绝；Phase-8D 已分类为 `generator_plan_incorrect`（主）+`abi_proof_insufficient`（主）+`verifier_rule_incorrect`（贡献），但未修规则也未修 plan。
- **证据**：`WT8D/docs/operations/phase8d-heap-abi-analysis.md:15,89-107`；`WT8D/artifacts/phase8d-heap-malloc-abi-2026-11-17/abi-analysis.json`。
- **影响**：deterministic claim 被撤回后无法恢复；同类"函数块本身合法但含间接调用/尾跳"的补丁会持续被误拒或（若放宽）误收。
- **根因**：plan 把整个函数声明为 `abi_blocks[0]` 而非注入 cave；verifier 不解析 `call [rip+disp]`/`jmp [rip+disp]` 的目标，也不接受以尾跳结束的块（`no_ret`）。
- **方案**：
  1. plan 侧：`app/services/binary_pipeline.py:1077 _derive_abi_blocks()`/`:1331` 改为优先声明注入 cave（`injected_va` + 长度 + 指令边界），函数块只作为 scope 证据；
  2. verifier 侧：`app/services/independent_verifier.py:1023-1045` + `verification_semantics.derive_abi_blocks` 增加"块内间接调用/尾跳解析"：用 relocation/import 表解析 `call/jmp [rip+disp]`，命中允许导入（malloc/puts/free）则记为 import call；尾跳视为 terminal exit（等价 `noreturn`），不再要求 `ret`；
  3. 解析失败仍 fail-closed（保持 `call_target_not_allowed`），并新增 1 个不可解析负例；
  4. 重跑 heap-malloc benchmark + acceptance 2.0，保持 `false_verified=0`。
- **验收**：heap-malloc 要么 9/9 verified（plan 修好），要么仍 rejected 但分类/证据完整且**规则未放宽**；ABI 正/负例测试各 ≥2；benchmark repeats 2 次一致。
- **依赖/工作量**：1–2 周（与 P1-2 共用 ABI 基础设施）。

### P1-2 P36 CaveABIBlock 完整出口语义

- **问题**：只覆盖 `ret` 结尾 cave；`tail_jump/continuation_jump/noreturn` 无独立结构与验证；未知出口可能被当作通过。
- **证据**：claims `explicitly_unimplemented`；`WT8D/docs/acceptance/p16-r3-2026-11-16.md`（7/10 的边界）。
- **影响**：跨函数跳转/尾调用类补丁无法被证明；P16-R3 的 7/10 不能外推。
- **方案**：新增 `app/services/cave_abi_contract.py`：出口分类器（指令边界→目标解析→CFG 边）+ 每类出口的允许条件；`continuation_jump` 必须证明目标在 scope 内且栈平衡；`noreturn` 必须证明不会返回（导入 noreturn 或无限循环有界证明）；每类 2 正 1 负测试（x86-64 先行，i386/arm64 后续）。
- **验收**：4 类出口各有独立测试；非法/未知出口 fail-closed；P16-R3 7/10 不下降；新增 1 个"未知出口被拒绝"的负例证据。
- **依赖/工作量**：2–3 周（x86-64 1.5 周）。

### P1-3 P37 真实 Authorization Record

- **问题**：`authorization_profile=STATIC_REFERENCE_ONLY`，`authorization_ref` 是静态字符串，不绑定原始 ELF/plan hash/修改范围/old-new bytes。
- **证据**：claims `autonomy_foundation`/P21 profile；`docs/acceptance/p21-p24-2026-11-16.md`。
- **影响**：P16-R3 的"严格验证"仍缺授权维度；无法证明补丁获得策略许可。
- **方案**：设计 Ed25519 签名记录：`{policy_id, issuer, issued_at, expires_at, binary_sha256, plan_sha256, actions:[{va, old_sha256, new_sha256, length}], scope:[start,end], signature}`；验证器用固定公钥验签 + 时效 + 逐字节绑定；profile 增加 `POLICY_SIGNED`；测试伪造/过期/越权/地址越界 4 类拒绝。
- **验收**：4 类负例全拒；1 个正例通过并与 plan/ELF 哈希绑定；`authorization_profile` 可从 STATIC 切到 POLICY_SIGNED 且 gate 不降。
- **依赖/工作量**：2 周。

### P1-4 Verifier 2.0：语义保持 + false-reject/规则变异套件（AUDIT-04/05）

- **问题**：Acceptance 2.0 只有 18 案、14 变异，且 3 条 false-reject 缺口是"预期 not_run/inconclusive/unsupported"；没有系统性"合法修复必须被接受"的夹具类，也没有对阈值/scope/evidence 规则的变异测试；"内存安全但行为改变"的补丁仍可能通过。
- **证据**：`WT8D/artifacts/phase8d-acceptance-2-2026-11-17/report.json#false_reject_gaps`；`WT8D/docs/operations/phase8d-acceptance-2.md`。
- **影响**：precision=1.0 可能是"全拒也成立"的假象；AUDIT-04/05 仍是 high open。
- **方案**：
  1. 为 AM01–AM28 每类构造 ≥1 个独立评审的"合法修复"夹具，要求模型必须 accept；新增 `false_reject_count/rate` 指标，0/0 视为无效；
  2. 规则变异：在 test-only 副本中削弱阈值/scope/required-evidence，要求审计检出 100%；记录 survival count；生产模型只读；
  3. 行为差分：stdout/stderr/exit/errno/fd offset/文件副作用 6 维，至少 1 个"内存安全但 stdout 改变"的负例被 reject；
  4. 回归引擎：候选自动跑既有 regression + 新生成的等价类输入，失败→rejected。
- **验收**：false_reject_rate 有非零分母且 ≤ 约定阈值；变异检出 14+/14；≥1 行为改变负例被拒；false_accept 仍 0。
- **依赖/工作量**：2–3 周。

### P1-5 UAF/整数/heap-canary/字符串 修复矩阵（A5/A15）

- **问题**：确定性模板对 UAF/整数/循环/sprintf 基本 analysis-only；UAF-noinput、heap-canary 在 AI benchmark 中 0；没有每类 ≥2 fixture 的矩阵。
- **证据**：claims `explicitly_unimplemented`；`WT8D/docs/acceptance/LIMITATIONS.md`（§ non-goals）；36-run cwe121 0/6。
- **影响**：跨 CWE 声明不成立；hidden 里的同类样本也无从修复。
- **方案**：每类先做**检测+定位**（复用 P1-7 的 callgraph/数据流）：UAF 做 malloc/free 配对与生命周期状态机；整数做 range/溢出/符号；heap-canary 做堆容量与哨兵；字符串做格式串/边界。每类 ≥2 fixture（PoC+regression+reference fix），修复由确定性模板或 AI 候选消费；每类先达到"检测+定位"再谈修复。
- **验收**：每类 ≥1 独立 verified，或明确 not_run + 证据；不得用 analysis-only 冒充修复。
- **依赖/工作量**：4–6 周（与 P1-7 并行）。

### P1-6 P35 60-run、P32/P33 live、5–6 模型矩阵

- **问题**：60-run 未执行（唯一正式数据 36 次 19/36）；OpenRouter/Ollama live NOT_RUN；Keychain/GitHub Secret NOT_RUN；provider 矩阵 4 模型/2 provider，intl 402，GLM 超时，DashScope 无 key。
- **证据**：`WT8D/docs/acceptance/p31-p34-2026-11-16.md:6,53,71-72`；实测 preflight（mock ok / openrouter BLOCKED exit 2）。
- **影响**：稳定性结论只有 52.8%（36 次）且集中在 loop；"多模型可复现"不成立。
- **方案**：
  1. P32 live：OpenRouter 1 次 identity probe（`--model` 显式、`allow_fallbacks=false`）+ Ollama 本地 `/api/chat` 1 次；记录 requested/served/identity_ok；
  2. P33：Keychain 读取、GitHub Actions Secret 注入各 1 次真实验证；preflight 增加 `--strict`（BLOCKED 非 0 已具备）与按 provider 的默认 model；
  3. P35：2 模型 × 10 case × 3 重复 = 60，checkpoint/断点续跑、独立验证器定状态、expected/started/completed/eligible 四计数、Wilson CI；预算上限与 canary 先跑；
  4. 5–6 模型：通过 OpenRouter 增 1–2 个模型（exact identity），仍不足则 `not_satisfied` + 证据。
- **验收**：60/60 有记录、无静默丢弃；每候选独立验证；统计报告（含失败分类）；live 调用各 1 条证据；模型矩阵达到 5 模型或明确 not_satisfied。
- **依赖/工作量**：1–2 周 + API 预算（owner）。

### P1-7 跨函数/别名/全局/结构体容量 + M2 接入

- **问题**：M2 只读原型（CFG/直接 callgraph/跨函数容量/may-alias）已交付，但明确"not consumed by any gate/planner"，且 runtime PoC not_run、DWARF 未实现、stripped 发现有限。
- **证据**：`WT8D/docs/operations/m2-analysis-api.md`（DRAFT 声明）；`WT8D/artifacts/m2-analysis-2026-11-16/`。
- **影响**：真实漏洞多为跨函数/结构体；当前引擎在同函数 fixture 上 verified、跨函数仅 analysis_only。
- **方案**：以 feature flag 把 M2 结果注入 planner packet（capacity/alias/scope 三字段），先只做"建议"不改 gate；补 DWARF（pyelftools）对象尺寸；stripped 目标解析（与 P0-3 共用）；在 guest 上为 1 个跨函数 fixture 跑 qemu PoC；用 2 个负例证明错误别名被拒。
- **验收**：跨函数 fixture 上"当前引擎失败/M2 定位成功"；planner 使用 M2 后候选独立 verified ≥1；alias 负例 fail-closed。
- **依赖/工作量**：3–4 周。

### P1-8 发现机制补全（AUDIT-8D-03）

- **问题**：历史 7 机制只跑 3；Phase-8D 增加 mutation+metamorphic（4 变体、11 变异、2 差异、2 stripped 不支持），`sample_based` 仍 not_run，`knowledge_source_scan` 仅 CWE 5.0 目录扫描（984/232，support_claimed=false）。
- **证据**：`WT8D/artifacts/phase8d-discovery-2026-11-17/README.md`；`WT8D/artifacts/phase8d-external-knowledge-2026-11-17/README.md`；`WT8D/artifacts/phase8d-discovery-registry-2026-11-17/registry.json`。
- **影响**：能力空间只被部分搜索；AUDIT-03 仍 open。
- **方案**：① mutation/metamorphic 扩到 8 变体（含 stripped），每个变体给 engine disposition；② 建立本地许可语料（≥20 样本，哈希+许可+污染审计）驱动 sample_based；③ knowledge_source_scan 增加"本地语料×CWE 候选"匹配与 not_run 原因；④ 7 机制统一 registry（run/not_run+reason），不自动晋级。
- **验收**：7/7 机制有状态与原因；新增 ≥1 个可复现 gap 且有证据；历史 registry 字节不变（lineage by reference）。
- **依赖/工作量**：2–3 周（语料获取另计）。

### P1-9 P40 GDB N3–N6 + AFL++

- **问题**：guest 实测 `gdb`/`afl-fuzz` 均 MISSING；N3–N6（寄存器/栈/控制流/RepairSpec invariant）与 AFL campaign 全 not_run；errno 只有进程退出级 LD_PRELOAD。
- **证据**：实测 `limactl shell binaryrepair -- command -v gdb afl-fuzz`；claims `explicitly_unimplemented`（"register/stack native trace (gdb unavailable)"、"AFL/fuzzing campaign"）。
- **影响**：动态证据只能到"进程退出码/stdout"层；无法证明函数返回瞬间的寄存器/栈/errno；无真实 fuzz 发现。
- **方案**：① guest `apt-get install -y gdb afl++`（clang/gcc 已在）；② x86-64 样本用 `qemu-x86_64 -g <port>` + gdb remote 调试，绕开 ptrace/qemu-user 限制；③ 实现 N3–N6 探针（函数返回断点、寄存器快照、栈 canary、CFG 边）；④ AFL++ 以确定性种子跑 1 个 fixture，crash 去重最小化并接入 regression；⑤ 全部记录 not_run 原因，缺一不声称。
- **验收**：≥1 条真实寄存器/栈 trace + ≥1 个 AFL crash 可复现并进入 verifier；否则保持 not_run 并写明工具缺失。
- **依赖/工作量**：1–2 周（含镜像变更）。

### P1-10 GUI 真实 LLM 联调

- **问题**：GUI 模板/JS 中无 openrouter/ollama/provider 选择（`grep -rln` 为空）；assistant 服务端虽有 gateway profile，但 GUI 只支持 DeepSeek key store；没有 live e2e；演示后端默认 mock。
- **证据**：`WT8D/app/templates/**`、`app/static/js/**` 无 provider 关键字；`results-portal` 概述"默认演示后端不执行真实修复…真实模型需服务端配置 key"。
- **影响**：P31 的"统一入口"在产品面未验证；用户无法在 GUI 选模型/看 identity/cost。
- **方案**：设置页增加 provider/model/base_url/identity 策略；服务端 `/api/assistant/status` 返回 requested/served/identity_ok；key 只走服务端 Keychain/环境；加 1 条 mock e2e + 1 条 live smoke（OpenRouter 或 Ollama）；UI 明示"演示/真实"。
- **验收**：GUI 可切换 mock/openrouter/ollama；修复任务记录 model identity；live smoke 证据 1 条；页面无 key。
- **依赖/工作量**：1 周（live 依赖 P1-6 的 key）。

### P1-11 promotion/reflection 闭环（AUDIT-06/07）

- **问题**：promotion gate 已实现并拒绝 4/4（正确），但缺人工审批/签名与合法转移服务化；reflection 101 条/12 决策无执行器，`verified=true` 恒 0。
- **证据**：`WT8D/artifacts/phase8d-promotion-2026-11-17/README.md`；claims `autonomy_foundation.reflection`。
- **影响**：能力状态仍靠人工维护；"发现→实验→晋级"未闭环，AUDIT-06/07 仍 open（critical）。
- **方案**：① promotion gate 增加 `approval`（独立人签名 + 时间 + 证据 hash）与合法转移表（已有）落成服务/CLI；② 选 1 个带 falsification 条件的 reflection 实验，在沙箱执行并持久化 input/output/exit/oracle；③ 结果只作为分析输入，不自动晋级；④ 发布 denied/allowed 决策。
- **验收**：1 个实验真实执行（非计划）；promotion 决策含人工审批字段；仍 0 自动晋级；`evaluate_promotion.py --check` 通过。
- **依赖/工作量**：1–2 周。

---

## 6. P2 详述（治理/债务，压缩表）

| ID | 问题与证据 | 解决方案 | 验收 |
|---|---|---|---|
| P2-1 | 口径漂移：门户 `results-portal/data/overview.json` 写 tests=2301、universe=240、gaps="0 open"、branch=final/consolidated-2026-11-16/commit=f1bb1f4；实际 2411/297/8 open（Phase-8D registry）/c0f9feb。claims `explicitly_unimplemented` 仍写 non-loop 0/6，`implemented` 仍留历史 CWE-121 "2/2 PoC"声明。 | 门户改为从 claims+registry 读取；"gaps"拆成 Phase-7 audit（0 open）与 Phase-8D audit（8 open）两行；claims 每条加 `as_of`+`scope`；历史 claim 标 historical。 | 门户所有数字可在 claims/registry 找到同值；`grep -n "0/6" LIMITATIONS/claims` 均带 as-of 或已更新；无 "2301/240" 残留 |
| P2-2 | CI：self-hosted Lima job `if: vars.BINARYREPAIR_RELEASE_GATE=='true'`（默认 inert，`ci.yml:353-366`）；final/d37 tip 无 CI；claims `latest_verified_ci`=78edb97/workbench-v3（43900916188）；main=8869b07。 | 用 d37bfad 的本地 13/13 gate 作为"本地冻结证据"，在 claims 增加 `final_release_sha`/`final_release_gate` 两字段；CI 增加 hosted portable job 绑定新分支 tip；owner 切默认分支或 fast-forward main。 | claims 能一眼看到 gated SHA 与 final SHA 两层；`git ls-remote --symref` 指向交付分支；CI 至少 1 次 success 绑定 tip |
| P2-3 | refs：97 heads/101 tag 行；重复 P31 提交（a9db731 vs e01fc9e，关键路径同源）；3 个 `post-final/*`（2026-11-03 旧提交）仍在远端。 | 新分支定稿后删除会话 refs；保留 `post-final/*` 前先确认与主线无关（仅 11-03 旧提交，建议归档 tag 后删）；两套 P31 只保留 d37 线。 | 远端 heads ≤ 25 且无 session/phase8/release-2026-11-1x 残留；被删 ref 全部在 mirror/bundle 中可恢复 |
| P2-4 | 备份文档写 bundle SHA 4129db…/127M，实际 89a649…/124,356,610B；mirror 203 refs 与当前 198 行不一致；文档未标"pre-P31"。 | 重生成 2026-11-17 备份并在文档写"as-of SHA + 生成命令 + 校验命令"；不写死易漂移的 SHA（改由 SHA256SUMS 提供）。 | 文档 SHA 与 `shasum` 一致；`SHA256SUMS` 覆盖 mirror/bundle/refs 清单 |
| P2-5 | hidden 隔离：19 项审计 pass、0700、无泄漏，但同 UID/root 可读，非密码学。 | 保持"operational"表述；如需强隔离用独立账号/加密卷；把 AUDIT-08 的 3 项（root mode/commitment/泄漏扫描）做成每次 release 的只读检查。 | 每次 release 有 isolation.json；文档不改口为"cryptographic" |
| P2-6 | 反思：12 问/101 记录/12 决策，无执行器、无证伪结果。 | 与 P1-11 合并执行 1 个实验；其余保持 proposed 并标 not_run。 | 1 条 executed 记录（input/output/exit/oracle） |
| P2-7 | 平台：32-bit Mach-O/fat/大端/arm32/riscv/mips/ppc 只分析；PE 仅 Unicorn；readelf 外部依赖；whole_image 永不 verified。 | 保持平台限制表；readelf 换 LIEF/llvm-readelf 后端（保留兼容）；每项"contract+measured+negative"才可声明。 | LIMITATIONS 平台表与实测一致；macOS 默认环境跑通 readelf 替代后端 |
| P2-8 | 测试耗时：全量 1015.7s，gate 1250s（含 full pytest 1064s）；无性能基线与分层。 | 分层（unit/integration/e2e）+ 并行非 gate 测试 + 缓存；记录 gate 时间基线。 | gate ≤ 20 分钟；分层命令与耗时写入 docs |
| P2-9 | 残留：`.tmp/`、`handoff/`（archive ~1.5GB）、`capacity-archive-2026-11-14/`、`results-portal/` 未入库（无 .git）；门户是唯一"成果总览"入口。 | 归档到大容量备份后清理本地；`results-portal/` 以 `delivery/portal/` 入新分支（去掉 run/ 与 token）；README 指向。 | 工作区无 >100MB 未归档目录；portal 在仓库内可启动（`--no-workbench`） |
| P2-10 | gateway 生产化：无 routing/queue/限流/成本；`run_model_preflight.py:25-26` 默认 `--model mock-model`，`--provider openrouter` 时会用假模型名。 | 增加 `routing.py`（provider order/fallbacks=false）、有限重试（401/402 不重试，429/5xx 退避）、队列/并发上限、cost=None 显式；preflight 按 provider 设默认模型并拒绝 `mock-model + --live`。 | 401/402/429/5xx/timeout 各有单测；preflight 在 openrouter 下默认模型非 mock；cost 缺失保持 null |

---

## 7. 旧报告第 6 节逐条状态（A/B/C/D，2026-11-17 复核）

> 判定：✅关闭 / 🟡部分 / ⛔未变 / 🕓过时。仅列结论，证据见上文对应条目。

| 旧编号 | 判定 | 现状一句话 | 新编号 |
|---|---|---|---|
| A1 非 loop 3/6 | ⛔ | 无新 live 运行；M1 只加管道 | P0-4 |
| A2 CWE-121 | 🟡 | 确定性 stand-in 独立 verified；AI 仍 0/6 | P0-4 |
| A3 CWE-134 | 🟡 | 字段诊断+scripted `%s` 过 Native gate；live 未跑 | P0-4 |
| A4 跨函数/别名/全局/结构体 | 🟡 | M2 只读原型，未接入 | P1-7 |
| A5 整数/字符串/UAF | ⛔ | 仍 analysis-only/not_run | P1-5 |
| A6 间接调用/路径敏感/并发 | 🟡 | M2 显式 unresolved，路径/并发无 | P1-7 |
| A7 格式/架构 | ⛔ | 平台限制表存在，能力未扩 | P2-7 |
| A8 Planner/Candidate 闭环 | 🟡 | promotion gate 有；planner 状态机仍词汇表 | P1-11 |
| A9 多函数/whole-program | ⛔ | whole_image 永不 verified | P2-7 |
| A10 hidden 0 | ⛔ | 0/6 runtime；新增 D05 归因 | P0-3 |
| A11 AI 增量 | ⛔ | 仍 0 increment | P1-6 |
| A12 CaveABI/Authorization | 🟡 | heap-malloc 已分类；出口/签名授权未做 | P1-1/2/3 |
| A13 Verifier 2.0 | 🟡 | Acceptance 2.0 ≠ 语义保持 | P1-4 |
| A14 Regression Engine | ⛔ | 无独立引擎 | P1-4 |
| A15 Fuzzing | ⛔ | guest 无 afl，not_run | P1-9 |
| A16 N3–N6/errno | ⛔ | guest 无 gdb（实测），not_run | P1-9 |
| A17 副作用等价 | 🟡 | 新发现 rodata 破坏未被 gate 拦住（修复未提交） | P0-6 |
| A18 Provider 矩阵 | ⛔ | 4 模型/2 provider；intl 402 | P1-6 |
| A19 60 次 | ⛔ | 19/36=52.8% | P1-6 |
| A20 外部语料/第二编译器 | 🟡 | CWE 5.0 知识扫描 984/232；cross-compiler 仍 false；guest 有 clang/gcc | P1-8/P2-7 |
| A21 hidden 隔离 | 🟡 | 19 项 pass，非密码学 | P2-5 |
| A22 性能/容量 | ⛔ | 1015s/20MiB 限制未变 | P2-8 |
| A23 v7 F1 fail-open | 🕓 | v7 冻结包不在整合分支 | P2-3 |
| A24 readelf | ⛔ | 仍依赖外部 readelf | P2-7 |
| A25 32-bit/fat/大端/PE | ⛔ | 只分析不改写 | P2-7 |
| A26 授权/晋级治理 | 🟡 | gate 有、审批/服务化无 | P1-11 |
| A27 反思/实验执行器 | 🟡 | 12 问/101 条，无执行 | P2-6 |
| A28 hidden/public 治理 | 🟡 | 隔离审计+污染 clean，轮换未产品化 | P2-5 |
| B1 Lima nightly | 🟡 | 本地 nightly 13/13 真跑；CI job 仍 inert | P2-2 |
| B2 claims CI 口径 | ⛔ | 仍指向 gated code，无 final 字段 | P2-2 |
| B3 CI 环境敏感 | 🟡 | 78edb97 修了 fetch/full history | P2-2 |
| B4 hosted vs 13 项 | ⛔ | 分层未写清 | P2-2 |
| B5 main 陈旧 | ⛔ | 8869b07 | P2-2 |
| B6 refs 膨胀 | 🟡 | 242→198 行，仍有重复/旧分支 | P2-3 |
| B7 看板漂移 | 未核实 | 团队看板状态未在本报告核验 | P2-9 |
| B8 残留物 | ⛔ | .tmp/handoff/capacity 仍在 | P2-9 |
| B9 凭据 | 🟡 | 清单+扫描完成，轮换未执行 | P0-1 |
| B10 文档口径 | 🟡 | LIMITATIONS §17 已加 as-of；claims/portal 仍漂 | P2-1 |
| B11 环境复现 | ⛔ | 版本/镜像未固化 | P2-8 |
| B12 测试耗时 | ⛔ | 1015s | P2-8 |
| C1 成果散落 | 🟡 | 11-16 整合过，11-17 又分叉 | P0-2 |
| C2 总览文档 | 🟡 | 有 166KB 报告但过时 | P2-1 |
| C3 默认分支 | ⛔ | main | P2-2 |
| C4 删除边界 | 🟡 | 已文档化，未执行 | P2-3 |
| D1 key 轮换 | ⛔ | owner | P0-1 |
| D2 默认分支 | ⛔ | owner | P2-2 |
| D3 hidden 保留 | 未核实 | owner 决策 | P2-5 |
| D4 60 次成本 | ⛔ | 预算未定 | P1-6 |
| D5 self-hosted runner | ⛔ | 无 runner | P2-2 |
| D6 非目标复审 | ⛔ | 2027-02-14 未到 | — |
| D7 对外口径 | 🟡 | portal/claims 仍不一致 | P2-1 |

**新增问题（旧报告没有）**：P0-6 工作树破坏态+writer 回归、P1-1 D04 根因、P1-10 GUI 联调、P2-1 门户数字漂移、P2-3 两套 P31、P2-4 备份 SHA 不符、P2-10 gateway 生产化。

## 8. Phase-8D 八个 AUDIT gap 的处置映射

| AUDIT | 严重度 | 现状 | 处置 | 本报告 |
|---|---|---|---|---|
| 8D-01 hidden 零候选无阶段归因 | high | D05 已加私有阶段计数；检测仍未修 | 修字段语义 + stripped 解析 + 检测模板；public 只发 counts | P0-3 |
| 8D-02 heap-malloc ABI 拒绝未分类 | high | 已分类（plan 主因+ABI 证据不足+规则贡献） | 修 plan 的 abi_block + verifier 间接调用/尾跳解析（不放宽） | P1-1 |
| 8D-03 七机制四未跑 | high | mutation/metamorphic 已部分；sample_based 未跑；knowledge_source_scan 仅目录扫描 | 扩到 7/7 状态；本地许可语料 | P1-8 |
| 8D-04 无 false-reject 类 | high | Acceptance 2.0 仅 3 条记录性缺口 | 合法修复夹具 + false_reject_rate | P1-4 |
| 8D-05 无规则变异 | high | 14/14 变异检出（已有基础） | 阈值/scope/evidence 变异套件 | P1-4 |
| 8D-06 反思只计划不执行 | high | 101 条/0 执行 | 执行 1 个带证伪条件的实验 | P2-6/P1-11 |
| 8D-07 无晋级状态机 | **critical** | gate 已实现并 4/4 拒绝；缺人工审批/服务化 | 签名审批 + 合法转移 CLI | P1-11 |
| 8D-08 hidden 隔离非密码学 | **critical** | 19 项审计 pass；同 UID 可读 | 保持 operational；release 前只读审计 | P2-5 |

## 9. 90 天执行路线（依赖顺序）

| 阶段 | 内容 | 出口条件 |
|---|---|---|
| W0（1–2 天） | P0-1 轮换、P0-6 保全现场并重放 3 个补丁、P0-2 定基线、P0-5 重建备份 | 干净树 + 单一 SHA + 可恢复备份 + 旧 key 失效 |
| W0–W1 | P0-4 live CWE-121/134（若 key 到位）；P2-1 口径修正；P2-2 claims final 字段 | 有 live 证据或明确 BLOCKED；门户/claims 无自相矛盾 |
| W1–W3 | P1-6（P32/P33 live + 60-run 启动）；P1-1 plan/verifier ABI 修复 | 60/60 记录；heap-malloc 结论稳定；false_verified=0 |
| W3–W6 | P0-3 detection（字段语义→stripped 解析→模板）+ P1-7 callgraph/M2 接入 | hidden 至少 1 detected/candidate；stripped 变体不再 unsupported |
| W6–W10 | P1-2/P1-3（CaveABI/授权）、P1-4（false-reject/语义保持） | 4 类出口测试；签名授权；false_reject 有分母 |
| W8–W12 | P1-5（UAF/整数/heap-canary）、P1-8（7/7 机制）、P1-9（gdb/AFL）、P1-10（GUI e2e） | 每类 ≥1 verified 或 not_run；7/7 机制；trace/crash 证据；GUI live |
| 持续 | P2-2/3/4/7/8/9/10 | 交付分支 CI 绿、refs 收敛、文档一致 |

**硬闸门（不满足不得宣称完成）**：① `git status` 干净 + 单一交付 SHA；② 2411 tests 0 fail + gate 13/13；③ public 2/24 不降、false_verified=0；④ hidden 只发 counts、无泄漏；⑤ not_run 全部显式；⑥ 旧 key 失效。

## 10. 风险与判断边界

- **不能声称**："通用二进制修复""hidden 泛化成立""CWE-121/134 已被 AI 修复""多模型可复现""CI nightly 通过""0 残留 refs"。
- **可以声称**：有界模板修复（public 2/24）、独立验证零 false_verified、Phase-8D 审计/验收/晋级框架、P31 offline gateway、13/13 本地冻结 gate、备份可恢复（重建后）。
- **最大不确定性**：① hidden 检测失败与 stripped 目标解析是否同源（需 private 阶段数据验证）；② 用户/owner 是否授权 key 预算（决定 P0-4/P1-6 能否从 BLOCKED 转 measured）；③ 新分支是否被设为默认分支（无 token，需 owner）；④ `post-final/*` 旧分支是否可删（本报告未追溯其来源）。
- **未核实**：团队看板 48 任务状态（B7）；v7 交付包是否仍需维护（A23）；handoff archive 全量 secret 扫描；写作时 `review/2026-11-17/` 下只有本文件，01–04 号报告的跨报告去重需 Lead 合并时完成。

## 交接给 Lead（10 条）

1. **先保现场再动 git**：GUI 工作树有 41 项改动，其中 `llm_gateway`/P31 测试/preflight 被暂存删除，磁盘上只剩 3 个文件；另有 3 个"任何分支都没有"的补丁（code_cave +76/−36、binary_pipeline +138、agent.js +140）。不要在该工作树 `commit -am`。证据：`git -C binary-repair-gui status --short`。
2. **最值钱的未提交改动是 `code_cave.py`**：它修的是 phdr 槽位写进 `.rodata`、`--list` 丢行但 gate 仍通过的回归——属于 gate 未覆盖的 false-accept 类。建议单独提交并配回归测试（`.rodata` 字节不变 + `--list` 完整）。
3. **单一交付 SHA 选 d37bfad 线**：它含 P31 代码（与 c0f9feb 的关键路径 diff 为空）、M1–M4、Phase-8D、13/13 gate；final 只多 2 个提交（1 个 P31 提交 + 1 个再生成），不需要 cherry-pick 代码，只需在新树上重新生成 provider-coverage/junit。
4. **备份必须先重建再删 refs**：mirror 的 final=f1bb1f4、`d37bfad` 对象不存在；bundle 实际 SHA 与文档不符。否则删除会话 refs 后无法从本地恢复 Phase-8D。
5. **hidden 0 的结论要改一句**：6/6 `detection_missed` 成立，但"引擎声称 detected=true 却 0 findings"是字段语义误读（`detected`=格式识别）。修正叙述，保留结论。
6. **P31–P40 的真实进度**：P31 offline 完成；P32/P33 live NOT_RUN（实测 openrouter BLOCKED exit 2）；P34 完成 offline；P35–P40 未开始。任何"P31–P40 完成"的表述都不成立。
7. **CWE-121/134 只是替身证据**：M1 的独立 verified 来自 reference/scripted 汇编，没有 live 模型；`3/6` 没有变成 `4/6`。要么花预算跑 live，要么明确写"仅管道验证"。
8. **8 个 AUDIT gap 中 2 个 critical**：AUDIT-07（无人工审批/晋级状态机服务化）、AUDIT-08（隔离非密码学）。前者已有 gate 且 4/4 拒绝，补审批即可；后者保持"operational"措辞。
9. **口径必须统一**：门户写 2301 tests/240 cells/0 open gaps，实际 2411/297/8 open；claims 仍留 "non-loop 0/6" 与历史 CWE-121 "2/2" 声明。Lead 合并文档时以 claims+registry 为准。
10. **不能声称**"hidden 泛化""通用修复""CI nightly 通过""0 残留 refs"；可以声称"有界修复 + 零 false_verified + 可审计证据 + 13/13 本地冻结 gate"。用户要求的新分支名建议 `final/consolidated-2026-11-17`，基线 d37bfad。
