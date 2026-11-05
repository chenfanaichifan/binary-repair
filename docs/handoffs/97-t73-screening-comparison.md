# 97 — T7.3 screening-test comparison (M3)

**Renumbered 91 → 97 on 2026-11-05.** `91` is taken by M5
(`91-m5-completion`); any earlier reference to `91-t73-screening-comparison`
means this file.


**Owner:** M3 · **Date:** 2026-11-05 · **Status:** module + real comparison
delivered. Evidence: `docs/handoffs/evidence/T73/`.

T7.3 is the behaviour half of the repair-comparison screen: not "which route
scored higher", but **per frozen case, what did each binary actually do**. The
route summaries already existed (`candidate_sha256`, `obligations`, `outcome`);
what was missing is the case-level view that makes "repaired" and "unchanged"
distinguishable.

## 1. What was built

`workers/broker/comparison.py` — a pure function over guest observations:

```python
compare(manifests=[...], original=<obs>, routes={"A": <obs>, ...}) -> ComparisonRecord
```

It judges every route with the **same** frozen oracle Route A and Route B are
judged by (`tests/v3_oracle.py`), then arranges the results side by side. It
executes nothing; observations come from `workers/broker/guest_behaviour.py`.

Output shape (`ComparisonRecord`, pydantic, `extra="forbid"`):

| Field | Meaning |
|---|---|
| `cases[]` | per frozen case: `expected_return_code`, `original`, `routes{}`, `changed_by` |
| `routes{}` | per route: `v3_result`, `passed/failed/not_run`, `valid_behaviour_preserved`, `repaired_invalid_cases`, `still_failing_invalid_cases` |
| `ranking` | **always `null`** — a smaller diff or a higher pass count does not imply a safer repair |
| `limitations[]` | one line per route whose invalid cases still fail, plus "vulnerability not demonstrated" when the original passes |

## 2. Measured comparison

Three binaries, one frozen matrix, one guest session:

| Route | sha256 | V3 | Valid preserved | Invalid repaired | Still failing |
|---|---|---|---:|---:|---|
| A | `c4a15921…aa82` | `passed` 6/6 | yes | both | — |
| B_roundtrip | `decdcdb8…954b` | `failed` 4/6 | yes | none | both |

`invalid-first` goes `0 → 1` (A) while staying `0` for the round trip;
`invalid-longer` goes `139 → 1` (A) while staying `139`. `changed_by` is `("A",)`
on exactly those two rows and empty everywhere else.

## 3. Why the round trip is the interesting control

`B_roundtrip` is the Gate 4 **unchanged** round trip. It reproduces the
original's behaviour exactly — same exits, same bytes on valid cases — and
therefore repairs nothing. That is what round-trip consistency means, and it is
what Nick's audit item 3 warned must not be presented as a repair.

This record makes the distinction mechanical rather than rhetorical: the
comparison shows the round trip changing no case, so a consumer cannot read its
"4/6 preserved" as progress.

## 4. Fail-closed rules

- A route with no observations is `not_run`, never "equivalent to the original".
- `changed_by` is decided by the **observed exit code** differing from the
  original's — not by a result label, which would call a still-vulnerable case
  "failed on both sides" and hide that nothing moved.
- `still_failing_invalid_cases` is reported even when the route's diff is smaller.
- If the original does not fail the invalid cases, the record states the
  vulnerability is not demonstrated, because "repaired" would then be vacuous.

12 unit tests (`tests/unit/test_broker_comparison.py`) pin these properties,
including `test_a_failed_on_both_sides_is_not_reported_as_changed` and
`test_no_ranking_is_produced`.

## 5. Limits

- Six frozen cases; no symbolic (V4) check, so "no other defect" is not claimed.
- `B_roundtrip` is a **control**, not a Route B repair candidate. No Route B
  repair candidate exists in this session, so the A-vs-B comparison the screen
  will eventually show is only half-populated.
- Route B's real candidate will arrive through T8.3 (guest half); T7.3 consumes
  observations regardless of which route produced them, so no rework is expected.
- This is comparison data, **not** an acceptance verdict. Outcomes still come
  from the acceptance engine.
