# Review 12 复验清单（M4）

前置：

```text
16b2a42 已在被复验的分支上
交付分支 head 为 7beb6e3 或其后继
```

## 一、代码定位

```bash
git log --oneline -1
git show --stat 16b2a42
```

该提交只应包含：

```text
app/static/js/agent.js
tests/test_agent_console.py
```

## 二、关键代码点

```bash
grep -n "agent-scope-bounded" app/static/js/agent.js
grep -n "scopeText\|boundedText" app/static/js/agent.js
```

必须满足：

```text
1. 卡片无条件渲染（有 job 时），不存在 "if (!view.scope && !view.bounded) return;"
2. 容器带 data-testid="agent-scope-bounded"
3. 缺失时 scopeText / boundedText 均为 "unknown"
4. exceeded === true 显示 "超出边界"
5. exceeded === false 显示 "未超出边界（上限 X，实测 Y）"
6. 任何分支都不输出 "通过"
```

## 三、页面复验

打开：

```text
/agent?job=9247357c54714546a7ff84891f7766f8
```

（179 的最终 P1 job；若页面用别的 id，只要是已 finished 的 job 即可。）

检查：

```text
[ ] diagnostics 区出现「范围与边界」卡片
[ ] 文案为 scope：unknown 与 bounded：unknown
[ ] 页面任何位置没有把 unknown 说成通过
[ ] 控制台无 JS 报错
```

该 job 的 snapshot 顶层确实没有 `scope` / `bounded`，所以看到 unknown 是正确结果，
说明「缺失 → unknown」生效，而不是被隐藏。

## 四、对照测试

```bash
bash run-m2-tests.sh /path/to/binaryrepair-mvp
```

预期（交付分支 `7beb6e3` 实测）：

```text
tests/test_agent_console.py      54
tests/test_agent_honesty.py       9
tests/test_assistant_llm.py      59
tests/test_assistant_tools.py    10
合计                            132 passed, 0 failed
```

关键用例：

```text
test_scope_and_bounded_never_turn_missing_into_pass
test_snapshot_id_is_accepted_as_job_id
test_comparison_is_only_shown_when_the_api_says_available
```

## 五、判定

| 结果 | 结论 |
|---|---|
| 卡片出现、值为 unknown、无「通过」 | Review 12 → PASS |
| 卡片不出现 | FAIL，回到 `16b2a42` 检查 early return |
| 出现值但不是 unknown | FAIL，检查字段读取路径 |
| 任何位置写「通过」 | FAIL，属诚实性缺陷 |

## 六、不要混淆

- Review 12 的 PASS 只表示 **UI 能如实表达 scope/bounded 缺失**；
- 它不代表 scope/bounded 已被证明满足；
- comparison 的 `not_provided` 同理，只是不可用，不是通过。

## 七、56e11ca 上传/下载 UI 的复核

Review 12 之外，M4 还需要看 M1 在 `56e11ca` 新增的上传与下载入口。
M2 已完成代码级复核，结论见 `REVIEW-UPLOAD-UI.md`。

页面检查（同一个 `/agent` 页）：

```text
[ ] 下载面板出现「上传修复文件」按钮与文件选择框
[ ] 未创建 job 时点击上传，提示「尚未创建任务」，不报错
[ ] 选择非 ELF 文件上传，后端返回 400，前端显示「上传失败：…」
[ ] 上传合法 ELF 后显示「已保存：<name>（可下载，不参与验收）」
[ ] 上传产物出现在下载列表，链接形如
    /api/jobs/<job_id>/artifacts/<artifact_id>/download
[ ] 下载得到的字节与上传文件一致（sha256 相同）
[ ] 上传不改变 phase / verdict / obligations
```

最后一条是红线：上传只产生 `operator_deliverable` artifact，永不参与验收。
