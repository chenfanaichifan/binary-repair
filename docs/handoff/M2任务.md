# M2 任务 — 跨函数语义最小原型（Phase-9 起点，只读分析）

> 本文件是 M2 的完整接手包。读完即可开工；不需要读历史会话。
> 任务来源：组长 2026-11-16 复核决议（总报告 §1.5）——Phase-9 只做**能解锁 Phase-10 的最小跨函数语义**，不做大而全。

## 0. 一句话目标

用 **3 周内可验证的最小原型**回答一个问题："当前 same-function/leaf-only 引擎为什么修不了跨函数/指针别名/全局目标漏洞？" 给出 CFG/call graph/跨函数数据流/指针别名的只读分析证据，并用 1–2 个真实 fixture 证明“当前引擎失败、新原型能定位”。**不接 gate、不产出候选、不宣称能力。**

## 1. 必读（按顺序，10 分钟）

1. `review/STATE.md`
2. `项目总体回顾_完成现状_剩余任务与解决方案_2026-11-16.md` 的 **§1.5**、§6.1 A4/A6、§7.2 Phase-9（E-01..E-06）
3. `tools/handoff/README.md`
4. `binary-repair-gui/docs/acceptance/LIMITATIONS.md`（heap/global/aliasing、跨函数相关段）
5. `binary-repair-gui/docs/operations/phase8-roadmap-2026-11-16.md`（G09–G18 状态）
6. `binary-repair-gui/app/services/repair/analyzer.py`（现有同函数分析器，**只读理解**）

## 2. 环境与前提（已由 Lead 备好）

- 仓库 `binary-repair-gui/`，分支 `final/consolidated-2026-11-16`；venv `.venv/bin/python` 3.11.8；
- 第一步：`tools/handoff/check-env.sh`；测试：`tools/handoff/run-scope-tests.sh m2`（新目录先建测试文件）；
- 报告：`tools/handoff/member-report.sh m2 "标题"`；
- **不做 git 写**；不调用 live 模型；不安装新依赖（如确需，先报 Lead，用现有 Capstone/LIEF/pyelftools）。

## 3. 准确基线（只读事实）

- 现有分析器：`app/services/repair/analyzer.py` 仅 same-function、leaf-only；heap 只覆盖同函数 immediate `malloc/calloc`；global/struct/跨函数别名 = 当前 non-goal/analysis-only。
- 证据：公开 benchmark 2/24 verified、hidden 0/8；剩余非 loop 含 cwe121/uaf/heap-canary；Phase-8A readiness：G09 partial、G10 non_goal、G11 non_goal、G16 missing、G17 missing。
- 验收原则：**原型是分析证据，不是修复能力**；不得接入 `unified_verification`/gate，不得产出可下载候选。

## 4. 你的任务（P0 → P2）

### P0-1（首增量，90 分钟）CFG + 直接 Call Graph 最小实现

新建（只新增，不改现有文件）：
```
app/services/analysis/__init__.py
app/services/analysis/cfg.py        # Capstone 指令块、分支目标、basic blocks、函数边界（可用符号/PLT）
app/services/analysis/callgraph.py  # 直接调用 E8 rel32 + PLT/导入调用；indirect 显式 unresolved
tests/test_analysis_cfg.py
```
要求：
- 用现有 fixture 的真实 ELF（如 `fixtures/elf/vuln-strcpy-x86_64.elf`）验证：能列出函数、block、直接调用边；
- 解析不了的地方返回 `unresolved` + 原因，不猜；
- 输出 JSON 结构固定（建议：`{format, arch, functions:[{va,name,blocks}], edges:[{from,to,kind,resolved}] , limitations}`）。

### P0-2 跨函数数据流 + 保守别名（最小）

```
app/services/analysis/dataflow.py  # 参数/返回传播、reaching def 简化、跨 1 层调用
app/services/analysis/alias.py     # points-to 保守：不确定即 may-alias，不产生错误确定性
scripts/analyze_crossfn.py         # CLI: --elf PATH --json，输出证据
tests/test_analysis_dataflow.py
tests/test_analysis_alias.py
```
只要求能回答：目标 sink 的 capacity/长度值从哪个函数参数/返回值/全局来；跨函数时给出路径；不确定就标 unknown。

### P0-3 夹具 + 失败/定位证据

```
fixtures/crossfn/                  # 2 个最小 C 源 + build.sh + original.elf + PoC manifest + 说明
artifacts/m2-analysis-2026-11-16/  # 分析 JSON + 对比证据 + SHA256SUMS
```
证据必须包含：
1. 当前确定性引擎在该 fixture 上的 `repair_any` 结果（`analysis_only`/`no candidate`/`unsupported` 等，通过现有 CLI/API 复现）；
2. 新原型输出的 sink 定位路径（函数/块/参数来源）；
3. 明确 `not_run`/`unknown` 项（例如结构体布局、间接调用、并发）。

### P1 与 M1 的接口草稿（只写文档，不改 M1 代码）

- 在 `docs/operations/m2-analysis-api.md` 给 M1 一个“分析结果 → RepairSpec 输入”的 JSON 草案（target function / site_va / capacity source / evidence refs / confidence），标注“草案，未经 gate 验证”。

### P2（时间允许）交叉验证

- 用原型分析 `fixtures/hard-cases/capacity_confusion.c` 类样本，解释为何同函数启发式能处理而跨函数不能；产出 1 页对照。

## 5. 写范围（严格）

允许新增/修改：
```
app/services/analysis/**        （新目录，只新增）
scripts/analyze_crossfn.py      （新文件）
tests/test_analysis_*.py        （新文件）
fixtures/crossfn/**             （新目录）
artifacts/m2-analysis-2026-11-16/**（新目录）
docs/operations/m2-analysis-api.md（新文件）
.tmp/handoff/m2/                （日志/草稿）
```
禁止修改：现有 `app/services/**`（分析/修复/gate 任何已有文件）、`scripts/` 已有脚本、`fixtures/` 已有文件、`docs/consolidation/*`、claims/LIMITATIONS/CI、M1/M3/M4 目录。

## 6. 红线

1. 只读分析：不接 gate、不产出候选、不修改 `repair_any` 行为；
2. 不宣称“支持跨函数修复/whole-program”；输出必须带 `limitations` 与 `unknown`；
3. 不猜地址/不硬编码 fixture 地址；所有结论可由 `--json` 复现；
4. 不做 git 写；不调用 live 模型；不打印 key；
5. 失败/卡点如实报，不空转。

## 7. 交付物

1. 新代码（写范围内）+ 测试；
2. `scripts/analyze_crossfn.py --elf ... --json` 可复现；
3. `artifacts/m2-analysis-2026-11-16/`（JSON + 对照 + SHA256SUMS）；
4. `.tmp/handoff/reports/m2-report-*.md`（工具生成，填满）；
5. 给 Lead 10 行摘要（关键发现/证据/未完成/需要决策）。

## 8. 时间盒

- 首增量 90 分钟（CFG + callgraph + 1 个 fixture 的 JSON 输出）；
- 当天结束前完成 P0-2/P0-3 的最小证据；P1/P2 可留给下一轮；
- 需要新依赖或需要读 hidden 语料 → 先报 Lead。
