# 175 — Post-P1 task board

Date: 2026-11-07  
Head: e14fe43 (plus later docs/status commits)

## Closed

```text
T8.3: COMPLETE (record 170/171)
P1: success_within_scope (record 173)
P2: ACCEPTANCE PASSED
124: V0-V5 passed
Route A V4: model-scope marker, candidate 2a96b108
Route A V1/V2/V3/V5: passed via real guest bundle
M1 controller/attempt worker/P2: done
M3 T6.2/P1 windows/V5: done
M5 Gate 2b/Review 9-11: done
```

## Open

```text
M2-T8.2 assistant_llm.py + test_assistant_llm.py: NOT DONE
M2-T7.4/T7.5/T7.6/T8.4/T7.8 GUI: NOT DONE
M4-T7.7 UI honesty: NOT DONE
M4-T8.5 LLM no-key-leak/no-injection: NOT DONE
Review 9-12 original text: MISSING
Lead tag decision: NO TAG
Lead main merge: NOT MERGED
```

## Ownership

M2: T8.2, T7.4, T7.5, T7.6, T8.4, T7.8, Review 12 UI.
M4: T7.7, T8.5, Review 9-12 independent verification.
M1: API fields for UI; no UI changes.
M3: no more guest work for P1; keep evidence frozen.
M5: no more usage; envelope only.
Lead: tag/main only after M2/M4.

## Code suites

```text
M1/M4/M5 targeted: exit 0
pytest -q: exit 0
```

## Boundary

```text
V4 model scope
M4 = Lead same operator
No tag
No merge main
118 VERIFIED independent
```
