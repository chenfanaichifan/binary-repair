# Role 5 启动包：DeepSeek API 接入 + Route B（recovered C）

> 对应 PRD **F3**、技术设计 **§10（DeepSeek integration）** 与 **§14（第五人分工）**。
> 本周你要交的两件东西：
> **① 一次真实、可复现、有成本记录的模型调用；② Route B 可行性记录（round trip 通过或明确失败）。**
> 不是"装好环境"，也不是"模型说修好了"。

---

## 0. 先把边界说清楚

你负责：

| 范围 | 具体内容 |
|---|---|
| DeepSeek 适配器 | `request_candidate(context, route, limits)`，JSON 模式 + 严格本地校验 + 类型化失败 |
| 提示词与上下文 | 只发送已审核的公开证据；二进制字符串一律当数据，不当指令 |
| 成本与用量 | 每次调用记录 model / tokens / 估算费用；预算上限可配置 |
| Route B | Ghidra 导出 → 归一化 → **unchanged round trip** → 模型修复 → 回填 → 用同一个 oracle 验证 |

你不负责（但必须能解释）：

- GUI 三个页面（2 号）
- 契约/job 状态机/验收引擎（1 号、4 号）
- Route A 的指令模板与编码（3 号）
- 符号执行（4 号）

一个硬规则：**模型只"提案"，验收永远由确定性检查决定。** 你写的任何输出里都不能出现
"AI 已修复 / 已验证 / 安全" 这种话；能说的是 "candidate accepted for validation"。

---

## 1. 今天（10/18）四小时怎么用

会议安排是 0–20 复盘、20–35 查环境、35–80 各自装工具、80–105 每人讲、105–120 定范围。
你的时间对应如下。

### 1.1 环境与一次无害调用（约 40 分钟，对应会议 20–80 分钟）

**在 Mac 上就能做完**，不需要等 Ubuntu。

```bash
cd binary-repair
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY（只填在这一台机器，不要进 Git）
```

先用假响应把管线跑通（不花钱、不需要 key）：

```bash
python scripts/smoke.py --mock
```

预期最后一行：`OK: endpoint, model, json mode and usage reporting are working.`

再发一次**真实**的无害请求（公开的合成文本，不含任何二进制/客户数据）：

```bash
python scripts/smoke.py
```

你会看到并需要记录这 8 个数：

```
http_status / model_returned / latency / attempts
prompt_tokens / completion_tokens / cache hit / estimated_cost_usd
```

预期形态（数字会不同）：

```
== configuration ==
  base_url: https://api.deepseek.com
  model: deepseek-flash
  thinking: False
  ...
== account check (GET /models) ==
  reachable; models: deepseek-flash, deepseek-v4-pro
== one json request ==
  http_status: 200
  model_returned: deepseek-flash
  latency: 1830 ms
  attempts: 1
  ...
  estimated_cost_usd: $0.00004120
OK: endpoint, model, json mode and usage reporting are working.
```

如果 401：key 复制错了/多了空格。402：余额不足。429：等几秒再试。
这三种都要原样记录，不要换号重试到"看起来成功"。

> 为什么默认关掉 thinking：DeepSeek 的 thinking 模式**默认开启、effort=high**，会先输出
> 推理再给答案，token 和延迟都更高。结构化候选生成先关掉，等 baseline 稳定后，
> 用同一批样例开/关各跑一次再决定。`DEEPSEEK_THINKING=enabled` 可切换。

### 1.2 Ghidra 与 recovered C（约 60 分钟，对应 35–80 分钟）

这一段到 Ubuntu 上做（Ghidra 需要 JDK 21；macOS 也能装，但最终目标是 ELF）。

```bash
sudo apt update
sudo apt install -y openjdk-21-jdk unzip
java -version        # 必须是 21.x

# 从 Ghidra 官方 release 下载 11.x PUBLIC zip，解压到 ~/
export GHIDRA_HOME=$HOME/ghidra_11.4_PUBLIC
$GHIDRA_HOME/support/analyzeHeadless 2>&1 | head -3
```

然后跑我们自己的小样本（没有客户数据，纯合成）：

