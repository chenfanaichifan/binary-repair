# DB v2（002）接口决定

**状态：** 2026-10-20，002 已实现并合入共享树（`member-5/db-v2`）。
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

---

## 6. SecurityContract v2：容量与非法路径变成数值字段

纯文本 `valid_domain` / `invalid_input_response` 只给人看；gate 3/5 和验收需要机器
可读，所以 `SecurityContract` 升到 **schema_version=2**，新增必填字段：

```python
dest_capacity_bytes: int          # 50
max_valid_input_bytes: int        # 49
capacity_includes_terminator: bool# True（strcpy 的 NUL 计入 50）
invalid_exit_code: int            # 1
invalid_stdout: str               # ""（空字符串是合法值，不 strip）
invalid_stderr: str               # "ERROR: input exceeds destination capacity\n"
```

约束：

- `dest_capacity_bytes >= 1`；
- `capacity_includes_terminator=True` 时 `max_valid_input_bytes < dest_capacity_bytes`；
- `False` 时 `max_valid_input_bytes <= dest_capacity_bytes`；
- `invalid_exit_code` 在 `0..255`；
- `invalid_stdout` / `invalid_stderr` 保留精确字节文本（不 strip、不折叠换行），只允许
  printable ASCII + `\n`/`\t`，允许空串。

fixture 的值：

```json
{"dest_capacity_bytes":50,
 "max_valid_input_bytes":49,
 "capacity_includes_terminator":true,
 "invalid_exit_code":1,
 "invalid_stdout":"",
 "invalid_stderr":"ERROR: input exceeds destination capacity\n"}
```

gate 3 的 guard 直接读 `max_valid_input_bytes`（`len > 49` → invalid），不要从文本里
正则解析 50/49。`valid_domain` 仍保留人类可读描述，两者必须一致（review 检查）。

`schema_version` 从 1 升到 2；`from_dict` 仍然 strict，旧 body 缺字段会被拒绝，不会
静默补默认值。

---

## 7. `runs.manifest_sha256`：canonical 索引，不是测试用例的重排

manifest 文件（`valid.json` / `invalid.json`）按字节冻结为 artifact；`manifest_sha256`
是下面这个小索引的 hash：

```json
{"case_id":"CWE121_src_char_declare_cpy_51b",
 "manifests":[{"name":"invalid.json","sha256":"<file sha>"},
              {"name":"valid.json","sha256":"<file sha>"}],
 "original_sha256":"aa4281...",
 "schema_version":1}
```

canonical 规则：

- 顶层 key 排序；compact separator `(",", ":")`；UTF-8；`ensure_ascii=False`；
- `manifests` **按 name 排序**；name 必须唯一、相对 POSIX 路径、不含 `..`；
- 每个 `sha256` 是该文件**原始字节**的 SHA-256（lowercase hex）；
- 文件内部 case 顺序、缩进、换行都影响文件 hash；冻结后重排/格式化 = 新 manifest。

唯一实现（controller 直接调，不要自己拼 JSON）：

```python
from app.domain.manifests import (
    ManifestEntry, manifest_entries_from_files,
    manifest_set_json, manifest_set_sha256,
)

entries = manifest_entries_from_files([valid_path, invalid_path], root=fixtures_dir)
manifest_json = manifest_set_json(case_id=..., original_sha256=..., entries=entries)
manifest_sha = manifest_set_sha256(case_id=..., original_sha256=..., entries=entries)
```

存哪：

- `runs.manifest_sha256` = 上面的 `manifest_sha`；
- `manifest_json` 作为 artifact（role `test_manifest`）保存，或由 controller 重算校验；
- 两个 JSON 文件本身也作为 artifact 保存，路径/哈希进 `artifacts`。

审批绑定：

```text
jobs.original_sha256
+ contracts.sha256
+ runs.manifest_sha256
```

run 创建时三者一起复制/校验；`reviewed_scope_sha256` 仍等于 `contracts.sha256`，
manifest 单独绑定，不塞进 contract body，避免循环 hash。

---

## 8. attempts 重试语义

| 概念 | 含义 |
|---|---|
| run | 一次执行：冻结的 `(job, contract, manifest)` + 一个 `idempotency_key` |
| attempt | run 内某一条路线的一次尝试；`sequence` 从 1 递增 |

规则：

1. **同一个 idempotency key 复用**：返回已有 run（HTTP 200）和它的 attempts；
   不新建 run，也不新建 attempt。
2. 如果同一个 key 但 `job_id` / `contract_id` / `manifest_sha256` 与已存 run 不一致：
   **409 conflict**，不覆盖、不新建。
3. **重试一条路线**：走显式 retry 端点，在**同一个 run** 下新建 attempt，
   `sequence+1`；旧 attempt 保留。
4. **新 run** 只在以下情况创建：
   - 新的 idempotency key；
   - 契约重新评审（新 `contracts.sha256`）或 manifest 重新冻结（新
     `runs.manifest_sha256`）后的新执行；
   - 操作员显式 "rerun"（生成新 key）。
5. provider 内部的 transport retry 不新建 attempt；它是同一个 attempt 内的一次
   `model_calls` 记录。候选被拒绝后重新生成，才新建 attempt。
6. run 进入终态后不可追加 attempt；要重跑必须新 key（规则 4）。

`attempts` 在 run 启动时预建 route_a/route_b 两行，`sequence=1`、`phase='queued'`、
`outcome=NULL`；retry 端点再追加。这样 `/api/attempts/{id}/evidence` 在生成期间
就有 id。
