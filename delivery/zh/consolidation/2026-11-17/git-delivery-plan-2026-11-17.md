# 06 — GitHub 交付与痕迹清理方案（只调查，**未执行**）

- 作者：第 6/6 号协作子 Agent
- 时间：2026-11-17（Asia/Singapore）
- 范围：远端 refs 全量分类、基线选择、应纳入文件、删除清单、备份、执行序列、验收与回滚、诚实边界
- 本文件**没有**执行任何 `push / delete / commit / branch -d / tag -d`；所有命令均为待批准方案
- 证据约定：`session:<id>#seq=<n>` 指会话事件序号；`binary-repair@<sha> path:line` 指提交内文件

---

## 0. 摘要（TL;DR）

1. **不能**把 `final/consolidated-2026-11-16`（`c0f9feb`）当作最终分支基线。它在 `f1bb1f4` 之上只加了 P31–P34 两个提交，**完全不含 Phase-8D**：`git diff a1d7150 c0f9feb` = 161 文件、`-76859` 行，删掉了 `app/services/acceptance_2.py`、`promotion_gate.py`、`metamorphic_discovery.py`、`phase8d_gap_registry.py`、全部 `tests/test_phase8d_*.py` 与 `artifacts/phase8d-*`。
2. 当前**内容最全**的 tip 是 `a1d7150`（`release/2026-11-17-phase8d-final-evidence`）：含 Phase-8D → CI 修复 → 8D 文档 → P31–P34 → 全量测试记录 → final gate 13/13 证据。建议新分支基线取 `a1d7150`。
3. `bdd3f84`（`release/2026-11-17-phase8d-evidence`）与 `a1d7150` **不是超集关系**：前者独有 9 个路径（`artifacts/release-gate-2026-11-17-phase8d/**` + `docs/release-phase8d-final-evidence-2026-11-17.md`）。新分支必须把这 9 个路径补进去。
4. `a0e6a24`（`worktree-feature-final` 的 detached HEAD）是**本地唯一未推送 commit**，但它与 `e01fc9e`/`a9db731` 的 **patch-id 完全相同**（`2841ba1c…`），属被取代的重复实现，**没有独有内容会丢失**。
5. 上一轮 CONSOLIDATION 自称"删除 23 分支 + 14 标签、会话相关残留 0"（`binary-repair@a1d7150 delivery/zh/consolidation/CONSOLIDATION-2026-11-16.md:75`）——**已过时**：`workbench-v3`、`feature/ai-binary-repair` 在 11-17 00:24 被重新创建，另新增 4 个 `release/*` 与 `phase8d-open-world`。相对 11-16 12:20 备份：**+6 heads、+6 tags（+12 解引用行）、-0**。
6. `workbench-v3` 是 **CI 触发分支**：`binary-repair@a1d7150 .github/workflows/ci.yml:5`（`branches: [main, workbench-v3]`）与 `.github/workflows/ubuntu-verify.yml:6`（`branches: [workbench-v3]`）。删它等于断掉 Ubuntu 验证触发路径 → 建议**保留并重指向新 HEAD**，而非删除。
7. 仓库是 **public**（`private:false`），已累计 **170** 次 Actions run，**0 个 open PR、11 个 closed PR**（`refs/pull/*` 永久残留）。删 ref 不等于删对象、不等于删 CI 记录——见第 9 节。
8. `binary-repair-gui` 工作树 **41 项脏改动**（把 `llm_gateway/*` 暂存删除又留成 untracked，半途 revert）。任何清理动作前**必须先备份该工作树**，否则会丢未提交改动。

---

## 1. 现状事实（已核验）

### 1.1 远端

| 项 | 值 | 证据 |
|---|---|---|
| 仓库 | `git@github.com:chenfanaichifan/binary-repair.git` | `git remote -v` |
| 可见性 | **public** | `GET /repos/chenfanaichifan/binary-repair` → `"private": false, "visibility": "public"` |
| 默认分支 | `main` | `git ls-remote --symref origin HEAD` → `ref: refs/heads/main`；API `default_branch: main` |
| heads | **97** | `git ls-remote --heads origin \| wc -l` |
| tag 行 / 真实 tag | **101 行 / 71 个**（30 行是 `^{}` 解引用） | `git ls-remote --tags origin` |
| 最新 push | 2026-11-16T17:26:02Z（= 11-17 01:26 +0800，即 `a1d7150`） | API `pushed_at` |
| Actions run | **170**；最近 `43907137267` on `workbench-v3`，`push / completed / success` | API `/actions/runs?per_page=5` |
| open PR | **0** | API `/pulls?state=open` |
| closed PR | **11**（#2–#11 等，多数 merged） | API `/pulls?state=closed` |
| 分支保护 | **未知**（API 需认证，返回 401） | `GET /branches/main/protection` |

`git ls-remote` 与本地 remote-tracking ref 逐一比对：**97/97 完全一致，无 stale ref**，因此本地对象库可安全用于离线核验与备份。

### 1.2 本地

| 项 | 值 |
|---|---|
| 本地分支数 | 107 |
| 全部 refs（含 tag/remote） | 280 |
| `.git` 体积 | 157 MB（objects 154 MB，4 个 pack） |
| 仓库工作树 | 160 MB |
| worktree 列表 | `binary-repair`(`member-5-deepseek-schema` 221e47c)、`binary-repair-gui`(`c0f9feb`，**脏 41**)、`worktree-p31-ci`(`d37bfad` detached，干净)、`worktree-p31-final`(`c0f9feb`，干净)、`worktree-feature-final`(`a0e6a24` detached，干净)、另有 2 个 `.agents/worktrees/` |
| 11-16 备份 | `backup/binary-repair-mirror-2026-11-16.git` 119 MB、`local-refs-2026-11-16.bundle` 119 MB、`remote-refs-2026-11-16.txt` 192 行、`SHA256SUMS` |