```bash
cd routeb
./fixture/build.sh

# 先确认漏洞真的存在：4 个有效输入正常，2 个超长输入 guard=CORRUPT
python3 verify.py --binary fixture/vuln --mode vulnerable

# 导出 copy_name 的反编译 C
./ghidra/export.sh fixture/vuln copy_name
cat out/copy_name.c
cat out/copy_name.c.meta.txt
```

**今天要交的不是"装好了"，而是这张观察表：**

| 问题 | 你的记录 |
|---|---|
| 原始反编译输出能直接编译吗？报哪几类错？ | |
| 参数类型/名字与 `nm`/meta 里的签名一致吗？ | |
| 出现 `undefined4/undefined8`、`goto`、地址常量、`code *` 了吗？ | |
| 函数体多少字节？原函数多少字节？（决定能否原地替换） | |
| `callees=` 是什么？（空 = 重定位简单；有 libc 调用 = 需要 PLT 解析） | |
| 你为"能编译"改了哪几处？每处一句话理由 | |

参考归一化结果在 `routeb/experiment/samples/normalized_reference.c`，**先自己做再对照**。
本样本的 Ghidra 输出通常只需改类型名和变量名，这正是我们选它的原因。

### 1.3 记录 blocker（10 分钟）

在会议 105–120 分钟环节，你只需要说三句话：

1. 真实调用成功/失败，失败在哪一步（key、余额、网络、模型名）。
2. Ghidra 是否导出成功，recovered C 的"可编译度"如何。
3. 本周 round trip 的最大风险是什么（例如 Patcherex2 装不上、ELF 段权限、重定位）。

---

## 2. 本周 5 小时计划

| 时间 | 任务 | 产出 |
|---|---|---|
| 1 h | **schema 契约冻结**：candidate/context JSON Schema + 示例 + drift 检查，交给 2 号/4 号评审 | `schemas/README.md` + `generated/*.json` + 64 个测试全绿 |
| 1 h | **DB 迁移**：001_init.sql 在临时库跑通，确认约束（幂等键、复合外键、pass 必须有证据） | `db/migrate.py` 可重复执行，`db/README.md` |
| 1 h | 把 `binaryrepair_ai` 接进主应用（1 号提供 job/contract/analysis 的 hash 与 evidence id） | `app/services/provider.py` 一层薄封装 + 一条真实 candidate 记录 |
| 1 h | Route B：归一化 → round trip（失败也要记录） | 一份 PASS/FAIL/UNSUPPORTED 记录（含 hash 与命令） |
| 0.5 h | 模型修复 → 回填 → `verify.py --mode fixed`（若 round trip 已通过） | 6/6 结果或明确 blocker |
| 0.5 h | 成本/延迟测量 + 汇报材料 | 一页数字 + 3 分钟演示脚本 |

完成标准（可检查）：

- [ ] `scripts/smoke.py` 在 Ubuntu 上真实跑通，输出被保存为证据文件
- [ ] `pytest` 64+ 用例通过（含 schema drift、JSON Schema 示例、DB 约束、AI 边界契约）
- [ ] 一次真实 `request_candidate` 产生 `model_calls` 记录，字段与 TechDesign §6 对齐
- [ ] Route B round trip 有明确结论：PASS / FAIL / UNSUPPORTED，且带 6 个用例的实际输出
- [ ] 汇报里每个数字都有来源，没有"应该可以"

---

## 3. 代码地图

