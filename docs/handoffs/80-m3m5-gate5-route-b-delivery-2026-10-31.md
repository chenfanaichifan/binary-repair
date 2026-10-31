# 80 — M3/M5 Gate 5 Route B 交付记录

日期：2026-10-31
作者：M3 (producer) / M5 (adapter)，交付给 M4 (verifier) / Lead

## 目的

补齐 Gate 5 Route B 的 successor probe 交付。此前 Gate 5 只交付了 Route A
（candidate `c4a15921…aa82`），Route B（candidate `208574ab…6717`）在
BOARD 上标记为 "NOT RUN / separate"。本记录完成 Route B 的 M4 placement
probe 运行与证据收口，满足「M3 / VMer 一次交齐」清单。

## 交付物清单

| 项 | 实体 | hash |
|---|---|---|
| successor 源码 | `route-a/jobwrap-gate5/jobwrap_gate5.c` | `c60c16eb…42ade` |
| Route B probe 脚本 | `scripts/m4_gate5b_probe.py` | `05d9a2cd…edb82` |
| build recipe | `route-a/jobwrap-gate5/build-recipe.md` | — |
| guest 编译 successor | `routeb-successor/jobwrap-gate5` | `0066973d…09eee` |
| 工具链 | gcc 13.3.0, Ubuntu 24.04, kernel 6.8.0-147 | — |
| Route B candidate | `routeb-evidence/candidate.elf` | `208574ab…6717` |
| Route B original | `routeb-evidence` (R1-original) | `aa428157…8393` |

## 关键结论

1. **Route B candidate 绑定**：`208574ab…6717`（与用户清单一致，与
   P3B/P2-real 三处 hash 一致）。

2. **successor 重编译**：Route A 版 successor（`90af91ef…ff20`）仅支持
   `m4-gate5`；为支持 Route B 新增 `m4-gate5b` 模式并钉死 Route B probe
   blob，重编译一次得到 `0066973d…09eee`。`m4-gate5`（Route A）模式的
   probe blob `f39a0302…d146cb` 与隔离语义**不变**，Route A 证据链不受影响。

3. **Route B probe 结果**：16 PASS / 0 FAIL / 0 NOT VERIFIED。

4. **隔离运行证据**（environment.txt）：
   - Uid/Gid = 1003
   - CapEff = 0000000000000000（0）
   - NoNewPrivs = 1
   - Seccomp = 2
   - default_route = ''（no egress）
   - netns = net:[4026532222]（isolated）

5. **入口重定向**（redirect-target.txt）：entry `0x4012b0` → target `0x4018ec`
   （落在 R-X tail `0x4018e9..0x402000` 内）。

6. **fail-closed**：篡改 probe blob（`a048821d…8e4b`）后 successor 拒绝执行，
   `probe blob mismatch`，exit 1。

## 证据文件结构

```
docs/handoffs/evidence/Gate5/
├── routeb-evidence/          # 31 文件（probe 运行证据 + 内部 SHA256SUMS）
│   ├── candidate.elf
│   ├── environment.txt
│   ├── gdb-probe.log         # 已 sanitize（无 evaluator 路径泄漏）
│   ├── probe-summary.json    # 16 项 PASS
│   ├── redirect-target.txt
│   ├── six-cases.json
│   ├── tail-file.bin / tail-memory.bin + .sha256
│   ├── case-*.rc / *.stdout.bin / *.stderr.bin   # 6 case × 3 = 18 文件
│   └── SHA256SUMS
├── routeb-fail-closed/       # 5 文件（command / exit-code / stderr / stdout / tampered hash）
├── routeb-successor/         # jobwrap-gate5 + m4_gate5b_probe.py + 源码 + README + build-env + build-recipe
├── routeb-invocation.txt
└── routeb-SHA256SUMS         # 顶层 43 行，LF
```

## 校验

- routeb-evidence 内部 SHA256SUMS：30/30 OK，0 FAILED
- routeb-SHA256SUMS 顶层：43/43 OK，0 FAILED
- 全部使用 LF 换行，可用标准 `sha256sum -c` 干净校验

## 待 M4 / Lead

1. M4 独立 re-hash Route B 证据（`sha256sum -c routeb-SHA256SUMS`）。
2. Lead 裁定 Gate 5 Route B（此前 record 51 的 unsigned 状态是否需要在
   Route B 完成后一并签名）。
