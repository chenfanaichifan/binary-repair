# BinaryRepair 10 分钟产品演示（中文版）

对象：潜在客户/合作方/评审人。
目标：展示「有界修复 + 可审计证据」，并展示产品会明确拒绝做不到的输入。
**演示全程不使用 API key，不访问外网。**
英文主文档：`BT`docs/product/DEMO.md`BT`。

## 0. 演示能证明什么 / 不能证明什么

能证明：

- 一条命令完成 scan -> repair -> 独立验证 -> 证据导出；
- 两个已提交 fixture 达到确定性 verified 结论，并被独立验证器确认；
- 一个矩阵外输入被拒绝，且不产出任何候选字节（失败关闭）；
- 报告中的每个结论都有 SHA256 证据索引支撑。

不能证明：

- 任意二进制修复、未知漏洞挖掘、whole-program 证明；
- 修复成功率：公开 benchmark 仅 **2/24 verified（8.3%）**、hidden **0/8**；
- 修复后的二进制可安全上生产。

## 1. 前置条件（1 分钟）

- 仓库已创建 `BT`.venv`BT`（`BT`./start-gui.sh`BT`，Python 3.11）；
- 演示本身不需要网络；
- 可选：运行中的 Lima 虚拟机作为 ELF x86-64 的 guest 运行时 oracle。没有它也能跑，
  但两个正例会显示 `BT`NOT_VERIFIED`BT` 并给出明确 not_run 原因（环境降级、失败关闭），
  产品绝不伪造验证。

`BT``BT``BT`bash
tools/product/run-demo.sh --list
`BT``BT``BT`

## 2. 三个 fixture

| id | 期望 | 说明 |
|---|---|---|
| `BT`strcpy-stack-x86_64`BT` | verified | CWE-121 栈 strcpy 溢出（ELF x86-64）；对应 benchmark 样本 `BT`stack-strcpy-x86_64`BT` |
| `BT`marcx-capacity`BT` | verified | capacity-check 混淆（ELF x86-64）；对应 benchmark 样本 `BT`heap-capacity-x86_64`BT` |
| `BT`unsupported-bigendian`BT` | refused | 64 字节大端 ELF64 头的合成负例；不是真实程序，只用于证明失败关闭 |

## 3. 先跑负例（1 分钟）

`BT``BT``BT`bash
tools/product/run-demo.sh unsupported-bigendian /tmp/binaryrepair-demo-neg
`BT``BT``BT`

预期（节选）：

`BT``BT``BT`text
[1/1] unsupported-bigendian: REFUSED (disposition=unsupported, verifier=not_run, oracle=not_run, tier=None)
      reason: big-endian elf/x86_64 is outside the repair matrix
      not_run: ... no candidate produced (disposition=unsupported); nothing is downloadable
`BT``BT``BT`

讲解点：矩阵外输入被拒绝、原因明确、**不产出任何字节**。

## 4. 跑完整演示（3 分钟）

`BT``BT``BT`bash
tools/product/run-demo.sh all artifacts/m3-product-2026-11-17/demo
`BT``BT``BT`

参考宿主上的预期输出：

`BT``BT``BT`text
[1/3] strcpy-stack-x86_64: VERIFIED_WITHIN_SCOPE (disposition=verified_patch, verifier=verified, oracle=pass, tier=emulated_run)
[2/3] marcx-capacity: VERIFIED_WITHIN_SCOPE (disposition=verified_patch, verifier=verified, oracle=pass, tier=emulated_run)
[3/3] unsupported-bigendian: REFUSED (disposition=unsupported, verifier=not_run, oracle=not_run, tier=None)
report (en): .../REPORT.md
report (zh): .../REPORT.zh.md
boundary: public benchmark 2/24 verified (8.3%) | hidden 0/8 | one target function/sink per candidate
`BT``BT``BT`

参考宿主实测耗时约 46 秒（见 `BT`demo-run.json`BT` 的 `BT`elapsed_seconds`BT`）。

## 5. 解读报告（2 分钟）

打开 `BT`artifacts/m3-product-2026-11-17/demo/REPORT.zh.md`BT`：

1. 第 0 节：边界（公开 2/24、hidden 0/8）与不可承诺清单；
2. 第 1 节：执行摘要（fixture、结论、disposition、独立验证、oracle、运行层级）；
3. 第 2 节：逐项结果（输入 SHA256、扫描视图、修复字段、独立验证检查表、限制、not_run）；
4. 第 3 节：失败关闭自检（必须为「通过」）；
5. 第 4 节：SHA256 证据索引；第 5 节：不可承诺口径。

校验证据：

`BT``BT``BT`bash
cd artifacts/m3-product-2026-11-17/demo
shasum -a 256 -c SHA256SUMS
`BT``BT``BT`

## 6. 边界沟通（2 分钟）

要说：

- 「这是有界修复 + 可审计证据：一个 target 函数/sink、给定 PoC/回归、独立验证器。」
- 「公开 benchmark 2/24 verified（8.3%），hidden 0/8；我们不宣称泛化。」
- 「验证不了就拒绝或标记未验证，不产出字节、不宣称成功。」
- 「AI 只是候选生成器，验收权在确定性 gate 与独立验证器；本演示不调用模型。」

不要说：

- 「任意二进制」「100%」「通用修复」「保证安全」；
- 「打了补丁就可以上生产」；
- 报告里没有的 hidden/多模型数字。

## 7. 排障

| 现象 | 含义 | 处理 |
|---|---|---|
| `BT`ERROR: python venv not found`BT` | 缺少 `BT`.venv`BT` | 先跑一次 `BT`./start-gui.sh`BT`；演示本身不需要网络 |
| 正例显示 `BT`NOT_VERIFIED`BT` 且有 runtime not_run | 该宿主无 guest oracle | 属于预期的失败关闭；不得宣称已验证 |
| `BT`unknown fixture(s)`BT` 且退出码 2 | fixture id 写错 | 先跑 `BT`--list`BT` |
| 报告出现 `BT`FAIL-CLOSED CHECK FAILED`BT` | 检测到内部不一致 | 停止演示并上报，不得展示该次运行 |

## 8. 演示验收标准

1. `BT`--list`BT` 恰好列出 3 个 fixture 及其期望；
2. 负例返回 `BT`REFUSED`BT`、原因明确、无候选字节；
3. 两个正例要么 `BT`VERIFIED_WITHIN_SCOPE`BT`（独立验证 verified），要么
   `BT`NOT_VERIFIED`BT` 且带 runtime not_run 原因（环境降级）；
4. 报告失败关闭自检为「通过」；
5. `BT`shasum -a 256 -c SHA256SUMS`BT` 通过；
6. 讲解人说出 2/24、0/8 与不可承诺清单。

## 9. 相关文档

- `BT`docs/product/PRODUCT-POSITIONING-2026-11-17.md`BT`（英文）/ 本目录中文版；
- `BT`docs/product/CUSTOMER-REPORT-TEMPLATE.md`BT`；
- `BT`docs/product/DELIVERY-PACKAGE.md`BT`；
- `BT`docs/product/TRIAL-GUIDE.md`BT` / 本目录 `BT`TRIAL-GUIDE.zh.md`BT`；
- 权威限制：`BT`docs/acceptance/LIMITATIONS.md`BT`、`BT`docs/status/claims.json`BT`。
