# M1 任务 — 非 loop / CWE-121 / CWE-134 能力攻关（最高优先）

> 本文件是 M1 的完整接手包。读完本文件即可开工；不需要读历史会话。
> 任务来源：组长 2026-11-16 复核决议（总报告 §1.5）——**能力优先于自主化设施；先打 hidden 0/8 与公开 8.3% 对应的真实能力缺口**。

## 0. 一句话目标

把非 loop 修复从 **3/6（单模型）** 推到 **4/6+ 且可复现**：先攻 **CWE-121 Behavior Contract**（门禁/规划/受控调用），再攻 **CWE-134 PLAN_INVALID 字段级诊断**，剩余案例给出 typed 根因。**不降 gate，不特化测试，不伪造 verified。**

## 1. 必读（按顺序，共 10 分钟）

1. `review/STATE.md`（项目当前认知与边界）
2. `项目总体回顾_完成现状_剩余任务与解决方案_2026-11-16.md` 的 **§1.5（组长复核决议）**、§3.6.1、§3.7、§5.3.3、§6.1 A1/A2/A3、§7.2 Phase-10
3. `tools/handoff/README.md`（环境工具；**只允许用这些工具操作环境**）
4. `binary-repair-gui/docs/acceptance/p16-r3-2026-11-16.md`、`p16-r2-2026-11-16.md`、`p16-p20-2026-11-16.md`
5. `binary-repair-gui/docs/acceptance/LIMITATIONS.md`（尤其 §21 容量/heap、AI paths、Phase-8A/8B 段）
6. `binary-repair-gui/docs/status/claims.json`（`non_goals`、`phase8b_verifier_semantics`、`explicitly_unimplemented`）

## 2. 环境与前提（已由 Lead 备好）

- 仓库：`binary-repair-gui/`，分支 `final/consolidated-2026-11-16`，当前 tip 以 `git log -1` 为准（初版 `4322a51`；执行记录 `fb807e2`；时间戳修正 `8d4ba1c`；本交接提交在其后）。
- Python：`binary-repair-gui/.venv/bin/python`（3.11.8，依赖已装）。
- 远程：`git@github.com:chenfanaichifan/binary-repair.git`（已有写权限；但**成员不做 git 写**，Lead 统一提交/推送）。
- **第一步必须执行**：`tools/handoff/check-env.sh`（全部 OK 才继续；FAIL 先报 Lead）。
- 报告工具：`tools/handoff/member-report.sh m1 "标题"`；测试工具：`tools/handoff/run-scope-tests.sh m1`。

## 3. 准确基线（不要沿用旧口径）

| 项 | 准确值 |
|---|---|
| 非 loop（Path A 12-case 矩阵） | 曾 0/6；a8934fe 后 **3/6**：hard-multicall / hard-sprintf / hard-nonconst = AI VERIFIED（**单模型 deepseek-flash**；deepseek-v4-pro 0/3） |
| 剩余非 loop 失败 | **cwe121-unchecked-strcpy**（Behavior Contract 未满足）、**uaf-noinput**、**heap-canary**；P11 中 cwe121 0/6 |
| P16-R3 严格验证 | **7/10 verified**（含 3 个非 loop 硬案例）/ 1 rejected（cwe121）/ 2 artifact missing（cwe787、cwe134） |
| CWE-121 具体失败 | plan/assembly/injection 都成功；candidate `stdout=""`、`exit=0`；PoC 要求 `exit=1 + 精确 stderr` |
| CWE-134 | 一直 `PLAN_INVALID`（v2 一致性校验失败，无字段级诊断） |
| 模型 A/B | 同管线 deepseek-flash 3/3、deepseek-v4-pro 0/3（ABI fatal / plan 空 / 非法 call 0x0） |
| gate 事实 | 独立验证器 9 项检查；AI 不能提升失败 gate；whole_image 永不 verified；resized 无 plan → not_run |

## 4. 你的任务（P0 → P1 → P2，按顺序做）

### P0-1（首增量，90 分钟内）CWE-121 Behavior Contract：数据结构 + 规划约束 + 受控调用

**目标**：让 CWE-121 的修复计划能够表达并满足“拒绝 + 返回码 + 精确 stderr”，且不破坏 leaf-only 安全检查。

实现要点：
1. `app/services/repair_spec.py`：新增/扩展 `failure_behavior`（结构建议：`{exit_code:int|null, stdout:String|null, stderr:String|null, stdout_hex:String|null}`），进入 v2 schema 校验与 `spec_from_plan`；v1 兼容（缺省 null）。
2. `app/services/ai_assembly_repair.py`：为“受控外部调用”增加**最小白名单模板**（不是任意 call）：允许 `exit`/`_exit`/`fputs`/`write` 这类**目标 ELF 实际存在的 PLT/符号**或固定 syscall 模板；必须 fail-closed（不存在/不确定 → 不允许，不改写模型汇编）；保留现有 forbidden construct 校验与 ABI 检查。
3. `scripts/run_hard_benchmark.py`：planner/assembly prompt 注入 PoC 的期望 `stdout/stderr/exit`（现有 PoC manifest 已有字段）；run manifest 记录 `failure_behavior` 与 gate 断言结果。
4. **不改** `unified_verification.py` / `independent_verifier.py` / gate 规则；只让候选有机会满足既有断言。
5. 测试（新增/扩展）：`tests/test_repair_spec.py`、`tests/test_repair_spec_v2.py`、`tests/test_repair_planning.py`；用 deterministic/scripted stand-in，不依赖 live LLM（无 key）。

