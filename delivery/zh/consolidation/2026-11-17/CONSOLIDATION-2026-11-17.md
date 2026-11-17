# 2026-11-17 整合与仓库交付记录

- 日期：2026-11-17（Asia/Singapore）
- 执行：Lead（本轮会话 `session-0842a3d0`）
- 用户要求：把「Linux 虚拟机验证漏洞修复-1」(`session-879cc62f`) 与「全类型二进制修复-1」
  (`session-b139b586`) 两个会话完成的任务整合后推送到 GitHub **新分支**，删除它们在仓库中的
  原位置/信息存放痕迹，并告知仓库地址。
- 结果分支：`final/consolidated-2026-11-17`
- 基线：`d37bfad81f39c2bfa3fc90babed7301d6244446d`
- 仓库：`git@github.com:chenfanaichifan/binary-repair.git`
  （<https://github.com/chenfanaichifan/binary-repair>）

## 1. 为什么基线是 `d37bfad`（而不是 `c0f9feb` 或 `a1d7150`）

| 候选 | 含 Phase-8D | 含 P31–P34 | 含 13/13 final gate | 判定 |
|---|---|---|---|---|
| `c0f9feb`（`final/consolidated-2026-11-16`） | 否 | 是 | 否 | 不可用：缺整个 Phase-8D |
| `d37bfad`（`workbench-v3` / `release/2026-11-17-phase8d-final`） | 是 | 是 | 否 | **采用**（被 CI 43907137267/43907136876 验证） |
| `a1d7150`（`release/…-final-evidence`） | 是 | 是 | 是 | 不直接作基线：删除 33 个被 `baseline.json` 与 universe builder 依赖的历史 gate 文件 |
| `bdd3f84`（`release/…-evidence`） | 是 | 否 | 部分 | 仅取独有 9 个路径 |

实际做法：以 `d37bfad` 为基线，**只新增**、不删除：

1. 从 `a1d7150` 取 `artifacts/release-gate-2026-11-17-phase8d-final/` 与
   `docs/release-phase8d-final-mainline-evidence-2026-11-17.md`；
2. 从 `bdd3f84` 取 `artifacts/release-gate-2026-11-17-phase8d/` 与
   `docs/release-phase8d-final-evidence-2026-11-17.md`；
3. 保留 `d37bfad` 原有的全部 7 个历史 `artifacts/release-gate-*` 目录，避免证据链断裂。

验证：`PYTHONPATH=. python3 scripts/build_phase8d_capability_universe.py --check` → `phase8d: check OK`（exit 0）。

## 2. 新分支内容

- 基线代码/证据：`d37bfad` 全树（2,359 tracked files；2411 tests；Phase-8D + P31–P34 + M1–M4）。
- 补充证据：`release-gate-2026-11-17-phase8d/`、`release-gate-2026-11-17-phase8d-final/`
  与两份 final evidence 文档（共 18 个新增路径）。
- 整合文档：`delivery/zh/consolidation/2026-11-17/` 9 份（总报告 + 6 份子报告 + 本记录 + refs 清单）。
- 配置：`.github/workflows/{ci,ubuntu-verify}.yml` 的 push 分支改为
  `main` / `final/consolidated-2026-11-17`，使新分支保持 CI/Ubuntu 验证能力（原 `workbench-v3` 将被删除）。
- 根 `CONSOLIDATION.md` 指向本记录。

## 3. 删除清单（远端）

### 3.1 heads（7 条，均为两个会话在 11-16/11-17 产生或推进）

`workbench-v3`、`feature/ai-binary-repair`、`phase8d-open-world`、
`release/2026-11-17-phase8d-final`、`release/2026-11-17-phase8d-final-evidence`、
`release/2026-11-17-phase8d-evidence`、`final/consolidated-2026-11-16`。

### 3.2 tags（6 个）

`release-2026-11-17-phase8d`、`release-2026-11-17-phase8d-evidence`、
`release-2026-11-17-phase8d-final`、`release-2026-11-17-phase8d-final-evidence`、
`phase8d-frozen-phase8c-release`、`phase8d-frozen-phase8c-evidence`。

### 3.3 保留

- `main`（`8869b07`，GitHub 默认分支，不可由普通 push 删除；本轮不动）；
- 2026-11-12 及以前的 M1–M5 / v1.2.1 / 集成分支与标签（约 90 heads / 65 tags）；
- 新分支 `final/consolidated-2026-11-17`。

## 4. 备份（删除前完成）

