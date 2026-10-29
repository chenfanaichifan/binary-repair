# Root 集成说明（成员5 切片）

**状态：** 2026-10-20，成员5 切片已合入共享树（`member-5/integration`）。
**规则：** 仓库根目录是唯一集成点；旧的 `agent/` 快照已归档到 tag
`archive/2026-10-22/pre-cleanup`，main 不再包含这些副本。

---

## 1. 模块地图

| 路径 | 归属 | 作用 |
|---|---|---|
| `app/domain/candidates.py` | 成员5 | `validate_candidate` / `validate_candidate_for_context` / `may_leave_host`；AI 边界唯一入口 |
| `app/domain/contracts.py` | 成员5 + 成员1 | `SecurityContract` 与规范化的 `sha256()`；不碰持久化 |
| `app/domain/manifests.py` | 成员5 | `manifest_sha256` 的 canonical 索引与文件哈希 |
| `app/services/provider.py` | 成员5 | `DeepSeekProvider`、`ProviderFailure(FailureReason)`、`require_candidate` |
| `app/db/connection.py`、`schema.sql` | 成员1 | v1 baseline（jobs + artifacts）；启动时初始化 |
| `app/db/migrate.py`、`migrations/002_ai_tables.sql`、`003_acceptance_verdict.sql` | 成员5 + 成员1 | v1 baseline + 002/003；旧 001 退役，检测到即报错 |
| `binaryrepair_ai/` | 成员5 | 实现细节：client / prompts / pricing / Pydantic schema；外部不要直接依赖 |
| `schemas/` | 成员5 | candidate/context JSON Schema v1、示例、drift 检查 |
| `routeb/` | 成员5 | Route B 合成 fixture、oracle、Ghidra 导出、Patcherex2 实验 |
| `tests/test_ai_boundary_contract.py` | 成员5 | 22 条 AI 边界契约 |
| `tests/test_provider_failures.py` | 成员5 | 6 种 typed failure |
| `tests/test_contracts.py` | 成员5 | SecurityContract v2、容量字段、哈希稳定性 |
| `tests/test_manifests.py` | 成员5 | manifest 索引 canonical hash |
| `archive/2026-10-22/pre-cleanup`（tag） | 团队 | 旧分支快照；只在需要查历史时 checkout，不在 main 中维护 |

外部代码只应 import `app.*`；`binaryrepair_ai.*` 是实现细节，重构时不保证稳定。

---

## 2. 调用链（谁调谁）

```text
reviewer 填契约
      │  SecurityContract(...)
      ▼
  contract.sha256() ──────────────► 存 contracts.sha256 / run.reviewed_scope_sha256
      │
      ▼
job controller 组 RepairContext
  original_sha256 / contract_sha256 / analysis_sha256
  target_entry / contract_summary / allowed_calls / templates
      │
      ▼
provider.request_candidate(ctx)
      │  CandidateV1（已过 schema/scope）或 ProviderFailure
      ▼
validate_candidate_for_context(payload, ctx)
      │  身份、证据签发、recovered hash 绑定
      ▼
验证（成员4）→ decide_attempt_outcome(...)
      │
      ▼
GUI 只渲染 verdict，不自己判断成功
```

**硬规则：** provider 只提案；候选必须过 `validate_candidate_for_context`；最终结论只来自验收引擎。

---

## 3. 契约哈希：回答成员1 的开放问题

`reviewed_scope_sha256` 对验收引擎是**不透明**的（verification-design §4.1），
但审批层必须能复现它。`app/domain/contracts.py` 给出的定义：

```text
sha256( utf-8( json.dumps(canonical_payload,
                          sort_keys=True,
                          separators=(",", ":"),
                          ensure_ascii=False) ) )
```

- `canonical_payload`：`to_dict()` 的副本，四个列表字段先排序（顺序无语义）；
- 文本只允许 printable ASCII（+ `\n`/`\t`），与团队"API/导出数据英文 ASCII"规则一致；
- 同一契约、不同列表顺序 → 同一个 hash；
- 任何字段变化 → 不同 hash。

成员1 的用法：

```python
from app.domain.contracts import SecurityContract

contract = SecurityContract.from_dict(reviewed_body)
body_json = json.dumps(contract.to_dict(), ensure_ascii=False)
scope_sha = contract.sha256()          # 存 contracts.sha256 与 run.reviewed_scope_sha256
```

加载时建议：

```python
stored = SecurityContract.from_dict(json.loads(row["body_json"]))
assert stored.sha256() == row["sha256"]   # 防止手改 body 后 hash 未更新
```

`SecurityContract` 不含 `id` / `job_id` / `approved_at` / `reviewer_label`；
这些是持久化字段，由成员1 的 `contracts` 表承担。

---

## 4. 合并顺序与当前状态

| 顺序 | 内容 | 状态 |
|---|---|---|
| ① | 成员5：`candidates.py` + `provider.py` + schema + db | ✅ 已在 main（`1250169`） |
| ② | 成员4：`acceptance.py` + `outcomes.py` + tests | ⏳ 等其 PR |
| ③ | 成员1：`app/services/jobs.py` + 002 迁移 | ⏳ |
| ④ | 成员2：GUI 接真实 controller | ⏳ |
| ⑤ | 成员3：公共样本 fixture | ⏳ |

成员1 加 `app/services/jobs.py` 时不需要改本切片的模块；只需：

- 用 `SecurityContract` 生成/校验 hash；
- 组 `RepairContext` 时把 `contract_summary`、`allowed_calls`、`target_entry` 填对；
- 候选落库前调 `validate_candidate_for_context`。

---

## 5. 验证命令

```bash
pytest -q                                  # 全仓；当前 149 passed, 2 skipped
pytest -q tests/test_ai_boundary_contract.py tests/test_provider_failures.py
pytest -q tests/test_contracts.py tests/test_db_schema.py
python schemas/generate.py --check
python -c "from app.db.connection import connect; connect('var')"
python scripts/smoke.py --mock             # 无 key 的管线自检
```

当前共享树：**149 passed, 2 skipped**；`schema up to date (4 files)`。
2 个 skip 是 V3 运行时测试（需要 Linux + candidate ELF），不是 pass。
旧的 3 个 identity skip 已随 controller-v2 合入消失。

---

## 6. 不做什么

- 不在旧快照 tag 里改代码；需要历史时 checkout `archive/2026-10-22/pre-cleanup`。
- 不让 GUI 计算成功/失败；只渲染 `Verdict`。
- 不在 host 上执行上传的二进制；执行属于 disposable VM + broker（成员1 落地）。
- 不把真实 DeepSeek 调用写进 CI；provider 测试全部用假 transport。
- 不在没有成员3 样本时声称 Route B 已真实往返；见
  [03-feasibility-checklist.md](03-feasibility-checklist.md)。
