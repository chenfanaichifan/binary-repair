# SiliconFlow key status (2026-11-14)

- Earlier supplied key: HTTP 401 `Token is invalid` on `.cn`; records retained.
- New international key (`.com`): **valid for identity probes** — `/v1/models`
  HTTP 200 and `resp.model == requested` for Qwen/Qwen3.8-27B,
  moonshotai/Kimi-K3.1-Pro, deepseek-ai/DeepSeek-V4.1-Flash.
- Full benchmark calls then returned **HTTP 402**
  `{"code":30001,"message":"Sorry, your account balance is insufficient"}`;
  the same key on `.cn` returns 401 (endpoint/region mismatch).
- No model call for the 12-case benchmark succeeded on SiliconFlow; no matrix
  result was fabricated.  The exact key is not stored in this repository.

Status: **P1 blocked by account balance**, not by model ID or transport.
