# 04 · 仓库 / 代码 / 测试 / CI 现状核验（对照旧报告第 5 节）

> 子 Agent 4/6 交付物。核验时间：2026-11-17 08:47–09:05（Asia/Singapore）。
> 核验对象：`d37bfad`（workbench-v3 / feature/ai-binary-repair / release/2026-11-17-phase8d-final）、`a1d7150`（release/2026-11-17-phase8d-final-evidence）、`c0f9feb`（final/consolidated-2026-11-16）、`996060d`（phase8d-open-world）、`4a7b235`（Phase-8C frozen）。
> 方法：只读 `git show/ls-tree/diff/archive`、解析已提交 junit/JSON、在 `/tmp` 的干净导出树上跑**小测试子集**、GitHub Actions API 只读查询。**没有**重跑 2411 条全量套件（会写工作树且约 17 分钟），因此“全量通过”的可信度来自三重交叉：提交的 junit + hosted CI + 独立 collection 计数（见 §4）。
> 规则：`not_run` 不写成 pass；未核实项单列 §10。

---

## 0. 结论摘要

1. **当前内容最全的提交是 `d37bfad`，不是 `c0f9feb`。** `final/consolidated-2026-11-16`（`c0f9feb`）只含 P31–P34，**完全不含 Phase-8D**（其树里没有 11 个 `tests/test_phase8d_*.py` 与 `artifacts/phase8d-*`）；`workbench-v3` 的 `d37bfad` 才同时含 Phase-8D + P31–P34 + 2411 条全量记录。`a1d7150 = d37bfad + final gate 证据`，但见第 3 条。
2. **测试与 CI 是真的，但口径要精确**：`artifacts/binary-universal-v5-2026-11-13/macos-junit.xml` 自报 **2411 tests / 0 failed / 0 errors / 9 skipped / 1015.7s**（2026-11-17 00:06:54，macOS）；我独立 collection = **2423**（含 e2e 12），减去 `--ignore=tests/e2e` 的 12 条正好 2411。GitHub 上 `d37bfad` 的 CI run **43907137267** 与 Ubuntu run **43907136876** 均 **success**（7 个 job：5 success + 2 按设计 skipped）。`c0f9feb` 的 2319 条是另一棵树，不能混用。
3. **`a1d7150` 不是“干净超集”**：它删除了 7 个历史 `artifacts/release-gate-*` 目录共 **33 个文件**，其中 `artifacts/release-gate-2026-11-16-phase8c/gate.json` 仍被同一提交树里的 `artifacts/phase8d-baseline-2026-11-17/baseline.json:47,115,119` 引用，且被 `scripts/build_phase8d_capability_universe.py:45-46,209` 硬依赖。我实测：`d37bfad` 树 `--check` 退出 0；删掉该目录后退出 1（`BuildError: missing source artifact ...phase8c/gate.json`）。**因此 06 号报告“以 a1d7150 为基线”的建议有证据级风险，需 Lead 裁决**（建议 `d37bfad` + 只 cherry-pick a1 的 `release-gate-2026-11-17-phase8d-final/` 与那份 final evidence 文档）。
4. **主工作树是脏的、且处于 P31–P34 半回退状态**：`binary-repair-gui`（`final/consolidated-2026-11-16`）有 **41 条** status；暂存区删除了整个 `app/services/llm_gateway/`、`scripts/run_model_preflight.py`、3 个 P31 测试与 `artifacts/p31-p34-*`，工作区又只以 untracked 方式恢复了一部分（磁盘上 `llm_gateway/` 只剩 `credentials.py/errors.py/usage.py`，缺 `__init__.py/base.py/client.py/providers/`）。GUI 进程仍在跑（8123），但“从当前工作树重启即等于 P31 特性”**未核实**；提交里的 `c0f9feb`/`d37bfad` 反而是完整的。
5. **旧报告第 5 节大部分数字已过时**（mainline、tree、refs、文件数、测试数、合同数、worktree 数），并有一处**实质性不一致**：旧报告/产品文档的“non-loop 3/6”在仓库中找不到对应聚合；仓库权威口径是 **12-case 矩阵 non-loop 0/6**（两模型各 0/6）与 **RepairSpec 三个 hard case 3/3（仅 flash）**，另有 36-run 稳定性 `hard-nonconst 3/6`（单 case，不是家族汇总）。详见 §5.2 与 §8。
6. **能力上限未变**：public **2/24 = 8.33%**、hidden runtime **0/6**（8 个 hidden 样本 = 6 runtime + 2 analysis-only）、297 units、Phase-8D **8 个 open audit gap**、0 promotion。P31–P34 只交付离线 gateway/适配器/凭据/preflight/稳定性 runner，真实 OpenRouter/Ollama 调用与 60-run 矩阵均 `NOT_RUN`。
7. **GUI 与成果门户都能打开**：GUI `127.0.0.1:8123` 返回 401（token 鉴权生效），门户 `127.0.0.1:8899` 返回 200、`/api/status` 显示 `guest_runner.available=true`（Lima `binaryrepair` 正在运行）。但门户数据停在 11-16（2301 tests/17 contracts/240 cells/“0 open”/gate 4a7b235），且 `/api/status` 未鉴权就回传带 token 的工作台 URL（token 在此 `[REDACTED]`）。

---

## 1. 核验对象与方法（可复现）

### 1.1 提交身份

