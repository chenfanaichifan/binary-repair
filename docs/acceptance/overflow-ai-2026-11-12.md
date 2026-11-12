# 缓冲区溢出 AI 识别/修复升级报告（2026-11-12）

## 1. 范围与结论

本轮把用户给出的 **6 类根因 × 2 个样本 = 12 个 C 种子** 做成可复现语料，
并升级了规则、候选记忆、编译验证和二进制表面扫描。

结论先说清楚：

- **12/12 种子**被确定性规则命中预期 CWE，并生成补丁；
- **12/12 原始代码和 12/12 规则补丁**通过 clang + ASan 编译；
- 合成同分布分类准确率约 1.0，但**留一种子准确率仅约 0.25**；
- 因此模型只做候选排序，不能替代规则/人工/动态验证；
- 没有“自动学会所有新型漏洞”的保证；所谓迁移是结构特征、规则和案例记忆。

## 2. 六类根因 / 十二个种子

| 组 | CWE | 代表根因 | 规则 |
|---|---|---|---|
| 栈 | CWE-121 | `strcpy` 无界；相邻 `is_admin` 被覆盖 | `c.strcpy` / `c.stack-adjacent-overwrite` |
| 堆 | CWE-122 | `malloc(128)` + 超长 `memcpy`；成员 `data[16]` 被 `strcpy` 覆盖 | `c.heap-length` / `c.heap-member-overflow` |
| 全局/静态 | CWE-119 | 全局函数指针相邻溢出；`strcat` 无界追加 | `c.global-pointer-overwrite` / `c.strcat` |
| 整数 | CWE-190 | `count*size` 回绕；`base_len+input_len` 回绕 | `c.mul-overflow` / `c.add-overflow` |
| 差一 | CWE-193 | `i <= len`；`malloc(len)` 后写 `buf[len]` | `c.off-by-one-loop` / `c.heap-off-by-one` |
| 格式化 | CWE-134 | `printf(user_input)`；`snprintf` 后再 `printf(buf)` | `c.format-string` |

种子与标签：`data/overflow-corpus/`。

## 3. 自训练流程

`scripts/generate_overflow_corpus.py`：

- 12 个种子 × 100 个标识符/容量/函数名变体 = **1200 条**；
- 标签继承种子的 CWE/规则；
- 变体只用于训练和回归，不声称代表真实项目分布。

`scripts/train_overflow_knowledge.py`：

1. 结构特征（30+ 维）：危险 API、数组、全局/静态、成员访问、`<=`、乘法/加法长度、malloc 常量/变量、格式化调用等；
2. 初始模型只看 20% 训练集；
3. 对剩余数据做置信度 ≥0.70 的伪标签；
4. 加入伪标签重训（本轮 768 条）；
5. 在 20% 测试集和“留一整颗种子”上分别评估；
6. 导出纯 JSON 权重，运行时不需要 sklearn。

结果：

```text
同分布 synthetic test accuracy: 1.0000
同分布 macro-F1:               1.0000
leave-one-seed-out accuracy:   0.2500
pseudo-labeled rows:           768
```

**解释**：同分布变体共享模板，准确率会虚高；整颗种子留出后模型明显退化。
这不是“模型已学会所有溢出”，而是“合成数据不足以证明泛化”。

## 4. 运行时如何使用记忆

`app/services/overflow_ai.py`：

- 加载 `knowledge/overflow_model.json`；
- 提取结构特征 → 标准化 → 逻辑回归 → softmax；
- 返回 `cwe/confidence/alternatives/novelty/candidate_only`；
- 没有任何已知风险特征时返回 `cwe: null, novelty: true`，避免把普通代码硬分类；
- API 响应始终 `not_verdict: true`。

API：

```text
GET  /api/knowledge/overflow
POST /api/knowledge/classify   {"code": "..."}
```

## 5. 编译与二进制表面

`scripts/validate_overflow_corpus.py`：

- clang `-fsanitize=address -g -O0` 编译 12 个原始样本；
- 编译 12 个规则补丁；
- 记录原始/补丁的 `nm -u` 导入面；
- 结果在 `knowledge/overflow_validation.json`。

**重要**：没有执行漏洞程序；编译通过不等于补丁正确。危险导入只是攻击面，
不是漏洞结论。`scripts/binary_overflow_surface.py` 提供同样的只读表面扫描。

## 6. 失败与教训

1. **正则规则能覆盖结构化形态，但不能覆盖语义。**
   `strcpy`/`memcpy` 只是入口；容量、长度来源、可达性才是漏洞。
2. **同分布准确率会骗人。**
   1200 条变体只改变名字/大小，测试集仍与训练集共享模板；必须做种子/项目/时间切分。
3. **模型不能直接生成“已验证补丁”。**
   补丁必须编译、运行、ASan/UBSan、回归、差分/符号验证。
4. **二进制表面扫描不能替代反汇编/数据流。**
   导入 `memcpy` 不等于溢出；优化和内联还会抹掉符号。
5. **“自动记忆”必须是可审计的离线训练。**
   运行时自动改权重会污染知识库；本轮采用离线 JSON 权重 + 显式版本/限制。

## 7. 下一阶段路线

- 接入真实修复语料（CVEfixes、Vul4J、ARVO、OSS-Fuzz），按项目/时间切分；
- 用 clang AST/LLVM IR 做容量/索引/长度的数据流，替代纯正则；
- 对候选补丁做 ASan/UBSan + 单元测试 + fuzz + 符号执行；
- 对二进制用 DWARF/Ghidra/angr 恢复栈帧/堆分配/长度来源；
- 引入补丁等价/差分验证（Alive2/CBMC/Diaphora）；
- 知识库记录“规则命中、模型候选、编译通过、动态触发、人工复核”五种不同证据级别；
- 不以单一 accuracy 作为安全结论；报告混淆矩阵、留出集和失败案例。

## 8. 复现命令

```bash
python3 scripts/generate_overflow_corpus.py --count 100
python3 scripts/train_overflow_knowledge.py
.venv/bin/python scripts/validate_overflow_corpus.py
.venv/bin/python scripts/classify_overflow.py data/overflow-corpus/seeds/01_stack_strcpy.c
```
