# Route B 真实样本可行性检查清单

**状态：** 等待成员 3 冻结公共样本（`route-a/docs/05-sample-analysis.md` 当前全部为 TBD）。
**用途：** 样本到位后，按 G0–G9 在 1–2 小时内给出 **PASS / FAIL / UNSUPPORTED** 结论，
而不是"感觉能跑"。

> 现在能做的只有预演：用 `routeb/fixture/vuln` 跑通流程本身（已 6/6）。
> 真实样本的 round trip 在 G0 未通过前一律记 `not_run`，不能写成"已验证"。

---

## 0. 需要成员 3 提供的输入

缺任何一项，对应 gate 记 `not_run`，不要用猜测值补。

| # | 输入 | 从哪里拿 | 缺失后果 |
|---|---|---|---|
| 1 | ELF 路径 + SHA-256 | `route-a/docs/05-sample-analysis.md` | 无法绑定身份，全部 gate 阻塞 |
| 2 | 构建命令、编译器/版本、日期、构建人 | 同上 | 无法判断"重编译差异"来源 |
| 3 | 漏洞函数名、入口地址、函数字节数 | Ghidra / `nm` | 无法导出与替换 |
| 4 | 有效/无效输入域、期望返回值/输出 | 契约（成员 4 复核） | 无法判定 round trip 是否保持行为 |
| 5 | 已知触发输入（长度/内容） | 复现记录 | 无法证明缺陷仍可复现（G5） |
| 6 | 二进制级可观察效果（崩溃/覆盖/退出码） | 复现记录 | 无法建立基线 |
| 7 | 允许的修改范围与禁用项 | 契约 | 无法判定候选是否越界 |
| 8 | 谁复核了上述内容 | 评审记录 | 结论不可用于验收 |

---

## 1. G0 — 身份与 provenance（最先做）

```bash
SAMPLE=fixtures/public/<sample>
FUNC=<vulnerable_function>
sha256sum "$SAMPLE"
file "$SAMPLE"
readelf -h "$SAMPLE" | sed -n '1,20p'
```

- [ ] hash 与成员 3 记录的完全一致（写进实验记录）
- [ ] `ELF 64-bit LSB executable, x86-64`，`ET_EXEC`（非 PIE），非 stripped 或符号可用
- [ ] 函数名能在符号表里找到：`nm "$SAMPLE" | grep " $FUNC$"`
- [ ] 样本不在客户数据范围（公开/合成），可外发

失败：`UNSUPPORTED`（画像不符）或 `ERROR`（身份对不上，停止）。

## 2. G1 — 支持画像

- [ ] 单进程、单线程
- [ ] 无 packed / 自修改代码
- [ ] 修复区域不依赖 TLS、C++ 异常、特殊 unwind
- [ ] 没有未解析的间接跳转进入将被覆盖的字节
- [ ] 不新增外部库依赖

任何一项不满足：`UNSUPPORTED`，并写清哪一条。

## 3. G2 — Ghidra 导出

```bash
./routeb/ghidra/export.sh "$SAMPLE" "$FUNC"
cat routeb/out/$FUNC.c.meta.txt
```

- [ ] 函数找到，`size_bytes` 合理（几十到几百字节）
- [ ] 记录 `callees=`：空 = 重定位简单；有 libc 调用 = 需 PLT 解析，风险升级
- [ ] 原始输出保存，未修改
- [ ] 记录 Ghidra 版本、JDK 版本

失败：`UNSUPPORTED`（函数过大/间接调用/无符号），保留日志。

## 4. G3 — 归一化

新建 `routeb/out/$FUNC.normalized.c`，只改类型和名字：

- [ ] 每次修改都有一行理由（diff 列表）
- [ ] 控制流、数组下标、检查逻辑**未改**
- [ ] 能独立编译：`cc -O0 -g0 -fno-stack-protector -fno-builtin -c routeb/out/$FUNC.normalized.c -o /tmp/$FUNC.o`
- [ ] 签名与二进制一致（参数个数/宽度/返回类型）

失败：回到 G2 或 `UNSUPPORTED`（例如出现 `code *`、结构体返回）。

## 5. G4 — unchanged round trip（核心 gate）

```bash
python routeb/probe_patcherex2.py \
  --binary "$SAMPLE" --func "$FUNC" \
  --mode roundtrip \
  --c-source "routeb/out/$FUNC.normalized.c" \
  --out "routeb/out/${FUNC}_roundtrip" \
  --skip-verify
```

> 真实样本不能用 `routeb/verify.py`：它是为本仓库合成 fixture 写的 oracle。
> 回填后请用团队冻结的测试清单（成员 4/1）验证，命令记入实验记录。

- [ ] 回填后的 ELF 能启动
- [ ] 团队有效输入用例全部通过，输出/返回值与原始一致
- [ ] 已知触发输入仍然触发（缺陷没有被"顺手修好"）
- [ ] `readelf -lW` 段数量/权限无意外变化；有新增段则记录
- [ ] 改动字节范围可解释（函数体 ± 重定位）
- [ ] Patcherex2 版本、编译器版本、命令记录