### 1.3 三条线的分叉结构（文字图）

```
f1bb1f4  2026-11-16 12:19  ops(backup) … ← 11-16 备份时 final/consolidated-2026-11-16 的指向
│         （merge-base of c0f9feb 与 d37bfad）
├── a9db731 ── c0f9feb      final/consolidated-2026-11-16   ← 只有 P31–P34，无 Phase-8D
│
└── d1b73bf ── 78edb97 ── 996060d ── e01fc9e ── 13d3c1d ── b896f1b ── d37bfad ── a1d7150
    Phase-8D    CI修复    8D文档     P31–P34    测试记录    测试记录    全量记录    final evidence
                                                                        │
                                                                        └─ bdd3f84（挂在 996060d 上，另一条 evidence 支线）

a1755a5 ── a0e6a24          worktree-feature-final（本地唯一未推送；patch-id 同 e01fc9e）
```

关键判定（全部实测）：

| 判定 | 命令 | 结果 |
|---|---|---|
| `c0f9feb` 是 `d37bfad` 祖先？ | `git merge-base --is-ancestor c0f9feb d37bfad` | **否** |
| `d37bfad` 是 `a1d7150` 祖先？ | 同上 | **是** |
| `a0e6a24` 在任何远端分支/tag 上？ | `git branch -r --contains` / `git tag --contains` | **都没有** |
| `a0e6a24` 是 `d37bfad` 祖先？ | `git merge-base --is-ancestor` | **否**（仅 1 个 commit 不在其历史中，父 `a1755a5` 在） |
| 三个 P31–P34 commit 是否同一补丁 | `git show C \| git patch-id --stable` | `a9db731`=`e01fc9e`=`a0e6a24`=`2841ba1c021b661a049698c0baae92855adef30c` |
| `a1d7150` vs `c0f9feb` 差异 | `git diff --shortstat a1d7150 c0f9feb` | 161 files, +2360, **-76859** |

---

## 2. 基线选择：为什么是 `a1d7150`

| 候选 | 含 Phase-8D | 含 P31–P34 | 含 final gate 13/13 | 结论 |
|---|---|---|---|---|
| `c0f9feb` `final/consolidated-2026-11-16` | ❌ | ✅ | ❌ | **不可用**（名为 consolidated，实为最旧的一条） |
| `d37bfad` `workbench-v3`/`feature/ai-binary-repair`/`release/…-final` | ✅ | ✅ | ❌ | 可用，但被 `a1d7150` 严格包含 |
| **`a1d7150`** `release/…-final-evidence` | ✅ | ✅ | ✅ | **推荐基线** |
| `bdd3f84` `release/…-evidence` | ✅ | ❌ | 部分（另一 gate 目录） | 需合并，不作基线 |
| `a0e6a24` 本地 | 否（基线 `a1755a5`） | ✅（同 patch） | ❌ | 不采用；仅备份 |

**为什么不是 `c0f9feb`**：它是 11-16 12:19（Phase-8D 尚未存在）的分支上继续加 P31–P34 的产物。11-17 00:05 提交时，Phase-8D 已在另一条线（`d1b73bf`，22:40 之后）落地，但该分支没有回合。所以它既不是"最新"，也不是"最全"。

**旁证（会话一末尾的卡死直接解释了这个分叉）**：会话一在 turn 36 以**完全相同的参数**连续轮询后台 job `bash-3a95be9b94f24972` 三次（`session:879cc62f#seq=19946`、`#seq=19953`、`#seq=19960`，参数均为 `{"job_id":"bash-3a95be9b94f24972","wait":true,"timeout_ms":1800000}`），该 job 是 80 次循环轮询 `workbench-v3` 上 `d37bfad` 的 Actions run（注册于 `#seq=19940`）；随后系统注入"你正在重复完全相同的工具调用"（`#seq=19967`）。它最后一条动作是 `git push origin HEAD:final/consolidated-2026-11-16`（`#seq=19978`，命令里先 `git merge-base --is-ancestor c0f9feb HEAD` 探测）。由于 `c0f9feb` **不是** `d37bfad` 的祖先，该推送必然被非快进拒绝 —— 这正是该分支至今停在缺 Phase-8D 的 `c0f9feb` 的原因，也说明**不存在**"已推送但未收尾"的 8D 内容（8D 全在 `d37bfad`/`a1d7150` 线上，已推送）。

**为什么不是 `d37bfad`**：`a1d7150` = `d37bfad` + 1 个 evidence 提交（`phase-8D final mainline evidence: d37 gate 13/13 with require policy`），后者是"最终证据"，丢掉它等于丢掉 13/13 的书面结论。

**为什么还要合并 `bdd3f84`**：两者各自新增 3 个文件、删除 42 个文件中的旧 gate 目录，但**新增路径不同**（`phase8d` vs `phase8d-final`）。`a1d7150` 树内**不存在** `artifacts/release-gate-2026-11-17-phase8d/`，需要从 `bdd3f84` 取回 9 个路径。

