# 96 · M2 对 M5 工具契约 v1 的核对结论

日期：2026-11-07
审查对象：`d01732f`（`m5/t83-deliverables-2026-11-07`）中的 `docs/interfaces/m5-tool-contracts-v1.md`
审查角色：M2（契约消费方 + evidence 代理实现方）
结论：**三份契约可以作为 agent 的目标接口，但不能当作“现有实现的薄包装”直接实现。**

| 工具 | 判定 | 原因 |
|---|---|---|
| `run_case` | **不满足** | runner 的 CLI、输入、超时、返回结构全部与契约不同；no-input fixture 会直接崩 |
| `read_evidence` | **部分满足** | `obligations`/`evidence` 一致；`gates`/`v3` 依赖尚未进入 canonical 的 M2 端点；`sha256`、`input_mode` 缺失 |
| `apply_candidate` | **不满足** | 实际入口要求 `run_id`/`attempt_id`/`route`/`bundle`，无 `artifact_id`/`dry_run`/幂等，返回也不是 `applied` |

## 1. run_case 逐项对照

契约映射写的是 `routeb/run_manifest_repaired.py` / `run_manifest_compare.py`。这两个脚本**不在仓库里**，只在 `dist/m5-routeb-kit-2026-10-22-v6.zip` 内（CI 引用 `routeb/...` 也是同一份 kit）。

| 契约要求 | 实际（kit 内 `routeb/run_manifest_repaired.py`） | 判定 |
|---|---|---|
| 入参 `binary_path/contract_path/input_mode/argv/stdin_*/timeout_ms` | CLI 只有 `--binary --tests --out`（L31–33） | 不满足 |
| `input_mode: none` 可用 | L37 强制读 `valid.json` + `invalid.json`；no-input fixture 没有 `invalid.json` → `FileNotFoundError` | **P0，会崩** |
| `argv` 可传 | L40 只取 `case["argv"][1]`，忽略调用方 argv | 不满足 |
| `stdin_literal/stdin_artifact` | 完全不支持 stdin | 不满足 |
| `timeout_ms` 由调用方给，硬上限 | L20 硬编码 `timeout=15`，无参数 | 不满足 |
| 返回 `status/exit_code/stdout_sha256/stderr_sha256/stdout_bytes/duration_ms/evidence_path` | 返回 `{binary, binary_sha256, cases[], passed, total, repaired_pass}`，stdout 以 hex 存在 `cases[].got`（L50–54） | 不满足 |
| `timeout` 不算 passed | L20–24 超时返回 `{"timeout": true}`，`ok=False`，不会计入 passed | **满足（唯一一致项）** |
| `idempotency_key`、`409 conflict` | 无 | 不满足 |

结论：`run_case` 需要一层真正的 adapter（按 `input_mode` 分派 runner、把 manifest 用例转成请求、把 `repaired_pass` 映射为 `status`、生成 `evidence_path`、实现幂等），不是“thin wrapper”。**并且 no-input 路径必须走 `run_manifest_compare.py` 或先补 `invalid.json` 的空清单契约。**

## 2. read_evidence 逐项对照

| 契约要求 | 实际 | 判定 |
|---|---|---|
| `obligations: {"A": [], "B": []}` | `_obligation_groups` 一致（`791caa3` L1311） | 满足 |
| `evidence: persisted/not_persisted` | `_evidence_state(rows)` 一致 | 满足 |
| `gates[]` | `3a107ab` 的端点**没有** `gates`（L1184–1201）；`791caa3` 才有（L1309） | **依赖 final head** |
| `v3` | `791caa3` 有 `_v3_summary`（L1261–1290），但契约示例缺 `input_mode`，只有 legacy `invalid_applicable` | 不满足（字段不全） |
| `sha256` | 端点没有该字段 | 不满足 |
| `status: ok/not_found/not_persisted/error` | 实际是 HTTP 404 + `evidence` 字段，无 `status` | 需 wrapper 映射，可接受 |
| 超时/幂等 | 只读，天然幂等 | 满足 |

对 M2 GUI 的直接影响：`invalid` 是否显示 `N/A` 以 `input_mode === "none"` 为准（`agent.js` L829/L833 同源）。契约如果只给 `invalid_applicable`，agent 和 GUI 会各写一套判断。**必须补 `input_mode`，并把 `invalid_applicable` 标为 legacy。**

