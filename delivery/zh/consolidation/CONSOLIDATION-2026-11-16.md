# CONSOLIDATION 2026-11-16 — 两会话成果整合与新分支

本文件记录把两个重点会话（Linux 虚拟机验证漏洞修复-1、全类型二进制修复-1）的全部完成成果整理整合到一个新分支、并清理原有 refs/痕迹的执行过程与恢复方法。

- 整合日期：2026-11-16（Asia/Singapore）
- 新分支：`final/consolidated-2026-11-16`
- 起点：`ec503e4b1df53ad39fa836bd34d93a18564d78f9`（Phase-8C evidence tip；历史包含两个会话全部 commit）
- 总报告：[PROJECT-MASTER-REPORT-2026-11-16.md](PROJECT-MASTER-REPORT-2026-11-16.md)
- 会话逐事件分析：[session-1-linux-vm-analysis.md](session-1-linux-vm-analysis.md)、[session-2-all-types-analysis.md](session-2-all-types-analysis.md)
- 早期项目历史：[project-history.md](project-history.md)

## 1. 为什么整合

两个重点会话把成果推到了多个分支/标签/证据分支（23 个分支 + 14 个标签），其中包括最终 mainline `workbench-v3`、`feature/universal-repair`、`feature/ai-binary-repair`、`feature/phase8b/8c`、`release/2026-11-14..16-*`、`coverage-audit-*` 以及 14 个 release/evidence tag。用户要求：整理整合为一个新分支；删除原有位置/痕迹；给出仓库地址。

## 2. 整合内容

1. 新分支 `final/consolidated-2026-11-16`（基于 `ec503e4`）。
2. 补归档证据（51 个文件，3.9 MB；此前只在各 evidence 分支或本地 `backup/capacity-86587da`，未进 mainline）：
   - `artifacts/marcx-repair-2026-11-14/`（marcx 一手证据包：README、marcx-fixed、patch-record、poc-manifest、runtime-evidence、challenge-suite、verification-report、gui-success.png、reproduce.py、SHA256SUMS）
   - `artifacts/marcx-capacity-gui-2026-11-14/`（GUI 断言、截图、review response）
   - `artifacts/release-gate-2026-11-14/`、`...-11-15/`、`...-11-15-autonomy/`、`...-11-16/`、`...-11-16-phase8a/`、`...-11-16-phase8b/` 的 gate/freeze/ci-run/provenance 证据
   - `docs/release-2026-11-15.md`、`docs/release-2026-11-15-autonomy.md`、`docs/release-2026-11-16-phase8a.md`、`docs/release-phase8b-final-evidence-2026-11-16.md`
3. 整合文档 `docs/consolidation/`（总报告 + 两会话分析 + 早期历史 + 本文件）。
4. 删除原有 refs/痕迹（两个会话产生的 23 个远端分支 + 14 个远端标签，见第 3 节）。
5. 本地完整备份（mirror + refs 清单，见第 4 节）。

## 3. 删除的远端 refs（两个会话产生）

### 3.1 分支（23）

handoff-v4-local、feature/universal-repair、feature/ai-binary-repair、feature/phase8b-verifier-semantics、feature/phase8c-ground-truth-v2、coverage-audit-2026-11-14、coverage-audit-2026-11-14-merged、release/2026-11-14-final、release/2026-11-14-evidence、release/2026-11-15-integration、release/2026-11-15-final、release/2026-11-15-evidence、release/2026-11-16-final、release/2026-11-16-evidence、release/2026-11-15-autonomy-final、release/2026-11-15-autonomy-evidence、release/2026-11-16-phase8a-final、release/2026-11-16-phase8a-evidence、release/2026-11-16-phase8b-final、release/2026-11-16-phase8b-evidence、release/2026-11-16-phase8c-final、release/2026-11-16-phase8c-evidence、workbench-v3。

### 3.2 标签（14）