**`a0e6a24` 的处理**：patch-id 相同 → 内容重复，**不 cherry-pick**。但它是"唯一未推送 commit"，应在备份 bundle 中保留，并在新的 refs manifest 中登记，避免以后有人误以为丢了工作。

---

## 3. 远端 refs 全量分类

### 3.1 分类口径

| 代号 | 含义 | 数量 |
|---|---|---|
| `HIST` | 2026-11-12 及以前的 M1–M5 / v1.2.1 历史线（两个重点会话**未**在这些 ref 上推进） | 90 |
| `S1` | 会话一 `879cc62f` 创建或推进 | 3（`workbench-v3`、`feature/ai-binary-repair`、`final/consolidated-2026-11-16` 的推进） |
| `S2` | 会话二 `b139b586` 创建 | 4（`phase8d-open-world`、`release/2026-11-17-phase8d-{evidence,final,final-evidence}`） |
| `PREV` | 上一轮 791a 整合产生 | 1（`final/consolidated-2026-11-16` 的创建，与 S1 共用） |

归属证据：
- 会话一日志出现 `workbench-v3` 2656 次、`feature/ai-binary-repair` 1232 次、`final/consolidated-2026-11-16` 85 次；`release/2026-11-17-*` **0 次**。
- 会话二日志出现 `workbench-v3` 3640 次、`phase8d-open-world` 975 次、`release/2026-11-17-phase8d-*` 合计 200+ 次。
- 相对 11-16 12:20 备份，新增的 heads 恰为上述 6 个（`comm -13` 差集），**被删除的 heads = 0**；新增 tag 行 12 条（6 个 annotated tag），被删除 = 0。

### 3.2 heads 全量表（97 行）