| 提交 | 时间（+08:00） | 角色 | 关键事实 |
|---|---|---|---|
| `f1bb1f4` | 2026-11-16 12:19 | 11-16 整合基线 | Phase-8C 之后的共同祖先；`c0f9feb`、`d37bfad`、`996060d` 的 merge-base |
| `4a7b235` | 2026-11-15 | Phase-8C frozen release | tree `4bf5013…`；tag `phase8d-frozen-phase8c-release`（annotated `b989bc5…`） |
| `996060d` | 2026-11-17 00:16 | Phase-8D 集成分支 | `phase8d-open-world`；CI 43905664704/43905664754 **success** |
| `d37bfad` | 2026-11-17 00:24 | **当前 workbench-v3** | 含 8D + P31–P34；2411 条 junit；CI 43907137267 **success** |
| `a1d7150` | 2026-11-17 01:25 | final evidence | `d37bfad` 的子提交；+final gate、-33 个历史 gate 文件 |
| `c0f9feb` | 2026-11-17 00:05 | `final/consolidated-2026-11-16` | 仅 P31–P34，**无 Phase-8D**；2319 条 junit |

> 证据：`git log -1 --format='%h %ci %s'` 于 `binary-repair@d37bfad` 工作树；ancestry 用 `git merge-base --is-ancestor` 实测（`c0f9feb` 不是 `d37bfad` 祖先；`d37bfad` 是 `a1d7150` 祖先）。

### 1.2 使用过的命令（摘要）

```bash
git -C worktree-p31-ci status --porcelain            # 干净
git -C binary-repair-gui status --porcelain | wc -l  # 41（脏）
git ls-remote --heads origin | wc -l                 # 97
git ls-remote --tags origin | wc -l                  # 101（含 30 行 ^{}）
python3 - <<'PY'  # 解析 junit：tests=2411 failures=0 errors=0 skipped=9
PY
git archive d37bfad | tar -x -C /tmp/br-full         # 只读导出，不碰工作树
cd /tmp/br-full && pytest --collect-only -q -p no:cacheprovider   # 249 files / 2423 tests
pytest -q tests/test_llm_gateway_*.py tests/test_stability_matrix_hardening.py  # 30 passed
python scripts/build_phase8d_capability_universe.py --check        # exit 0
# 移走 artifacts/release-gate-2026-11-16-phase8c 后再 --check          # exit 1
curl -s https://api.github.com/repos/chenfanaichifan/binary-repair/actions/runs?per_page=15
```

### 1.3 环境（本机）

Python **3.11.8**；FastAPI **0.162.2**、uvicorn **0.54.0**、pytest **9.2.0**、httpx **0.28.1**；Lima `limactl 2.3.0`，VM `binaryrepair` 状态 Running（aarch64，4 CPU/6 GiB）。

---

## 2. 仓库与代码结构（d37bfad）

| 项 | 值 | 说明 / 证据 |
|---|---|---|
| tracked 文件 | **2,359** | `git ls-files | wc -l` |
| `artifacts/` 证据文件 | **1,121** | `git ls-files artifacts | wc -l` |
| 测试文件 | **249** 个 `test_*.py` | 217 顶层 + 28 integration + 2 unit + 2 e2e |
| 应用服务模块 | **68** 个 `app/services/*.py` | 含 acceptance_2、promotion_gate、metamorphic_discovery、phase8d_gap_registry、llm_gateway 子包 |
| 脚本 | **95** 个 `scripts/*.py` | 含 11 个 phase8d builder/audit |
| 路由装饰器 | **78** 处 | `app/*.py` + `app/services/*.py` 的 `@app/@router` 统计（粗口径） |
| 模板 | **18** 个 HTML | `app/templates` |
| JSON 合同 | **20** | `contracts/*.json`；Phase-8C 时是 17，8D 新增 acceptance-2 / phase8d-capability-universe / phase8d-experiment-bundle |
| benchmark | public 32 + hidden 8 | `benchmark/phase8c/manifest.json`：`sample_count=32`、`hidden_available=false`；hidden commitment 单列 |
| 应用框架 | FastAPI + Jinja/原生 JS | `app/main.py`；GUI 无 Flask 依赖（venv 里没有 flask） |

**结构判断**：Phase-8D 的代码已经“产品化分层”——`app/services/acceptance_2.py`（L0–L7）、`promotion_gate.py`、`metamorphic_discovery.py`、`phase8d_gap_registry.py`、`external_knowledge.py`、`capability_dimensions.py`；脚本侧对应 11 个 `build_*/audit_*phase8d*`。P31–P34 新增 `app/services/llm_gateway/`（11 文件）与 `scripts/run_model_preflight.py`。

---

## 3. Git 拓扑、refs、worktrees（含新发现）

### 3.1 文字拓扑（只列核验过的线）

```
f1bb1f4 (2026-11-16 12:19, 11-16 整合基线)
├── 4a7b235 (Phase-8C frozen; tree 4bf5013; tags phase8d-frozen-phase8c-*)
│     └── … Phase-8C evidence (ec503e4)
├── d1b73bf ── 78edb97 ── 996060d            # phase8d-open-world（8D 集成，CI success）
│                              └── e01fc9e ── 13d3c1d ── b896f1b ── d37bfad
│                                                                    └── a1d7150  # final evidence
└── a9db731 ── c0f9feb                        # final/consolidated-2026-11-16（仅 P31–P34，无 8D）
```

