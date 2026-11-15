# Native semantic feedback retry (2026-11-15)

Controlled real run, DeepSeek flash, `hard-sprintf`, **no initial RepairSpec**:

- round 1: assembly failed native security gate;
- NativeFeedback classified `candidate_crash` / retryable with observed signal;
- round 2: planner + assembly revision with feedback; **VERIFIED**;
- both rounds and candidate artifacts are preserved.

This proves the feedback loop works on a real failure; it does not claim that
every failure is retryable.
