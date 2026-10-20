# 数据库 schema（SQLite，migration 001）

对应技术设计 §6。目标不是"建几张表"，而是把**产品语义**放进约束里，让错误状态写不进去：

- 一个 idempotency key 只能启动一次 run（双击不会重复扣费）；
- run 引用的 contract 必须属于同一个 job（复合外键）；
- `outcome` 只能是 PRD 的六个词；
- `pass` 的 obligation 必须挂证据；
- 成本为 NULL 表示"不可用"，不是 0。

---

## 1. 表关系

```
jobs 1─n contracts (job_id, revision) UNIQUE
  │
  └─1─n runs ──(job_id, contract_id)──▶ contracts(job_id, id)
          │
          └─1─n attempts (run_id, route, sequence) UNIQUE
                  ├─1─n obligations ──evidence_artifact_id──▶ artifacts
                  ├─1─n model_calls
                  └─1─n artifacts
events ──▶ runs / attempts
```

| 表 | 作用 | 关键约束 |
|---|---|---|
| `jobs` | 一次修复任务 | `original_sha256` 必须 64-hex；phase 枚举 |
| `contracts` | 审核过的契约 revision | `UNIQUE(job_id, revision)`；批准时间与审核人同为空或同存在 |
| `runs` | 一次执行（两条路线） | `idempotency_key UNIQUE`；contract 必须同 job |
| `attempts` | 单条路线的一次尝试 | `UNIQUE(run_id, route, sequence)`；route ∈ {route_a, route_b} |
| `artifacts` | 文件与 hash | `UNIQUE(job_id, relative_path)`；只存相对路径 |
| `obligations` | 每条验证义务 | `pass` 必须有 evidence；结果枚举含 `not_run` |
| `events` | 进度/审计流 | 自增 sequence，按 run 分页 |
| `model_calls` | AI 调用与成本 | 成本非负；usage 为合法 JSON 或 NULL |

## 2. 枚举（写死在校验里）

```
phase      : draft screening awaiting_review queued analyzing generating
             applying roundtrip validating finished cancelled
outcome    : success_within_scope unsupported rejected inconclusive error cancelled
obligation : pass fail unknown not_run unsupported skipped
route      : A B
```

`not_run` 与 `unknown` 是**独立状态**，不能当作 `pass`——这是 PRD 的硬要求。

## 3. 迁移规则

```bash
python app/db/migrate.py --db var/app.db           # 应用
python app/db/migrate.py --db var/app.db --dry-run # 只看待应用
```

- 文件名 `NNN_name.sql`，按数字顺序应用；已应用的文件**永远不改**，改 schema 就加新文件。
- 每个文件连同 `schema_migrations` 记录在**一个事务**里执行；失败整体回滚（有测试覆盖）。
- 启动时跑一次即可；重复执行是 no-op。
- 应用是唯一写者；GUI 和 worker 不直接写库（技术设计 §6）。

## 4. 常用查询

```sql
-- 某个 job 的 AI 用量（含"成本未知"的调用数）
SELECT * FROM job_ai_usage WHERE job_id = ?;

-- 一次 run 的完整事件流（增量分页）
SELECT sequence, timestamp, event_type, payload_json
FROM events WHERE run_id = ? AND sequence > ? ORDER BY sequence LIMIT 200;

-- 某条尝试的必需义务
SELECT kind, result FROM obligations WHERE attempt_id = ? AND required = 1;

-- 某路由的候选
SELECT sequence, candidate_sha256, outcome, reason_code
FROM attempts WHERE run_id = ? AND route = 'B' ORDER BY sequence;
```

## 5. 与 AI 层（`model_calls`）的对应

`binaryrepair_ai.provider.CallRecord` → `model_calls`：

| CallRecord | 列 |
|---|---|
| `request_id` | `request_id` |
| `model` / `model_returned` | `model` / `model_returned` |
| `prompt_sha256` / `response_sha256` | 同名 |
| `status` | `status`（保留 reason_code，便于统计失败原因） |
| `usage` | `usage_json`；`None` 写 NULL |
| `estimated_cost_usd` | 同名；`None` 写 NULL |
| `latency_ms` / `attempts` / `thinking` | 同名 |
| `created_at` | `created_at` |

注意：`estimated_cost_usd` 是估算，不是账单；`job_ai_usage` 把未知成本单独计数，
GUI 显示 "unavailable" 而不是 0。

## 6. 还没做（明确留给后续）

- 备份/恢复演练：用 SQLite 在线备份 API，不要直接 copy 正在写的库。
- artifact 清理策略：导出后按 30 天复核（技术设计建议），当前不自动删。
- 多用户/并发写：MVP 不要求；WAL 允许读并发，但只有一个写者。
