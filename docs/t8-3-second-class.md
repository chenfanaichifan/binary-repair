# T8.3 第二类缺陷：CWE-416（Lead 已定）

状态：**已定类** · 2026-11-06 · 第二类 = CWE-416 use-after-free
第一类仍是 CWE-121 stack buffer overflow。
CWE-787 的说法已过期；CWE-122 不用（`m3/cwe122-fixture-build` 只作历史）。
T8.3 仍 blocked：build/trigger 未验证，**不 merge / 不打 tag / 不上线**。

## 1. “不同”的定义

验收用的“不同”不是换个编号，而是两条同时成立：

1. **不同 CWE**：CWE-416（释放后使用），不是 CWE-121（栈缓冲区溢出）；
2. **不同修复机制**：修复点是**对象生命周期 / 所有权**（释放后失效引用、置空、
   引用计数），不是第一类那种“目标缓冲区长度检查”。如果第二类样本只是把释放顺序
   挪一下、崩溃点不变，M4 应判为“换皮”，不算通过。

plan 与 GUI 都不得按类别分支；类别只出现在 fixture 元数据和 M4 的报告里。

## 2. GUI 验收清单（M2）

第二类 plan 到位后，用 `/agent/new` 逐条勾：

| # | 检查 | 期望 |
|---|---|---|
| 1 | 输入描述后请求 `POST /api/assistant/plan` | 返回 `plan.steps` 非空；`mode` 是 `llm` 或 `deterministic` |
| 2 | 欢迎语 | 列出 plan 的 `title`，不是固定的“样本 → 缺陷 → 用例 → 契约 → 复核” |
| 3 | 步骤数与第一类不同 | 3 步、6 步都能渲染，不要求五步 |
| 4 | 问题标签 | 用 `question.label`；plan 没有 `defect` / `valid_tests` / `environment` 这些第一类 key 时，不显示英文 key |
| 5 | 下一步按钮 | 下一步 `kind=review` 显示“进入复核”，否则“保存并继续” |
| 6 | 复核表 | 列出 plan 的全部 question 与答案；`（未填）` 不被当成已填 |
| 7 | `fallback=true` | 页面明确写“回退计划，没有发生真实模型调用” |
| 8 | 端点 503 | 显示“计划服务未接通（原因）”；**不**渲染 fixture |
| 9 | 创建任务 | `plan_id` 与展示的 plan 一致（依赖 M5/M1 的关联字段） |
| 10 | 页面文案 | 不出现 “CWE-121” / “stack buffer overflow” 的专属说明 |
| 11 | 结果屏（no-input 契约） | `input_mode="none"` 时 `invalid` 显示 `N/A`、`valid` 显示 `1/1`；不显示 `0/0 passed` |

第 1–8 条现在就能用一份手写 plan 在本地验证；第 9 条要等 `POST /api/jobs`
接受 `plan_id`（或创建后 `save_plan`）。

## 3. M2 不在范围

- fixture 的源码、ELF、build 脚本、contract、4 valid + 2 invalid 测试；
- `generic repair proposal` 的字段与内容；
- 第二类 candidate、V0–V5 证据、result-bundle；
- guest build path。

这些分别归 M1、M5、M3、M4。

## 4. 依赖顺序

```
Lead 定类（已完成：A / CWE-787）
  → M1 入库 fixtures/public/cwe787/
      src.c · original.elf · build.sh · build.json · contract.json
      tests/valid.json（4） · tests/invalid.json（2） · SHA256SUMS
      来源 URL / commit / license · original SHA-256 / build-id
  → M3 建 scripts/guest_build_cwe787.sh
      固定 argv · 无 shell 拼接 · fail-closed · 不联网 · 不 root · 不访问 host 路径
  → M5 冻结第二类 deterministic plan + generic repair proposal schema
  → M3 出第二类包（result-bundle 进 handoff.files + SHA256SUMS）
  → M2 跑第 2 节清单
  → M4 独立验证（fixture 可复现、V0–V5、generic planner 真处理第二类）
  → Lead 解 blocked
```

`tests/invalid.json` 至少一条要触发 CWE-787 本身（越界写），否则 M4 只能证明
“行为没坏”，不能证明“第二类缺陷被覆盖”。

## 5. 当前事实

- GUI 已无第一类硬编码（`a9de810`）：欢迎语、复核按钮、复核标签都由 plan 驱动。
- `app/` 下 grep 不到 `CWE-121` / `CWE-787` / `route_a_evidence` 之类分支。
- `/agent/new` 已接 `POST /api/assistant/plan`；controller 路由仍归 M1。
- 第二类 fixture / plan / candidate 尚未出现，因此 T8.3 仍不能进入 M4 验证。
