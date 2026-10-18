# 成员5 回复：候选 schema 与数据边界接口确认（verification-design §4.3）

**收件人：** 成员4（verification）
**发件：** 成员5（候选 schema + provider）
**日期：** 2026-10-18
**状态：** 已实现，可并行联调
**说明：** 本文件取代 2026-10-18 初稿，是按实现结果确认后的接口版本

---

## 0. 一页结论

| # | 你的问题 | 答复 |
|---|---|---|
| 4.3.1 | 接受两个签名吗？ | **接受**，已按你写的调用方式实现：`validate_candidate(payload)`、`may_leave_host(classification=..., derived=...)` |
| 4.3.2 | schema v1 顶层字段：Route A 12 个？Route B 再加 2 个？ | **是。Route A 12 个**；Route B 在这 12 个上再加 `recovered_function_sha256` + `replacement_c`，**共 14 个**。A 路 payload 不用改 |
| 4.3.3 | target 白名单谁提供？ | 模块默认 `{copy_input, copy_name}`，可用 `allowed_targets=` 注入；候选不能扩展 |
| 4.3.4 | typed failure 放哪、叫什么？ | `app.services.provider.ProviderFailure(reason: FailureReason)` |
| 4.3.5 | 怎么拒绝多余字段？ | Pydantic `extra="forbid"` + 语义校验；**不是**手写字典检查 |
| — | 超长字符串上限 | 单条 **512** 字符；列表 **32** 条；`replacement_c` **20,000** 字符 |

**你那边需要改的地方：没有。** 你的骨架 payload（`route_a`、`bounded-copy-guard`、`capacity: 64`）
按现在的实现可以直接通过；你还没写的第 7 条（超长字符串）现在有确定数值可以断言。

与初稿的 4 处差异：

1. `route` 的 JSON 取值按你的骨架定为 **`route_a` / `route_b`**（我们同步改了 DB 枚举）；
2. v1 是 **14 字段**（Route A 12 个 + Route B 专属 2 个），A 路 payload 里两个 Route B 字段可完全省略；
3. 增加"指令样文本整份拒绝"（你的第 5 条），并给出 512/32 上限（你的第 7 条）；
4. 提供 `validate` 作为 `validate_candidate` 的别名，防止骨架里用的是简称。

---

## 1. 两个入口（已实现）

模块：`app/domain/candidates.py`（骨架 `pytest.importorskip` 绑定的名字）

```python
def validate_candidate(
    payload: dict,
    *,
    allowed_targets: Iterable[str] | None = None,
    templates: Iterable[TemplateSpec] | None = None,
    allowed_calls: Iterable[str] | None = None,
    max_replacement_chars: int = 20_000,
) -> CandidateV1:
    """合法 payload 返回非 None 的 CandidateV1；任何不合法都抛 CandidateRejected。"""

def may_leave_host(
    classification: str,
    derived: bool = False,
    *,
    authorized: bool = False,
) -> bool:
    """public/synthetic -> True；client -> False；未知 -> False（默认拒绝）。"""
```

补充说明：

- `validate_candidate` 只有 `payload` 是位置参数，其余全部有默认值，测试可以只传 payload；
- 失败抛 `CandidateRejected(reason_code, message)`，它是 `Exception` 子类，你的
  `pytest.raises(Exception)` 直接可用；
- `CandidateRejected.reason_code` 是稳定字符串（`schema_invalid` / `scope_violation` /
  `identity_mismatch`），GUI 和验收引擎按它分支；
- `validate` 是别名：`validate is validate_candidate`。

**它不能做什么（重要）：** 没有 job context 时，它无法证明某个 hash 或 evidence id
是本次 job 发出的。这类绑定在 `validate_candidate_for_context(payload, ctx)` 里做，
provider 在返回候选前已经做了同样的 context 绑定检查（`check_candidate`）。所以：

| 入口 | 结构/语义 | 身份 hash 归属 | evidence 签发 | recovered hash |
|---|---|---|---|---|
| `validate_candidate(payload)` | ✅ | 只校验格式 | 只校验格式 | 只校验格式 |
| `validate_candidate_for_context(payload, ctx)` | ✅ | ✅ | ✅ | ✅ |
| `require_candidate(result)`（provider 之后） | ✅ | ✅ | ✅ | ✅ |

---

## 2. schema v1 字段（最终）

`route_a` 的合法 payload 就是 12 个字段；`route_b` 用其中 10 个（去掉 `template_id` / `parameters`），再加 2 个，也是 12 个。