失败处置见 §10。

## 6. G5 — 缺陷仍可复现

- [ ] 用成员 3 给的触发输入，在 round-trip 二进制上得到与原始相同的可观察效果
- [ ] 如果缺陷消失：**不是修复成功**，是行为变化；记 round-trip FAIL

## 7. G6 — 布局与兼容性审计

```bash
readelf -lW "$SAMPLE" > /tmp/before.segments
readelf -lW "routeb/out/${FUNC}_roundtrip" > /tmp/after.segments
diff -u /tmp/before.segments /tmp/after.segments
```

- [ ] 入口地址、load 段、权限符合契约
- [ ] 无重叠写入、无未解析重定位
- [ ] 不静默关闭 NX/RELRO/栈保护
- [ ] 记录 changed / added bytes 两个数字

## 8. G7 — 模型候选（DeepSeek）

前提：G4/G5 通过。

```bash
# CONTRACT = 成员4 复核过的契约文本文件（不是 PRD 摘录）
CONTRACT=docs/route-b/contracts/<sample>.txt

python scripts/demo_candidate.py \
  --binary "$SAMPLE" \
  --function "$FUNC" \
  --recovered "routeb/out/$FUNC.normalized.c" \
  --signature "<从 meta 抄的签名>" \
  --contract "$CONTRACT" \
  --allowed-calls "<逗号分隔，没有就留空>" \
  --out-c "routeb/out/$FUNC.model.c"
```

`--allowed-calls` 取 G2 的 `callees=` 与契约的交集；为空表示只允许纯函数。

- [ ] 候选通过 schema + scope 校验（`accepted_for_validation`）
- [ ] 只改了允许的范围；`expected_effects` 与契约一致
- [ ] 没有新增调用/头文件/属性
- [ ] 记录 prompt hash、model、tokens、费用

失败：`REJECTED`（格式/越界）或 `ERROR`（provider），保留诊断。

## 9. G8 — 修复候选验证

```bash
python routeb/probe_patcherex2.py \
  --binary "$SAMPLE" --func "$FUNC" \
  --mode fixed \
  --c-source "routeb/out/$FUNC.model.c" \
  --out "routeb/out/${FUNC}_fixed" \
  --skip-verify
# 然后用团队测试清单跑最终 ELF
```

- [ ] 修复后的 ELF 上，触发输入不再越界/崩溃
- [ ] 无效输入走契约规定的错误路径
- [ ] 有效输入 100% 通过
- [ ] 有界符号检查（成员 4）在最终 ELF 上完成，且不是 unknown/timeout
- [ ] 改动区域与 G6 审计一致

## 10. G9 — 证据与复现

- [ ] 原始/候选 hash、契约 hash、测试清单 hash
- [ ] raw / normalized / model C 三份文件与 diff
- [ ] 工具版本、命令、环境
- [ ] 失败/未跑的项显式标注，不用"应该"补
- [ ] 另一位成员能按记录复跑

---

## 11. 失败处置矩阵

| 现象 | 结论 | 动作 |
|---|---|---|
| hash/画像不符 | `UNSUPPORTED` | 停止，退回成员 3 换样本或补信息 |
| Ghidra 导出失败/函数过大 | `UNSUPPORTED` | 记录原因，不硬改 |
| 归一化后编译失败 | `UNSUPPORTED` / `ERROR` | 保留 diff，评估是否换函数 |
| 回填后不启动 | `ERROR` | 查重定位/段权限；未定位前不继续 |
| 有效输入行为变化 | `REJECTED`（round trip） | 回 G3 逐行 diff |
| 触发输入不再越界 | `REJECTED`（行为变化） | 不是修复；查编译器差异 |
| 模型候选格式/越界 | `REJECTED` | 保留候选与 reason_code |
| provider 超时/配额/空 | `ERROR` | 按 typed failure 记录，不伪造候选 |
| 符号检查 unknown/timeout | `INCONCLUSIVE` | 不能显示成功 |

---

## 12. 时间盒（样本到位后）

| 阶段 | 上限 | 超时动作 |
|---|---|---|
| G0–G2 | 30 min | 记 blocker，先问成员 3 |
| G3 | 30 min | 超过 2 小时仍未编译通过 → `UNSUPPORTED` |
| G4–G6 | 45 min | 失败即记录，不在当天死磕 |
| G7–G8 | 45 min | 只跑一次候选，不无限重试 |

---

## 13. 记录模板

```markdown
### Route B feasibility — <sample> — <date>

- sample sha256:
- func / entry / size:
- build: <cmd>, compiler <version>
- Ghidra/JDK:
- callees:
- normalization edits:
- Patcherex2 version:
- G4 round trip: PASS / FAIL / UNSUPPORTED
- G5 defect still observable: yes / no
- G6 segments changed: yes / no (details)
- G7 candidate: accepted / rejected:<reason>
- G8 fixed: pass / fail:<case>
- evidence paths:
- blockers:
```
