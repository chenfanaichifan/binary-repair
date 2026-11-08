# DeepSeek candidate quality — 2026-10-22

**Context:** `copy_name` Route B reviewed context, `deepseek-flash`, thinking disabled.
**Calls:** 4 real calls (1 on 2026-10-20 + 3 on 2026-10-22). Only public synthetic
fixture text was sent.

| run | latency | prompt | completion | total | cost (est.) | status | candidate sha256 |
|---|---:|---:|---:|---:|---:|---|---|
| 1 (10-20) | 2318 ms | 1111 | 532 | 1643 | $0.0009717 | accepted_for_validation | `aec0e6cb…` |
| 2 (10-22) | 3037 ms | 1111 | 553 | 1664 | $0.00073348 | accepted_for_validation | `aec0e6cb…` |
| 3 (10-22) | 2647 ms | 1111 | 554 | 1665 | $0.00073468 | accepted_for_validation | `aec0e6cb…` |
| 4 (10-22) | 3328 ms | 1111 | 587 | 1698 | $0.00077428 | accepted_for_validation | `aec0e6cb…` |

- **Acceptance rate:** 4/4 = 100% (`accepted_for_validation`).
- **Candidate bytes:** all four are byte-identical: `aec0e6cbc09306d21c816bb26b627f635efcf8682437fea2d4913de92c81a9ce`.
- **Failure types observed:** none. No `EMPTY`, `MALFORMED_JSON`, `SCHEMA`, `QUOTA`,
  `TIMEOUT`, or `SCOPE` failure in these four calls.
- **Latency:** 2318–3328 ms; **cost:** $0.00073–$0.00097 per accepted candidate.
- Prompt cache: first call 0 hit / 1111 miss; later calls 896 hit / 215 miss.

## What this proves

- The real endpoint + JSON mode + candidate schema + context binding work repeatedly.
- The model reliably returns the same safe-looking `copy_name` guard for this context.

## What this does not prove

- It is **not** a repair or V3 pass: the candidate has not been compiled/reintegrated/run.
- Four calls on one synthetic context are not a population; no claim about other
  functions, binaries, or client data.
- "Accepted for validation" means schema/scope only, not semantic correctness.

## Logs

`run1.txt`, `run2.txt`, `run3.txt` (no API key); candidate copies were temporary
(`/tmp/deepseek_candidate_*.c`) and are not committed.
