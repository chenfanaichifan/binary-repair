# 73 — Lead: Gate 5 successor 修正指示

**From:** Lead
**To:** M3+M5, M4
**Date:** 2026-10-31 (Asia/Hong_Kong)
**Status:** APPROVED — 修正 successor 执行规格，替代 66 号草案中的待定项

## 1. 定位

继续 Gate 5 successor 工作，规则如下：

- **保留旧 `jobwrap b232d60b`**，不覆盖、不重签 P4 / Gate 4 证据链；
- **另建独立 `jobwrap-gate5`**，新 hash 只绑 Gate 5；
- 两条证据链彻底分开。

## 2. 修正点（binding）

1. **probe hash 钉死 `F39A0302…D146CB`**（即 `f39a0302dd1aa42635da80fa4e9160d37a221f5ac383270add3eaedcffd146cb`），编译期常量，**不读 env**；
2. **固定 argv**：`jobwrap-gate5 probe m4-gate5 -- <repo-root> <work-dir>` → `execv` 绝对路径 `/usr/bin/python3 <repo>/scripts/m4_gate5_probe.py`，无 shell 字符串、无 PATH 解析、无 caller 自定义命令；
3. **隔离要求**（语义等价即可，不要求 byte-equivalence）：root-only、netns/no-egress、`setgroups`→`setgid(1003)`→`setuid(1003)`、`CapEff=0`、seccomp、`NoNewPrivs=1`、rlimits、`clearenv`、fixed argv、绝对路径、脚本 root-owned 不可写、fail-closed；
4. **源码 + build recipe 必须进 git**（旧 jobwrap 丢失的根因正是从未进 git）；
5. **Gate 5 记录绑定新 binary + probe hash**；记录 `51` 仍 **unsigned**，等 M4 独立核查。

## 3. 与 66 号草案的关系

66 号草案中的开放点已由本记录全部落定：

| 66 号开放点 | 本记录裁定 |
|---|---|
| 开放点 1：`GATE5_SCRIPT_SHA256` 钉死谁 | **(a)** 直接 `exec /usr/bin/python3`，编译期钉死 probe blob `F39A0302…D146CB`，不读 env，**否决 (b)** |
| B2（`jobwrap_gate5.sh` 无校验） | 已过时：main `99db9c9` 的 `jobwrap_gate5.sh` 已带 `GATE5_SCRIPT_SHA256` 校验（blob `FB5FD90B…`）；successor 不再依赖该脚本 |
| `m4_gate5_fixed.sh` | 记录其 blob `B751BB7F…13C5`，但它走 PATH 且不 hash probe；**推荐直接 probe，不用 fixed.sh** |
| 隔离是否 byte-equivalence | **语义等价即可**，不要求 byte-equivalence |

## 4. 签名

| Role | Date | Signature |
|---|---|---|
| Lead | 2026-10-31 | approved (verbatim per message) |
| M3+M5 | 2026-10-31 | executing |
| M4 | — | pending independent verification |
