# 216 — real DeepSeek provider smoke

Date: 2026-11-09  
Branch: `release/v1.2.1`  
Key handling: key supplied interactively; never written to repository, logs, or this record.

## Result

```text
test_provider_connection() -> ok: true
model: deepseek-flash
usage: prompt_tokens=38 completion_tokens=5 total_tokens=43
latency_ms: 1904
request_id: null
```

No key was echoed in the response. No `.env` or key file was committed.

## UI path

```text
save -> 已保存（sk-…<masked>，保护：mode-0600）
input cleared -> True
provider test -> 连接失败：llm_http_error (fake key only)
clear -> 已清除；助手回到未配置状态
key in server log -> 0
```

The fake-key UI test intentionally does not claim provider success. The real
smoke above is the only provider-success evidence.

## Boundary

```text
v1.2.1 is still a staging/local release; public tag/main not moved.
M4 signed v1.2.0 receipt: db99eb0
```