| 项 | 路径 | 说明 |
|---|---|---|
| 远端 mirror | `backup/2026-11-17/binary-repair-mirror-2026-11-17.git`（129 MB） | 含全部 heads/tags/pull refs（清理后刷新）；`a1d7150`/`c0f9feb` 可检出 |
| 本地全 refs bundle | `backup/2026-11-17/local-refs-2026-11-17.bundle`（128 MB） | `git bundle verify` → "complete history" |
| 删除前 refs | `backup/2026-11-17/remote-refs-2026-11-17.txt` | 97 heads / 101 tag 行 |
| GUI 工作树现场 | `backup/2026-11-17/gui-worktree-*.patch`、`-status.txt`、`-untracked.tgz` | 41 项脏改动的完整补丁与 6 个 untracked 文件 |
| 本地保护 refs | `backup/final-consolidated-2026-11-16`、`backup/p31-p34-feature-a0e6a24`、`backup/phase8d-evidence-bdd3f84`、`backup/phase8d-final-evidence-a1d7150` | 防对象被 GC |

恢复示例：

```bash
git -C backup/2026-11-17/binary-repair-mirror-2026-11-17.git \
  push git@github.com:chenfanaichifan/binary-repair.git \
  refs/heads/workbench-v3:refs/heads/workbench-v3
```

## 5. 执行序列

1. 快照远端 refs、重建 mirror/bundle、保全 GUI 工作树；
2. `git worktree add worktree-final-1117 -b final/consolidated-2026-11-17 d37bfad`；
3. 从 `a1d7150`/`bdd3f84` 取独有证据，保留历史 gate；
4. 写入 9 份整合文档、更新 `CONSOLIDATION.md` 与 CI 触发分支；
5. `git commit` → `git push -u origin final/consolidated-2026-11-17`；
6. 校验新分支包含 `d37bfad`/`4a7b235`，再删除 7 heads + 6 tags；
7. `git fetch --prune`，复核无会话 ref 残留、默认分支仍 `main`、新分支可 checkout。

## 6. 诚实边界（必须与"已删除"同时说明）

- 删 ref ≠ 删对象：commit 仍可按 SHA 访问，直到 GitHub GC；`c0f9feb`/`d37bfad`/`a1d7150` 等 SHA 会长期可达。
- 11 个已关闭 PR 的 `refs/pull/*` 与 170 条 Actions run 仍保留分支名/提交引用，无法通过删 ref 消除。
- 默认分支仍是 `main`（`8869b07`，11-12）；本轮无 admin token，未切换默认分支。
- 本分支是**交付整合**，不是重新 gate 的 release；被 gate 的 SHA 仍是 `d37bfad`（13/13、CI success）。
- 仓库是 **public**；凭据轮换（K1–K4）仍未执行，优先级高于痕迹清理。
- 本地 `binary-repair-gui` 的 41 项脏改动未被提交，已保全为补丁；其中 `code_cave.py` phdr 修复是
  未进任何分支的真实缺陷修复，需单独立项（见总报告 P0-6）。

## 7. 执行结果（2026-11-17 实测）

| 项 | 结果 |
|---|---|
| 新分支 | `final/consolidated-2026-11-17`；首批提交 `9194b02`（基线 `d37bfad`）；文档提交后 tip 以 `git log -1` 为准 |
| 基线包含关系 | `git merge-base --is-ancestor d37bfad HEAD` → 0；`4a7b235` → 0 |
| 远端 heads | **97 → 91**（删 7 + 新增 1） |
| 远端 tag 行 / 真实 tag | **101 / 71 → 89 / 65** |
| `git ls-remote` 总行（含 pull 11 + HEAD 1） | **210 → 192** |
| 会话相关 ref 残留 | **0**（`workbench-v3`/`feature/ai-binary-repair`/`phase8d*`/`release-2026-11-17*`/`final/consolidated-2026-11-16` 全部消失） |
| 默认分支 | 仍 `main` = `8869b07`（未动） |
| 删除 heads | **7/7 成功**（workbench-v3、feature/ai-binary-repair、phase8d-open-world、release/2026-11-17-phase8d-{final,final-evidence,evidence}、final/consolidated-2026-11-16） |
| 删除 tags | **6/6 成功**（release-2026-11-17-phase8d* ×4、phase8d-frozen-phase8c-* ×2） |
| 备份 | mirror 129 MB / 167 refs（清理后刷新）（`a1d7150`、`c0f9feb` 可检出）；bundle 128 MB（complete history）；SHA256SUMS 7 个文件 |
| 构建校验 | `scripts/build_phase8d_capability_universe.py --check` → `phase8d: check OK`（exit 0） |
| 工作树 | `worktree-final-1117` 干净；`binary-repair-gui` 的 41 项脏改动未混入，已保全为补丁 |

> 诚实例外：`refs/pull/*` 11 条与 170 条 Actions run 仍在；commit 对象仍可按 SHA 访问；默认分支未切换。详见总报告 §9.6。
