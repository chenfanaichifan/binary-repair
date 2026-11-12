# Overflow candidate memory · 说明与诚实边界

这里存放“源级 C 溢出候选记忆”，用于：

1. 把 12 个手工种子扩展成可复现的训练/回归数据；
2. 训练一个轻量、可解释的 CWE 候选分类器；
3. 给规则引擎提供一个**候选排序**，而不是替代规则；
4. 把验证过的结构、指标和限制留成可审计的知识库。

## 目录

| 文件 | 作用 |
|---|---|
| `overflow_model.json` | 结构特征 + 标准化 + 多项逻辑回归系数（运行时纯 Python 加载） |
| `overflow_kb.json` | 语料统计、指标、12 个种子、规则/根因/修复说明 |
| `overflow_validation.json` | 12 个种子/补丁的编译结果与二进制导入面 |

## 语料

- 12 个种子，覆盖 6 类根因：
  - CWE-121 栈溢出（2）
  - CWE-122 堆溢出（2）
  - CWE-119 全局/静态区（2）
  - CWE-190 整数回绕（2）
  - CWE-193 差一（2）
  - CWE-134 格式化字符串（2）
- 每个种子生成 100 个变体：标识符、容量、函数名变化，共 1200 条。
- 生成器：`scripts/generate_overflow_corpus.py`
- 训练器：`scripts/train_overflow_knowledge.py`
- 验证器：`scripts/validate_overflow_corpus.py`

## 指标（必须连同限制一起读）

训练脚本记录两类指标：

- **同分布合成测试**：约 1.0 accuracy / 1.0 macro-F1；
- **留一种子（leave-one-seed-out）**：约 0.25。

这不是矛盾，而是说明：

> 变体与种子共享模板，同分布准确率会虚高；把整颗种子留出后，模型并不能稳定泛化到新的代码结构。

因此：

- **规则引擎是主检测器**：12/12 种子命中预期规则；
- 模型只用于“候选 CWE 排序”，不能单独宣布漏洞；
- 不能在运行时自动更新权重；
- “自训练”是指离线伪标签轮次，不是模型自己改自己；
- 不能把 1.0 合成准确率当作真实世界泛化能力。

## 编译验证

`overflow_validation.json`：

- 12/12 原始样本：clang + ASan 编译通过；
- 12/12 规则补丁：编译通过；
- 未执行漏洞程序，因此**不证明**补丁正确；
- 记录的 unsafe imports 是二进制攻击面，不是漏洞结论。

## 已知边界

- 仅覆盖 12 个结构化种子，不是通用 C 静态分析器。
- 规则基于正则/结构，复杂指针、宏、`goto`、模板、C++ 容器、编译器优化后的二进制不在覆盖范围。
- 真实二进制缺少类型/容量信息，需要 DWARF、Ghidra/angr、ASan、符号执行和差分验证。
- 没有使用真实 CVE 语料；后续应接入 CVEfixes/Vul4J/ARVO 等，并做时间切分/项目切分评估。
- 不存在“自动获得所有新型漏洞”的保证；所谓迁移是特征/规则/案例检索，不是无监督地产生无限能力。

## 复现

```bash
# 1. 生成 1200 个合成变体（写入 var/，不提交）
python3 scripts/generate_overflow_corpus.py --count 100

# 2. 离线训练，写 knowledge/overflow_model.json 与 overflow_kb.json
#    需要系统 Python 的 scikit-learn/numpy；应用运行时不需要它们
python3 scripts/train_overflow_knowledge.py

# 3. 编译验证 12 个种子与补丁
.venv/bin/python scripts/validate_overflow_corpus.py

# 4. 单文件候选分类（运行时纯 Python）
.venv/bin/python scripts/classify_overflow.py data/overflow-corpus/seeds/01_stack_strcpy.c
```

API：

```text
GET  /api/knowledge/overflow
POST /api/knowledge/classify   {"code": "..."}
```

响应始终带 `not_verdict: true` / `candidate_only: true`。