```
.
├── binaryrepair_ai/
│   ├── settings.py     环境变量与 .env；key 只进这个进程
│   ├── pricing.py      官方价格表 + peak/off-peak + 最坏情况预估
│   ├── schemas.py      Candidate v1、RepairContext、语义校验（scope/identity）
│   ├── prompts.py      system/user 提示词；<untrusted_...> 数据围栏
│   ├── client.py       HTTP、JSON 模式、超时、一次瞬态重试、usage 解析
│   ├── provider.py     request_candidate：预算 → 调用 → 解析 → 校验 → 记录
│   └── errors.py       稳定的 reason_code（GUI/验收引擎按它分支）
├── scripts/
│   ├── smoke.py        今天的无害调用（--mock 可离线）
│   └── demo_candidate.py  审核上下文 → 模型 → 校验后的 candidate（可写出 C）
├── schemas/            candidate/context JSON Schema（生成物 + 契约说明 + 示例）
├── db/                 SQLite DDL（001_init.sql）+ 迁移器 + 表说明
├── app/                与 verification 对齐的公共入口（domain/candidates、services/provider）
├── tests/              64 个离线用例：provider、schema 契约、数据库约束、AI 边界
├── routeb/
│   ├── fixture/        合成漏洞样本 + 构建脚本
│   ├── ghidra/         ExportFunction.java + export.sh
│   ├── verify.py       行为 oracle（vulnerable / fixed / roundtrip）
│   ├── probe_patcherex2.py  文档示例 + round trip + fixed 三个实验
│   └── experiment/     归一化/修复参考实现
└── docs/route-b/
    ├── README.md       本文件
    └── 02-member-5-candidate-provider.md   给成员4的接口回复
```

### 3.1 给 1 号（集成）的接口

```python
from binaryrepair_ai import DeepSeekProvider, RepairContext
from binaryrepair_ai.schemas import RepairContext  # 同物

provider = DeepSeekProvider.from_env()
result = provider.request_candidate(ctx)     # 不抛异常（预期失败都是值）

if result.ok:
    candidate = result.candidate             # CandidateV1
    record = result.record                   # 写 model_calls 表
else:
    failure = result.failure                 # reason_code / message / retryable
```

`model_calls` 建议字段（与 TechDesign §6 一致）：

| 列 | 来源 |
|---|---|
| `provider_model` | `record.model`（配置名）；实际返回的版本用 `record.model_returned` |
| `prompt_sha256` | `record.prompt_sha256` |
| `status` | `record.status` |
| `usage_json` | `json.dumps(record.usage)`；未知就写 `null`，**不要写 0** |
| `estimated_cost_usd` | `record.estimated_cost_usd`，未知 `NULL` |

### 3.2 给 2 号（GUI）的显示字段

每个 route 的 AI 卡片至少显示：

- 状态：`not_run / running / accepted_for_validation / rejected / error`
- 模型名、耗时、tokens、估算费用（缺失显示 "unavailable"）
- 失败原因：`reason_code` + 一句人话（`Failure.message`）
- **不要**显示 "AI 修复成功"；只显示 "candidate 已提交验证"

`reason_code` → 文案建议：

| reason_code | 显示 | 验收语义 |
|---|---|---|
| `provider_auth_failed` | API key 无效 | error（配置问题） |
| `provider_insufficient_balance` | 账户余额不足 | error |
| `provider_rate_limited` | 限流，已重试 | error（可再试） |
| `empty_content` | 模型返回空内容 | error（不是"没有漏洞"） |
| `invalid_json` / `schema_invalid` | 提案格式不合法 | rejected（保留诊断） |
| `identity_mismatch` / `scope_violation` | 提案越界/对不上输入 | rejected |
| `budget_exceeded` | 超出本 job 预算 | error（未发送） |
| `provider_timeout` | 调用超时 | error（不自动重发计费请求） |

### 3.3 Schema 的边界（你独立负责的部分）

两层，别混：

| 层 | 文件 | 回答什么 | 谁消费 |
|---|---|---|---|
| 候选契约 | `schemas/generated/candidate.v1.json` | 模型能返回什么字段、什么类型 | GUI、验证、文档 |
| 请求上下文 | `schemas/generated/context.v1.json` | 服务端允许发什么 | 集成、评审 |
| 持久化 | `db/migrations/001_init.sql` | job/run/attempt/证据/成本怎么落库 | 1 号控制器 |

三条规则：

1. **Pydantic 是源头**，`generated/*.json` 只能由 `python schemas/generate.py` 生成；
   CI 用 `python schemas/generate.py --check` 抓 drift。
2. v1 是封闭契约（`additionalProperties: false`），**加字段 = 升 v2**，不能偷偷放宽。
3. JSON Schema 只管结构；"Route A 不能带 replacement_c" 这类规则在
   `check_candidate()` 里，测试 `test_json_schema_does_not_encode_route_semantics`
   就是在记录这个分层。

数据库侧把产品语义写进约束，而不是只写在 Python 里：