release-2026-11-14、release-2026-11-14-evidence、release-2026-11-15、release-2026-11-15-evidence、release-2026-11-16、release-2026-11-16-evidence、release-2026-11-15-autonomy、release-2026-11-15-autonomy-evidence、release-2026-11-16-phase8a、release-2026-11-16-phase8a-evidence、release-2026-11-16-phase8b、release-2026-11-16-phase8b-evidence、release-2026-11-16-phase8c、release-2026-11-16-phase8c-evidence。

### 3.3 保留

- `main`（GitHub 默认分支，2026-11-12 前历史；两会话未在 main 上直接推进）；
- 2026-11-13 之前的历史 refs（M1–M5 角色分支、v1.2.1 发布线等）；
- 新分支 `final/consolidated-2026-11-16`。

## 4. 本地备份与恢复

- `backup/binary-repair-mirror-2026-11-16.git`（git clone --mirror 自 origin；129 MB；含删除前全部 branch/tag/commit 对象）
- `backup/remote-refs-2026-11-16.txt`（删除前 git ls-remote origin 242 行原始输出）

恢复示例（把 mirror 的某个 ref 推回远端）：

```bash
cd backup/binary-repair-mirror-2026-11-16.git
git push git@github.com:chenfanaichifan/binary-repair.git refs/heads/workbench-v3:refs/heads/workbench-v3
git push git@github.com:chenfanaichifan/binary-repair.git refs/tags/release-2026-11-16-phase8c:refs/tags/release-2026-11-16-phase8c
```

## 5. 重要说明

- 这是交付整合分支，不是被 gate 的 release SHA。被 gate 的 release SHA 仍是 `4a7b2355ffc5225d013a777bc7d588abac58f944`（Phase-8C），`docs/status/claims.json` 与 gate 证据保持不变。
- 新增文件均为 docs/evidence，不改代码、不改 claims、不改 gate 结果。
- 删除 ref 不会立即删除 Git 对象；GitHub 可能在 GC 前仍可通过 SHA 访问旧 commit。要物理删除需 GitHub Support 或全仓历史重写（本次不做）。
- 默认分支仍是 `main`；建议 owner 在 GitHub Settings 把 `final/consolidated-2026-11-16` 设为默认分支。
- 会话中出现的 API key 应全部轮换（安全 P0）。

## 6. 验证

（执行结果见第 7 节；最终以 git ls-remote 与分支内容为准。）

## 7. 执行结果（2026-11-16 实做）

| 项 | 结果 |
|---|---|
| 新分支 | `final/consolidated-2026-11-16`，commit `4322a51`（父 `ec503e4`），已推送 |
| 整合文件 | 51 个补归档证据 + `docs/consolidation/` 5 份 + `CONSOLIDATION.md` + README 顶部说明 = 58 个文件变更 |
| 远端分支删除 | 23/23 成功 |
| 远端标签删除 | 14/14 成功 |
| 远端 refs | 243 行（含新分支）→ **192 行**；heads 91；tag refs 89（unique 65）；会话相关残留 **0** |
| 本地清理 | 删除 23 个会话分支 + 14 个会话 tag + 4 个本地会话分支 + 移除 `worktree-feature-final`；本地仅保留新分支 |
| 备份 | mirror 129 MB + local bundle 127 MB + 删除前 refs 清单 242 行 |
| gated release SHA | 仍为 `4a7b2355ffc5225d013a777bc7d588abac58f944`（未改代码/claims/gate） |

验证命令（可复核）：

```bash
git ls-remote git@github.com:chenfanaichifan/binary-repair.git | wc -l         # 192
git ls-remote --heads git@github.com:chenfanaichifan/binary-repair.git | wc -l # 91
git ls-remote git@github.com:chenfanaichifan/binary-repair.git | grep -E 'workbench-v3|phase8|universal|coverage-audit|release-2026-11-1' # 空
git ls-remote git@github.com:chenfanaichifan/binary-repair.git refs/heads/final/consolidated-2026-11-16
```

仓库：https://github.com/chenfanaichifan/binary-repair
