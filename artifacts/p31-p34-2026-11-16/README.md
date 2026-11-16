# P31-P34: unified LLM gateway, adapters, credentials and stability

## Scope

This acceptance records the offline implementation and smoke tests for
P31-P34. Real OpenRouter and Ollama network calls were not made; their status is
`NOT_RUN`.

## P31: unified gateway

Implemented in `app/services/llm_gateway/`:

- `base.py`: request/result types, typed errors, exact model identity;
- `client.py`: provider selection and `gateway_from_env` without network;
- `providers/`: Mock, OpenRouter (OpenAI-compatible) and Ollama (`/api/chat`);
- `credentials.py`, `errors.py`, `usage.py` for redacted credentials, typed
  failure codes and usage/latency records;
- `assistant_llm.py` and `binaryrepair_ai` preserve their legacy
  `chat_json`/fallback behavior while an optional gateway is configured.

The gateway does not make an acceptance decision and does not read a generator
verdict. Independent verification remains the sole authority.

## P32: adapters

- `MockProvider`: deterministic offline provider.
- `OpenRouterProvider`: OpenAI-compatible adapter with usage/request-id/latency
  and typed HTTP/timeout/transport errors; keys are redacted.
- `OllamaProvider`: local `/api/chat` adapter; no real network in tests.

Tests inject `httpx.MockTransport`; no live provider response is claimed.

## P33: credentials and preflight

`scripts/run_model_preflight.py` performs a configuration-only preflight by
default. A missing OpenRouter key returns `BLOCKED`/`ConfigurationError`; the
Mock provider returns `CONFIGURED` without a network call. The credentials
module keeps missing usage fields as `None` and never logs a key.

Live keychain/GitHub-Secret verification is `NOT_RUN`.

## P34: stability runner

`scripts/run_stability_matrix.py` now:

- uses independent verification, not the generator gate, for final status;
- separates `PLAN_INVALID`, `NO_CANDIDATE`, `ARTIFACT_MISSING`,
  `VERIFIER_ERROR` and `TIMEOUT`;
- captures subprocess timeouts;
- records expected/started/completed/eligible counts;
- supports checkpoint/resume without overwriting completed runs.

The live 60-run matrix was not executed. A previous partial record and one smoke
run remain explicitly partial.

## Tests

```text
tests/test_llm_gateway_credentials.py       15 passed
tests/test_llm_gateway_integration.py        9 passed
tests/test_stability_matrix_hardening.py     6 passed
tests/test_stability_matrix.py               1 passed
tests/test_assistant_llm.py / provider tests: passed
```

## Limitations

- Real OpenRouter/Ollama calls: `NOT_RUN`.
- Live 60-run matrix: `NOT_RUN`.
- P21 profile and historical evidence were not changed.
