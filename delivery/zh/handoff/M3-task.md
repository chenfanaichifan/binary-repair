# M3 任务 — 产品化与端到端交付（产品视角，SaaS 形态）

> 本文件是 M3 的完整接手包。读完即可开工；不需要读历史会话。
> 任务来源：组长 2026-11-16 复核决议——**这是产品（全自动 SaaS），不是只交研究报告；能力有限但必须能交付、能演示、能说清边界。**

## 0. 一句话目标

把当前**有界但真实**的修复能力包装成 "10 分钟内可演示、可试用、边界诚实" 的产品形态：产品定位与 ICP、端到端一键流程（scan→repair→verify→导出证据）、客户报告模板、部署/交付方案、定价与包装原型、90 天路线。**不夸大能力、不改修复算法。**

## 1. 必读（按顺序，10 分钟）

1. `review/STATE.md`
2. `项目总体回顾_完成现状_剩余任务与解决方案_2026-11-16.md` 的 **§1.5**、§5（现状/能力矩阵）、§6.2/6.3（问题与交付缺口）
3. `binary-repair-gui/README.md`、`START-HERE.md`、`DELIVERY.md`、`docs/acceptance/LIMITATIONS.md`（**必须原文引用边界，不能改写**）
4. `tools/handoff/README.md`

## 2. 环境与前提（已由 Lead 备好）

- 仓库 `binary-repair-gui/`，分支 `final/consolidated-2026-11-16`；venv 3.11.8；
- 第一步 `tools/handoff/check-env.sh`；
- 报告 `tools/handoff/member-report.sh m3 "标题"`；
- **不做 git 写**；不调用 live 模型；演示用现有确定性/mock 路径（无网络、无 key）；不新增依赖。

## 3. 准确的产品事实边界（必须写进所有产品材料）

| 事实 | 值/口径 |
|---|---|
| 公开 benchmark | **2/24 verified（8.3%）**；detection/root-cause/localization 各 3/24 |
| hidden | **0/8 verified**（8/8 executed、0 candidate）；不得宣称泛化 |
| 可修复范围 | 确定性矩阵内：ELF/PE/Mach-O x86-64/arm64 + ELF32/PE32 i386；拷入栈/堆（immediate heap）/容量校验类 sink；**每候选一个函数** |
| AI 能力 | asm_roundtrip / binary_direct 两条路径；3/3 非 loop 硬案例仅单模型（flash）；v4-pro 0/3；不能宣称通用 |
| 验证 | 确定性 gate + 独立验证器；**不是** whole-program/形式化证明；无 PoC 时 fail-closed（不下载、不 success） |
| 未运行/不可用 | self-hosted nightly、国际 5–6 模型矩阵、external ingestion、GDB/AFL、hidden 泛化 → 全部 `not_run`，产品材料必须显式列出 |
| 产品定位 | **有界修复 + 可审计证据**（target-scoped，PoC/回归证明），不是“任意二进制 100% 修复” |

## 4. 你的任务（P0 → P2）

### P0-1（首增量，90 分钟）产品定位与边界文档

新建 `docs/product/PRODUCT-POSITIONING-2026-11-17.md`，必须包含：
1. **客户与场景（ICP）**：谁最需要（无源码/第三方二进制供应链、遗留系统、CVE 应急修复）；不适用场景（whole-program、未知漏洞挖掘、任意架构/大端、UAF/格式串等）；
2. **产品承诺**：一次修复 = 一个 target 函数/sink + 可复现 PoC/回归 + 可审计证据包；
3. **能力矩阵与 SLO**：哪些 case 能承诺、哪些 `analysis_only`、哪些 `unsupported`；
4. **不可承诺清单**（直接引用 LIMITATIONS/claims 的 not_claimed，逐条列）；
5. **与竞品/替代方案的对比**（开源的 angr/Patcherex2/Ghidra 工作流、商业二进制热补丁；只写事实与差异，不贬低）。

### P0-2 端到端一键流程（产品 Demo）