- `c0f9feb` **不是** `d37bfad` 祖先；`a1d7150` 是 `d37bfad` 的直接子提交。
- `996060d` 与 `d37bfad` 是**两条 8D 线**：`996060d` 是 8D 集成交付（tag `release-2026-11-17-phase8d`），`d37bfad` 在其后叠加 P31–P34 并重记 2411 条全量。
- `a1d7150` 相对 `d37bfad`：**33 删 / 3 增 / 0 改**；删除的正是 7 个历史 `artifacts/release-gate-*` 目录（含 phase8c gate），新增 `artifacts/release-gate-2026-11-17-phase8d-final/` 与 `docs/release-phase8d-final-mainline-evidence-2026-11-17.md`。

### 3.2 远端 refs（`git ls-remote`，2026-11-17 08:50）

| 类型 | 数量 | 备注 |
|---|---|---|
| heads | **97** | 与任务说明一致 |
| tag 行 | **101** | 其中 **30** 行是 `^{}` 解引用 → 实际 tag 对象 **71** |
| 默认 `main` | `8869b07` | 仍是 11-12 后未前进的旧 main |
| `workbench-v3` | **`d37bfad`** | CI 触发分支；不是“已删除” |
| `feature/ai-binary-repair` | `d37bfad` | 与 workbench-v3 同点 |
| `final/consolidated-2026-11-16` | `c0f9feb` | 缺 8D |
| `release/2026-11-17-phase8d-final` | `d37bfad` | |
| `release/2026-11-17-phase8d-final-evidence` | `a1d7150` | |
| `release/2026-11-17-phase8d-evidence` | `bdd3f84` | 与 a1 非超集（06 报告已列 9 个独有路径） |

> 旧报告“113 分支 + 117 标签 = 242”已过时；11-16 清理后 11-17 又重建/新增，当前是 97 + 71。

### 3.3 worktrees（6 个）

| 路径 | HEAD | 状态 |
|---|---|---|
| `binary-repair` | `221e47c`（member-5-deepseek-schema，旧树） | 干净但**不是**交付树 |
| `binary-repair-gui`（main worktree） | `c0f9feb` | **脏 41 条**（见 §3.4） |
| `.agents/worktrees/phase8d-final-d37` | `a1d7150` | — |
| `.agents/worktrees/phase8d-open-world` | `bdd3f84` | — |
| `worktree-p31-ci` | `d37bfad`（detached） | 干净 |
| `worktree-p31-final` | `c0f9feb` | 干净 |
| `worktree-feature-final` | `a0e6a24`（detached） | 干净 |

### 3.4 主工作树脏状态的实质（P0 交付风险）

`binary-repair-gui` 的 41 条 status 不是普通未提交改动，而是 **P31–P34 的半回退**：

- 暂存区：`D app/services/llm_gateway/*`（10 文件）、`D scripts/run_model_preflight.py`、`D tests/test_llm_gateway_*.py`、`D tests/test_stability_matrix_hardening.py`、`D artifacts/p31-p34-2026-11-16/*`、`D docs/acceptance/p31-p34-2026-11-16.md`；净 `git diff --stat HEAD` ≈ **+448 / −2107**。
- 工作区：`?? app/services/llm_gateway/` 只剩 `credentials.py`、`errors.py`、`usage.py`（**缺 `__init__.py`、`base.py`、`client.py`、`providers/`**），`?? tests/test_llm_gateway_credentials.py` 重新出现；`app/services/assistant_llm.py` 以未暂存方式 +310 行（OpenRouter/Ollama profile、`_gateway_client_from_env`、importlib 动态导入）。
- `from app.main import app` 仍能成功（动态导入有 fallback），所以**运行中的 8123 服务不代表 P31 gateway 可用**；从该工作树重启能否保持 P31 行为未验证。
- 结论：**任何“GUI 已集成 P31 gateway”的声明都不能绑定到当前工作树**；能绑定的是 `c0f9feb`/`d37bfad` 提交（`e01fc9e` 完整加入 11 个 gateway 文件与 30 条测试）。

---

## 4. 测试与 CI 现状

### 4.1 全量套件（非浏览器）

| 项 | 值 | 证据 |
|---|---|---|
| tests | **2411** | `binary-repair@d37bfad artifacts/binary-universal-v5-2026-11-13/macos-junit.xml:1`（`<testsuite tests="2411" errors="0" failures="0" skipped="9" time="1015.702" timestamp="2026-11-17T00:06:54+08:00">`） |
| failed / errors / skipped | **0 / 0 / 9** | 同上；9 个 skip 是平台限制（Mach-O 原生/Linux 执行类），不是失败 |
| 我独立 collection | **2423**（249 文件） | `/tmp` 干净导出树上 `pytest --collect-only`；含 e2e 12 → 2411 + 12 正好对齐，证明 junit 与这棵树同构 |
| 浏览器 e2e | **12/12**，但**不是 11-17 跑的** | `artifacts/browser-e2e-2026-11-14/junit.xml`（timestamp 2026-11-15T00:34:20，12 tests/0 fail） |
| 旧值 | 2243（Phase-8C）/ 2319（c0f9feb） | 均已过时；当前工作树是 2411 |

**可信度说明（重要）**：我没有重跑 2411 条。结论由三条独立证据交叉支持：① 提交的 junit 自报；② 独立 collection 的 2423 与 2411+12 完全吻合；③ hosted CI 的 `test` job 在 `d37bfad` 上执行 `pytest -q -p no:xdist --ignore=tests/e2e` 并 16/16 步 success（run 43907137267）。任何引用都应写成“junit + hosted CI 记录通过”，而不是“本次复跑通过”。