```sql
-- 一个幂等键只能启动一次 run
idempotency_key TEXT NOT NULL UNIQUE
-- run 的 contract 必须属于同一个 job
FOREIGN KEY (job_id, contract_id) REFERENCES contracts(job_id, id)
-- pass 必须有证据
CHECK (result <> 'pass' OR evidence_artifact_id IS NOT NULL)
-- 成本未知是 NULL，不是 0
estimated_cost_usd REAL CHECK (estimated_cost_usd IS NULL OR estimated_cost_usd >= 0)
```

### 3.4 给 4 号（验证）的交接物

模型产出只有一样东西可以进入验证：`candidate.replacement_c`（Route B）或
`candidate.template_id + parameters`（Route A）。验证方要用**最终 ELF**跑
`verify.py` 那类 oracle，不能拿"编译通过"当证据。

---

### 3.5 与 verification 的接口（`02-member-5-candidate-provider.md` 的实现侧）

```python
# app/domain/candidates.py —— 验证骨架 import 的就是这个模块
validate_candidate(payload) -> CandidateV1      # 结构 + 语义；失败抛 CandidateRejected
may_leave_host(classification, derived=False) -> bool   # 默认拒绝
validate_candidate_for_context(payload, ctx) -> CandidateV1  # 带 job 绑定的版本

# app/services/provider.py —— typed failure
require_candidate(result) -> CandidateV1        # 失败抛 ProviderFailure(FailureReason)
```

四类失败映射：`provider_timeout` → `TIMEOUT`，`provider_insufficient_balance` / `budget_exceeded`
→ `QUOTA` / `BUDGET`，`empty_content` → `EMPTY`，`invalid_json` → `MALFORMED_JSON`。

### 3.6 给 2 号（GUI）的 schema 用法

不需要 import Python。直接读 `schemas/generated/candidate.v1.json`：

- 字段名来自 `properties`，枚举来自 `enum`，必填来自 `required`；
- 展示时把 `expected_effects / assumptions / uncertainties` 分开，不要合并成"AI 结论"；
- 任何 `additionalProperties` 之外的字段都不该出现——出现就是上游 bug。

`schemas/examples/` 里有 A/B 两条路线的真实形状，可以直接拿去做模板。

---

## 4. 安全与数据边界（会被评审问）

- 只有公开样本可以发给托管 API。客户二进制、反编译全文、测试 oracle 一律不出本机。
- key 只存在于 host 的 provider 进程：不进 VM、不进日志、不进报告、不进浏览器。
- 日志里只有 `prompt_sha256`；原始响应默认不落盘（`BINARYREPAIR_STORE_RAW=1` 才存）。
- 提示词把二进制文本放进 `<untrusted_recovered_c>`，并明确"只当数据"；即便如此，
  最终防线是 `check_candidate()` 的结构校验（模板白名单、参数范围、调用白名单、禁用构造）。
- 模型不能改 scope：模板列表、evidence id、target entry、容量全部由服务端给。

---

## 5. 成本（2026-10-18 官方价，USD / 1M tokens）

| 模型 | 输入 cache miss（off-peak / peak） | 输出（off-peak / peak） |
|---|---|---|
| `deepseek-flash` | 0.15 / 0.30 | 0.60 / 1.20 |
| `deepseek-v4-pro` | 0.66 / 1.32 | 1.98 / 3.96 |

- peak：UTC 周一至周五 01:00–04:00、06:00–10:00；其余半价。
- 例：10k 输入 + 4k 输出，flash peak = `0.01*0.30 + 0.004*1.20 = $0.0078`。
- 我们的默认上限：单 job $2，实验期总额 $20；超预算**在发送前**拦截。
- 计费是估算，不是账单；usage 缺失时显示 "unavailable"，不要当 0。

省钱做法：关 thinking、只发必要上下文、同一 context 复用、失败不盲目重试。

---

## 6. 会议演示（3 分钟，按这个顺序讲）

