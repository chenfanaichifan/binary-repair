# 合并说明（M1）

目标分支：`delivery/all-hands-2026-11-07`
来源分支：`tmp/m2-on-791`，head `34d054c`
增量基线：`791caa319028a42071c7744a0042d147f90d5c6d`

## 方式 A：bundle（推荐）

```bash
cd /path/to/binaryrepair-mvp

# 1. 验证完整性
git bundle verify /path/to/m2-on-791.thin.bundle

# 2. 取回分支
git fetch /path/to/m2-on-791.thin.bundle tmp/m2-on-791:refs/heads/tmp/m2-on-791

# 3. 确认 head
git rev-parse tmp/m2-on-791      # 应为 34d054ce039f3d0e233e45b9297b1c92a1ecadf5

# 4. 切到交付分支后合并
git switch delivery/all-hands-2026-11-07
git merge --no-ff tmp/m2-on-791 -m "merge: M2 T7.6/T7.8/T8.4 + Review 12 UI + comparison UI"
```

预期：无冲突。M2 的 8 个提交只改了下面三个文件：

```text
app/static/js/agent.js
tests/test_agent_console.py
docs/agent-console.md
```

（T8.4 与 Review 12 都在这三个文件内；comparison 也未新增文件。）

## 方式 B：8 个补丁

```bash
git switch delivery/all-hands-2026-11-07
git am /path/to/patches-m2/*.patch
```

补丁基于 `4f512f5`。若交付分支在 `4f512f5` 之后改动过 `agent.js`，
`git am` 可能冲突，此时用 `git am -3` 走三方合并，或退回方式 A。

## 合并后必做

```bash
# 1. 测试
bash run-m2-tests.sh /path/to/binaryrepair-mvp

# 2. 确认关键提交在分支上
git log --oneline -8

# 3. 通知 M4 复验 Review 12
```

## 不要做的事

- 不要 squash 这 8 个提交：M4 需要按提交核对 Review 12 与 comparison 的边界；
- 不要改写 `app/domain/assistant.py`、`app/controller_api.py`、`app/services/assistant.py`：
  这些不属 M2；
- 不要把 bundle 里的 `tmp/m2-on-791` 直接当交付分支推送。

## 冲突时怎么判断

M2 的改动只应出现在：

```text
agent.js          badge / scope-bounded / comparison / attempts 渲染
test_agent_console.py  对应源码级断言
docs/agent-console.md  T8.4 说明
```

若冲突出现在 `controller_api.py`、`assistant.py`、`domain/assistant.py`，
说明不是 M2 的改动，应保留对方版本。
