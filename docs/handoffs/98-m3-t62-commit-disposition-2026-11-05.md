# 98 — M3 → Lead：T6.2 提交方式待定（2026-11-05）

**发起人：** M3 · **状态：** 只询问，未提交、未建分支、未动 live-bridge
**一句话：** T6.2 的代码和证据都已就位并通过测试，但落在这条 live-bridge 线上的
样子和你上一条指令里假设的不一样，我不擅自决定提交方式，等你定。

---

## 1. 现在是什么状况

### 已完成且实测的部分

| 步骤 | 结果 |
|---|---|
| 核对 bundle 哈希 | `fb94e8bd85194a612936af389223bfc56deac76dbd1ebc810f916301e44c990d` = 你给的 64 位，**完全一致** |
| 核对大小 | `22366988` bytes，一致 |
| `git bundle verify` | `is okay`，`complete history` |
| bundle 记录的 ref | `refs/heads/integration/live-bridge-2026-11-03` @ `8c77fcdb7813e4d3dec24a8f2eb0f40a9f5dbdb3` |
| `git fetch` | 成功，分支 `integration/live-bridge-2026-11-03` 已建立 |
| `git switch` + 核对 HEAD | **`8c77fcd`**，与你说的一致 |
| 提交 | **零**。HEAD 仍是 `8c77fcd` |

### 当前仓库状态

```
分支   integration/live-bridge-2026-11-03 @ 8c77fcd
工作区 T6.2 文件以「未跟踪」状态存在（未 add、未 commit）
stash  M3 原分支 member-3-route-a 的既有改动已安全存放（stash@{0}）
备份   .tmp/t62-payload/ 共 40 个文件
```

我按你「不要创建新的分支」的指示，已经把先前建的空分支删掉了（零提交，因此无损失）。
现在 `git branch` 只有三条：`main`、`member-3-route-a`、`integration/live-bridge-2026-11-03`。

### 在这条分支上的实测（新做的）

| 测试集 | 结果 |
|---|---|
| `test_broker_executor / conformance / comparison` | **49 passed** |
| `test_jobwrap_routea_source` + `test_v3_oracle` | **57 passed** |
| 分支原有 `test_attempt_from_bundle` + `test_acceptance` | **31 passed（无回归）** |

---

## 2. 六个与预期不符的事实（会直接影响提交决策）

这六条都是我在这条分支上实测出来的，不是推测。

### F1. 这条分支没有 `route-a/jobwrap-gate5/`

`git diff f561542 8c77fcd -- route-a/jobwrap-gate5/` 显示 **726 行全部是删除**，即该目录在
`8c77fcd` 上根本不存在。

**后果：** 我的 C 改动在这里是「整目录新增」，不是「修改」。提交历史里会看到三个新文件，
看不到「在原文件上加了 routea 模式」的 diff。

### F2. 这条分支缺 `v3_oracle.py`

`fixtures/public/CWE121_src_char_declare_cpy_51b/tests/` 在 `8c77fcd` 上只有
`SHA256SUMS` + `valid.json` + `invalid.json`，**没有 `v3_oracle.py`、没有 `test_v3_oracle.py`**。
而 `workers/broker/comparison.py` 和 `test_broker_comparison.py` 都依赖 oracle。

**后果：** 要么把 oracle 一并带进这个目录（我现在就是这么做的，测试才能通过），
要么把 comparison 相关文件从这次提交里拿掉。**这条需要你定。**

注意：该目录的 `SHA256SUMS` 只钉了两个 json 文件，不覆盖代码文件，所以加 oracle
不算破坏冻结；但目录里出现未列在 SHA256SUMS 中的文件，评审时可能被问到。

### F3. 这条分支有 `tools/host_broker.py`，和我的 `workers/broker/` 不是同一层

- `tools/host_broker.py`（M1）：**结果包入库** broker —— 把 attempt 信封导入 controller store，
  成功后触发 worker。
- `workers/broker/`（我）：**任务与操作规划** —— 六个固定 op 的类型化清单、固定 argv 请求构造、
  conformance 判定、对比。

两者不重复，但名字接近。**建议在提交说明里写清分层**，否则容易被误认为第二套实现。

### F4. 记录编号：90 和 92 已被占用

`8c77fcd` 上 `docs/handoffs/` 已用：`80–87`、`90-live-bridge-continuation`、
`92-t6-baseline-migration`。

**空号：** `88`、`89`、`91`、`93`、`94`、`95`、`96`、`97`。

我用的 `95 / 96 / 97` 是空的，`88` 在这条线上也是空的（我在原分支用了 88）。
**请确认这三个编号可用。**

### F5. 这条分支的 `.gitignore` 不忽略 `.tmp/`、`worklogs/`、`dist/`

原分支 `f561542` 的 `.gitignore` 忽略这些；这条分支的**没有**。

**后果：** 任何人在这条分支上执行 `git add -A`，会把 `.tmp/`（里面有那个 22MB 的 bundle）、
`worklogs/`、`dist/`（几十个 zip）、`.dsh-acl-recovery/` 全部扫进提交。

这不是我造成的问题，但**在我把 bundle 放进 `.tmp/` 之后变成了现实风险**。
我建议提交前处理，见 Q5。

### F6. 两条线已经分叉

`git merge-base --is-ancestor f561542 8c77fcd` → 否。
`git diff --stat f561542 8c77fcd` → **560 文件，+49514 / −14646**。

**后果：** 我的工作不是「在 live-bridge 上继续」，而是「把另一条线的成果搬过来」。
所以下面 §3 的问题不是流程细节，而是路线选择。

---

## 3. 需要你回答的六个问题

每条都附我的建议，你回编号 + 同意/改即可。

