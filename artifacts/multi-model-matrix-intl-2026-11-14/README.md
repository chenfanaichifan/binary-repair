# International SiliconFlow / 2-model matrix attempt (2026-11-14)

Valid international key: identity probes for all three requested SiliconFlow
models passed with exact `resp.model`:

- `Qwen/Qwen3.8-27B`
- `moonshotai/Kimi-K3.1-Pro`
- `deepseek-ai/DeepSeek-V4.1-Flash`

However **every full benchmark call returned HTTP 402**
`{"code":30001,"message":"Sorry, your account balance is insufficient"}` on
`https://api.siliconflow.com/v1`; the same happens on `.cn` with this
international key (401).  Small identity probes had succeeded before the
benchmark and are retained in `identity-probe/`.

Completed real benchmarks in this run:

| model | baseline | AI verified | loop | non-loop |
|---|---:|---:|---:|---:|
| deepseek-flash | 0/12 | 6/12 | 6/6 | 0/6 |
| deepseek-v4-pro | 0/12 | 6/12 | 6/6 | 0/6 |

The 5-model matrix is therefore **blocked by account balance**, not by model
identity or code.  A 4–6 model matrix requires either a topped-up SiliconFlow
account or another provider key.  No result was fabricated.

Native PoC: Linux VM, qemu-x86_64 binfmt.
