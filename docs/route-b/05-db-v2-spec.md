# DB v2（002）接口决定

**状态：** 2026-10-20，成员5 提案；002 尚未合入 main。
**基线：** main 的 `app/db/schema.sql`（jobs + artifacts）记为 v1；002 记为 v2。
**原则：** 只支持 v1 baseline 新建库；检测到旧 001 直接失败；不静默混用、不自动删数据。

---

## 1. canonical 序列化：唯一实现在 `app/domain/contracts.py`

controller **只能**调用下面四个入口，不能自己写 `json.dumps` / 排序：

```python
from app.domain.contracts import SecurityContract

SecurityContract.from_dict(data: dict[str, Any]) -> SecurityContract
contract.canonical_payload() -> dict[str, Any]
contract.canonical_json() -> str
contract.sha256() -> str

# 给“只有 dict”的调用方（controller/approval）：
canonical_contract_json(data: dict[str, Any]) -> str
contract_sha256(data: dict[str, Any]) -> str
```

规则：

- `canonical_json()` 固定：
  `json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`
- 四个列表字段先排序：`authorized_edits`、`allowed_calls`、
  `environment_assumptions`、`required_obligations`（顺序无语义）。
- 文本只允许 printable ASCII（+ `\n`/`\t`）。
- 存库时：
  - `contracts.body_json = contract.canonical_json()`（就是这段文本，不要再 pretty-print）
  - `contracts.sha256 = contract.sha256()`
- 读取时：
  ```python
  stored = SecurityContract.from_dict(json.loads(row["body_json"]))
  assert stored.sha256() == row["sha256"]
  ```
  不一致就拒绝，不要“重新算一个覆盖旧值”。
- `reviewed_scope_sha256` 现在等于 `contracts.sha256`；`runs.manifest_sha256` 单独绑定。
  两者都在审批时写入，验收引擎只检查非空。

**禁止：** controller 里出现第二份 `sorted(...)` 或 `json.dumps(..., sort_keys=True)`。

---

## 2. 旧 001 的处理：失败，不迁移

v1 baseline 是 `app/db/schema.sql`，记录为：

```text
schema_migrations(version=1, name='base')
```

002 记录为 `version=2, name='ai_tables'`。

**检测到 001 时：抛 `LegacySchemaError`，不执行任何 DDL，不删表，不自动转换。**

检测顺序（`connection.init_db()` 在应用启动时调用一次）：

1. 打开连接，`PRAGMA foreign_keys=ON`；
2. `CREATE TABLE IF NOT EXISTS schema_migrations`；
3. **先检查 legacy**（在任何 `schema.sql`/002 之前）：
   - `PRAGMA table_info(jobs)` 含 `fixture_id` → 旧 001；
   - 或 `schema_migrations` 有 `version=1` 且 `name <> 'base'` → 旧 001；
   - 或 `schema_migrations` 有 `version=2` 但没有 `version=1` → 损坏；
   - 命中 → 抛错，消息明确写：
     `legacy 001 schema detected; delete var/app.db and recreate; no automatic migration`
4. 执行 `schema.sql`（`CREATE TABLE IF NOT EXISTS`，幂等）；
5. 插入 `(1,'base')`（若不存在）；
6. artifacts 重复预检（见 §3）；
7. 应用 `002_ai_tables.sql`；
8. 可选 `PRAGMA user_version=2`。

**不提供 001→002 迁移脚本。** 001 从未进 main；开发库里跑过 001 的直接删库重建。

---

## 3. artifacts 重复：失败并列出，不自动清理

002 要加：

```sql
ALTER TABLE artifacts ADD COLUMN attempt_id TEXT REFERENCES attempts(id);
ALTER TABLE artifacts ADD COLUMN media_type TEXT NOT NULL
    DEFAULT 'application/octet-stream';
CREATE UNIQUE INDEX IF NOT EXISTS ux_artifacts_job_path
    ON artifacts(job_id, relative_path);
```

SQLite 不能 `ALTER TABLE ... ADD UNIQUE`，所以用唯一索引。

**迁移前预检**（在 `migrate.py`，执行 002 之前）：

```sql
SELECT job_id, relative_path, COUNT(*) AS n
FROM artifacts
GROUP BY job_id, relative_path
HAVING n > 1;
```

- 有行 → 抛 `DuplicateArtifactsError`，消息里带完整 `(job_id, relative_path, n)` 列表；
  迁移中止，不执行 002 的任何语句。
- 无行 → 继续；唯一索引作为第二道保险。
- **绝不自动删除或合并行**：artifact 行是证据，静默删数据比迁移失败更糟。

操作员处理：按 `sha256`/`role` 人工决定保留哪一行，删除多余行后重跑迁移。

**顺序：** 先建 `attempts`，再 `ALTER artifacts ... REFERENCES attempts(id)`，否则外键找不到表。

---

## 4. 002 的关键约束

| 表 | 约束 |
|---|---|
| `contracts` | `UNIQUE(job_id, revision)`、`UNIQUE(job_id, id)`；`body_json` 是 canonical 文本 |
| `runs` | `UNIQUE(job_id, idempotency_key)`；`FOREIGN KEY (job_id, contract_id) REFERENCES contracts(job_id, id)` |
| `attempts` | `UNIQUE(run_id, route, sequence)`；`route IN ('route_a','route_b')`；outcome 六值 |
| `obligations` | `result IN ('passed','failed','not_run','unknown','timed_out')`；`passed` 必须有 `evidence_artifact_id` |
| `model_calls` | `estimated_cost_usd IS NULL OR >= 0`；`usage_json IS NULL OR json_valid` |
| `events` | `sequence INTEGER PRIMARY KEY AUTOINCREMENT` |

词表解释：

- `unknown` / `timed_out` 独立保留，不压成 `failed`；
- 路由级 `unsupported` 存 `attempts.outcome`，不塞进 obligations；
- 被跳过的检查记 `not_run` + detail，不记 `passed`。

`attempts` 由 controller 在 run 启动时预建（route_a/route_b 各一行，`sequence=1`，
`phase='queued'`，`outcome=NULL`）；重试 `sequence+1`。`/api/attempts/{id}/evidence`
从第一秒就有 id。

---

## 5. 分工

| 工作 | 写 | review |
|---|---|---|
| `002_ai_tables.sql` | 成员5 | 成员1（jobs/artifacts 兼容）、成员4（obligations 词表） |
| `migrate.py`：baseline v1、legacy 检测、artifacts 预检 | 成员5 | 成员1 |
| `connection.init_db()` 启动调用 | 成员1 | 成员5 |
| attempts 创建/重试 | 成员1 | 成员4 |

002 合入后，成员1 再改 `jobs.py` / `controller_api.py` / `connection.py`，并报
identity / controller API / attempts 的真实 pytest 数。
