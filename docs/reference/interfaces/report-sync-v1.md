# 报告同步与整理接口 v1（M2 消费侧契约）

状态：M2 已实现，2026-11-05。基线提交 `424b070` + 本轮改动。
范围：GUI 只读 controller 的报告数据，整理成页面与导出件；**不新增 controller 行为**。

---

## 1. 数据流

```
controller (127.0.0.1:8000, app.controller_api)
   │  GET /api/jobs/{id}
   │  GET /api/jobs/{id}/obligations
   │  GET /api/jobs/{id}/artifacts
   │  GET /api/artifacts/{id}/download
   ▼
HttpBackend (app/backend.py)
   │  语言校验：payload 含 CJK → 502，不渲染
   ▼
build_export_bundle()  ← 唯一的"整理"入口，不计算 outcome
   ├── /api/jobs/{id}/export      JSON v2（英文 ASCII）
   ├── /jobs/{id}/report          HTML 报告
   └── /jobs/{id}/evidence        证据页
```

**铁律**：整理层只搬运与排序，`outcome` / `verdict` 一律来自 controller；
GUI 不聚合两条路线、不把 `not_run` 当通过、不把空表当通过。

---

## 2. 已消费的真实字段（2026-11-05 抓取，样本见 `docs/reference/interfaces/samples/`）

| 来源 | 字段 | 用途 |
|---|---|---|
| snapshot | `id / filename / original_sha256 / defect / valid_tests / environment / created_at` | 任务身份卡 |
| snapshot | `phase / cancelled / execution / data_source / demo` | 阶段与演示横幅 |
| snapshot | `contract.{revision,sha256,approved,approved_at,reviewer_label,四个契约字段}` | 契约与批准徽章、409 语义 |
| snapshot | `run.{id,phase,manifest_sha256,reviewed_scope_sha256}` | 运行身份，导出 `run` 块 |
| snapshot | `verdict.{outcome,reason,failing_obligation,detail}` | run 级结论，只读展示 |
| snapshot | `routes.{A,B}.{phase,outcome,outcome_reason,verdict}` | 路线结论 |
| snapshot | `routes.*.obligations[]` | V0–V5 行，逐字渲染 |
| snapshot | `routes.*.evidence` = `persisted` \| `not_persisted` | **新增透传**：区分"没有结果"和"结果为空" |
| snapshot | `routes.*.{verification,compatibility,tests,stages,changed_regions,elapsed_s,manual_interventions,ai_usage}` | 事实表与时间线 |
| artifacts | `id / name / role / sha256 / size_bytes / available / content_url / media_type` | 产物表与下载 |
| obligations | `{A:[],B:[]}` | 快照里没有义务时兜底（真实返回通常为空） |

样本文件：`docs/reference/interfaces/samples/snapshot-real.json`、`obligations-real.json`、`artifacts-real.json`、`visuals-real.json`。

---

## 3. 本轮落地的整理规则

1. **`evidence_state` 透传**：导出每条路线新增 `evidence_state`。`not_persisted` 原样保留，
   并追加 limitation：`no obligation results have been received ... an empty table is not a pass.`
2. **空义务表不当通过**：证据页在义务为空时显示"后端尚未写入义务结果"，不再渲染空表。
   顶部同时显示 `evidence: not_persisted` 徽章。
3. **产物可下载性**：`available` 仅在 controller 给了 `id` 且 `available=true` 时为真；
   导出保留 `artifact_id` 与 `content_url`；`download` 与之一致，避免"标了可下载但 404"。
4. **GUI 产物代理**：新增 `GET /api/artifacts/{id}` 与 `GET /api/artifacts/{id}/download`，
   在 http 模式下转发 controller。此前证据页链接 404，属真实缺陷，已修。
5. **`reason` 空串归 null**：controller 的 `outcome_reason: ""` 不再输出为空字符串。
6. **新增 `run` 与 `sync` 块**：导出记录 run 身份与数据来源，并显式标注
   `gui_computes_outcome: false`。
7. **不破坏 v2**：`job` / `contract` 字段集合保持不变，只做增量，旧断言全绿。

实测（真实任务 `e15c141a…`，`phase=queued`）：

```
evidence_state A/B: not_persisted / not_persisted
download: 200, 26792 bytes = original.elf
limitations: 6 条（两条路线各 3 条，含 "empty table is not a pass"）
```

---

## 4. 缺口清单（需要其他成员提供）

### P0 · 阻塞报告完整度

