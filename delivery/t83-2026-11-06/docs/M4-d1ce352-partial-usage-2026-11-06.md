# M4 — canonical d1ce352 partial usage review (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** partial usage/controller at canonical `d1ce352`. No gate promotion,
no merge, no tag.

---

## 0. Verdict

| Item | Result |
|---|---|
| canonical review point | **`d1ce352`** — confirmed 16:49 |
| usage code vs `dc3bcd3` | **no diff** in `model_calls.py` / `controller_api.py` |
| `aggregate_job_usage` partial | **PASS** — real + NULL sibling sums real, `partial=True`; all real → `False`; all NULL/no calls → `None` |
| controller pass-through | **PASS** — `_ai_usage_for_job` returns the aggregate unchanged |
| plan fallback | **PASS** — `partial: False` |
| tests | **19 passed** |
| one-sided NULL | **boundary** — present half not counted, row only marks partial |
| 124 | **`inconclusive` / `required_check_not_run` / `symbolic`** |
| 118 | **VERIFIED** — independent of T8.3 |

---

## 1. Canonical pin

Fresh `ls-remote` at **2026-11-06T16:49+0800**:

```text
d1ce352f60057ab3cd389c6af609c7b5ed3bcefd  refs/heads/canonical/m1-m5-integration
7817a20cd5a215e4423de6e045bf754691671120  refs/heads/integration/live-bridge
```

`d1ce352` is the merge of `dc3bcd3` (partial usage) and `40a4153` (v3 no-input
baseline). The merge did not change the usage code:

```text
$ git diff --stat dc3bcd3 d1ce352 -- \
    app/services/model_calls.py app/controller_api.py
(empty)
```

---

## 2. Partial semantics at d1ce352

```python
real = [row for row in rows
        if row["prompt_tokens"] is not None
        and row["completion_tokens"] is not None]
if not real:
    return None
return {
    "input_tokens": sum(int(row["prompt_tokens"]) for row in real),
    "output_tokens": sum(int(row["completion_tokens"]) for row in real),
    "partial": len(real) != len(rows),
}
```

`_ai_usage_for_job` returns `aggregate_job_usage(...)` untouched when model_calls
rows exist; the plan fallback returns `partial: False`.

Probe at `d1ce352`:

| Case | Aggregate | Controller |
|---|---|---|
| real `(12,3)` + NULL sibling | `{12, 3, partial: True}` | same, unchanged |
| all NULL | `None` | `None` |
| all real `(5,7)+(1,2)` | `{6, 9, partial: False}` | — |
| one-sided NULL only `(5,None)` | `None` | — |
| one-sided NULL `(5,None)` + real `(1,2)` | `{1, 2, partial: True}` | — |

---

## 3. Tests

```text
tests/integration/test_ai_usage_sources.py
tests/integration/test_assistant_plan.py
tests/integration/test_contract_gaps.py
→ 19 passed
```

They cover model_calls over plan, both bindings, partial marked not dropped,
all-NULL `None`, plan fallback `partial=False`, and no usage `None`.

---

## 4. Boundary

A call with `prompt=5, completion=NULL` contributes neither number; it only sets
`partial=True` (or `None` if it is the only call). This matches “an incomplete
row does not erase its siblings' real usage”, but does not count the row's
present half. Confirm with M5 if “sum every non-NULL token” was intended.

---

## 5. 124 and 118

```text
124: V0 passed, V1 passed, V2 not_run, V3 passed, V4 not_run, V5 passed
     outcome = inconclusive
     reason  = required_check_not_run
     failing = symbolic
```

`118 = VERIFIED (rebuild evidence package)` remains independent: it does not
promote V0–V5, does not produce a candidate, and does not relieve T8.3.
T8.3 stays **BLOCKED**.

---

## 6. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 7. Evidence

| File | Content |
|---|---|
| `M4-d1ce352-partial-usage-evidence-2026-11-06.txt` | pin, empty usage diff, partial lines, probe, 19 tests, 124 gate index |
| `probe_partial_usage.py` | five-case aggregate/controller probe |
| `_m4-verify/d1ce352/` | clean canonical archive |