| # | ref (heads) | sha | 提交时间 | 归属 | 建议 |
|---:|---|---|---|---|---|
| 1 | `member-5/latest` | `a29d217` | 2026-10-20 | HIST | 保留 |
| 2 | `member-4-verification` | `9c6e1f7` | 2026-10-22 | HIST | 保留 |
| 3 | `member-5/gate3-m5-crossinput` | `3c48288` | 2026-10-22 | HIST | 保留 |
| 4 | `member-5/gate3-v3-addendum` | `3ba7020` | 2026-10-29 | HIST | 保留 |
| 5 | `member-5/t5-gaps` | `78a0097` | 2026-10-29 | HIST | 保留 |
| 6 | `member-5/interface-main` | `2c57057` | 2026-10-29 | HIST | 保留 |
| 7 | `integration/consolidation-2026-10-29` | `604d49d` | 2026-10-29 | HIST | 保留 |
| 8 | `member2-backend-adapter` | `0118a38` | 2026-10-29 | HIST | 保留 |
| 9 | `member-5/handoff-converter` | `78a895d` | 2026-10-29 | HIST | 保留 |
| 10 | `member-5/m3-execution-paths` | `815d4f8` | 2026-10-29 | HIST | 保留 |
| 11 | `member-5/p3b-status` | `b641683` | 2026-10-29 | HIST | 保留 |
| 12 | `member-5/p3b-fixed-c` | `df16c1d` | 2026-10-29 | HIST | 保留 |
| 13 | `member-5/interface-v1-final` | `11e39a4` | 2026-10-29 | HIST | 保留 |
| 14 | `member-5/fixed-c-existing-imports` | `b24da7a` | 2026-10-29 | HIST | 保留 |
| 15 | `member-5/gate5-jobwrap` | `9339b66` | 2026-10-29 | HIST | 保留 |
| 16 | `backup/main-before-restore-11e39a4` | `b8a944d` | 2026-10-29 | HIST | 保留 |
| 17 | `backup/main-before-restore-b8a944d` | `b8a944d` | 2026-10-29 | HIST | 保留 |
| 18 | `member-5/interface-reconcile` | `b8a944d` | 2026-10-29 | HIST | 保留 |
| 19 | `member-5/p3b-v2-review` | `de9244f` | 2026-10-29 | HIST | 保留 |
| 20 | `member-5/main-restore` | `6c843bf` | 2026-10-29 | HIST | 保留 |
| 21 | `member-5/p4-cli-b` | `5b7b711` | 2026-10-29 | HIST | 保留 |
| 22 | `member-5/df16-align` | `9b07fa7` | 2026-10-29 | HIST | 保留 |
| 23 | `member-5/independent-witness` | `ffca9a0` | 2026-10-29 | HIST | 保留 |
| 24 | `member-5/p4-cli-b-docs` | `328d355` | 2026-10-29 | HIST | 保留 |
| 25 | `member-5/docs-44-fix` | `cf2f46d` | 2026-10-29 | HIST | 保留 |
| 26 | `member2/i18n-cleanup` | `24d19f5` | 2026-10-29 | HIST | 保留 |
| 27 | `member2/witness` | `be3bb09` | 2026-10-29 | HIST | 保留 |
| 28 | `member-5/pr10-test-fix` | `691c7b2` | 2026-10-29 | HIST | 保留 |
| 29 | `member-5/p3b-v3-adapter` | `c9dd8d3` | 2026-10-29 | HIST | 保留 |
| 30 | `member-5/gate4-observed` | `f5c36f1` | 2026-10-29 | HIST | 保留 |
| 31 | `member2/f5-export` | `9e99895` | 2026-10-29 | HIST | 保留 |
| 32 | `member2/demo-pack` | `aab9cb1` | 2026-10-29 | HIST | 保留 |
| 33 | `member-5/p3b-log-hash` | `add0871` | 2026-10-29 | HIST | 保留 |
| 34 | `member-5/pr10-p2-strict` | `34a2f2f` | 2026-10-29 | HIST | 保留 |
| 35 | `integration/consolidation-final-2026-10-29` | `aab162a` | 2026-10-29 | HIST | 保留 |
| 36 | `release/m2-consolidated-2026-10-29` | `4cb1750` | 2026-10-29 | HIST | 保留 |
| 37 | `member2/witness-main` | `b6c3365` | 2026-10-29 | HIST | 保留 |
| 38 | `member2/fix-gate4-record-4cb1750` | `3efa826` | 2026-10-30 | HIST | 保留 |
| 39 | `member-5/evidence-upload` | `012cdb1` | 2026-10-30 | HIST | 保留 |
| 40 | `member-5/v9-supplements` | `1943ae8` | 2026-10-31 | HIST | 保留 |
| 41 | `fix/expected-sha256-approved-candidate` | `9407dfc` | 2026-10-31 | HIST | 保留 |
| 42 | `member-5/gate4-observed-64` | `99db9c9` | 2026-10-31 | HIST | 保留 |
| 43 | `member-5/gate4-v6-2` | `cdb6b72` | 2026-10-31 | HIST | 保留 |
| 44 | `integration/exact-head-2026-10-31` | `187ad6b` | 2026-10-31 | HIST | 保留 |
| 45 | `member-5/lf-sums` | `a24bbbf` | 2026-10-31 | HIST | 保留 |
| 46 | `member-5/v4-line` | `52062b1` | 2026-10-31 | HIST | 保留 |
| 47 | `member-5/gate4-pass` | `4134065` | 2026-10-31 | HIST | 保留 |
| 48 | `member-5/carry-75b` | `309970a` | 2026-10-31 | HIST | 保留 |
| 49 | `member-5/gate5-conditional` | `ae89b39` | 2026-10-31 | HIST | 保留 |
| 50 | `member-5/board-76` | `d86f539` | 2026-10-31 | HIST | 保留 |
| 51 | `member-5/gate5-pass2` | `bf1fb54` | 2026-10-31 | HIST | 保留 |
| 52 | `member-5/mvp-candidate` | `b505f90` | 2026-10-31 | HIST | 保留 |
| 53 | `lead/consolidation-verified-64c6f3eb` | `ee85012` | 2026-10-31 | HIST | 保留 |
| 54 | `member-5/gate5b-record` | `27d6260` | 2026-10-31 | HIST | 保留 |
| 55 | `member-5/gate5b-boundary` | `44ed925` | 2026-10-31 | HIST | 保留 |
| 56 | `member-5/gate5b-probe` | `06a417e` | 2026-10-31 | HIST | 保留 |
| 57 | `lead/approval-records-2026-10-31` | `5be0e70` | 2026-10-31 | HIST | 保留 |
| 58 | `member-3-route-a` | `f561542` | 2026-10-31 | HIST | 保留 |
| 59 | `backup/main-before-refresh-472aa94-2026-11-12` | `472aa94` | 2026-11-03 | HIST | 保留 |
| 60 | `post-final/worker-executor-env` | `63b6eb8` | 2026-11-03 | HIST | 保留 |
| 61 | `post-final/m5-adapter-env` | `a9196d9` | 2026-11-03 | HIST | 保留 |
| 62 | `post-final/host-importer-broker` | `1da22ff` | 2026-11-03 | HIST | 保留 |
| 63 | `member-3/t62-host-safe` | `472b26e` | 2026-11-05 | HIST | 保留 |
| 64 | `member-5/complete-m5` | `4c36898` | 2026-11-05 | HIST | 保留 |
| 65 | `integration/live-bridge-2026-11-03` | `e231777` | 2026-11-05 | HIST | 保留 |
| 66 | `integration/live-bridge` | `7817a20` | 2026-11-06 | HIST | 保留 |
| 67 | `m5/elf-type-check` | `a63f80d` | 2026-11-06 | HIST | 保留 |
| 68 | `canonical/m1-m5-integration` | `3a107ab` | 2026-11-06 | HIST | 保留 |
| 69 | `delivery/t83-2026-11-06` | `df99853` | 2026-11-06 | HIST | 保留 |
| 70 | `m3/cwe122-fixture-build` | `79cd4f9` | 2026-11-06 | HIST | 保留 |
| 71 | `m3/cwe416-v3-noinput` | `eb60468` | 2026-11-07 | HIST | 保留 |
| 72 | `m5/t83-deliverables-2026-11-07` | `cdcbb4a` | 2026-11-07 | HIST | 保留 |
| 73 | `m1/t30-acceptance-ab-2026-11-05` | `101d034` | 2026-11-07 | HIST | 保留 |
| 74 | `m2-fix-188-windows-gates` | `db814a8` | 2026-11-08 | HIST | 保留 |
| 75 | `m2-r4` | `2838f7e` | 2026-11-08 | HIST | 保留 |
| 76 | `m2-h` | `5b5e71b` | 2026-11-08 | HIST | 保留 |
| 77 | `m1-gui-comparison-route` | `937650b` | 2026-11-08 | HIST | 保留 |
| 78 | `m2-comparison-ui` | `ff87cea` | 2026-11-08 | HIST | 保留 |
| 79 | `m2/v1.2.0-upload-gate` | `1cb2489` | 2026-11-09 | HIST | 保留 |
| 80 | `v1.2.0-source` | `60c4aab` | 2026-11-09 | HIST | 保留 |
| 81 | `m2/assistant-key-ui` | `a2eae2b` | 2026-11-09 | HIST | 保留 |
| 82 | `release/v1.2.0` | `e3a6cba` | 2026-11-09 | HIST | 保留 |
| 83 | `integration/final-2026-11-06` | `99ad6ee` | 2026-11-10 | HIST | 保留 |
| 84 | `release/v1.2.1-handoff-2026-11-09` | `5196e35` | 2026-11-10 | HIST | 保留 |
| 85 | `release/v1.2.1-candidate-2026-11-11` | `612510d` | 2026-11-11 | HIST | 保留 |
| 86 | `release/v1.2.1` | `fe7cf79` | 2026-11-11 | HIST | 保留 |
| 87 | `m3/review-key-store-2026-11-09` | `ae97984` | 2026-11-11 | HIST | 保留 |
| 88 | `delivery/all-hands-2026-11-07` | `3f2bcba` | 2026-11-11 | HIST | 保留 |
| 89 | `integration/main-refresh-2026-11-12` | `8869b07` | 2026-11-12 | HIST | 保留 |
| 90 | `main` | `8869b07` | 2026-11-12 | HIST | 保留 |
| 91 | `final/consolidated-2026-11-16` | `c0f9feb` | 2026-11-17 | PREV+S1 | 删除（缺 Phase-8D，被新分支取代） |
| 92 | `phase8d-open-world` | `996060d` | 2026-11-17 | S2 | 删除（已打 tag） |
| 93 | `feature/ai-binary-repair` | `d37bfad` | 2026-11-17 | S1 | 删除（内容已被新分支包含） |
| 94 | `release/2026-11-17-phase8d-final` | `d37bfad` | 2026-11-17 | S2 | 删除（已打 tag） |
| 95 | `workbench-v3` | `d37bfad` | 2026-11-17 | S1 | 留存·CI触发分支，重指向新 HEAD |
| 96 | `release/2026-11-17-phase8d-evidence` | `bdd3f84` | 2026-11-17 | S2 | 删除（已打 tag） |
| 97 | `release/2026-11-17-phase8d-final-evidence` | `a1d7150` | 2026-11-17 | S2 | 删除（已打 tag，内容进新分支） |

