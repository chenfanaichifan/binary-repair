# M4 任务 — 安全、备份、发布治理与口径复核

> 本文件是 M4 的完整接手包。读完即可开工；不需要读历史会话。
> 任务来源：组长 2026-11-16 复核决议——**P0 安全（key 泄露）比一切能力任务都急；备份只在本机不算备份；默认分支仍是旧 main；报告口径要复核。**

## 0. 一句话目标

把项目的**安全、备份、发布与口径**全部收口：key 轮换清单与扫描、异地备份执行/验证、默认分支切换步骤、报告口径复核、交接就绪清单（20 项）。**只新增 ops 文档与工具，不改主报告/claims/代码。**

## 1. 必读（按顺序，10 分钟）

1. `review/STATE.md`
2. `项目总体回顾_完成现状_剩余任务与解决方案_2026-11-16.md` 的 **§1.5（组长决议）**、§6.2 B1–B12/§6.3/§6.4、§8（整合与备份）
3. `tools/handoff/README.md`、`tools/handoff/check-env.sh`、`scan-secrets.sh`、`offsite-backup.sh`
4. `binary-repair-gui/docs/operations/release-gate-2026-11-14.md`、`release-evidence-procedure.md`、`phase8c-ci-signoff.md`
5. `binary-repair-gui/docs/status/claims.json` 的 `ci_evidence`、`release_evidence`、`phase8c_ground_truth`

## 2. 环境与前提（已由 Lead 备好）

- 仓库 `binary-repair-gui/`，分支 `final/consolidated-2026-11-16`；venv 3.11.8；
- 备份资产：`backup/binary-repair-mirror-2026-11-16.git`（129MB）、`backup/local-refs-2026-11-16.bundle`（127MB）、`backup/remote-refs-2026-11-16.txt`（242 行）；
- 工具：`tools/handoff/scan-secrets.sh`、`offsite-backup.sh`、`check-env.sh`；
- **不做 git 写**；不修改主报告/claims/代码；不打印任何 key 明文。

## 3. 你的任务（P0 → P2）

### P0-1（最急）API key 泄露处置与扫描

背景：会话历史中出现过明文 provider key（SiliconFlow CN/US、DashScope、DeepSeek 等），**视为已泄露**。

产出 `docs/operations/security-key-rotation-2026-11-17.md`：
1. 泄露清单（**只写 provider/用途/出现位置类型，不写 key 明文、不写前几位**）；
2. 轮换/吊销步骤（每个 provider 控制台路径 + 验证方法：新 key 跑一次最小 identity/hello 调用后立即销毁测试脚本）；
3. 扫描结果：运行 `tools/handoff/scan-secrets.sh` 覆盖 `binary-repair-gui/`（docs/scripts/app）与 `review/`，记录 exit code 与脱敏 hits；
4. 防再犯：pre-commit/CI secret scanning 建议（给 patch 草稿，不直接改 `.github/`）；
5. 明确“需要用户/owner 执行”的项（你无法代做）。

### P0-2 异地备份（执行 + 验证）

1. 先跑一次**演练**到 `/tmp/binrepair-offsite-drill`：`tools/handoff/offsite-backup.sh /tmp/binrepair-offsite-drill`，确认 SHA256SUMS 校验通过；
2. 向 Lead 索要真实异地路径（移动硬盘/云盘挂载点）；拿到后执行并记录：路径指针、`du -sh`、`SHA256SUMS` 校验结果、mirror refs 数；
3. 产出 `docs/operations/backup-2026-11-17.md`：备份清单、校验命令、恢复演练（从 mirror 恢复一个 ref 到临时目录并验证 commit）、保留周期建议；
4. 如果用户暂不提供异地路径：明确写 `blocked_by=user:offsite_path` + 待执行命令，不算完成。

### P0-3 默认分支切换（Runbook）

