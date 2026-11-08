# 56e11ca 上传/下载 UI 复核（M2，2026-11-08）

复核对象：交付分支 `b6d110b` 中的 `56e11ca feat: add repaired ELF upload and download entry`。

```text
改动文件 12 个
前端      app/templates/agent.html（+8）
          app/static/js/agent.js（+75/-7）
后端      app/controller_api.py（+45）
          app/main.py（+29）
          app/backend.py（+12）
          app/services/jobs.py（+39）
测试      tests/integration/test_deliverable_upload.py（新增 68 行）
          tests/test_agent_console.py（+16）
```

结论先行：**三项均实现正确，未发现阻断缺陷**。
另有两条观察项，见第六节。

## 一、上传控件

前端：

```text
app/templates/agent.html:134  <input id="agent-deliverable-input" type="file"
                                     accept=".elf,application/x-elf">
app/templates/agent.html:136  <button id="agent-deliverable-upload">上传修复文件</button>
app/templates/agent.html:138  <span id="agent-deliverable-status"></span>
app/static/js/agent.js:1554   按钮存在才绑定点击
app/static/js/agent.js:1522   uploadDeliverable()
```

行为核对：

| 场景 | 代码 | 结果 |
|---|---|---|
| 未创建 job | `agent.js:1525` | 提示「尚未创建任务」，不发起请求 |
| 未选文件 | 检查 `input.files.length` | 提示「请选择修复后的 ELF 文件」 |
| 上传中 | `setText(..., "上传中…")` | 有进度文案 |
| 成功 | 显示「已保存：<name>（可下载，不参与验收）」并刷新列表 | 正确 |
| 失败 | 显示「上传失败：<detail>」 | 正确 |

请求：

```text
POST /api/jobs/{jobId}/deliverables
headers: x-csrf-token: CSRF        （agent.js:51 定义，同源 token）
body:    multipart/form-data，字段名 file
```

未手动设置 `Content-Type`，由浏览器带 boundary，正确。

后端校验（`controller_api.py`）：

```text
空文件            -> 422
> 64 MiB          -> 413
缺 \x7fELF magic  -> 400
文件名含路径/..   -> 400
通过              -> 201，写 jobs/<job>/deliverables/<uuid>-<name>
                     role = operator_deliverable
```

`app/main.py` 的代理层额外要求 CSRF，并且在非 controller 模式（无
`upload_deliverable` 方法）时返回 404，前端会显示「上传失败：…」，不会崩溃。

## 二、artifact 链接

前端渲染（`agent.js:1300`）：

```js
(view.artifacts || []).concat(state.artifacts || []).forEach(function (artifact) {
  if (!artifact || typeof artifact.id !== "string" || !artifact.id || seen[artifact.id]) return;
  seen[artifact.id] = true;
  var label = artifact.name || artifact.label || artifact.id;
  if (artifact.role) label += "（" + artifact.role + "）";
  link.href = "/api/jobs/" + encodeURIComponent(state.jobId) + "/artifacts/" +
    encodeURIComponent(artifact.id) + "/download";
});
```

核对：

```text
[x] 缺 id 不生成死链（沿用 dc7a012 的规则）
[x] state.artifacts 与 view.artifacts 合并后按 id 去重
[x] label 优先 name，其次 label，最后 id
[x] role 后缀让 operator_deliverable 在列表里可辨认
[x] 链接使用 job 维度路由 /api/jobs/{job}/artifacts/{aid}/download
```

后端路由存在且一致：

```text
controller_api.py:1479  GET /api/jobs/{job_id}/artifacts/{artifact_id}
controller_api.py:1484  GET /api/jobs/{job_id}/artifacts/{artifact_id}/download
controller_api.py:1434  GET /api/jobs/{job_id}/artifacts   -> {"A": [...], "B": [...]}
```

上传产物没有 `attempt_id`，`list_artifacts` 的 `LEFT JOIN` 得到 `route = NULL`，
`artifacts()` 把它归入 `A` 组，前端 `fetchArtifacts` 会读取到，因此上传后
无需刷新整页即可出现在下载列表。

## 三、空 job 状态

```text
agent.js:1283  下载区无内容时显示「尚未创建任务」
agent.js:1324  下载面板在空 job 时显示「尚未创建任务」
agent.js:414   fetchArtifacts() 无 jobId 直接 resolve([])
agent.js:433   请求失败时把 state.artifacts 置空，不抛错
```

因此空 job、无 artifact、artifact 请求失败三种情况都不会出现
`undefined` 链接，也不会出现空白卡片。

## 四、不参与验收（红线）

后端把上传物只登记为 artifact：

```text
role = operator_deliverable
media_type = application/x-elf
sha256 = 实际字节摘要
```

`add_artifact` 只写 `artifacts` 表；不写 obligations、attempts、runs，
不改变 `phase` 与 `verdict`。集成测试直接断言：

```python
snapshot["phase"] == "draft"
snapshot["verdict"] is None
```

## 五、测试覆盖

```text
tests/integration/test_deliverable_upload.py
  test_deliverable_is_registered_and_downloadable
      201 / role / sha256 / 下载字节一致 / phase 与 verdict 未变
  test_deliverable_rejects_non_elf
      400

tests/test_agent_console.py
  test_deliverable_upload_controls_exist
      input / button / testid / uploadDeliverable / "/deliverables" / "/artifacts"
  test_no_model_calls_or_new_transport
      fetch( 计数由 5 调整为 7，仍全部同源 GET/POST
```

`test_agent_console.py` 的 fetch 计数断言与实现一致（本地 132 passed）。

## 六、观察项（不阻断）

1. **上传只在 controller(http) 模式可用**。
   `app/main.py` 用 `getattr(BACKEND, "upload_deliverable", None)` 判断，
   fake/in-memory 模式返回 404。这是设计选择，但建议在页面上把按钮在
   非 http 模式隐藏，避免用户看到「上传失败」。
2. **前端没有大小提示**。
   64 MiB 限制只在后端，超限时用户只看到「上传失败：Uploaded file is too large.」。
   可接受，不属缺陷。

## 七、给 M4 的页面步骤

见 `REVIEW-12-CHECKLIST.md` 第七节。核心是：空 job 提示、非 ELF 被拒、
合法 ELF 可下载且 sha256 一致、上传后 phase/verdict 不变。
