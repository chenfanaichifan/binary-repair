# 试用指南（中文版）

状态：试用设计原型（M3，2026-11-17）。目标是验证「有界产品是否有用、边界是否讲清」，
**不是** 证明通用修复能力。英文主文档：`BT`docs/product/TRIAL-GUIDE.md`BT`。

## 1. 试用规则

1. 只使用你有权分析/修改的二进制（许可证允许修改，或已有内部书面授权）；
2. 优先使用内置 fixture 与非生产二进制；试用期间不要上传/处理生产二进制；
3. 每次运行记录：完整命令、宿主、耗时、结论、not_run 原因；
4. 「试用成功」不代表「任意修复可用」，只代表理解并验证了有界流程与证据；
5. 不得写「任意二进制/100%/保证安全」的客户材料；权威数字是公开 2/24（8.3%）、hidden 0/8。

## 2. 五个试用任务

### T1 验证失败关闭（10 分钟）

`BT``BT``BT`bash
tools/product/run-demo.sh unsupported-bigendian /tmp/trial-neg
`BT``BT``BT`

成功判定：

- 结果为 `BT`REFUSED`BT`、`BT`disposition=unsupported`BT`；
- 原因写明矩阵边界；
- 输出目录中不存在 `BT`candidate.bin`BT`；
- `BT`not_run`BT` 行解释为何没有产出。

失败判定：出现候选文件、宣称成功、或原因缺失。

### T2 跑栈溢出正例（20 分钟）

`BT``BT``BT`bash
tools/product/run-demo.sh strcpy-stack-x86_64 /tmp/trial-stack
`BT``BT``BT`

成功判定：

- `BT`VERIFIED_WITHIN_SCOPE`BT` + `BT`independent_decision=verified`BT` + oracle `BT`pass`BT`
  （无 guest oracle 的宿主上为 `BT`NOT_VERIFIED`BT` 并带 runtime not_run 原因，需记录属于哪种情况）；
- 报告失败关闭自检为「通过」；
- `BT`shasum -a 256 -c SHA256SUMS`BT` 通过；
- 试用者能说明「验证了什么、没验证什么」（一个函数 + 给定 PoC/回归，不是整个二进制）。

### T3 跑 capacity 混淆正例（20 分钟）

同 T2，fixture 换成 `BT`marcx-capacity`BT`。额外成功判定：试用者能解释 capacity-check
混淆类，以及为什么错误容量候选会被运行时 oracle 拒绝而不是静默接受。

### T4 用 CLI 试一个矩阵外/不支持输入（20 分钟）

`BT``BT``BT`bash
.venv/bin/python scripts/repair_binary.py <binary> /tmp/trial-out.bin \
    --target <SYMBOL 或 VA 区间> --require-target \
    --poc <POC-MANIFEST.json> --report /tmp/trial-report.json
`BT``BT``BT`

（没有 PoC manifest 时可省略 `BT`--poc`BT`；此时结果不能 verified，必须失败关闭。）

成功判定：

- 返回明确 disposition（`BT`analysis_only`BT` / `BT`unsupported`BT` / `BT`invalid`BT` /
  已验证或未验证）并生成 JSON 报告；
- 被拒绝的输入：退出码 2、无输出文件，是预期的失败关闭；
- 试用者能指出报告中的确切原因。

失败判定：被拒绝输入仍产出文件，或无运行时证据却宣称成功。

### T5 审计证据包（15 分钟）

`BT``BT``BT`bash
cd /tmp/trial-stack
shasum -a 256 -c SHA256SUMS
python3 -m json.tool EVIDENCE-INDEX.json > /dev/null
grep -n "failed|not_run|not claimed|2/24|0/8" REPORT.md
`BT``BT``BT`

成功判定：校验和通过；索引覆盖全部证据文件；试用者无需帮助即可找到边界数字、
限制与 not_run 行。

## 3. 反馈模板

`BT``BT``BT`markdown
试用者/角色：
日期/宿主：
完成任务：T1 T2 T3 T4 T5
各任务观察到的结论：
阻塞点（卡在哪里）：
异常行为（命令 + 输出）：
边界清晰度（1-5，5=完全清楚）：
证据可用性（1-5，5=可独立审计）：
是否会用于「已知 CVE + 无源码二进制」场景？（会/不会/取决于：原因）
下一次试用最有价值的内容：
NPS（0-10）及原因：
定价反应（原型问题、无承诺）：过高/合理/过低/需要解释价值指标：
可引用的原话（需授权）：
`BT``BT``BT`

## 4. 试用项目成功的标准

- 试用者无需帮助完成 T1-T3，并能解释失败关闭行为；
- 至少一位试用者可独立完成 T5 证据审计；
- 试用者不会过度解读结果（不产生「任意修复可用」的结论）；
- 具体阻塞点（oracle 可用性、报告清晰度、矩阵缺口）进入产品待办，而不是被隐藏。

## 5. 明确未运行（not_run）

- 尚未招募/执行任何外部试用用户（not_run）；
- 定价与包装尚未验证（not_run）；
- 试用期间不处理、也不应处理生产二进制。
