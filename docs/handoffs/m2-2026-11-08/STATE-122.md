# 122 · V5 16/16 确认 + comparison UI 接 179 契约（2026-11-08 00:40）

## 一、V5 字节核验：这次是真的 16/16

```text
fetch origin delivery/all-hands-2026-11-07
head = 5f8efa0d2603e730b597f7daf8707c5464080752   （与整理声明一致）
git archive 导出，zip 177,246 B
```

| 清单 | 结果 |
|---|---|
| `v5-replay-2026-11-07/HOST-SHA256SUMS` | **16/16，bad=0，missing=0** |
| `v5-replay-2026-11-07/SHA256SUMS` | **8/8，bad=0，missing=0** |
| 顶层 `delivery/.../SHA256SUMS` | **65/65，bad=0，missing=0** |
| v5 目录文件数 | 17（16 载荷 + 内置清单） |

结论：`outputs/121` 的 12/16 已失效，以本条为准。

## 二、P1 最终 job（179 口径）

```text
job      9247357c54714546a7ff84891f7766f8
run      54a088e418d94a75b10d08bd893a5581
route A  516d69ac6a5e44eca23ec9bca914dc5d
route B  90aa7abe41cd4dd2b7d9211a44d247db
created  2026-11-07T15:36:50+00:00
phase    finished
verdict  success_within_scope
```

本机核对：

- `attempts.json`：`available:true`，2 条，`route_a/direct`、`route_b/repaired`，
  均 `timeline_status:ok`、`exit_code:null`（前端显示「未知退出码」）
- `snapshot.json`：`id` 与 job 一致，`routes.A/B` 各 6 条 obligations
- `verdict` 为对象：`outcome=success_within_scope`，`failing_obligation=null`
- 顶层仍无 `scope` / `bounded` → Review 12 的 UI 显示 `unknown`

注意：179 的 job 与上一条消息里的 `1f426d79…` 不是同一个，说明存在两轮 P1 final。
当前以 179 + 仓库 canonical 路径为准。

## 三、comparison：179 首次给出正式契约，前端此前完全没有接

契约：

```http
GET /api/jobs/{job_id}/comparison
{"job_id":"…","status":"not_provided|available","detail":"…","comparison":null,"artifacts":[]}
```

实现（`34d054c`）：

| 响应 | 页面 |
|---|---|
| `status=available` | `comparison：已提供（N 个 artifact）` |
| `status=not_provided` | `comparison：未提供（not_provided）` |
| HTTP 非 2xx | `comparison：不可用（HTTP xxx）` |
| 网络失败 | `comparison：不可用（请求失败）` |
| payload 无 status | `comparison：不可用（payload 不可解析）` |

红线：

- 不解析 `comparison` 内部字段，不猜字段名；
- 任何分支都不显示「通过」；
- 卡片带 `data-testid="agent-comparison"`，供 M4 复验定位。

测试：`test_comparison_is_only_shown_when_the_api_says_available`，
并更新 fetch 计数 4 → 5（新增 comparison 路径）。
`test_agent_console + test_agent_honesty` = **62 passed**。

## 四、M2 提交链（分支 `tmp/m2-on-791`）

```text
3db4719  T8.4 徽章：scripted v1 / LLM
102d0fb  文档：T8.4 badge / 横幅 / 元数据
16b2a42  Review 12：scope/bounded 缺失显示 unknown
34d054c  comparison：只认 status，不做字段推断
```

## 五、现在的状态

| 项 | 状态 | 备注 |
|---|---|---|
| T7.4 / T7.5 | 完成 | 早前提交 |
| T7.6 | 完成 | 真实 job 字段全部对上 |
| T7.8 | 完成 | job id 校验 + 同源代理 |
| T8.4 | 完成 | 徽章 / 横幅 / 元数据 |
| Review 12 UI | 完成，待复验 | `16b2a42` |
| comparison UI | 完成 | `34d054c`，179 契约 |
| V5 | 16/16 | `5f8efa0d`（核验时 head；当前 7beb6e3，freeze c40b694） |

## 六、唯一剩余动作：把 M2 提交合入交付分支

> 2026-11-08 更新：该动作已完成。8 个提交全部合入，
> 当前 head `7beb6e3`，code/evidence freeze `c40b694`。

（以下为 122 当时的记录）

M2 的四个提交在 `tmp/m2-on-791`，不在 `delivery/all-hands-2026-11-07`。
M4 要复验 Review 12，必须先看到 `16b2a42`。

两个选项：

1. M1 直接 cherry-pick 四个提交到交付分支（推荐）；
2. 我导出 bundle，由 M1 在本地 fetch 后合并。

在此之前，Review 12 只能停在 `NOT VERIFIED`，不是 M2 侧未完成，而是提交尚未进入被复验的分支。
