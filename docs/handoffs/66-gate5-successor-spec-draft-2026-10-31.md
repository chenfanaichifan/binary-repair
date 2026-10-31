# 66 — Gate 5 successor 规格（APPROVED，待实施）

**From:** M3+M5 (merged agent)
**To:** Lead, M3/VMer, M4
**Date:** 2026-10-31 21:46 (Asia/Hong_Kong)（初稿 21:40，批准 21:46）
**Status:** **Lead 已批准实施**（2026-10-31）。开放点全部落定（见 §5）。下一步进入 guest 内实施。

---

## 0. 背景与目的

`jobwrap_v3.c` 源码已确认永久丢失（见 65 号及 `.tmp/jobwrap-recovery/RECOVERY-ARCHIVE.md`）。
但 Lead 52 §3 已明确：**D3 不要求重编同一个已部署的 jobwrap**，允许"另建 fixed-argv 的 probe
模式"或"文档化已存在的等价 fixed-argv 调用"。

本草案按 **path 4** 定案推进：**保留旧 `jobwrap b232d60b` 给 Gate 4（不重签 P4），另建独立
successor 只绑 Gate 5，两条证据链分开。**

本草案回答一个具体问题：**Gate 5 的 successor 应该长什么样、满足哪些硬约束、hash 如何绑定。**

---

## 1. 阻塞点的精确归因（对齐 Lead 52 §3 / 44 号裁定，已按 main 99db9c9 更新）

Gate 5 Route A 阻塞，不是"源码丢了"，而是 jobwrap 二进制缺 fixed-argv 的 `probe m4-gate5`
模式（现有只有 `gate3`/`probe`/`gate4`）：

| # | 缺失项 | 出处 |
|---|---|---|
| B1 | jobwrap 二进制缺 `gate5`（或等价的 fixed-argv `probe m4-gate5`）模式 | Lead 52 §3 |
| B2 | ~~`routeb/jobwrap_gate5.sh` 不校验 SHA-256~~ **已解决**：main `99db9c9` 的 `jobwrap_gate5.sh` 已含 `GATE5_SCRIPT_SHA256` 校验（blob `FB5FD90B…`） | 已过时，见下 |

> **B2 修正（2026-10-31）**：main `99db9c9` 的 `routeb/jobwrap_gate5.sh` 已带
> `GATE5_SCRIPT_SHA256` 校验，blob 为 `FB5FD90B…`。早前 44 号裁定里"wrapper 只 exec 不校验"
> 的描述针对的是旧 blob `859ac8fe…`，现已过时。故当前唯一剩余阻塞是 **B1**：jobwrap 二进制
> 缺 `probe m4-gate5` 模式。

---

## 2. successor 规格（草案）

### 2.1 名称与定位

- **产物名**：`jobwrap-gate5`（独立二进制，**不覆盖** `/usr/local/sbin/jobwrap`）。
- **定位**：Gate 5 Route A 的 fixed-argv 隔离执行器。**只绑 Gate 5**，不参与 Gate 4 证据链。

### 2.2 调用形态（严格对齐 Lead 52 §3 preferred）

```bash
# 单一 fixed argv，无 shell 字符串，无 caller 自定义命令
jobwrap-gate5 probe m4-gate5 -- <repo-root> <work-dir>
```

执行语义（必须逐字满足）：

1. `execv` **直接**执行 `/usr/bin/python3 <repo-root>/scripts/m4_gate5_probe.py <repo-root> <work-dir>`（绝对路径 `/usr/bin/python3`，不依赖 `PATH`，不经 `m4_gate5_fixed.sh`）；
2. **先**建立 no-egress netns、**再**降权到 uid 1003；
3. **无 shell 字符串拼接**（不 `system()`、不 `sh -c`、不拼接再 `exec`）；
4. **不接受 caller 提供的任意命令** —— argv 形态完全固定；
5. **编译期钉死 probe blob**：probe `scripts/m4_gate5_probe.py` 的 SHA-256 常量 `F39A0302…D146CB` 存于 `.rodata`，exec 前校验（fail-closed，不读 env）。

### 2.3 隔离要求（语义等价于旧 jobwrap，不要求 byte-equivalence）

successor 的隔离链必须语义等价于旧 jobwrap `run_argv`，逐项列出以便 M4 独立核查。**语义等价即可，不要求 byte-equivalence**（旧 jobwrap 无源码，逐字节等价无法保证）：

| 控制项 | 要求 |
|---|---|
| root-only | 非 root 启动即拒绝（与旧 jobwrap 一致） |
| netns | `unshare` 建 no-egress netns（mount 空 `/proc`） |
| 降权 | `setgroups` → `setgid(1003)` → `setuid(1003)` |
| 能力 | `CapEff=0`（全清零） |
| seccomp | 启用 seccomp filter |
| NoNewPrivs | `prctl(PR_SET_NO_NEW_PRIVS, 1)` |
| rlimit | `setrlimit`（CPU/内存上限） |
| env | `clearenv` 后仅设最小白名单 `setenv` |
| fixed argv | argv 形态完全固定，无 shell 字符串 |
| 绝对路径 | 目标 `python3` 与 probe 均用绝对路径，不依赖 `PATH` |
| 脚本归属 | 被执行的 probe 脚本 root-owned、不可写（隔离内不可篡改） |
| fail-closed | 任何 hash 不匹配/前置失败 → 立即退出，拒绝执行 |
| egress | probe 内 `curl example.com` 必须 `egress=blocked` |

### 2.4 fail-closed hash 校验（编译期钉死 probe blob）