| 字段 | 类型 | Route A | Route B | 说明 |
|---|---|---|---|---|
| `schema_version` | `1` | 必填 | 必填 | 契约版本 |
| `original_sha256` | 64-hex | 必填 | 必填 | 原始 ELF |
| `contract_sha256` | 64-hex | 必填 | 必填 | 已审核契约 |
| `analysis_sha256` | 64-hex | 必填 | 必填 | 分析 bundle |
| `route` | `"route_a"` / `"route_b"` | 必填 | 必填 | 与骨架一致 |
| `target_entry` | C 标识符或 `0x…` | 必填 | 必填 | 必须在白名单 |
| `evidence_ids` | string[]，1–16 | 必填 | 必填 | 格式校验；签发校验需 context |
| `template_id` | string? | **必填** | 必须缺省/`null` | 必须在此次提供的模板里 |
| `parameters` | object<string,int>? | **必填** | 必须缺省/`null` | 键必须完全匹配，值在区间内 |
| `recovered_function_sha256` | 64-hex? | 必须缺省/`null` | **必填** | 必须等于请求里的 recovered hash |
| `replacement_c` | string?，≤20,000 | 必须缺省/`null` | **必填** | 完整函数定义；调用白名单 |
| `expected_effects` | string[]，1–32，每条 ≤512 | 必填 | 必填 | 展示用，不作为证据 |
| `assumptions` | string[]，0–32，每条 ≤512 | 可选 | 可选 | 展示用 |
| `uncertainties` | string[]，0–32，每条 ≤512 | 可选 | 可选 | 展示用 |

顶层 `additionalProperties: false`。`parameters` 内部键由模板声明决定，不套用"顶层多余字段"规则。

**route 值：** JSON 里只出现 `route_a` / `route_b`；文档里说 "Route A/B" 只是叙述。
数据库 `attempts.route` 的 `CHECK` 已同步为这两个值。

---

## 3. 你的 8 条检查如何被满足

本地契约测试：`tests/test_ai_boundary_contract.py`（64 个测试全绿）。

| # | 你的检查 | 实现位置 | 本地测试 |
|---|---|---|---|
| 1 | 合法 payload 通过，返回值非 None | `validate_candidate` | `test_valid_payload_returns_candidate` |
| 2 | 多余字段（`requested_permissions`）拒绝 | `extra="forbid"` | `test_extra_field_is_rejected` |
| 3 | 非法 route（`route_z`）拒绝 | `Literal["route_a","route_b"]` | `test_invalid_route_is_rejected` |
| 4 | 畸形哈希拒绝 | `StringConstraints(pattern=...)` + validator | `test_malformed_hash_is_rejected` |
| 5 | 指令样文本拒绝（整份，不过滤后接受） | 文本扫描 `_INSTRUCTION_RE` | `test_instruction_like_text_is_rejected` |
| 6 | 超契约 target 拒绝 | 白名单 | `test_target_outside_whitelist_is_rejected` |
| 7 | 超长字符串拒绝 | 512 / 32 | `test_overlong_text_is_rejected` |
| 8 | `may_leave_host` 三态 | 默认拒绝 | `test_data_boundary` |

第 5 条的文案：拒绝原因写 `text contains instruction-like or URL content`。覆盖
`ignore previous instructions`、`run:`、`rm -rf`、`sudo`、`http(s)://`、
`</untrusted`、`tool_call` 等。它是兜底；真正的保证是"候选永远不能改权限、工具、范围"。

第 7 条的具体数值（你要求写明）：

```text
自由文本单条：512 字符
expected_effects / assumptions / uncertainties：各 32 条
replacement_c：20,000 字符（单次请求的 context 默认再收紧到 8,000，可配到 20,000）
```

---

## 4. typed provider failure（4.3.4）

模块：`app/services/provider.py`

```python
class FailureReason(str, Enum):
    TIMEOUT = "provider_timeout"
    QUOTA = "provider_insufficient_balance"
    BUDGET = "budget_exceeded"
    EMPTY = "empty_content"
    MALFORMED_JSON = "invalid_json"
    SCHEMA = "schema_invalid"
    RATE_LIMIT = "provider_rate_limited"
    AUTH = "provider_auth_failed"
    NETWORK = "provider_network_error"
    SERVER = "provider_server_error"
    CONTEXT_TOO_LARGE = "context_too_large"
    IDENTITY = "identity_mismatch"
    SCOPE = "scope_violation"
    UNKNOWN = "unknown_provider_failure"

class ProviderFailure(Exception):
    reason: FailureReason
    retryable: bool
    details: dict
```