新建：
```
scripts/product/demo_repair.py   # scan → repair → verify → export（复用现有 repair_any/verify，不复制核心逻辑）
scripts/product/export_report.py # 生成客户可读报告（md/html 均可）+ 证据清单
tools/product/run-demo.sh        # 工具入口：tools/product/run-demo.sh <fixture> <outdir>
docs/product/DEMO.md             # 10 分钟演示脚本（3 个 fixture：vuln-strcpy-x86_64 / marcx-capacity / 一个 unsupported 负例）
tests/test_product_demo.py       # 只测 CLI 结构与 fail-closed 行为，不测真实修复质量
```
要求：
- 演示路径**不需要模型 key/网络**；确定性路径失败时显式输出 `analysis_only/unsupported`，不伪造成功；
- 导出报告必须包含 verdict、检查表、limitations、not_run、证据 SHA256；
- `tools/product/run-demo.sh` 必须能一条命令跑完并在 stdout 给出结果摘要。

### P1-1 客户交付物模板

新建 `docs/product/CUSTOMER-REPORT-TEMPLATE.md`（客户报告：范围/发现/修复/验证/残余风险/证据索引）与 `docs/product/DELIVERY-PACKAGE.md`（交付包结构：报告 + 证据 + 候选 + 使用说明 + 限制）。

### P1-2 部署与商业化原型（只做原型，不做商业承诺）

新建 `docs/product/DEPLOYMENT-AND-PACKAGING.md`：
- 三种部署形态：本机 CLI/工作台、私有云（Docker/内网）、托管 SaaS（边界：客户二进制不出客户环境？如何做）；
- 定价/包装**原型**（3 档：单次修复/订阅/企业定制），标注“原型，需真实客户验证”；
- 合规/安全边界（客户数据、凭据、隔离、审计日志）；
- 90 天产品路线（与 §1.5 能力优先级对齐：先 Phase-10 能力，再产品化扩量）。

### P2 试用与反馈闭环

`docs/product/TRIAL-GUIDE.md`：5 个试用任务 + 成功/失败判定 + 收集反馈模板（NPS/阻塞点/误报）。

## 5. 写范围（严格）

允许新增/修改：
```
docs/product/**                 （新目录）
scripts/product/**              （新目录）
tools/product/**                （新目录）
tests/test_product_demo.py      （新文件）
artifacts/m3-product-2026-11-17/**（新目录，演示输出/截图/SHA256SUMS）
.tmp/handoff/m3/                （日志）
```
禁止修改：`app/**`、核心 `scripts/`（repair/verify/gate）、`fixtures/`、`docs/consolidation/*`、claims/LIMITATIONS、CI、M1/M2/M4 目录。

## 6. 红线

1. **不夸大**：任何材料不得出现“任意二进制/100%/通用修复”；公开 2/24、hidden 0/8 必须写；
2. **不改算法/不碰 gate**：M3 只做产品层；发现能力问题 → 报 M1/Lead；
3. **Demo 必须可跑、可复现**：无 key/无网络；失败显式；
4. 不做 git 写；不打印 key；不引入付费服务/新依赖；
5. 产品材料与 LIMITATIONS/claims 冲突时，以 claims/LIMITATIONS 为准并报 Lead。

## 7. 交付物

1. 产品文档（定位/DEMO/客户报告模板/部署与包装/试用）；
2. `tools/product/run-demo.sh` 可运行 + 演示输出（`artifacts/m3-product-2026-11-17/`）；
3. `.tmp/handoff/reports/m3-report-*.md`（工具生成）；
4. 给 Lead 10 行摘要（产品结论/演示结果/与能力的边界/需要决策）。

## 8. 时间盒

- 首增量 90 分钟：P0-1 定位文档 + P0-2 demo 脚本骨架；
- 当天完成 P0-2 可运行与 1 份演示输出；P1/P2 可留次日；
- 需要客户素材/价格决策 → 报 Lead，不自行编造市场数据。