### 4.2 我实际跑过的子集（本次）

| 子集 | 命令 | 结果 |
|---|---|---|
| P31–P34 离线测试 | `pytest -q tests/test_llm_gateway_credentials.py tests/test_llm_gateway_integration.py tests/test_stability_matrix_hardening.py`（`/tmp/br-full`） | **30 passed**（15+9+6），0 failed |
| Phase-8D 子集 | 6 个 `tests/test_phase8d_*.py`，deselect 1 条依赖 git 祖先的测试 | **60 passed**；被 deselect 的 `test_phase8c_release_and_evidence_are_ancestors` 只在 `/tmp` 非 git 目录失败，属环境限制 |
| 全量 | 未跑 | `not_run`（≈1015s，且会写工作树） |

### 4.3 CI 记录（GitHub Actions API，只读）

| run | 分支/SHA | 结论 | 用途 |
|---|---|---|---|
| **43907137267** | `workbench-v3` / `d37bfad` | **success**（CI，7 job：test/coverage-gate/browser-e2e/release-gate-pr/release-gate-hosted success；release-nightly-gate/release-drift skipped） | **最终 mainline CI** |
| **43907136876** | `d37bfad` | **success** | Ubuntu verification |
| 43905664704 / 43905664754 | `996060d` | **success** | 8D 集成 CI |
| 43900916188 / 43900916201 | `78edb97` | **success** | claims.json 当前记录的“latest_verified_ci”（**已不是最新**） |
| 43897595363 / 43897595463 | `d1b73bf` | **failure** | 8D 首版 CI 失败，由 `78edb97` 修复（“fetch full history + demo interpreter portable”） |
| 43744573286 / 43744573230 | `f1ba37e`（gated code） | **success** | 旧报告 §5.2.1 引用的 Phase-8C CI，**属实** |
| 43748886046 / 43748886289 | `4a7b235` | **success** | Phase-8C 最终 release CI，**属实** |

> CI 总共 170 个 run（API `total_count`）。`release-nightly-gate` 仍靠 `vars.BINARYREPAIR_RELEASE_GATE == 'true'` 才启用；**self-hosted Lima nightly 仍是 `not_run`**（`docs/operations/phase8c-ci-signoff.md:1-12`）。`ubuntu-verify.yml` 只在 `workbench-v3` push 触发。

### 4.4 最终发布门禁（13/13）

`a1d7150` 的 `artifacts/release-gate-2026-11-17-phase8d-final/phase8d-final-gate/gate.json` 实测：

- `mode=nightly`、`release_sha=d37bfad`、`frozen_sha=d37bfad`、`clean_tree=true`、`ok=true`、`elapsed_ms=1250277`（≈20.8 min）、`generated_at=2026-11-16T17:24:39Z`；
- **13/13 checks 全 passed**（release-tree-identity、static-coverage-gate、claims-measurement-diff、acceptance-contract、local-coverage-gate、meta-audit、acceptance-invariants、universe-unknown-zero、provenance-complete、provider-matrix、provider-coverage、nightly-real-lima-acceptance、full-pytest）；
- 诚实字段：`not_run=["github_actions","international_provider_matrix","self_hosted_nightly_lima_capture"]`；`lima.available=true`、`vms=["binaryrepair"]`；`mitigated_residual=["RG-runtime-evidence::elf/x86_64/64/little::native_run"]`。
- 证据范围明确写的是 **local frozen-tree gate**，不是 GitHub Actions run。

### 4.5 测试规模演进（旧报告表 + 当前值）

| 阶段 | 旧报告 | 当前核验 |
|---|---|---|
| v1.2.1 | 741 collected | 历史，不重核 |
| v4/v5 | 950 | 历史 |
| Phase-8A/8B/8C | 2,243 | Phase-8C gate 内全绿；**c0f9feb 树 2,319** |
| 8D + P31 | — | **2,411**（非浏览器） |
| 含 e2e | — | **2,423** |

> 结论：旧报告“2,243”不是错，是 **4a7b235 时点**的值；11-16 整合后 +76，8D+P31 后 +168。

---

## 5. 能力、基准与治理数字核验

### 5.1 权威数字（全部有仓库文件）

| 指标 | 值 | 证据 |
|---|---|---|
| public verified | **2/24 = 8.33%** | `benchmark/phase8c/results.json`（verified_count=2、denominator=24）；`docs/status/claims.json:805,811` |
| public executed / unsupported | 30 / 2（共 32） | 同上 |
| detection / root-cause / localization | 3/24 各 | claims.json phase8c |
| false_verified | **0**（public + hidden） | 同上 |
| hidden | 8 样本 = **6 runtime + 2 analysis-only**；**0/6 verified**、0 candidate | `artifacts/phase8d-hidden-attribution-2026-11-17/aggregate.json`；release doc:40 |
| 能力宇宙 | **297 units**（20 dim + 240 cells + 32 public + 2 hidden + 3 prototypes） | `artifacts/phase8d-capability-universe-2026-11-17/registry.json`（units=297）；release doc:33 |
| 状态分布 | discovered 98 / not_applicable 131 / unmeasurable 24 / unknown 7 / independently_verified 2 / candidate_generated 1 / analysis_only 32 / unsupported 2 / generalized 0 / promoted 0 / not_run 0 | release doc:35-37 |
| 覆盖审计 | 240 cells、68 gaps、**0 open**、55 closed/1 mitigated/12 non-goal | claims.json `audit_status.release` |
| Phase-8D 新增 gap | **8 个 open audit gap**（另加，不替换 68） | `artifacts/phase8d-gap-registry-2026-11-17/gaps.json`；release doc:19 |
| 合同 | **20**（8C 时 17） | `contracts/*.json` |
| 反思记录 | **101**（旧报告 91） | `artifacts/autonomous-reflection-2026-11-16/reflection.json` records=101 |
| 4 模型 pooled | **36/96**（flash 18/36、v4-pro 18/36、Qwen3-8B 0/12、Qwen2.5 0/12） | `artifacts/provider-coverage-2026-11-14/summary.json` |