### 3.3 会话相关 tags（6 个，全部 annotated）

| tag | 类型 | 指向 | 归属 | 建议 |
|---|---|---|---|---|
| `release-2026-11-17-phase8d` | tag | `996060d` | S2 | 记录后删除 / 或保留 |
| `release-2026-11-17-phase8d-evidence` | tag | `bdd3f84` | S2 | 同上 |
| `release-2026-11-17-phase8d-final` | tag | `d37bfad` | S2 | 同上 |
| `release-2026-11-17-phase8d-final-evidence` | tag | `a1d7150` | S2 | 同上 |
| `phase8d-frozen-phase8c-release` | tag | `4a7b235` | S2 | 同上（8C 冻结锚点） |
| `phase8d-frozen-phase8c-evidence` | tag | `ec503e4` | S2 | 同上 |

其余 65 个真实 tag 属 `HIST`（`archive/2026-10-22/*` 37 个、`controller-*`、`mvp-*`、`m1-pr10-*`、`v1.2.1-*` 等），**不在本轮清理范围**。完整清单见 `backup/remote-refs-2026-11-16.txt` 与待生成的 `remote-refs-2026-11-17.txt`。

---

## 4. 应纳入新分支的文件

### 4.1 代码/证据（来自既有提交，无需新写）

| 来源 | 内容 | 动作 |
|---|---|---|
| `a1d7150` | Phase-8D 全部实现与 `artifacts/phase8d-*-2026-11-17/`（14 个目录）、`artifacts/p31-p34-2026-11-16/`、`docs/acceptance/p25-p34*`、`docs/release-phase8d-final-mainline-evidence-2026-11-17.md`、`artifacts/release-gate-2026-11-17-phase8d-final/**` | 基线自带 |
| `bdd3f84` | `artifacts/release-gate-2026-11-17-phase8d/{README.md,SHA256SUMS,freeze.json,gate.json}` 与 `…/phase8d-gate-evidence/{同 4 文件}`、`docs/release-phase8d-final-evidence-2026-11-17.md`（共 9 路径） | `git checkout bdd3f84 -- <9 paths>` |
| `a1d7150` 已有 | `delivery/zh/consolidation/` 5 份 11-16 文档（总报告 166009 B 与工作区文件 SHA256 相同 `db5df30d…`） | 保留并归档 |

### 4.2 本轮新增文档（Lead 汇总后写入）

| 目标路径（仓库内） | 来源 |
|---|---|
| `delivery/zh/consolidation/2026-11-17/PROJECT-MASTER-REPORT-2026-11-17.md` | Lead 合成的总报告（工作区同名文件） |
| `…/2026-11-17/01-session1-linux-vm.md` … `06-git-delivery-plan.md` | `review/2026-11-17/` 六份子报告 |
| `…/2026-11-17/CONSOLIDATION-2026-11-17.md` | 本轮整合过程 + 执行结果 |
| `…/2026-11-17/refs-manifest-2026-11-17.txt` | **删除前**全量 refs（ref、SHA、归属、删除理由）——保证"删了也能查" |

### 4.3 不得纳入