| # | 需要什么 | 归属 | 为什么现在做不了 | 验收方式 |
|---|---|---|---|---|
| 1 | `GET /api/attempts?job_id=` 或 `GET /api/runs/{run_id}/attempts`：返回 `id/route/sequence/phase/outcome/reason/failing_obligation` | M1 | 现在只有 `GET /api/attempts/{id}/evidence`，GUI 拿不到 attempt id 列表，无法展示重试历史（`/api/runs/{run_id}/attempts/retry` 已存在但无法发现） | 给定 job，能列出每次 attempt 与其结论 |
| 2 | `GET /api/jobs/{id}/visuals` 返回真实代码视图（原始/修复后/差异/AI 候选），字段与现 `visuals-real.json` 同构 | M1 接收、M3/M5 产出 | 现在固定 `available:false`，报告页只能显示"未提供" | `available:true` 且含 disassembly / recovered_c / diff / candidate |
| 3 | 漏洞分析报告的落盘规范：M5 的 `expected_effects` / `assumptions` / `uncertainties` 与 Route B `manifest-compare.json` 以什么 artifact `role` 注册 | M5 + M1 | 没有命名约定，报告无法稳定识别"分析类产物" | 约定 `role=analysis` / `role=manifest-compare` 并在 artifacts 中出现 |
| 4 | M3 `status.json` v1 与 `audit.json` 的 artifact role 名 | M3 | 报告需要区分 `status` / `audit` / `edit-manifest` / `readelf` | 四个 role 在 artifacts 中稳定出现 |

### P1 · 语义澄清

| # | 问题 | 归属 | 影响 |
|---|---|---|---|
| 5 | run 级 `verdict` 是否带 `scope`（有界验证范围）与 `bounded:true`？现在只有 outcome/reason/failing_obligation/detail | M4 | 报告无法说明"结论覆盖到哪一步" |
| 6 | `ai_usage` 真实结构：现在真实值是字符串 `"unavailable"`，文档曾按对象描述 | M5 + M1 | 报告 AI 用量卡片只能显示原文 |
| 7 | 失败/取消时 `routes.*.evidence` 是否始终为 `not_persisted`？还是可能有 `persisted` 但全 `not_run`？ | M1 | 决定提示文案分支 |
| 8 | `execution-bridge-v1.md`（§4a/§4b）仍不存在；`execution` 枚举目前只见 `not_started` / `queued` | Lead + M1 | 无法固定 execution 状态机文案 |
| 9 | obligations 行增加 `scope` 字段（当前 DB 只有 `id/attempt_id/kind/required/result/evidence_artifact_id/detail`） | M1 | GUI 目前用「证据域」映射兜底，无法显示后端认定的真实范围 |
| 10 | 把 V3 拆成 `round_trip` 与 `repaired_behaviour` 两个 kind，并各自落盘 | M1 + M5 | 否则「保持原始行为」会被算成「修复通过」（评审第 3 条） |

---

## 5. 同步语义

- 页面轮询 `GET /api/jobs/{id}`，间隔 2 秒；页面隐藏时 8 秒。
- 每次响应整体替换展示，不在前端累积状态，不做差分合并。
- controller 不可达：HttpBackend 抛 `BackendError(502)`，页面显示"后端不可用"，
  **保留上次已知数据但不伪装成新数据**（时间戳停在原处）。
- 语言：controller payload 含中日韩字符直接 502，不渲染（`_has_cjk_in_payload`）。
- 下载：`/api/artifacts/{id}/download` 由 GUI 代理；controller 返回 404 时 GUI 也返回 404，
  不生成空文件。

---

## 6. 验证命令

```powershell
# 1. controller
.\start-controller.ps1                      # 127.0.0.1:8000

# 2. GUI（http 模式）
$env:BINARYREPAIR_BACKEND = "http"
$env:BINARYREPAIR_API_BASE = "http://127.0.0.1:8000"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8011

# 3. 报告同步测试
.\.venv\Scripts\python.exe -m pytest tests/test_report_sync.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_export_bundle.py tests/test_backend_contract.py -q
```

---

## 7. 已知预存在失败（与本轮无关，基线同样失败）

- `tests/test_evidence_endpoint.py` 5 项：`attempts/<id>.json` 未创建。
- `tests/integration/test_worker.py`、`test_attempt_writer.py`、`test_host_broker.py`、
  `test_e2e_smoke.py`、`test_routeb_executor.py`：Windows 下 attempts 目录未预建 / 静态包文件数 7<8。
- `tests/test_routea_*.py`、`test_schema_contract.py`：环境缺 `jsonschema`。

基线对照：同一批测试在 `424b070` 的干净 worktree 中失败集完全一致。