验收（缺一不可）：
- `tools/handoff/run-scope-tests.sh m1` 全绿（exit 0）；
- 新增单测覆盖：合法 `failure_behavior` 通过、非法/缺字段 fail-closed、无 PLT 的 exit 被拒；
- 一段脚本化证据（`artifacts/m1-2026-11-16/`）：候选的 `stdout/stderr/exit` 与 PoC 期望逐项比对，**如果 gate 仍失败，如实记录为失败/not_verified，不得把辅助脚本结果当 verified**；
- 报告写入 `.tmp/handoff/reports/m1-report-*.md`（用工具生成），含“能声称/不能声称/未运行”。

### P0-2 CWE-134：PLAN_INVALID 字段级诊断 + 最小可行修复策略

1. 定位 `PLAN_INVALID` 的具体失败点（v2 校验的哪个字段/哪条规则），新增**结构化诊断子类型**（例如 `plan_invalid.reason_code`、`field`、`expected`），写测试。
2. 给 CWE-134 一个**最小策略**：固定格式串/长度受限修复（若当前 matrix/策略不支持，先支持“用固定格式替换”并对 PoC/回归做断言）；若判断短期不可行，给出 typed 结论 + `non_goal` 建议，**不要硬造成功**。
3. 验收：`cwe134-format-string` 至少从 `PLAN_INVALID` 变成可解释的 typed 状态（plan_valid 或明确 reason_code），有单测 + 一段证据 JSON。

### P1 非 loop 3/6 → 4/6+（优先借 P0-1 打通 cwe121-public）

- 在 cwe121 上重跑 hard benchmark（**live 模型不可用时用 scripted/stand-in，并在报告里说明这是协议/管线验证、不是 AI 质量结论**）；
- 目标：cwe121 至少 1 个候选达到独立验证器 `verified`（不是只“注入成功”）；
- 对 uaf-noinput / heap-canary 各给 1 页 typed 根因（为什么当前管线失败），写进报告；
- **禁止**：为了“通过”注入固定 `br_fail()` 输出、特化测试 fixture、改 PoC 期望、放宽 ABI/scope 检查。

### P2（时间允许）v4-pro 0/3 的失败诊断

- 对 deepseek-v4-pro 的 ABI fatal / 空 plan / 非法 call 0x0 做**离线诊断**（读历史 artifacts/run 目录），给出每类失败的 typed 分类与修复建议；不改 gate。

## 5. 写范围（严格，不得越界）

允许修改：
```
app/services/repair_spec.py
app/services/ai_assembly_repair.py
app/services/repair/abi.py
scripts/run_hard_benchmark.py
fixtures/hard-cases/            （只新增/最小修改，需要时）
fixtures/poc/                   （只新增/最小修改，需要时）
tests/test_repair_spec.py
tests/test_repair_spec_v2.py
tests/test_repair_planning.py
tests/test_abi_check.py
tests/test_ai_assembly_repair.py
tests/test_ai_assembly_calls.py
tests/test_hard_benchmark.py
artifacts/m1-2026-11-16/        （新目录，证据）
docs/operations/m1-2026-11-16.md（新文件，简版说明）
.tmp/handoff/m1/                 （日志）
```
禁止修改：`unified_verification.py`、`independent_verifier.py`、`binary_pipeline.py`、`repair_matrix.py`、`docs/consolidation/*`、`docs/status/claims.json`、`docs/acceptance/LIMITATIONS.md`、`.github/*`、M2/M3/M4 的目录。

## 6. 红线（违反即任务失败）

1. **不降 gate**：不得修改 required checks / 断言 / 权重来让候选通过；
2. **不特化测试**：不得为了让某个 case 过而硬编码 fixture/路径/地址；
3. **不伪造证据**：`verified` 只能来自独立验证器；辅助脚本输出必须标注“辅助/非 gate”；
4. **不打印/不写入 key**：不触碰 provider key，不复制会话日志到仓库；
5. **不越界**：只改上述写范围；跨成员文件先报 Lead；
6. **不做 git 写**：不 commit/push/checkout/delete；Lead 统一集成；
7. **失败即记录**：无法完成就写 not_run/blocked + 具体原因，不用“完成了”掩盖。

## 7. 交付物（完成后 10 分钟内）

1. 代码改动（写范围内）；
2. `tools/handoff/member-report.sh m1 "CWE-121 failure_behavior 首增量"` 生成报告，填满 6 节；
3. 证据目录 `artifacts/m1-2026-11-16/`（JSON + SHA256SUMS）；
4. 给 Lead 发 `send_message`：10 行摘要（改了什么/证据/测试/未完成/需要决策）。

## 8. 时间盒与升级路径

- 首增量 90 分钟；若 P0-1 无法在 90 分钟形成可测试增量 → 报告“卡点 + 已排除的假设”，不要空转；
- 被环境/工具挡住 → 先问“是不是工具缺口”，是则报 Lead 补工具（不许把工具缺口写成自我约束）；
- 涉及 live 模型/API 成本 → 一律先报 Lead，不自行调用。

## 9. 参考（只读）

- 独立验证器：`app/services/independent_verifier.py`、`scripts/verify_repair.py`、`artifacts/independent-verification-p16r3-2026-11-16/README.md`
- 历史 3/3 非 loop 证据：`artifacts/ai-repair-planning-2026-11-15/README.md`、`artifacts/ai-repair-planning-model-ab-2026-11-15/`
- AI 路径说明：`docs/architecture/ai-binary-repair-paths.md`
- 基准夹具：`fixtures/repair-benchmark/`、`fixtures/hard-cases/{cases.json,multicall_fix.c,sprintf_fix.c,nonconst_fix.c,uaf_fix.c}`