- `binary-repair-gui` 的 41 项脏改动（半途 revert，`llm_gateway/*` 暂存删除又 untracked）。这是**未收尾状态**，不是成果；应只备份为 patch。
- 任何 `results-portal/`、`.tmp/`、`handoff/` 下的临时产物（工作区级，未在仓库跟踪）。
- 任何密钥：仓库为 **public**，提交前须跑敏感串扫描（见 7.4）。

---

## 5. 删除 / 保留清单

### 5.1 建议删除（7 个 heads + 6 个 tags，全部有备份与 manifest）

| ref | 当前 SHA | 理由 | 风险 |
|---|---|---|---|
| `feature/ai-binary-repair` | `d37bfad` | 与 `workbench-v3`、`release/…-final` 三指向同一 SHA，纯冗余 | 低（内容进新分支） |
| `release/2026-11-17-phase8d-final` | `d37bfad` | 同上 | 低 |
| `release/2026-11-17-phase8d-final-evidence` | `a1d7150` | 新分支基线的旧壳 | 低 |
| `release/2026-11-17-phase8d-evidence` | `bdd3f84` | 内容（9 路径）已并入新分支 | 低 |
| `phase8d-open-world` | `996060d` | 已被 `a1d7150` 包含 | 低 |
| `final/consolidated-2026-11-16` | `c0f9feb` | **缺 Phase-8D**，与 `final/consolidated-2026-11-17` 语义冲突，保留会误导 | 中：上一轮文档曾建议把它设为默认分支 |
| 6 个 11-17 tag | 见 3.3 | 用户要求清痕迹 | 中：tag 是发布锚点，删除后只能从 mirror 恢复 |

### 5.2 建议保留

| ref | 理由 |
|---|---|
| `main`（`8869b07`） | GitHub 默认分支，不可删；本轮不动 |
| **`workbench-v3`** | `ci.yml`/`ubuntu-verify.yml` 的 push 触发分支；**重指向**到新 HEAD 以保留 CI 能力 |
| 90 个 `HIST` refs | 早于两个重点会话，不属"它们的痕迹"；删除会破坏 M1–M5/v1.2.1 审计链 |
| `final/consolidated-2026-11-17`（新建） | 本轮交付分支 |

### 5.3 tag 的折中建议

优先执行"**记录后删除**"：把 6 个 tag 的 name/type/target/annotated-object SHA 写进 `refs-manifest-2026-11-17.txt` 并提交到新分支，再从远端删除。若用户更看重发布可追溯性，则**只删 4 个 `release-2026-11-17-*`，保留 2 个 `phase8d-frozen-phase8c-*`**（后者是 8C 基线冻结锚点，与 8D 交付无冲突）。

---

## 6. 备份方案（先备份，后动刀）

目标：把"删除前"的完整状态固化到 `WORKSPACE/backup/*-2026-11-17*`，与 11-16 同构。

```bash
set -euo pipefail
W="${WORKSPACE:?set WORKSPACE to the project root}"
B="$W/backup"
R="$W/binary-repair"
STAMP=2026-11-17

# 1) 远端 refs 快照（删除前）
git -C "$R" ls-remote origin > "$B/remote-refs-$STAMP.txt"

# 2) mirror（含全部 branch/tag/commit 对象）
git clone --mirror git@github.com:chenfanaichifan/binary-repair.git \
  "$B/binary-repair-mirror-$STAMP.git"

# 3) 本地全 refs bundle（含仅本地的 a0e6a24 与 107 个本地分支）
git -C "$R" bundle create "$B/local-refs-$STAMP.bundle" --all

# 4) GUI 工作树未提交改动（41 项）——防止清理时丢失
git -C "$W/binary-repair-gui" diff HEAD --binary > "$B/gui-worktree-dirty-$STAMP.patch"
git -C "$W/binary-repair-gui" ls-files -o --exclude-standard \
  > "$B/gui-worktree-untracked-$STAMP.txt"

# 5) 校验和
cd "$B"
shasum -a 256 \
  "local-refs-$STAMP.bundle" "remote-refs-$STAMP.txt" \
  "gui-worktree-dirty-$STAMP.patch" "gui-worktree-untracked-$STAMP.txt" \
  > "SHA256SUMS-$STAMP"
# mirror 目录本身另存一份树级摘要（可选）
git -C "binary-repair-mirror-$STAMP.git" for-each-ref \
  --format='%(objectname) %(refname)' | LC_ALL=C sort \
  > "mirror-refs-$STAMP.txt"
```

验收：

```bash
git -C "$B/binary-repair-mirror-$STAMP.git" for-each-ref | wc -l   # ≥ 97 heads + 71 tags
git bundle verify "$B/local-refs-$STAMP.bundle"                     # 结尾须为 "ok"
shasum -a 256 -c "$B/SHA256SUMS-$STAMP"
```

> 注意：`git clone --mirror` 会额外拉取 `refs/pull/*`（若 GitHub 暴露），体积约 120–140 MB。11-16 的 mirror 为 119 MB，本轮因 Phase-8D 证据目录预计 130–150 MB。

---

## 7. 执行序列（待批准；每步含预期输出）

### 步骤 0 — 冻结与再确认（只读）

```bash
cd "$R"
git ls-remote origin > /tmp/refs-before.txt
git rev-parse a1d7150 bdd3f84 c0f9feb d37bfad 996060d a0e6a24
```
预期：`a1d7150f06fa…`、`bdd3f8402554…`、`c0f9febce1639…`、`d37bfad81f39…`、`996060d0b473…`、`a0e6a24…`（本地）。
若任一 SHA 与第 1 节不符 → **停止**，重新核验（说明远端被他人改动）。

