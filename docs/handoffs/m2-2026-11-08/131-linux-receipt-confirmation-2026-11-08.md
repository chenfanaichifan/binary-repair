# 131 · 对 189 Linux 回执的确认（2026-11-08）

## 0. 结论

四条全部确认，无异议。r4 的交付阻断已用分支消除，18/18 现在可以不复述任何文件就复现。

## 1. Linux 结果与预期逐项吻合

| 项 | 预期 | 你的实测 | 判定 |
|---|---|---|---|
| 全量 | 719 / 717 / 2 / 0 | 719 / 717 / 2 / 0 | 一致 |
| F5 有 binutils | 5 views → 12 rows | 5 views → 12 rows | 一致（7 + 5） |
| F5 无 binutils | 0 或 1–4 views 必须失败 | 1 view → FAILED | 门控生效 |
| 干净 clone | exit 0 | exit 0 | 一致 |

**你拿到的 1 view 恰好是这条门控存在的理由。**
如果断言写成 `file_count >= 7` 或 `>= 8`，1 个 view 时 rows 是 8，
`file_count >= 8` 会直接放过 —— 那就是假通过。
现在的写法是 `len(views) in (0, 5)` 且 `rows == 7 + len(views)`，
1–4 一律失败。你这条实测正好把「为什么是 0/5 而不是 >=」证完了。

## 2. 一处需要修正的描述：base 不是 7beb6e3

远端实际历史：

```text
1c202cc  docs: record Linux F1-F5 run and Review 12 PASS
97ba487  test: keep evidence bundles pristine and gate ELF cases
9c95b55  docs: decide M2 F1-F5 fixes
7beb6e3  docs: ...
```

- `9c95b55` 是 `1c202cc` 的祖先，188 文档在 `1c202cc` 的树里
- 所以不存在「基于 7beb6e3、绕过 188」的情况，也不需要 rebase

建议把 189 里那句 `Applied ... to source 7beb6e3` 改成 `9c95b55`，
否则后来的人会以为 188 被跳过了。

## 3. 内容一致性：tree 哈希相同

```text
M2 db814a8^{tree}     21eb9f7baea2a3d4e86ebc566c3c499f03752c88
M1 97ba487^{tree}     21eb9f7baea2a3d4e86ebc566c3c499f03752c88
```

两点结论：

1. 补丁逐字节等价，`git apply` / `git am` 两条路径不存在内容差异
2. 我这边的 Windows 结果（719 / 706 / **0 failed** / 13 skipped）与你的
   Linux 结果（719 / 717 / 2 / 0）作用于**同一棵树**，可以直接并列写进验证矩阵

## 4. Review 12：闭环

187 补上了 `Review 12: PASS`，并写明「scope/bounded 缺失 → unknown，
不显示通过，属于 UI honesty，不代表分析通过」。这个口径与实现一致，接受。

## 5. r4 交付：阻断已消除，不需要转发 10.6 MB

远端新增分支：

```text
refs/heads/m2-r4   2838f7efc50d2f9bc140c28008f544d7213a4f88
```

它就是 r4 的 18 个文件原样，含 `m2-on-791.thin.bundle`（10,647,207 B）。

```bash
git fetch origin m2-r4
git checkout m2-r4
sha256sum -c handoff-r4/m2-handoff-2026-11-08/MANIFEST.sha256
# 18 OK
```

我从远端 fetch 回干净工作树实测过：**18 OK / 0 bad**，且字节保持：

```text
MANIFEST.sha256   1957 B  CR=0
run-m2-tests.sh   2889 B  CR=0
README.md         4059 B  CR=0
thin.bundle  10647207 B
```

目录带了 `* -text`。没有它，仓库级 `text=auto` 会把这些文件转成 CRLF，
任何人 clone 下来校验都是 18 个红叉 —— 这一点我在 130 里已经踩过一次。

### 132 的跑法

```bash
git fetch origin m2-r4
git checkout m2-r4
bash handoff-r4/m2-handoff-2026-11-08/run-m2-tests.sh
```

脚本会强制 pydantic ≥ 2，找不到可用解释器时退码 2（不静默用错环境）。

## 6. 现在远端有三个分支

```text
m2-fix-188-windows-gates  db814a8   只有 F1–F5 修复
m2-h                      b401dca   修复 + 交接材料（21/21）
m2-r4                     2838f7e   r4 原样（18/18）
```

按需要取一个即可：只要代码用第一个，要文档用第二个，要严格对齐 r4 用第三个。

## 7. 状态

```text
Linux F1-F5           PASS（你的 1c202cc）
Windows F1-F5         PASS（706 / 0 / 13）
F5 0/5 门控           已被你的 1-view 实测证明有效
Review 12             PASS
r4 18/18              可通过 m2-r4 复现，无需传文件
132 用例集            可通过 m2-r4 + run-m2-tests.sh 执行
```

没有剩余阻塞。唯一还需要注意的是分类账：Windows 的 13 个 skip 里
3 个是本次新增的 ELF 门控，10 个是原有平台门控，报告时不要混成一个数。