### 5.2 AI 修复数字：旧报告“3/6”是错误聚合（必须纠正）

| 实验 | 正确结果 | 证据 |
|---|---|---|
| 12-case 矩阵（11-14，2 模型 × 3 runs） | 每模型 **6/12**；loop **6/6**、**non-loop 0/6**（两模型一致） | `artifacts/multi-model-matrix-2026-11-14/README.md:9-10`；`claims.json:241` |
| RepairSpec 三个 hard non-loop case（11-15） | deepseek-flash **3/3**；v4-pro **0/3** | `artifacts/ai-repair-planning-model-ab-2026-11-15/README.md:7-10`；`claims.json:287-289` |
| 36-run 稳定性（11-16） | **19/36**；cwe122 6/6、cwe787 6/6、**hard-nonconst 3/6**、hard-multicall 2/6、hard-sprintf 2/6、cwe121 0/6 | `artifacts/stability-2026-11-16/README.md:7-19`；`claims.json` #67 |
| P16-R3 独立验证 | **7/10**（1 rejected CWE-121，2 ARTIFACT_MISSING） | `docs/acceptance/p16-r3-2026-11-16.md:1-30` |

**判定**：旧报告 §5.3.3 的“非 loop 合计 3/6”、以及 `docs/product/PRODUCT-POSITIONING-2026-11-17.md:230-231,245` 的“3/6 non-loop in the same 12-case matrix”**不被任何仓库证据支持**。仓库里同时存在两个正确但不可合并的口径：矩阵 **0/6** 与 RepairSpec **3/3**；“3/6”最接近的来源是稳定性表里 **hard-nonconst 单 case 3/6**（一个 case 的重复通过率，不是 6 个 case 的家族汇总）。**Lead 合成时必须用“0/6（12-case 矩阵）+ 3/3（RepairSpec 单模型）”，不要写 3/6。**

### 5.3 Phase-8D D00–D10 结果（逐项核验）

| D | 交付 | 声明的诚实结果 | 我的核验 |
|---|---|---|---|
| D00 | baseline + frozen object tags | 4a7b235/4bf5013/ec503e4/CI 记录；原 refs 已被整合删除 | ✅ `artifacts/phase8d-baseline-2026-11-17/baseline.json`；但其中 gate 路径在 `a1d7150` 已被删（见 §3.1） |
| D01 | 297-unit universe | 2 verified、0 generalized/promoted、unknown=null | ✅ registry.json units=297；状态分布与 release doc 一致 |
| D02 | 8 个 audit gap | 8/8 open，有 lineage/experiments | ✅ gaps.json（8 个 id、7 类） |
| D03 | Acceptance 2.0 L0–L7 + 变异 | 18 cases；14/14 变异检出；0 false accept；2 inconclusive/2 not_run | ✅ report.json case_count=18；`claims.json` phase8d.acceptance_2 同值 |
| D04 | heap-malloc ABI 根因 | `generator_plan_incorrect` + `abi_proof_insufficient`，candidate 仍 rejected | ✅ `artifacts/phase8d-heap-malloc-abi-2026-11-17/abi-analysis.json` |
| D05 | hidden 归因 | 6/6 runtime 执行，首阻塞 `detection_missed` 6/6；0 candidate | ✅ aggregate.json（runtime_count=6、detection not_observed=6） |
| D06 | CWE 5.0 外部快照 | 984 entries、232 mapped、15 new、752 unmapped、no support claim | ✅ `artifacts/phase8d-external-knowledge-2026-11-17/external-knowledge.json` |
| D07 | metamorphic + 机制注册 | 4 变体（2 engine diff、2 not_run）；11/11 输入变异执行；sample_based not_run | ✅ release doc:24；claims phase8d.discovery |
| D08 | 实验包 | 10 records，`promotion_effect=none` | ✅ `artifacts/phase8d-experiments-2026-11-17/experiments.json` |
| D09 | hidden 隔离审计 | operational pass；same-UID/root 可读，非密码学隔离 | ✅ isolation.json |
| D10 | promotion gate | 4/4 denied、0 promoted | ✅ promotion.json `capability_promotion=false` |

> 结论：Phase-8D 是**测量/治理交付，不新增修复能力、不 promotion**；所有“完成”都必须带这个限定。

---

## 6. P31–P34 产物核验