### 步骤 1 — 备份

执行第 6 节全部命令。

### 步骤 2 — 建新分支（在干净的新 worktree，勿用 `binary-repair-gui`）

```bash
cd "$R"
git worktree add "$W/worktree-final-1117" -b final/consolidated-2026-11-17 a1d7150
cd "$W/worktree-final-1117"
git status --short --branch        # 预期：## final/consolidated-2026-11-17 … 干净
```

### 步骤 3 — 补入 `bdd3f84` 独有的 9 个路径

```bash
cd "$W/worktree-final-1117"
git checkout bdd3f84 -- \
  artifacts/release-gate-2026-11-17-phase8d \
  docs/release-phase8d-final-evidence-2026-11-17.md
git status --short | wc -l          # 预期：9
```

### 步骤 4 — 写入本轮文档与 refs manifest

```bash
D=delivery/zh/consolidation/2026-11-17
mkdir -p "$D"
cp "$W"/review/2026-11-17/0[1-6]-*.md "$D"/
cp "$W/项目总体回顾_完成现状_剩余任务与解决方案_2026-11-17.md" "$D/PROJECT-MASTER-REPORT-2026-11-17.md"
cp "$W"/review/2026-11-17/CONSOLIDATION-2026-11-17.md "$D"/
cp "$B/remote-refs-2026-11-17.txt" "$D/refs-manifest-2026-11-17.txt"
```

### 步骤 5 — 敏感串扫描（public 仓库，必做）

```bash
cd "$W/worktree-final-1117"
git grep -n -I -E 'sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----' -- "$D" || echo "clean"
```
预期：`clean`。命中则先脱敏再提交（写 `[REDACTED]`）。

### 步骤 6 — 提交

```bash
cd "$W/worktree-final-1117"
git add -A
git commit -m "docs(consolidation): integrate session 879cc62f/b139b586 into final/consolidated-2026-11-17

- base a1d7150 (Phase-8D + P31-P34 + final gate 13/13)
- carry bdd3f84 unique gate evidence (9 paths)
- add 2026-11-17 master report, 6 sub-reports, refs manifest"
git log --oneline -3
```

### 步骤 7 — 推送新分支（普通 push，**不需要** force）

```bash
git push -u origin final/consolidated-2026-11-17
```
预期：`* [new branch] final/consolidated-2026-11-17 -> final/consolidated-2026-11-17`

### 步骤 8 — 重指向 CI 触发分支 `workbench-v3`（保留 CI 能力）

```bash
git push origin +HEAD:workbench-v3       # 非快进，需 force；用 --force-with-lease 更稳
```
更稳妥写法：

```bash
git push --force-with-lease=workbench-v3:d37bfad origin HEAD:workbench-v3
```
预期：`+ d37bfad...<new> HEAD -> workbench-v3 (forced update)`，随后 GitHub 触发一次 `CI` 与 `Ubuntu verification`。

### 步骤 9 — 删除冗余 refs（带 SHA 守卫）

```bash
cd "$R"
for r in feature/ai-binary-repair release/2026-11-17-phase8d-final \
         release/2026-11-17-phase8d-final-evidence release/2026-11-17-phase8d-evidence \
         phase8d-open-world final/consolidated-2026-11-16; do
  git push origin --delete "$r"
done
git push origin --delete \
  refs/tags/release-2026-11-17-phase8d refs/tags/release-2026-11-17-phase8d-evidence \
  refs/tags/release-2026-11-17-phase8d-final refs/tags/release-2026-11-17-phase8d-final-evidence \
  refs/tags/phase8d-frozen-phase8c-release refs/tags/phase8d-frozen-phase8c-evidence

git fetch --prune origin
```

> 删除 `final/consolidated-2026-11-16` 前，确认步骤 7 成功且新分支 `git log` 含 `a1d7150`。

### 步骤 10 — 验收

```bash
git ls-remote --heads origin | wc -l                 # 预期 91（97 - 6，workbench-v3 保留）
git ls-remote --tags origin | wc -l                  # 预期 89（101 - 12）
git ls-remote origin | wc -l                          # 预期 181 左右
git ls-remote origin | grep -E 'feature/ai-binary-repair|phase8d-open-world|release/2026-11-17|final/consolidated-2026-11-16' || echo "无残留"
git ls-remote origin refs/heads/final/consolidated-2026-11-17
git ls-remote origin refs/heads/workbench-v3
```

预期：无残留；两条命令各返回一行，且**同一 SHA**（新提交）。

---

## 8. 回滚

任一步失败，均可从 mirror 原样推回（ref 删除不改对象，恢复是"重新指向"）：

```bash
cd "$B/binary-repair-mirror-2026-11-17.git"
for r in feature/ai-binary-repair release/2026-11-17-phase8d-final \
         release/2026-11-17-phase8d-final-evidence release/2026-11-17-phase8d-evidence \
         phase8d-open-world final/consolidated-2026-11-16; do
  git push git@github.com:chenfanaichifan/binary-repair.git "refs/heads/$r:refs/heads/$r"
done
git push git@github.com:chenfanaichifan/binary-repair.git 'refs/tags/release-2026-11-17-phase8d*:refs/tags/release-2026-11-17-phase8d*'
```

