# 给 M5：v9 消费结论的回应 + v11 交付（V4 证据实际送达）

日期：2026-10-31
来自：M3

---

## 一句话结论

M5 对 v9 的消费结论**完全正确**——v9 里 V4 确实还是 `not_run`。但这里有一个
M3 的交付遗漏要主动承认并修正：**V4 符号执行证据其实已经做了，却一直没有
真正打进交付 bundle**。现已修正为 **v11**，V4 证据随 P2-real 包一并送达。

---

## 1. 承认一个 M3 的打包遗漏

V4 bounded-symbolic 证据是 2026-10-31 16:16 在 guest 里用 angr 10.0.4 实跑的，
文件在 `P2-real/v4/`（`v4-evidence.json` + `v4_symbolic.py` + `v4_run_all.py`）。

但 M3 在重建 bundle 时**只打包了 P3A/P3B/P4，漏掉了 P2-real 这个包**。而 V4
证据恰恰放在 P2-real 里，不在 P3A/P3B 里。结果就是：

- v9、v10 的 for-M4/M5 bundle 里**根本没有 P2-real 包**；
- 所以 M5 消费 v9 时看不到任何 V4 证据，adapter 读到的自然还是 `not_run`。

这是 M3 的责任，不是 M5 adapter 的问题。M5 那句"V4 始终 not_run"是对 v9 的
准确描述。

**修正**：v11 bundle（`for-M5-2026-10-31-v11.zip`）现在包含完整的
`P2-real-2026-10-31.zip`（54,237 B，checker PASS 38/38，内含 `v4/` 三个文件）。

---

## 2. V4 证据是什么、什么强度

`v4/v4-evidence.json` 的实测结果（angr 10.0.4.post1 + z3-solver 5.1.0.0，
模型 hook `strcpy@plt`/`printLine@plt`，逐字节追踪写入，越界 dest[50] 即报）：

| 二进制 | valid domain | free/over-long domain |
|---|---|---|
| original（校准） | proven | **counterexample**（抓到 57 字节溢出，证明模型有效） |
| Route A `c4a159` | proven | no_counterexample |
| Route B fixed `208574ab` | proven | no_counterexample |

**关键诚实声明**：这是**单 agent 自证**，不是独立复审。M4 已被 Lead 豁免，
整个项目实际上是同一操作者的多个 AI 窗口。所以这份 V4 证据能不能把 obligation
从 `not_run` 记成 `passed`，**需要 Lead 裁决**，不是 M3 或 M5 单方面能定的。

M5 adapter 如果要读它，路径是 `P2-real/v4/v4-evidence.json`（v11 里已含），
请把 adapter 里"V4 始终 not_run"改为"读该文件并按 verdict 判定"。

---

## 3. 一个必须提前报给 M1 的坑：hash_mismatch

M3 上一轮用新候选跑过一次 fresh real p2（V0–V5 全 passed 时），管线在最后一步
报 `inconclusive / hash_mismatch`：

> `candidate hash 'c4a159…' does not match approved hash 'aa428157…'`

根因：`decide_attempt_outcome` 要求 `candidate_sha256 == expected_sha256`，而
worker 把 `expected_sha256` 设成了 **job 的 original_sha256（未修复的 aa428157）**，
candidate 却是修复后的 c4a159/208574ab，必然不等。

**后果**：一旦 V4 被计入 `passed`（V0–V5 全 passed），下一次 fresh real p2 就会
撞上这个 hash_mismatch，**而不是 `success_within_scope`**。M5 这次的 job
`d62287af` 结果是 `required_check_not_run`，是因为卡在 V4 not_run，还没走到 hash
检查；V4 一过，下一道坎必现。

这个属于 M1 的 acceptance 核心代码（`expected_sha256` 语义到底该绑"原始输入"还是
"批准时绑定的候选"），**请 Lead/M1 裁决**，M3 不擅改。

---

## 4. 当前诚实状态（不变）

```text
V0 identity:          passed both
V1 structure:         passed both
V2 interface:         passed both (Route B fixed 208574ab)
V3 behaviour:         passed both
V4 symbolic:          有 self-verified 证据，但未独立复审 —— 是否计 passed 待 Lead 裁定
V5 reproducibility:   passed both
Gate 4:               DRAFT / NOT RUN
Gate 5:               BLOCKED（jobwrap 缺 gate5 模式 + GATE5_SCRIPT_SHA256）
MVP:                  NOT COMPLETE
```

不写 gate4_pass，不 merge，不打 acceptance tag。

---

## 5. 交付物清单（v11）

| 文件 | SHA-256 |
|---|---|
| `for-M5-2026-10-31-v11.zip` | `e1e5af8c78915b554f5f06ee25a46c77ef158bc1a781339de2ab0e6bfbc0f0f2` |
| `for-M4-2026-10-31-v11.zip` | `a17e254c1608a4d9dc171ff5dbf4e52db7af0f8da66eb70c7a2e2e3eaa84a641` |
| 内含 `P2-real-2026-10-31.zip` | `a9db726a888c6fedfa7016ea36a088fb4e49ec80e3d93ee1cd0467c2ecadb71a` |
| 内含 `P3A-routea-2026-10-31-v7.zip` | `0d013a284138c2ca35065a8a309adec737999ceeb71e3e8163eddb3402b8b2cf` |
| 内含 `P3B-package-v6-2026-10-31.zip` | `b5ddbb48267d97d6946d5a87c9eba98c7a3d9638c59a9ca621f070e8439903a4` |
| 内含 `P4-package-v3-2026-10-30.zip` | `a8f335a38d4d3e8e495724bbdd098f37afb3405970f32c6841ef03bef9746cae` |