### Q1. 提交落在哪条 ref？

- **A（我建议）** 由 **M1** 在 `integration/live-bridge-2026-11-03` 上提交，我提供 patch 或文件清单。
  理由：这条是 Lead 的集成分支，提交者与推送者一致，责任链清楚。
- **B** 你自己在这条分支上提交。
- **C** 你再授权我建一条 `member-3/t62-*` 分支（这与你刚才「不要创建新的分支」冲突，需你明确改口）。

### Q2. 整目录新增 `route-a/jobwrap-gate5/` 是否接受？

按 F1，它在这条线上不存在。两个选择：

- **A（我建议）** 接受新增。文件内容就是完整的继任者源码（含 probe + routea 两个模式），
  能编译、能跑、conformance 10/10。
- **B** 只提交 C 文件、不提交 `README.md` / `build-recipe.md` / `routea.conf.sample`，
  避免在这条线上引入一套新文档。

### Q3. `v3_oracle.py` 要不要一并带进 `fixtures/.../tests/`？

- **A（我建议）** 带进去，含 `test_v3_oracle.py`。否则 `comparison.py` 和它的测试在这条分支上
  无法运行，提交里会有一个「存在但跑不了」的模块。
- **B** 不带，同时把 `comparison.py` + `test_broker_comparison.py` + 记录 97 从这次提交移出，
  留到 T7.3 单独处理。

### Q4. 记录编号 95 / 96 / 97 确认可用？（按 F4，这三个号在这条线上是空的）

### Q5. `.gitignore` 差异怎么处理？（按 F5）

- **A（我建议）** 提交前把 `.tmp/`、`worklogs/`、`dist/`、`.dsh-acl-recovery/` 加进这条分支的
  `.gitignore`，作为这次提交的一部分。这样 M1 后续 `git add -A` 不会误吞 22MB bundle 和几十个 zip。
- **B** 不改 `.gitignore`，但要求 M1 推送时只用明确 pathspec（不许 `add -A`）。风险靠纪律兜。
- **C** 我把 bundle 移出仓库目录，`.tmp/` 里其余内容不管（仍有 dist/ 风险）。

### Q6. 提交信息用我起草的那份吗？

已写好：**`.tmp/t62-commit-message.txt`**（76 行）。要点：

- 说明 routea 模式是「继任者加模式」，不是重建丢失源码（Lead 72 path 4）
- 记录实测数据：conformance 10/10、V3 原始 4/6 → 候选 6/6、T73 三路对比
- 明确声明 `/usr/local/sbin/jobwrap`（`b232d60b…`）与 `jobwrap-gate5`（`0066973d…`）**未被替换**
- 列出五个「这不能证明什么」（不是 Gate 6、未跑 V4、公开样本、无 Route B 候选、job 目录 0777）
- 钉住三个证据包 `SHA256SUMS` 的哈希

需要我按你的裁决改哪几段，说一声。

---

## 4. 我没有做、也不会擅自做的事

- 没有提交，没有 `merge`，没有打 tag
- 没有新推任何 ref；`integration/live-bridge-2026-11-03` 保持 `8c77fcd` 原样
- 没有新建任何分支（先前那个空分支已删除）
- 没有动 `member-3-route-a`（原改动在 stash 里）
- 没有改任何人的文件（`tools/host_broker.py`、`app/`、`docs/handoffs/80–87/90/92` 一律未触碰）

## 5. 附：待提交文件清单与哈希（供你核对）

```
route-a/jobwrap-gate5/jobwrap_gate5.c        2f15b5ceefbf8bd14ab8e1da4fdfc3939315d14337916f48f0294fbd1d7e3e8f
route-a/jobwrap-gate5/routea.conf.sample     889f9cd3d3da150fe759f7b7e7e94ed8b99ea13c9013f4c10f7ae2e29ca77318
workers/broker/operations.py                 aa1eb8a10aa0cfcbe9ecb60f034f9269f652128836eabc11e26a960248e02627
workers/broker/task_request.py               81771a2434343231373b2a010d5f01c6114d6a53115d35ba7e11cfcb8ec072bd
workers/broker/conformance.py                bef6a4ea62d8e30768a15ccac46678b8fedbde56e6c289a42587afe5f2febbf5
workers/broker/guest_conformance.py          4b22ab8585ca93c4ae46db43980ac8a1cf07b77bad29582f8ba4f8ae802ab15e
workers/broker/guest_behaviour.py            547eb4c2588f820f79ffc6c16c636800956c65dbfd0825246dfa616a82c5ef7f
workers/broker/comparison.py                 20257bb63bbcd4d7e7c4ee0d07ff93a6a43e7b19361b3b8536967d2fa14cc128
```

**可复现性说明：** 上文 conformance 用的二进制是 `293df727636e800d1735443e9ca82cf62add85ccd52d6c93c482b29dd6c128bc`
（在 guest 内 `gcc -O2 -Wall -Wextra -Werror -static` 编出，退出码 0、零警告），
源码即上表第一行的 `jobwrap_gate5.c`。任何人重编译应得到同一哈希（同 gcc 版本 13.3.0）。

## 6. 一个必须说明的边界

conformance（10/10）、V3（4/6 → 6/6）、T73 三路对比这三组**实测**，是在
`member-3-route-a` 那条线的工作树上做的，证据包随这次提交带入。

证据本身与分支无关（是 guest 里跑出来的字节级记录，哈希可校验），但**这条分支上没有重跑 guest**。
如果你要求「在这条分支上重跑一遍再提交」，说一声，我按同样的流程在 guest 里重做一次，
大约需要一次编译 + 两次观测（约 5 分钟）。

---

*M3 · 2026-11-05 · 未提交，等裁决*