产出 `docs/operations/default-branch-2026-11-17.md`：
1. 当前事实：GitHub 默认分支仍是 `main`（8869b07），交付分支 `final/consolidated-2026-11-16`；
2. owner 操作步骤（Settings → Branches → Default branch → 切换 + 保留 main）；
3. 校验命令：`git ls-remote --symref origin HEAD` 应指向交付分支；`git ls-remote origin` 统计；
4. 风险与回滚（切回 main 的步骤）；
5. 明确“本机无 gh/token，无法代办，需 owner 执行”。

### P1-1 报告口径复核（只报告，不改主报告）

复核并输出 `docs/operations/report-consistency-2026-11-17.md`：
1. 非 loop 口径：应为 **3/6（单模型 flash；v4-pro 0/3；CWE-121 public/UAF/heap-canary 仍 0）**，检查总报告 §1.4/§1.5/§3.6/§3.8/§5.3.3/§6.1/§6.5/§7.3/§7.5 是否一致；
2. benchmark 数字：2/24、hidden 0/8、false_verified=0、P16-R3 7/10 在各文档是否一致；
3. CI 口径：gated SHA vs final release SHA 的双记录是否清楚；self-hosted nightly 是否仍 `not_run`；
4. 发现不一致 → 列**具体文件+行号+建议改法**，交 Lead 修；不改原文。

### P1-2 交接就绪清单（20 项）

产出 `docs/operations/handoff-readiness-2026-11-17.md`，逐项 [PASS/FAIL/未执行] + 证据命令：仓库/分支、远程可见、venv、`check-env.sh`、四份任务文件、工具区、备份（本机+异地）、key 轮换清单、默认分支、报告口径、claims/LIMITATIONS 一致、训练/材料无 key、hidden 未泄漏、CI 状态、release gate 证据、tag/分支清理状态、回滚方案、成员权限、首次同步会时间。

### P2（时间允许）CI/安全门禁 patch 草稿

在 `docs/operations/ci-security-proposal-2026-11-17.md` 给出建议 patch（secret scanning step / pre-commit），**不直接改 CI**；交 Lead 决策。

## 4. 写范围（严格）

允许新增/修改：
```
docs/operations/security-key-rotation-2026-11-17.md
docs/operations/backup-2026-11-17.md
docs/operations/default-branch-2026-11-17.md
docs/operations/report-consistency-2026-11-17.md
docs/operations/handoff-readiness-2026-11-17.md
docs/operations/ci-security-proposal-2026-11-17.md
scripts/security/**            （新目录，扫描/校验辅助脚本）
tools/handoff/**               （只允许修复/增强已有工具，不删功能）
.tmp/handoff/m4/               （日志、演练输出）
```
禁止修改：`docs/consolidation/*`（主报告/分析）、`docs/status/claims.json`、`docs/acceptance/LIMITATIONS.md`、`app/**`、核心 scripts、`fixtures/`、`.github/**`、M1/M2/M3 目录、备份原始文件（只读）。

## 5. 红线

1. **绝不打印/写入 key 明文**（扫描只输出脱敏位置）；不把会话日志复制到仓库；
2. 不修改主报告/claims/代码来“消除”不一致——只列问题交 Lead；
3. 备份必须校验（SHA256SUMS + refs 数 + 恢复演练）；单机副本不算完成；
4. 不做 git 写；不推送；不删除任何 ref/备份；
5. 明确列出“需 owner/用户执行”的项，不用“已完成”掩盖。

## 6. 交付物

1. 6 份 ops 文档（按 P0/P1/P2）；
2. `scan-secrets.sh` 扫描记录（脱敏）+ 演练备份校验日志 + 恢复演练记录；
3. `.tmp/handoff/reports/m4-report-*.md`（工具生成）；
4. 给 Lead 10 行摘要（P0 状态/需用户操作项/发现的不一致/备份结论）。

## 7. 时间盒

- 首增量 60 分钟：P0-1 清单 + 扫描 + P0-2 演练备份；
- 90 分钟内给 Lead 第一版 P0 状态（key/备份/默认分支）；P1 当天完成；
- 需要异地路径/owner 操作 → 立即报 Lead，不空等。
