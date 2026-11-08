# 132 · 最终验证矩阵（2026-11-08）

## 0. 一句话

除 M4 那一行签字外，M2 的全部可验证项已在两个平台、三条取用路径上闭环，
包括之前只在纸面上成立的「r4 bundle 可用」。

## 1. 双平台全量（同一棵树）

| 平台 | 提交 | tree | collected | passed | failed | skipped |
|---|---|---|---|---|---|---|
| Linux（M1） | 1c202cc | 21eb9f7b | 719 | 717 | **0** | 2 |
| Windows（M2） | db814a8 | 21eb9f7b | 719 | 706 | **0** | 13 |

两行是同一棵树（`21eb9f7b…`），所以差异只来自平台门控，不来自代码。

### skip 差额 11 的构成

```text
Linux 2 个    tests/test_fixture_v3_manifest.py x2（非 Linux / 缺候选 ELF）
Windows 13 个 = 10 原有 + 3 本次新增

Windows 独有 11 个：
  6  test_v3_no_input_e2e        skipif os.name == "nt"
  1  integration/test_worker     skipif os.name == "nt"
  1  integration/test_route_bundle_ingest   symlink 不可用
  3  test_mcp_tool_adapters      Linux ELF execution（本次新增）
```

报告时不要把这 13 个写成一个笼统的「环境跳过」：
3 个是本次为 ELF 语义新增的，另 10 个是项目原有的平台门控。

## 2. F5 门控的三种状态都被实测覆盖

| 工具链 | independent-views | manifest rows | 结果 |
|---|---|---|---|
| binutils 完整（Linux） | 5 | 12 | PASS |
| 无 binutils（Windows） | 0 | 7 | PASS |
| 只有部分工具（Linux） | 1 | 8 | **FAIL（门控生效）** |

第三行是关键。如果断言写成 `file_count >= 8`，1 个 view 时 rows 恰好是 8，
就会假通过。现在的 `len(views) in (0, 5)` 让 1–4 一律失败。

## 3. 132 用例集（本次在最终树上复跑）

```text
tests/test_agent_console.py      54
tests/test_agent_honesty.py       9
tests/test_assistant_llm.py      59
tests/test_assistant_tools.py    10
------------------------------------
total                           132   passed 132   failed 0   errors 0   skipped 0
rc = 0
```

跑在 `m2-h` 树上（修复 + 交接材料），不是旧树。

## 4. r4 bundle 的可用性（新增证据）

18/18 只证明字节没变，不证明 bundle 能用。本次补做：

```text
git bundle verify      ... is okay
requires 3 refs        1da22ff / d1ce352 / 791caa3
list-heads             34d054ce039f3d0e233e45b9297b1c92a1ecadf5  refs/heads/tmp/m2-on-791
git fetch <bundle>     [new branch]  tmp/m2-on-791 -> refs/tmp/frombundle  rc=0
resolved               34d054ce039f3d0e233e45b9297b1c92a1ecadf5
8 个 M2 提交可达       missing=0 of 8
```

结论：bundle 不是摆设，能在有 basis 的仓库里真实还原 M2 的全部提交。

## 5. 三条取用路径结果一致

```text
分支    git fetch origin m2-fix-188-windows-gates   → db814a8
am      git am 0001-evidence-and-elf-gates.patch    → 97ba487（M1 实测）
apply   git apply 188-windows-test-fixes.patch      → 同 tree
三者 tree 均 21eb9f7baea2a3d4e86ebc566c3c499f03752c88
```

## 6. 交付面

```text
refs/heads/m2-fix-188-windows-gates   db814a8   只有修复
refs/heads/m2-h                       6f14556   修复 + 交接材料（22/22）
refs/heads/m2-r4                      2838f7e   r4 原样（18/18，bundle 已验证可用）
refs/heads/delivery/all-hands-...     1c202cc   上游，含 187 Review 12 PASS + 189
```

## 7. 还剩什么

```text
1  M4 在 187 里写一行 Review 12 结论 —— 已 PASS，但需要他本人确认这行是他加的
2  （建议）把 189 的 base 描述从 7beb6e3 改为 9c95b55
```

其余全部闭环。没有待我处理的阻塞项。