| 项 | 状态 | 证据 |
|---|---|---|
| 代码提交 | `e01fc9e`：27 文件、+2673/−71 | `git show --stat e01fc9e` |
| unified gateway | `app/services/llm_gateway/` 11 文件（base/client/credentials/errors/usage/providers: mock/openrouter/ollama） | `git show e01fc9e` |
| preflight | `scripts/run_model_preflight.py`（配置型，默认不发网络） | 同上 |
| 稳定性 runner | `scripts/run_stability_matrix.py` 重构 +293 行；独立验证、checkpoint/resume | 同上 |
| 测试 | 15 credentials + 9 integration + 6 hardening = **30**；我实跑 **30 passed** | `docs/acceptance/p31-p34-2026-11-16.md:61-65`；本次 `/tmp` 子集 |
| 全量记录 | **2411 / 0 / 0 / 9** | 同上:65；junit |
| 真实 OpenRouter/Ollama | **NOT_RUN**（测试全部 `httpx.MockTransport`） | 同上:3-6,67-69 |
| 60-run 矩阵 | **NOT_RUN**（只有历史 partial 与一次 smoke） | 同上:55-58,68 |
| 凭据/preflight 实网校验 | **NOT_RUN** | 同上:47-48 |

> 评价：P31–P34 是“离线实现 + 冒烟测试”级别的完成，不是“多 provider 已联调”。`docs/status/claims.json` 的 `explicitly_unimplemented` 仍保留“multi-provider/multi-model statistics”等条目，与之一致。

---

## 7. GUI / 成果门户可运行性

### 7.1 运行态（本次探测）

| 服务 | 探测 | 结果 |
|---|---|---|
| GUI（FastAPI） | `GET http://127.0.0.1:8123/` | **401**（token 鉴权生效）；`/api/config`、`/health` 也 401 |
| 门户 | `GET http://127.0.0.1:8899/` | **200**；`/api/status` 200，27 篇文档已渲染，`tools.demo/elf_verify/scan=true`，`jobs_running=[]` |
| Lima guest | `limactl list` | `binaryrepair` **Running**（aarch64）；门户 `guest_runner.available=true` |
| GUI 进程 | `ps` | `.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8123`（从脏工作树启动） |

### 7.2 门户数据 vs 仓库（**系统性过时**）

`results-portal/data/overview.json` 与 `docs/status/claims.json`/`contracts/` 对比：

| 指标 | 门户值 | 仓库当前值 | 判定 |
|---|---|---|---|
| branch/commit | `final/consolidated-2026-11-16` / `f1bb1f4` | 实际 head `c0f9feb`；最新 `d37bfad` | 过时 |
| tests | **2301** / 235 文件 | **2411**（非浏览器）/ 249 文件 | 过时 |
| contracts | **17** | **20** | 过时 |
| capability universe | **240 cells** | **240 cells + 297 units** | 不完整 |
| gaps | **0 open** | 68 gaps 0 open **+ Phase-8D 8 open audit gaps** | 误导 |
| release gate | 13/13 @ `4a7b235` | 13/13 @ `d37bfad`（final） | 过时 |
| hidden | **0/8** | 8 样本 = 6 runtime + 2 analysis-only；verified **0/6** | 分母口径不一致 |

> 门户“0/8”把 analysis-only 也放进分母，和仓库 claims 的 `hidden_runtime_denominator=6` 冲突；应改成“0/6 runtime（另有 2 个 analysis-only 不计入分母）”。

### 7.3 安全/卫生问题（不输出 token）

- `results-portal/server.py:125-132` 从 `var/session.token` 读取工作台 token 并拼成 `/?token=...`；`/api/status` 在**无鉴权**情况下把这个 URL 回传（本次返回 200）。token 在此 `[REDACTED]`。本机绑定 `127.0.0.1` 降低了风险，但仍是凭据卫生缺陷。
- 门户是**工作区级目录**，不在 `binary-repair` git 仓库内；新分支若不带 `results-portal/`，门户不可复现（06 号报告需决定）。
- GUI 主工作树脏（§3.4），且 `artifacts/p31-p34-2026-11-16/` 在暂存区被删；门户引用的 `binary-repair-gui/...` 路径可能指向半回退内容。

---

## 8. 旧报告第 5 节逐条核对（一致 / 不一致 / 过时）

