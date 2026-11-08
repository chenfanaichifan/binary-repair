# 196 · comparison 三态 UI（M2）

日期：2026-11-08
起点：`c3bca0e01dce3204991c7ac47b158a1a5ffdd13f`（M1 路由已合入 delivery）
上游：`docs/interfaces/behavior-comparison-v1.md`（M5 草案）

## 0. 一句话

comparison 卡片现在能区分三态，`available` 会展开 summary 与 cases，
且卡片里没有任何「通过」字样。

## 1. 改动

```text
app/static/js/agent.js
  1. fetchComparison 保留 payload.comparison
     原来只存 status/detail/artifacts，cases 永远拿不到
  2. appendComparisonBox：available 由「已提供（N 个 artifact）」改为「已提供」
  3. 新增 appendComparisonCases：summary + cases + not_claimed
  4. 新增 CASE_KIND_LABELS / CASE_VERDICT_LABELS 中文标签

tests/test_agent_console.py
  新增 test_comparison_cases_are_rendered_without_becoming_a_verdict
```

## 2. 第 1 条为什么是必须的

```js
// 修复前
comparisonCache = { status: ..., detail: ..., artifacts: [...] };
```

`payload.comparison` 被丢掉，前端拿不到 cases。三态 status 是对的，
但 `available` 永远只能显示一个数量。这是既有代码的问题，不是新增逻辑。

## 3. 映射

```text
status       卡片文案
not_provided 未提供（not_provided）
invalid      不可用（<detail>）
available    已提供 + summary + cases + not_claimed
网络失败/401 不可用（HTTP xxx）
```

cases 内部：

```text
kind     known_good 已知正常 / known_bad 已知异常 / valid 合法输入 / invalid 非法输入
verdict  same 行为一致 / different 行为不同 / not_run 未执行 / unknown 未知
```

`not_claimed` 原样列出，前缀「不构成验收结论：」。

## 4. 实测

Windows 全量：

```text
729 tests / 716 passed / 0 failed / 0 errors / 13 skipped
```

真实浏览器（Edge，CDP）：

```text
not_provided（真实路由）
  行为对比comparison：未提供（not_provided）

invalid（注入 200 + invalid）
  行为对比comparison：不可用（comparison artifact hash mismatch）

available（注入 200 + 合法 payload）
  行为对比comparison：已提供
  summary：合计 2 · 一致 1 · 不同 1 · 未执行 0 · 未知 0
  case-1 · 已知正常 · 行为一致
  case-2 · 已知异常 · 行为不同 · returncode differs
  不构成验收结论：not a repair verdict；same is not acceptance evidence；
                  different is not a failure verdict by itself
```

三次检查 `innerText.includes("通过")` 均为 `false`。

## 5. 与 M5 口径已对齐（197）

M5 在 197 里把这两点写进 schema，路由行为不变：

```text
kind     = known_good | known_bad | valid | invalid
           kind=unknown / unsupported -> 整个 artifact invalid

verdict  = same | different | not_run
           verdict=unknown -> invalid

original / candidate   必须存在（对象）
returncode              int | null
stdout_sha256           64 hex | null
stderr_sha256           64 hex | null
timed_out               bool，必填，不能 null
detail                  string，必填，不能 null

not_run        still not_run, never a pass
same/different 两侧输出必须完整，否则 invalid
```

UI 侧相应把 `unknown` 从 verdict 标签表移除，`unknown` 不会以标签形式出现；
这类 artifact 在路由层就已经是 `invalid`，卡片显示「不可用」。

## 6. 边界

```text
未改 V0–V5
未改 v1.1.1
未碰 main
validation 判定细节归 M5（本次只对齐口径，不新增校验）
```

## 7. 复现

```powershell
$env:BINARYREPAIR_BACKEND="local"
$env:BINARYREPAIR_DATA_DIR="C:\ptreview\var"
$env:BINARYREPAIR_SESSION_TOKEN="review-session-token"
python -m uvicorn app.main:app --port 8123
python ui_comparison_cdp.py     # 注入 available / invalid
python ui_cmp_real.py           # 真实路由 not_provided
```
