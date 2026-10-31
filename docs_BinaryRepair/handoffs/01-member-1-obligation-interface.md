# To member 1: confirm the Obligation / Verdict interface (verification-design §4.1)

**Recipient:** Member 1 (job controller / identity and state slice)
**From:** Verification slice (Member 4)
**Date:** 2026-10-18
**Basis:** `docs_BinaryRepair/verification-design.md` §4.1 (quoted verbatim); implementation in `app/domain/acceptance.py`
**Needs a reply:** two things — (1) do you accept this interface shape; (2) where is the single authoritative home of `reviewed_scope_sha256`. A fill-in template is at the end; two minutes to reply.

---

## 1. Why this is the only thing I need from you

The verification slice is implemented: `app/domain/outcomes.py` + `app/domain/acceptance.py`, 29 unit tests passing. It is a pure function: evidence goes in, one of six outcome labels comes out; it does no I/O, does not touch the database, and renders no pages.

It is also the only decision point in the whole project. The API, GUI, export, and tests all call it — any second place that computes "success" is a defect.

So there is exactly one interface between your job controller and it: **you build the `Obligation` list from persisted evidence -> call `decide_attempt_outcome` -> store the returned `Verdict` verbatim.** Once the interface is fixed, both sides can write code in parallel without guessing the call shape.

## 2. The interface verbatim (§4.1)

```python
@dataclass(frozen=True)
class Obligation:
    kind: str            # stable identifier, e.g. "structure", "regression", "symbolic"
    required: bool       # does the reviewed contract require this evidence?
    result: CheckResult  # passed / failed / not_run / unknown / timed_out
    detail: str = ""     # human-readable context, shown next to the result
```

Call:

```python
decide_attempt_outcome(
    obligations=...,
    candidate_sha256=...,     # hash of the final candidate actually validated
    expected_sha256=...,      # approved candidate hash, NOT the original input hash
    reviewed_scope_sha256=...,# hash of the reviewed verification scope
    cancelled=...,            # operator stop
    error_reason=..., error_detail=...,
    unsupported_reason=..., unsupported_detail=...,
) -> Verdict
```

`Verdict` has only four fields: `outcome`, `reason`, `failing_obligation`, `detail`. **Persist those four fields verbatim; do not translate them into your own labels.**

Two behaviours you must know:

- `CheckResult` has exactly five values: `passed` / `failed` / `not_run` / `unknown` / `timed_out`. Only `passed` can contribute to success; a check that did not run or is not implemented must be `not_run`, **never `passed`** ("missing is not passing").
- Use `decide_run_outcome(route_a=..., route_b=...)` for the whole run: both routes must be `success_within_scope`; one successful route is not a successful run.

## 3. Three things on your side

| # | Do | Where it goes wrong |
|---|---|---|
| 1 | Build `obligations` from persisted evidence | When evidence is missing, include the obligation as `NOT_RUN` rather than dropping it; an empty list yields `inconclusive`, which is deliberate (it stops checks from being silently dropped) |
| 2 | Call with the approved candidate hash, or `None` | `expected_sha256` is the **approved candidate hash**, never `job.original_sha256`. If approval does not bind a candidate, pass `None`; passing the original input hash would reject every real repair candidate as a hash mismatch. |
| 3 | Store all four `Verdict` fields | Do not re-decide success in a task, route handler, or template; the GUI only renders `outcome` |

## 4. Four points to confirm

| # | Question | Default answer (implemented; accept as-is) |
|---|---|---|
| 4.1.1 | Are the four `Obligation` fields enough? Do you need extra information when building it (gate id, evidence id, timestamp)? | Enough. Put extra information in the database row or in `detail`; do not add it to the dataclass — it would become a parameter every call site has to supply, and the engine does not use it |
| 4.1.2 | Does this keyword-only, all-defaults call form fit your orchestration layer? | It fits. A wrapper that takes a job record is fine, but it may only assemble parameters — it must not copy the decision logic (no second `if all_passed:`) |
| 4.1.3 | Where is the single authoritative `reviewed_scope_sha256` stored: contract row, run row, or both? | The acceptance call reads exactly **one** value. If both rows store it, state which one wins; otherwise the same scope has two hashes and the `empty_scope` / hash-mismatch decisions lose their footing |
| 4.1.4 | Should `kind` names be frozen as a shared list now? | A suggestion only. The engine treats `kind` as an opaque string (it is only echoed into `failing_obligation`), so naming does not change decisions; but mismatched names make human reports confusing. Suggested V0–V5 names: `identity`, `structure`, `interface`, `behaviour`, `symbolic`, `reproducibility` |

If you disagree with anything: give the alternative shape, why it is needed, and which hash it binds. Changes on the verification side are confined to `app/domain/acceptance.py` and the unit tests, so the earlier you say it the cheaper it is.

## 5. Reply template (copy and fill in)

```text
§4.1 interface:
[ ] accept as-is
[ ] needs changes: ____ (write the alternative shape)

4.1.1 Obligation fields: enough / need ____
4.1.2 call form: accept / need a wrapper ____
4.1.3 reviewed_scope_sha256 home: contract row / run row / both (authoritative: ____)
4.1.4 kind list: accept suggestion / use this: ____

Other:
```

## 6. Appendix: current state and what confirmation does and does not unlock

Measured 2026-10-18:

- `python -m pytest tests/unit -q -p no:cacheprovider` -> **29 passed**
- `python -m pytest tests/integration -q -p no:cacheprovider -rs` -> **2 skipped** (the skips exist because `app.services.jobs` / `app.domain.candidates` do not exist; skip is not a pass)

One thing needs to be clear: **confirming the interface does not by itself turn the skeletons into real tests.** The skeletons use `pytest.importorskip("app.services.jobs")`, so they move from skip to run only when the module exists and its entry points follow §4.2. What confirmation unlocks is "write the module without guessing the shape", which is the actual prerequisite for parallel development.

The five behaviours in §4.2 (create / read / approval binding / idempotent start / restart recovery) are not in scope for this letter — the skeleton is already written to §4.2 and will run as written once you land the module.