| 旧报告项（行号） | 旧值 | 本次核验 | 判定 |
|---|---|---|---|
| 源仓库（673） | `chenfanaichifan/binary-repair` | 同 | **一致** |
| 公开快照（675） | `leesirleesirlee-star/Binary_Repair` v1.2.1 | 未访问外部仓库 | **未核实** |
| 最终 mainline（677） | `workbench-v3 = 4a7b235` | `workbench-v3 = d37bfad`；4a7b235 是 Phase-8C frozen | **过时** |
| 最终 gated tree（678） | `4bf5013…` | 8C tree 仍是它；final tree `2708ad2…` | **过时** |
| 最终 evidence 分支（679） | `release/…phase8c-evidence = ec503e4` | 该 ref 已不存在；对象由 tag `phase8d-frozen-phase8c-evidence` 固定 | **过时** |
| 旧默认分支（680） | `main = 8869b07` | remote `main = 8869b07` | **一致** |
| 本地 worktrees（681） | 3 个 | **6 个** | **过时** |
| 远端 refs（682） | 113 heads + 117 tags = 242 | **97 heads + 71 tag 对象**（101 行含 30 peeled） | **过时** |
| tracked 文件（683） | 2,074 | **2,359** | **过时** |
| artifacts（683） | 960 | **1,121** | **过时** |
| JSON 合同（683） | 17 | **20** | **过时** |
| public/hidden 样本（683） | 32 + 8 | 32 + 8 | **一致** |
| Python 环境（684） | 3.11.8 | 3.11.8 | **一致** |
| collected（685） | 2,243 | **2,411**（非浏览器）/ 2,423（含 e2e） | **过时** |
| 工作树 clean（686） | clean（仅 .venv） | 主工作树 **脏 41 条**；其余 5 个干净 | **不一致** |
| gated code SHA（694） | `f1ba37e` | 历史值；final 是 `d37bfad` | **过时** |
| hosted CI（695） | 43744573286 success | API 验证 **success** | **一致** |
| Ubuntu（696） | 43744573230 success | API 验证 **success** | **一致** |
| 最终 release CI（697） | 43748886046 / 43748886289 | API 验证均 **success** | **一致** |
| frozen-tree nightly（698） | 13/13 | 8C 13/13；8D final 13/13（d37，require） | **一致（需分阶段）** |
| self-hosted Lima nightly（699） | not_run | 仍 `not_run`；CI job 默认 skip | **一致** |
| 测试演进表（703-717） | …2,243 | 分段历史大体成立；当前 2,411 | **过时（末行）** |
| CI 工作流（723） | 7 个 job | 仍是这些 job；test/coverage/browser-e2e/release-gate-pr/hosted + 2 skipped | **一致** |
| 容器/架构矩阵（729-737） | ELF/PE/Mach-O 各架构 | `claims.json:11` 声明一致；无新增容器 | **一致** |
| 确定性修复类（741-744） | 拷贝/容量类 | `claims.json` 仍同；8D 未加模板 | **一致** |
| AI 路径 3/6（750） | 3/6 | **0/6 矩阵 + 3/3 RepairSpec** | **不一致** |
| P11 19/36（750） | 19/36 | stability artifact 19/36 | **一致** |
| P16-R3 7/10（750） | 7/10 | p16-r3 文档 7/10 | **一致** |
| 4 模型 pooled（754） | 36/96 | provider-coverage 36/96 | **一致** |
| 独立验证 9 checks（760） | 9 项 | 8B 9 项仍成立；8D 新增 L0–L7/18 cases | **部分过时** |
| 8A/8B/8C 基准（768-771） | 2/24、hidden 0/8、19/36、7/10 | 2/24、0/6 runtime、19/36、7/10 | **基本一致（hidden 分母需注明）** |
| 浏览器 e2e（775） | 12/12 | 12/12，但为 11-15 记录，11-17 未重跑 | **一致（时点需注明）** |
| 覆盖审计（776） | 240 cells/68 gaps/0 open | 仍成立；8D 另加 8 open audit gaps | **一致（需加限定）** |
| 合同（780） | 17 | **20** | **过时** |
| 反思引擎（784） | 91 records | **101** | **过时** |
| 缺口治理（783） | 68 gaps/12 non-goals | 68/12 仍成立 | **一致** |
| L8 自主进化（800） | ❌ 未开始 | 8D 已交付“测量/治理/归因/门禁”基础设施，但 **0 capability promotion** | **过时（应改为“部分：基础设施完成，能力未晋级”）** |

> 统计：一致 13 项、过时 16 项、不一致 2 项（工作树 clean、AI 3/6）、未核实 1 项（公开快照）、部分过时 1 项（独立验证 9 checks）。**旧报告第 5 节的“静态数字”不可直接复用；结论/分层判断大体仍成立。**

---

## 9. 新发现问题（供 05 号报告分级；此处只给证据与影响）

| 级别 | 问题 | 证据 | 影响 |
|---|---|---|---|
| **P0** | `a1d7150` 删除被引用的 Phase-8C gate 证据，并让 `build_phase8d_capability_universe.py --check` 失败 | `git diff --name-status d37bfad a1d7150`（33 D）；`artifacts/phase8d-baseline-2026-11-17/baseline.json:47,115,119`；`scripts/build_phase8d_capability_universe.py:45-46,209`；实测 exit 1 | 若以 a1 为交付基线，证据链自相矛盾、8D builder 不可复现 |
| **P0** | 主工作树 P31 半回退、`llm_gateway` 包不完整 | `binary-repair-gui` status 41 条；`ls app/services/llm_gateway` 只有 3 个 .py | GUI 重启/交付内容不确定；门户与文档指向的工作树≠提交 |
| **P0** | “non-loop 3/6” 错误聚合并进入产品文档 | 旧报告 §5.3.3；`docs/product/PRODUCT-POSITIONING-2026-11-17.md:230-231,245`；反证见 `multi-model-matrix…:9-10`、`stability…:11` | 对外口径失实，属诚实性风险 |
| **P1** | 门户数字整体停在 11-16 | `results-portal/data/overview.json:18,26,58,82`（2/24、0/8、17、2301） | 成果展示与仓库不一致 |
| **P1** | `claims.json` 的 `latest_verified_ci` 不是最新 | `docs/status/claims.json:12-17`（43900916188@78edb97）；实际最新 43907137267@d37bfad | 读者会误以为最终 SHA 没有 CI |
| **P1** | `docs/acceptance/LIMITATIONS.md` 测试数停在 1160 | `LIMITATIONS.md:26-27` | 与 2411 冲突；外部评审会质疑 |
| **P1** | 根 `CONSOLIDATION.md` 的 4 个链接指向不存在的 `docs/consolidation/*` | `CONSOLIDATION.md:3-7`；实际文件在 `delivery/zh/consolidation/`（`docs/consolidation/README.md:5-10`） | 交付导航断链 |
| **P2** | 历史 v5 的 macOS junit 被 11-17 全量 junit 覆盖 | `docs/acceptance/binary-universal-v5-2026-11-13.md:158,169` 仍指该文件；`git log --follow` 显示被 11-17 改写 | 旧证据不可从工作树复核（git 历史仍可） |
| **P2** | `docs/consolidation/README.md` 称 `workbench-v3` 已删除 | `README.md:24-29`；实际 remote `workbench-v3=d37bfad` | 文档过时 |
| **P2** | 门户 `/api/status` 未鉴权回传带 token 的 URL | `results-portal/server.py:125-132`；本次 200，token `[REDACTED]` | 本机凭据卫生 |
| **P2** | 门户 hidden 用 0/8，仓库用 0/6 runtime | `overview.json:26` vs `release-2026-11-17-phase8d.md:40` | 分母口径不一致 |