## 3. apply_candidate 逐项对照

实际入口：`tools/route_bundle_ingest.py`（`3a107ab`，`main` L395–403）。

| 契约要求 | 实际 | 判定 |
|---|---|---|
| 入参 `job_id/artifact_id/candidate_sha256/dry_run/idempotency_key` | 实际 `--data-dir --job-id --run-id --attempt-id --route --bundle --no-trigger` | 不满足 |
| 由 `job_id` 自动定位 candidate | 必须预先存在 `run_id`/`attempt_id`，且给完整 bundle 目录 | 不满足（需先建 run/attempt） |
| `dry_run` | 无 | 不满足 |
| 幂等：同 key 同 hash → `no_op`；不同 → `conflict` | 无幂等键；重复 ingest 行为未定义 | 不满足 |
| 返回 `status: applied/rejected/...` + `bundle_path` + `previous_candidate_sha256` | 返回 `{imported, evidence, analysis_artifact_ids}` | 不满足 |
| `candidate_hash_mismatch` | 实际校验的是 bundle 内 V0 证据与 `manifest["candidate_sha256"]`，不是调用方断言 | 需重定义语义 |

结论：`apply_candidate` 的契约描述的是“应用候选”的上层语义，实际入口是“导入已生成的执行 bundle”。中间缺一层：创建 run/attempt、把 candidate 组装成 bundle、写幂等记录、返回 applied/no_op/conflict。

## 4. 给 M5 的修正清单

**P0（不修则 agent MVP 无法开工）**
1. `run_case` 明确按 `input_mode` 分派：`none` → `run_manifest_compare.py`（或空 `invalid.json` 契约），`argv` → `run_manifest_repaired.py`；写清分派表。
2. `run_case` 删除或降级 `stdin_literal/stdin_artifact/argv` 参数：现有 runner 不支持，写成“v1 不支持，显式 `invalid_request`”，不要留假参数。
3. `run_case` 重写返回映射：`repaired_pass=true → status=passed`；逐 case 的 `ok=false → failed`；`timeout=true → status=timeout`；`evidence_path` 由 adapter 写。
4. `apply_candidate` 补齐“建 run/attempt + 组装 bundle”的前置步骤，或把契约改成 `ingest_bundle`（与现有实现同名同义）。
5. `apply_candidate` 明确 `candidate_sha256` 是“断言值”，必须与 bundle 内 V2/V0 证据一致，否则 `candidate_hash_mismatch`（现在无法实现）。

**P1（契约冻结前补齐）**
6. `read_evidence` 增加 `input_mode`（`none|argv|stdin`），`invalid_applicable` 标 legacy；`v3` 补 `kind/result`。
7. `read_evidence` 删除 `sha256`，或定义为 wrapper 对 `obligations` 规范序列化后的摘要（并写清算法）。
8. 三份契约补：`schema_version` 版本策略、错误码→HTTP/异常映射、审计事件（谁调用、job/attempt、耗时）、调用方权限（禁网、工具白名单）。
9. 补一个“契约样例测试”：用一份真实 evidence JSON 和一份 no-input runner 输出，断言 adapter 映射后的字段与枚举。

## 5. 对 Gate 2 的影响

Gate 2（契约冻结）现在**不具备冻结条件**：
- `run_case` 与 `apply_candidate` 需要新增 adapter 代码，属于 Gate 3 的实现工作量，不是文档修订；
- `read_evidence` 的 `gates/v3` 依赖 final head 合成，而 final head 仍缺 M2 `06eb7ee`；
- 因此建议 Gate 2 拆成 2a（文档修订，M5 本周）和 2b（adapter 实现 + 样例测试，M5/M1）。

## 6. 证据

- kit 内容：`dist/m5-routeb-kit-2026-10-22-v6.zip` → `routeb/run_manifest_repaired.py` L20/L31–33/L37/L40/L54
- canonical evidence：`3a107ab` `app/controller_api.py` L1184–1201
- M2 evidence：`791caa3` `app/controller_api.py` L1261–1290、L1293–1312
- ingest：`3a107ab` `tools/route_bundle_ingest.py` L256、L395–403
- 审查时 `06eb7ee` 已打包为 `outputs/m2-06eb7ee.bundle`（SHA256 `6AEF3C73…6CC6`）；`git push` 被远端拒绝（`Could not read from remote repository`），需人工转交或提供凭据。