1. **一句话**：我负责 DeepSeek 适配器和 Route B 的可行性，今天验证到"真实调用 + 反编译输出"。
2. **屏幕 1**：`scripts/smoke.py` 的真实输出，指出 model、latency、tokens、cost 四个数。
3. **屏幕 2**：`out/copy_name.c` 与 `meta.txt`，指出函数大小、callees、需要归一化的 3 处。
4. **屏幕 3**：`verify.py --mode vulnerable` 的 6/6，说明"漏洞可复现"是后面一切的前提。
5. **风险**：round trip 依赖 Patcherex2；若装不上或回填后行为变化，按 unsupported 记录，
   不偷偷换成"手工改字节"。
6. **下一步**：本周给出一份 PASS/FAIL 记录，并接进 1 号的 job 流程。

---

## 7. 常见问题

**Q: `--mock` 和真实调用的差别？**
A: 只差 transport。schema 校验、预算、日志、失败映射完全相同；mock 用来在没有 key 时
证明代码路径，不产生费用，也不能当作"API 已验证"。

**Q: 为什么 JSON 模式还会返回空/带 Markdown？**
A: 官方明确说 JSON 模式偶尔返回空内容，且要求 prompt 里出现 "json" 并给示例。我们已加：
`response_format`、示例、"json" 关键词、空内容重试一次、fence/花括号容错解析。

**Q: 模型名写哪个？**
A: 用 `deepseek-flash`（当前文档名，V4.1-Flash）。旧别名可能还能用但会被路由到新模型，
计费/行为不可控，不要写死旧名。

**Q: 为什么 temperature=0 有时"没效果"？**
A: thinking 模式不支持 temperature/presence/frequency，传了也不报错但被忽略。我们在
thinking 模式下干脆不传。

**Q: Ghidra 报 `JAVA_HOME` 错？**
A: 装 JDK 21 并 `export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64`；Ghidra 11.3+ 不接受 JDK 17。

**Q: Patcherex2 装不上？**
A: 它依赖 angr/LIEF，建议单独 venv。装不上就记录版本、报错、Python 版本，结论写
"backend unavailable — unsupported"，这是合法结果，不是失败。

**Q: 我能直接在 Mac 上做 Route B 吗？**
A: 行为 oracle 可以（`verify.py` 已通过），但回填目标是 ELF，最终必须在 Ubuntu 上做。
Mac 产物是 Mach-O，不能作为交付证据。

---

## 8. 评审可能问你的 5 个问题

1. **"JSON 模式了，为什么还要本地校验？"**
   JSON 只保证"能被解析"，不保证字段、哈希、范围、路由字段正确。模型可以返回合法
   JSON 但把 capacity 写成 4096。`CandidateV1` + `check_candidate()` 才是门槛。

2. **"模型能不能自己换修复位置/改容量？"**
   不能。模板列表、参数范围、target_entry、evidence id 都由服务端给；越界直接
   `scope_violation`，不会进入验证。

3. **"空输出、超时、402 分别怎么处理？"**
   空输出：重试一次（官方已知问题），仍空则 `empty_content`；
   超时/5xx/429：一次有界重试，之后报 error，不无限重发计费请求；
   402/401：不重试，直接报配置/余额问题。

4. **"你怎么证明这个候选是安全的？"**
   我不证明。我只产出"通过 schema 与 scope 校验的候选"，安全性由 4 号的
   oracle + 符号执行在最终 ELF 上判定。模型的话不是证据。

5. **"为什么默认关 thinking？"**
   默认开启且 effort=high，token 与延迟更高；结构化输出先要稳定和便宜。等 baseline
   稳定后，用同一批样例做 A/B，再决定是否对难样本开启。

---

## 9. 参考

- DeepSeek JSON Output：https://api-docs.deepseek.com/guides/json_mode/
- DeepSeek Models & Pricing：https://api-docs.deepseek.com/quick_start/pricing/
- DeepSeek Thinking Mode：https://api-docs.deepseek.com/guides/thinking_mode
- DeepSeek Error Codes：https://api-docs.deepseek.com/quick_start/error_codes
- Ghidra AnalyzeHeadless：https://ghidra.re/ghidra_docs/api/ghidra/app/util/headless/AnalyzeHeadless.html
- Patcherex2 ModifyFunctionPatch：https://purseclab.github.io/Patcherex2/examples/modify_function_patch/