这是 successor 相对旧 wrapper 的**核心新增**：

- successor 内建 **probe blob 常量**：`scripts/m4_gate5_probe.py` 的 SHA-256 = `F39A0302…D146CB`（`const` 存于 `.rodata`）；
- 在降权、exec 之前，**先 `sha256sum` 校验** probe 脚本与常量比对；
- **不匹配 → 立即退出，非零 rc，拒绝执行**（fail-closed，不 fallback、不放行）；
- **不读 env** —— 期望 hash 硬编码进二进制，不接受 `GATE5_SCRIPT_SHA256` 等环境变量覆盖（明确否决方案 b）；
- 校验发生在**降权之前**（避免 uid 1003 无法读脚本导致校验被绕过）。

> **关于 `m4_gate5_fixed.sh`（不推荐路径）**：其 blob 为 `B751BB7F…13C5`，但它是
> `#!/bin/bash` 且走 `PATH` 解析 `python3`，**不 hash 校验 probe**。因此 successor 应**直接
> exec probe**，不经 `m4_gate5_fixed.sh`。若坚持经它，需额外钉死其 blob 并确保其内部
> `python3` 也走绝对路径——成本更高且多一层 shell，故**推荐直接 probe**。

### 2.5 hash 绑定策略

| 项 | 策略 |
|---|---|
| successor 自身 hash | 编译后在 guest 内 `sha256sum` 生成，写入 Gate 5 记录（`51`）与 `SHA256SUMS` |
| 绑定的 gate | **仅 Gate 5**；Gate 4 继续绑 `b232d60b`，两者不交叉 |
| 旧 jobwrap | 保持 `/usr/local/sbin/jobwrap`（b232d60b）原样，**不删除、不覆盖、不重签 P4** |
| 校验链 | successor 的 hash 从 bytes 独立计算，不从聊天摘要推断 |

---

## 3. 交付物清单（草案）

| # | 交付物 | 归属 |
|---|---|---|
| 1 | `jobwrap-gate5` 二进制（guest 内编译）+ 其 SHA-256 | M5 写规格/源码，M3/VMer guest 编译 |
| 2 | `jobwrap-gate5` 的 fixed-argv 调用文档（精确语法 + hash + 隔离 attestation 输出） | M5 |
| 3 | Gate 5 Route A 真实 probe 输出（probe.sh 隔离项 + m4_gate5_probe.py 结果） | M3/VMer 跑，M4 独立核查 |
| 4 | 记录 `51` 补 `PASS/FAIL/NOT VERIFIED` | M4 |

---

## 4. 与旧 jobwrap 的关系（关键边界，避免证据链污染）

| 维度 | 旧 `jobwrap` (b232d60b) | 新 `jobwrap-gate5` |
|---|---|---|
| 绑定的 gate | Gate 4 | Gate 5 |
| 源码状态 | 丢失（仅 derived reconstruction 归档） | 新建（有源码，进 git） |
| 模式 | gate3 / probe / gate4 | probe m4-gate5 |
| 是否重签 P4 | **否** | 无关 |
| 证据链 | P4/fingerprint/SHA256SUMS 不变 | 新 hash 只进 Gate 5 记录 |

---

## 5. 开放点裁决（已由 Lead 落定，2026-10-31）

1. **`probe blob` 钉死谁** → **选 (a)**：successor 直接 `exec /usr/bin/python3 <repo>/scripts/m4_gate5_probe.py`，编译期钉死 probe blob `F39A0302…D146CB`；**不读 env**；**明确否决 (b)**。`m4_gate5_fixed.sh`（blob `B751BB7F…13C5`）走 PATH 且不 hash probe，**推荐直接 probe，不经 fixed.sh**。

2. **隔离是否要求 byte-equivalence** → **否**。语义等价即可（root-only、netns/no-egress、setgroups→setgid(1003)→setuid(1003)、CapEff=0、seccomp、NoNewPrivs=1、rlimits、clearenv、fixed argv、绝对路径、脚本 root-owned/不可写、fail-closed），不要求逐字节等价。

3. **successor 源码是否进 git** → **是**。源码 + build recipe 必须进 git（旧 jobwrap 丢失的根因就是没进 git）。

---

## 6. 明确不做的事（scope 边界）

- 不重编、不覆盖旧 `jobwrap`（`/usr/local/sbin/jobwrap` 保持 b232d60b）；
- 不重签 P4 / Gate 4 证据链；
- 不声称 derived reconstruction（`jobwrap_v3_reconstructed.c`）可 hash 等价，它只归档审计；
- 不在 host 编译任何二进制（AGENTS.md 红线，编译必须在 guest 内）。

## 6b. 绑定与记录策略（批准定案）

- successor 源码 + build recipe **必须进 git**；
- Gate 5 记录绑定**新 binary hash + probe blob `F39A0302…D146CB`**；
- 记录 `51` **仍 unsigned**，等 M4 独立核查后才填 `PASS/FAIL/NOT VERIFIED`。

---

## 7. 签名（待补）

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead（批准） | Lead | 2026-10-31 | **APPROVED** — B2 已过时（main 99db9c9 已有校验 blob FB5FD90B…）；开放点 1 选 (a) 直接 probe、钉死 F39A0302…D146CB、否决 (b)；不要求 byte-equivalence；源码+build recipe 进 git；不覆盖旧 jobwrap/不重签 P4；51 仍 unsigned |
| M5（规格） | — | — | pending |
| M3/VMer（guest 编译 + 执行） | — | — | pending |
| M4（独立核查） | — | — | pending |