---

## 10. 假设、限制与未核实

1. **未重跑 2411 条全量**：结论是“提交 junit + hosted CI 记录 + 独立 collection 三重一致”，不是本次复跑。
2. **junit 与树的绑定是间接的**：junit 时间戳 2026-11-17T00:06:54 早于 `d37bfad` 的提交时间 00:24；但独立 collection 的 2423−12=2411 与 junit 完全一致，且 P31/8D 测试类名均出现在 junit 中（`test_llm_gateway_*` 15+9、`test_stability_matrix_hardening` 6、`test_phase8d_*` 93），可认为同构。
3. **GitHub API 未认证**：run 的 conclusion 来自公共 API；未下载日志逐行核验测试输出。`total_count=170` 是 API 报告值。
4. **公开快照仓库**（`leesirleesirlee-star/Binary_Repair`）未访问，旧报告的 v1.2.1 外部事实未复核。
5. **`binary-repair-gui` 的脏状态可能是正在进行中的操作**（非永久损坏）；我未做任何恢复/清理。其 41 条 status 的“净 diff”是相对 `c0f9feb` 计算。
6. **`/tmp` 子集测试**：P31 30 条与 8D 60 条通过；8D 有 1 条依赖 git 祖先的测试在 `/tmp` 被 deselect，不能据此说“该测试失败”。
7. **早期历史（10-15 → 11-13）** 未逐条重核，沿用旧报告 §5.7 与 `delivery/zh/consolidation/project-history.md`。
8. **CI 的 Linux 平台 skip 数**与 macOS 不同；2411/9 skipped 是 macOS 记录，hosted Ubuntu 的 skip 数未逐条比对。

---

## 交接给 Lead（8 条）

1. **基线选择要改**：`a1d7150` 虽然内容最全，但删了 33 个历史 gate 证据，并使 `build_phase8d_capability_universe.py --check` 实测失败。建议新分支从 **`d37bfad`** 起，只 cherry-pick a1 的 `artifacts/release-gate-2026-11-17-phase8d-final/` 与 `docs/release-phase8d-final-mainline-evidence-2026-11-17.md`；若坚持 a1，必须先恢复 7 个 `artifacts/release-gate-*` 目录。**这与 06 号报告的建议直接冲突，请以本节实测为准裁决。**
2. **测试口径统一写**：非浏览器 **2411 / 0 failed / 0 errors / 9 skipped**（junit，2026-11-17 00:06:54）；加 e2e 共 **2423**，e2e **12/12** 但为 11-15 记录、11-17 未重跑。不要写“2243”或“2301”。
3. **CI 口径**：最终 `d37bfad` 的 CI 是 **43907137267 success** + Ubuntu **43907136876 success**；`claims.json` 里的 43900916188 是更早的 `78edb97`，不是最新。13/13 gate 是 **local frozen-tree**（20.8 min），`not_run` 明确含 `github_actions` 与 self-hosted nightly。
4. **修正 “3/6”**：正确是 **12-case 矩阵 non-loop 0/6（两模型）** + **RepairSpec 3 hard cases 3/3（仅 flash，v4-pro 0/3）**；`3/6` 只对应稳定性表里 `hard-nonconst` 单 case 的 3/6。产品文档 `PRODUCT-POSITIONING-2026-11-17.md:231,245` 与旧报告 §5.3.3 都要改。
5. **能力上限不变**：2/24、hidden 0/6 runtime（8=6+2）、297 units、8 个 8D open gap、0 promotion；Phase-8D 是测量/治理，不是新修复能力。
6. **P31–P34 只能写“离线实现 + 30 条离线测试通过”**；真实 OpenRouter/Ollama 与 60-run 矩阵均 `NOT_RUN`。完整 P31 代码只在 `c0f9feb`/`d37bfad`；主工作树处于半回退（gateway 包缺 8 个文件），不要用它做交付证据。
7. **门户/GUI 可运行但数据过时**：8123 返回 401（鉴权生效）、8899 返回 200、Lima `binaryrepair` Running；门户的 2301/17/240/“0 open”/0/8 全部要更新到 2411/20/297/“+8 open”/0/6，并修复 `/api/status` 的 token 回传。
8. **文档债清单**（P1/P2）：`LIMITATIONS.md:26-27`（1160）、根 `CONSOLIDATION.md:3-7`（4 个断链）、`docs/consolidation/README.md:24-29`（workbench-v3 已删的旧说法）、v5 junit 被覆盖、`claims.json` latest CI 过时。这些不影响能力判断，但会直接影响“可审计交付”的观感。
