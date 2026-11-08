# M2 移交包（2026-11-08，r4）

本包把 M2 的全部待移交内容一次交齐：分支、补丁、说明、复验清单、自检脚本。

r2 修订（针对 M4 的四条反馈）：

```text
M2-1  MANIFEST.sha256 改为 LF；全部文本文件统一 LF；zip SHA-256 重算
M2-2  run-m2-tests.sh 不再盲选系统 Python，要求 pydantic >= 2
M2-3  测试口径改为实测 132 passed，并按文件拆分
M2-4  新增 REVIEW-UPLOAD-UI.md，复核 56e11ca 的上传/下载 UI
```

r3 修订（针对 M1 的 head 口径与失败分类要求）：

```text
head 口径   交付分支 head = 7beb6e3，code/evidence freeze = c40b694
            b6d110b 与 5f8efa0d 均不再作为当前交付 head
失败分类   新增 WINDOWS-FAILURES.md：5 个 Windows 失败逐条取证
            （1 个产品缺陷、3 个测试侧 POSIX 依赖、1 个工具缺失）
```

## 包内导航

| 文件 | 干什么 |
|---|---|
| `m2-on-791.thin.bundle` | 增量 git bundle，ref `tmp/m2-on-791`，head `34d054c` |
| `patches-m2/0001..0008.patch` | M2 的 8 个自有提交，可 `git am` |
| `MERGE-INSTRUCTIONS.md` | 两种合并方式，含命令和冲突处理 |
| `REVIEW-12-CHECKLIST.md` | 给 M4 的 Review 12 复验步骤 |
| `REVIEW-UPLOAD-UI.md` | M2 对 56e11ca 上传/下载 UI 的复核结论 |
| `WINDOWS-FAILURES.md` | 5 个 Windows 失败逐条取证与分类 |
| `STATUS.md` | 完成项、提交链、口径红线 |
| `STATE-122.md` | V5 16/16 与 comparison 契约的核验记录 |
| `verify-v5.sh` | 只读核验 V5 与交付清单 |
| `run-m2-tests.sh` | 跑 M2 的测试子集（强制 pydantic >= 2） |
| `MANIFEST.sha256` | 本包文件自校验（LF） |

## 三件事

### 1. 合并代码（M1）

按 `MERGE-INSTRUCTIONS.md` 执行，核心三步：

```bash
git bundle verify m2-on-791.thin.bundle
git fetch ./m2-on-791.thin.bundle tmp/m2-on-791:refs/heads/tmp/m2-on-791
git merge tmp/m2-on-791
```

推荐用 bundle：`git bundle verify` 先验，再 fetch、merge。

### 2. 复验 Review 12（M4）

按 `REVIEW-12-CHECKLIST.md` 执行，关键是看到 `data-testid="agent-scope-bounded"`
且文案为 `scope：unknown` / `bounded：unknown`。

### 3. 复核 V5（任何人）

```bash
bash verify-v5.sh /path/to/binaryrepair-mvp
```

预期三项全 0 missing。

## 运行测试：必须用项目 venv

M2 的测试依赖 `pydantic >= 2`。系统 Anaconda 常带 pydantic 1.x，直接运行会报：

```text
ImportError: cannot import name 'field_validator'
```

正确做法：

```bash
cd /path/to/binaryrepair-mvp
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
bash run-m2-tests.sh /path/to/binaryrepair-mvp
```

已有解释器时显式指定：

```bash
M2_PYTHON=/path/to/venv/bin/python bash run-m2-tests.sh /path/to/binaryrepair-mvp
```

脚本会先探测 `pydantic.VERSION` 主版本，不满足就报错退出，不会回退到 1.x。

## bundle 前置条件

```text
prerequisite: 791caa319028a42071c7744a0042d147f90d5c6d
```

已确认该提交在 `delivery/all-hands-2026-11-07` 的历史中，因此接收方无需额外操作。
若 `git bundle verify` 报 `prerequisite commit not found`，说明本地仓库没有这条历史，
改用 `patches-m2/` 逐个应用。

## 校验本包

```bash
shasum -a 256 -c MANIFEST.sha256
```

预期 18/18 OK，不需要 `tr -d '\r'`。

## 当前状态

```text
M2 分支        tmp/m2-on-791
M2 head        34d054c（8 个提交，相对 4f512f5）
交付分支 head   7beb6e3（M2 的 8 个提交已全部合入；freeze c40b694）
测试           132 passed（4 个文件，见下）
V5             16/16（交付分支已确认）
Review 12      代码就绪；M4 复验后由 M4 定状态
上传/下载 UI   已复核，见 REVIEW-UPLOAD-UI.md
```

测试拆分（交付分支 `7beb6e3`，Windows + 项目 venv 实测）：

```text
tests/test_agent_console.py      54
tests/test_agent_honesty.py       9
tests/test_assistant_llm.py      59
tests/test_assistant_tools.py    10
合计                            132 passed, 0 failed
```