回滚 `workbench-v3`：`git push --force-with-lease origin d37bfad:workbench-v3`。
回滚 GUI 工作树：`git -C "$W/binary-repair-gui" apply "$B/gui-worktree-dirty-2026-11-17.patch"`（untracked 依 `gui-worktree-untracked-*.txt` 清单核对）。

---

## 9. 诚实边界（不可宣称"0 残留"）

| 事实 | 含义 |
|---|---|
| 删 ref ≠ 删对象 | commit 仍可按 SHA 访问，直到 GitHub GC；`a1d7150`、`c0f9feb` 等 SHA 会长期可达 |
| 11 个 closed PR | GitHub 永久保留 `refs/pull/{n}/head` 与 `merge`，其分支即使删除，commit 仍被 PR 引用（`member1/*`、`agent-layout` 等） |
| 170 次 Actions run | 删除分支不会删除历史 run；run 列表仍显示已删分支名，属正常残留 |
| 默认分支 `main` | 不可删除；本轮不动，故 `main` 仍停在 `8869b07`（11-12），**落后于新分支** |
| 分支保护 | 未认证无法确认；若 `main` 有保护，只有 `main` 受影响，本方案不推 `main` |
| 公开仓库 | 所有已推内容（含历史证据）对全网可见；**凭据轮换优先级高于痕迹清理** |
| gated SHA ≠ 新分支 tip | `binary-repair@a1d7150 docs/status/claims.json:441` 的 `ci_evidence.gated_sha = 78edb97…`（Phase-8D 前置提交），不是 `d37bfad`/`a1d7150`。新分支是**交付整合**，不是"重新 gate 的 release"；不得宣称 gate 覆盖新 tip |
| `a0e6a24` | 不推、不删；只在 bundle + manifest 中留档（同 patch 已在 `e01fc9e`） |

---

## 10. 与上一轮文档（CONSOLIDATION-2026-11-16）的差异

| 上一轮声明 | 实测（2026-11-17 08:5x） | 判定 |
|---|---|---|
| 新分支 `final/consolidated-2026-11-16` = `4322a51`（父 `ec503e4`） | `4322a51` 存在且在两条线历史中；但分支现指向 `c0f9feb`（`4322a51`→…→`f1bb1f4`→`a9db731`→`c0f9feb`） | **已过时**（分支被推进） |
| 删除 23 分支 + 14 标签，"会话相关残留 0"（`binary-repair@a1d7150 delivery/zh/consolidation/CONSOLIDATION-2026-11-16.md:75`） | `workbench-v3`、`feature/ai-binary-repair` **重新存在**；新增 4 个 `release/*` + `phase8d-open-world` | **已过时** |
| 远端 192 行 / heads 91 / tags 89（同上 `:77`） | 198 行 / heads 97 / tag 行 101（真实 71） | **已过时** |
| 删除时备份 242 行 refs | 现存 `remote-refs-2026-11-16.txt` 为 192 行（删除**后**快照） | **口径不一致**：备份不含删除前状态 |
| 建议把 `final/consolidated-2026-11-16` 设为默认分支 | 该分支缺 Phase-8D | **不建议**，应改为新分支 |
| gated release SHA 仍 `4a7b235`（Phase-8C） | `claims.json` 现为 `78edb97`（Phase-8D 前置） | **已更新**，需以 `claims.json` 为准 |

---

## 11. 交接给 Lead

1. **基线必须改成 `a1d7150`**。若 Lead 按旧文档用 `final/consolidated-2026-11-16`（`c0f9feb`）建分支，会静默丢掉整个 Phase-8D（-76859 行）——这是本轮最大单点风险。
2. **新分支 = `a1d7150` + `bdd3f84` 的 9 个路径 + 本轮 7 份文档 + refs manifest**，命名 `final/consolidated-2026-11-17`（普通 push，无需 force）。
3. **不要直接 push 到 `main`**；`main` 停在 11-12 的 `8869b07`，本轮不处理（默认分支变更需 owner 在 Settings 操作）。
4. **`workbench-v3` 要留**：它是 `ci.yml`/`ubuntu-verify.yml` 的 push 触发分支；删了 CI 就只能靠 `workflow_dispatch`。用 `--force-with-lease` 重指向新 HEAD。
5. **`a0e6a24` 不是丢失的工作**：patch-id 与 `e01fc9e` 相同；只在 bundle/manifest 留档，别 cherry-pick。
6. **先备份再删**：11-16 的 mirror/bundle 只到 `f1bb1f4`（11-16 12:20），**不覆盖 Phase-8D**；必须新做 11-17 mirror + bundle（约 130–150 MB）。
7. **GUI 工作树 41 项脏改动是半途 revert**（`llm_gateway/*` 暂存删除却留 untracked），无论是否清理，都要先落 patch 备份，且**不得**作为成果提交。
8. **删 ref ≠ 0 残留**：11 个 closed PR 的 `refs/pull/*`、170 条 Actions run、按 SHA 可达的 commit 都会留下；对外只能表述为"分支/标签已删除，对象级残留不可消除"。
9. **仓库是 public**：提交前必须跑密钥扫描；会话中出现的凭据应轮换（优先级高于痕迹清理）。
10. **未核实项**：① 分支保护规则（API 401）；② `phase8d-frozen-phase8c-*` 两个 tag 是否另有本地锚点（本地仅有 `freeze/phase8c-release-4a7b2355` 分支）；③ 上一轮"删除前 242 行 refs"清单是否存在别处副本（当前仅见 192 行）。
