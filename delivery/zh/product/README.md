# delivery/zh/product - 中文版产品材料

本目录存放 M3 产品化材料的中文版本；**英文主文档**在 `BT`docs/product/`BT`（受
`BT`scripts/check_markdown_language.py`BT` 的 ASCII-English 门禁约束），两者内容对应，
冲突时以 `BT`docs/status/claims.json`BT` 与 `BT`docs/acceptance/LIMITATIONS.md`BT` 为准。

| 文件 | 说明 |
|---|---|
| `BT`PRODUCT-POSITIONING-2026-11-17.md`BT` | 产品定位与边界（ICP、能力矩阵、SLO、不可承诺清单、竞品差异） |
| `BT`DEMO.zh.md`BT` | 10 分钟演示脚本（3 个 fixture、预期输出、验收标准） |
| `BT`TRIAL-GUIDE.zh.md`BT` | 试用指南（5 个试用任务、成功/失败判定、反馈模板） |

英文主文档索引见 `BT`docs/product/README.md`BT`。客户报告由
`BT`scripts/product/export_report.py`BT` 自动生成：
`BT`REPORT.md`BT`（英文）与 `BT`REPORT.zh.md`BT`（中文）。

产品材料必须写明：公开 benchmark **2/24 verified（8.3%）**、hidden **0/8**；
不得宣称任意二进制 / 100% / 通用修复。
