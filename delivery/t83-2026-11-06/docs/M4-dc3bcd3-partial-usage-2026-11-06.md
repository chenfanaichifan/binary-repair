# M4 — dc3bcd3 partial usage and controller pass-through (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** usage aggregation and controller rendering at `dc3bcd3`. No gate
promotion, no merge, no tag.

---

## 0. Verdict

| Item | Result |
|---|---|
| `aggregate_job_usage` partial semantics | **PASS** — real + NULL sibling sums real, `partial=True`; all real → `False`; all NULL / no calls → `None` |
| controller pass-through | **PASS** — `_ai_usage_for_job` returns the aggregate unchanged, including `partial` |
| legacy plan fallback | **PASS** — returns `partial: False` |
| tests | **19 passed** |
| one-sided NULL row | **boundary** — its present half is not counted; the row only marks `partial` |
| 124 | **`inconclusive` / `required_check_not_run` / `symbolic`** |
| 118 | **VERIFIED** — independent of T8.3 |

---

## 1. The change

`app/services/model_calls.py`:

```python
real = [
    row for row in rows
    if row["prompt_tokens"] is not None and row["completion_tokens"] is not None
]
if not real:
    return None
return {
    "input_tokens": sum(int(row["prompt_tokens"]) for row in real),
    "output_tokens": sum(int(row["completion_tokens"]) for row in real),
    "partial": len(real) != len(rows),
}
```

`app/controller_api.py`:

- `_ai_usage_for_job` returns `aggregate_job_usage(...)` **untouched** when
  model_calls rows exist — it does not re-derive, zero-pad, or drop `partial`;
- the legacy plan fallback returns
  `{"input_tokens": ..., "output_tokens": ..., "partial": False}`;
- `_snapshot` assigns the same `ai_usage` object to every route, so the flag
  reaches the API response.

---

## 2. Measured behavior

Probe with synthetic jobs (`_m4-verify/probe_partial_usage.py`):

| Case | Aggregate | Controller |
|---|---|---|
| real `(12,3)` + NULL sibling | `{12, 3, partial: True}` | same, unchanged |
| all NULL | `None` | `None` |
| all real `(5,7)+(1,2)` | `{6, 9, partial: False}` | — |
| one-sided NULL only `(5,None)` | `None` | — |
| one-sided NULL `(5,None)` + real `(1,2)` | `{1, 2, partial: True}` | — |

The key case — a NULL sibling does not erase real usage and sets `partial` — is
correct, and the controller does not drop the flag.

---

## 3. Tests

```text
tests/integration/test_ai_usage_sources.py
tests/integration/test_assistant_plan.py
tests/integration/test_contract_gaps.py
→ 19 passed
```

They cover: model_calls win over the plan; both job_id/attempt bindings count;
partial is marked and not dropped; all-NULL is `None`; plan fallback is
`partial=False`; no usage is `None`.

---

## 4. Boundary to confirm: one-sided NULL

A call with `prompt=5, completion=NULL` contributes **neither** number; it only
makes the aggregate `partial=True` (or `None` if it is the only call). This is
consistent with “one incomplete row does not erase the real usage its siblings
recorded” — but it does not count the row's present half.

If M5 intends “sum every non-NULL token, mark partial”, the code needs a
different rule. If “a row is real only when both counts are present”, the
current behavior is correct. This is a semantic choice, not a bug in the
implemented rule.

---

## 5. Count note

The 133 record says `410 passed / 2 skipped / 0 failed`; the local full suite at
`dc3bcd3` is **410 passed / 9 skipped / 0 failed** (no failures, 7 more skipped
here). The 6d67140 merge message similarly says 506/9/0 while the local merge tip
is 513/9/0. These are documentation/count discrepancies, not semantic failures;
they should be corrected or qualified with the exact tree/command.

---

## 6. 124

```text
V0 passed, V1 passed, V2 not_run, V3 passed, V4 not_run, V5 passed
outcome = inconclusive
reason  = required_check_not_run
failing = symbolic
```

The usage change does not touch V0–V5; V4 remains `not_run` pending M4 replay.

---

## 7. Record 118 and T8.3

`118 = VERIFIED (rebuild evidence package)` remains independent: it does not
promote V0–V5, does not produce a candidate, and does not relieve T8.3.
T8.3 stays **BLOCKED**.

---

## 8. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 9. Evidence

| File | Content |
|---|---|
| `M4-dc3bcd3-partial-usage-evidence-2026-11-06.txt` | commit stat, partial code lines, probe output, 19 tests, 124 gate index |
| `probe_partial_usage.py` | the five-case aggregate/controller probe |
| `_m4-verify/dc3bcd3/` | clean archive used for all runs |
