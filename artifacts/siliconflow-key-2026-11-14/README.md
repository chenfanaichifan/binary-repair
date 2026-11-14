# SiliconFlow key status (2026-11-14)

The supplied key was checked against `https://api.siliconflow.cn/v1/models` and
returned **HTTP 401 `Token is invalid`**.  The same key also returned 401 from
DashScope and DeepSeek; no model call was made and no matrix result was
fabricated.  The key is not stored here.

To run P1, replace it with a valid SiliconFlow account key in
`SILICONFLOW_API_KEY` (do not commit), then run the identity probe before the
12-case matrix.