四类失败的映射（你补测试时可以直接断言）：

| 你的类别 | 触发 | `FailureReason` |
|---|---|---|
| timeout | 请求超时（已做一次有界重试） | `TIMEOUT` |
| quota | HTTP 402 | `QUOTA`；本地预算拦截是 `BUDGET` |
| empty | 200 但 `content` 为空 | `EMPTY` |
| malformed JSON | 内容不是 JSON | `MALFORMED_JSON`；JSON 合法但字段不对是 `SCHEMA` |

用法二选一：

```python
# 值风格（job controller 用）
result = provider.request_candidate(ctx)
if not result.ok:
    show(result.failure.reason_code, result.failure.message)

# 异常风格（worker / 测试用）
from app.services.provider import require_candidate, ProviderFailure
try:
    cand = require_candidate(result)
except ProviderFailure as exc:
    stage_outcome = "error" if exc.reason is not FailureReason.SCHEMA else "rejected"
```

关键行为：**失败绝不伪造候选**；`require_candidate` 只在 `result.ok` 时返回。

---

## 5. 数据边界（4.3.2 / 附一）

```python
may_leave_host("public")                                  # True
may_leave_host("synthetic")                               # True
may_leave_host("client")                                  # False
may_leave_host("client", derived=True)                    # False
may_leave_host("client_authorized")                       # False（默认）
may_leave_host("client_authorized", authorized=True)      # True（调用方已记录授权）
may_leave_host("")                                        # False
may_leave_host("unknown")                                 # False
```

`derived` 只是签名兼容，不会放宽 client 规则；未知分类一律 False。

---

## 6. 你那边怎么激活

把两个目录放到仓库根（与 `app/` 平级）：

```text
app/domain/candidates.py
app/services/provider.py
binaryrepair_ai/            # 上面两个模块的实现依赖
```

然后：

```bash
python -m pytest tests/integration -q -p no:cacheprovider -rs
```

预期：不再 skip；你写的 8 条全过。若失败，把 payload 和 `reason_code` 发我，
按 `schema_invalid` / `scope_violation` / `identity_mismatch` 三类定位。

我本地同一套断言的副本在 `tests/test_ai_boundary_contract.py`，当前 `64 passed`。

---

## 7. 给成员4的 6 条回复（可直接粘贴）

```text
总    签名：接受。
4.3.1 validate_candidate(payload)（单位置参数）/ may_leave_host(classification, derived=False)
      （关键字调用）：接受，已按此实现。
4.3.2 v1 顶层字段：Route A 12 个；Route B 再加 recovered_function_sha256 + replacement_c，
      共 14 个。A 路 payload 不需要改。
4.3.3 target 白名单：模块内默认契约（含 copy_input、copy_name），另留 allowed_targets=None；
      测试只传 payload，不要求额外传白名单。
4.3.4 typed failure：app.services.provider.ProviderFailure(reason: FailureReason)；
      超时/配额/空内容/畸形 JSON 分别映射 TIMEOUT / QUOTA（或 BUDGET）/ EMPTY /
      MALFORMED_JSON（结构不对是 SCHEMA）。
4.3.5 超长上限：自由文本 512 字符/条；expected_effects / assumptions / uncertainties
      各 32 条；replacement_c 20,000 字符。多余字段用 pydantic extra="forbid"。
其他  route 取值 route_a / route_b（与骨架一致）；指令样文本整份拒绝，不过滤后接受；
      无 context 的 validate_candidate 不做 hash 归属/evidence 签发校验，由
      validate_candidate_for_context 补。
```

## 8. 已知限制（不用回复，但请写进验收证据）

- `validate_candidate(payload)` 不绑定 job：hash 格式对、但不属于本 job 的候选，
  只有 `validate_candidate_for_context` 能拒。骨架若只测前者，覆盖的是结构边界。
- JSON Schema 只表达结构，Route A/B 的跨字段规则由 Pydantic 负责；这是分层，不是遗漏
  （本地测试 `test_json_schema_does_not_encode_route_semantics` 记录了这个边界）。
- provider 测试全部用假 transport：不调用真实 API、不需要 key、不花钱。
- 真实 API 首次调用需要 key，属于人工步骤，不在 CI。

---

## 9. 安全线（不变）

- 默认拒绝：无法判断 classification 时 `may_leave_host` 返回 `False`。
- 候选 payload 是不可信数据：字符串不能变成指令、权限或范围变更。
- 校验失败 = typed failure / 抛异常，绝不"猜一个合法候选"。
- 不为测试方便放宽 schema；宁可拒绝。
