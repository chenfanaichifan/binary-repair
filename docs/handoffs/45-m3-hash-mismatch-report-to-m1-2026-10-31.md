# 给 M1 / Lead：acceptance 的 `expected_sha256` 语义缺陷（hash_mismatch 必现）

日期：2026-10-31
来自：M3
关联：M5 v11 消费结论（`docs/handoffs/44-m3-reply-to-m5-v9-consume-2026-10-31.md` 第 3 节）

---

## 一句话结论

在当前 acceptance 代码里，**任何"真的改变了二进制"的修复候选，在 V0–V5 全部 passed
之后，都会被第 6 步 hash 检查判成 `inconclusive / hash_mismatch`，永远到不了
`success_within_scope`**。这不是 M3/M5 的输入问题，是 `expected_sha256` 的语义
绑错了对象。

---

## 根因（精确到代码）

`app/domain/acceptance.py` `decide_attempt_outcome` 第 178–188 行：

```python
# 6. Evidence must describe the approved artifact. A mismatch means the
#    evidence is about something else, so the claim is unproven.
if expected_sha256 is not None and candidate_sha256 != expected_sha256:
    return Verdict(outcome=Outcome.INCONCLUSIVE,
                   reason=ReasonCode.HASH_MISMATCH, ...)
```

而 `expected_sha256` 的来源链路是：

1. `app/services/orchestration.py` `_run_context`（第 138 行）：
   `"input_sha256": job["original_sha256"]`  ← **原始未修复 hash**
2. 同文件 `evaluate_attempt`（第 166 行）：
   `expected_sha256=body.get("input_sha256")`  ← 把这个原始 hash 当成 expected

所以第 6 步比较的是「修复后候选 hash」vs「原始未修复 hash」，修复必然改变二进制，
两者必然不等 → 永远 `hash_mismatch`。

**语义上应绑定的，是「批准时锁定的候选 hash」（approval 绑定的 artifact），而不是
「原始输入 hash」**。原始 hash 只在 V0 identity 校验里用来证明"修的是同一个 original"，
不该拿来做 candidate 的相等性判据。

---

## 为什么之前 job1/job2 没暴露

job1/job2 里 Route B 的 V2 是 `failed`（15/16），Route A 的 V4 是 `not_run`。两者都在
第 4 步（required failure → REJECTED）或第 5 步（required not_run → INCONCLUSIVE）
**提前返回了**，根本没走到第 6 步 hash 检查。只有当 V0–V5 全部 passed 时才会撞上它。

M5 的 v11 fresh real p2（job `22b49d49`）结果是 `solver_unknown`（V4 unknown），同样是
在第 5 步返回，仍没走到第 6 步。**一旦 Lead 把 V4 判成 passed，下一次 real p2 就会撞上
这个 hash_mismatch。**

---

## 复现 / 证据

- 单测已固化此行为：`tests/integration/test_orchestration.py::test_candidate_hash_mismatch_is_inconclusive`
  （candidate 传 `"9"*64`、expected 传 original → 断言 inconclusive/hash_mismatch）。
- 单测里 `success_within_scope` 的用例，`candidate_sha256` 传的是 `record.original_sha256`
  （原始 hash，而非修复后 hash），才能走通第 6 步 —— 这从侧面印证：当前实现默认
  "candidate == original" 才能 success，与"修复改变二进制"的前提自相矛盾。
- M3 实测：用新候选 208574ab 跑 fresh real p2，V0–V5 全 passed 后 verdict 为
  `inconclusive/hash_mismatch`，报错 `candidate hash 'c4a159…' does not match approved
  hash 'aa428157…'`。

---

## 需要 M1 裁决（二选一，或给出第三种正解）

1. **改语义**：`expected_sha256` 应绑定 approval 时锁定的候选 hash（或 attempt 携带的
   candidate hash），而非 `job.original_sha256`。原始 hash 仅用于 V0 identity 校验。
2. **改数据流**：如果 `expected_sha256` 本意就是"original"，那第 6 步的判据应改为
   "candidate 与 approval 绑定的候选一致"，而不是与 original 比较。

M3 不擅改核心 acceptance 代码，等 M1 的书面结论后再动。

---

## 与本次交付的关系（诚实声明）

- 这个缺陷**不阻塞 v11 交付**——v11 的 V4 证据、V2/V5 supplement 都是有效的。
- 它阻塞的是「V4 判 passed 之后的 `success_within_scope`」这一最终判定。
- 它和 Gate 5（jobwrap 缺 gate5 + GATE5_SCRIPT_SHA256）是**两个独立**的未决项，
  互不掩盖。
