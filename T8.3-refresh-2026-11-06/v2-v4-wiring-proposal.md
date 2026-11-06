# Proposal — how V2 and V4 enter an attempt, and why M3 cannot write it

Status: **proposal only**. Nothing here is implemented, and M3 does not own
`routeb/` or `app/domain/`. Written because the next blocking step is not more
evidence — it is that the product cannot read the evidence this sample already
has.

## The gap, measured

`routeb/attempt_writer.py` builds the gate map for every bundle:

```
line 219   "V2": "not_run"
line 221   "V4": "not_run"
line 228   "V2": "interface check not implemented in Route B executor"
line 233   "V4": "symbolic check not run"
```

`app/services/orchestration.py` marks all six gates `required=True`, and the
worker calls `evaluate_attempt` without a `required=` override, so both of those
hardcoded values are *required* obligations. `app/domain/acceptance.py` turns a
required `not_run` into `REQUIRED_CHECK_NOT_RUN` → `inconclusive`.

Consequence, independent of evidence quality: **a bundle can never reach
`success_within_scope` while those two lines say `not_run`.** For this sample V2
is measured 5/5 and V4 producer evidence validates, and the attempt still lands
`inconclusive`. That is the real remaining distance to T8.3, and it is a product
change, not another deliverable.

## What the bundle already provides

| gate | file | shape | what a reader would accept |
|---|---|---|---|
| V2 | `gates/V2-interface.json` | `state`, `passed`, `total`, 5 `checks[]`, both binary hashes | `passed == total == 5` **and** hashes match the bundle's binaries |
| V4 | `v4/v4-symbolic.json` | validated by `app/domain/v4.py::validate_v4_evidence` | validation OK **and** hashes bound **and** an independent replay receipt |

Both files are producer output. That is exactly why they cannot be trusted on
their own: `docs/handoffs/62 §1` — a producer does not certify its own result.

## Proposed change, in the smallest shape that keeps that rule

**1. Let the writer read, but only where a receipt exists.**

```python
# sketch — routeb/attempt_writer.py
V2 = "not_run"; V4 = "not_run"
v2 = bundle.get("gates", {}).get("V2-interface.json")
if v2 and v2.get("passed") == v2.get("total") == 5 \
        and v2.get("original_sha256") == original_sha \
        and v2.get("candidate_sha256") == candidate_sha:
    V2 = f"{v2['passed']}/{v2['total']}"      # counting, not "passed"
```

- V2 has no independent verifier in this project, so it is *allowed* to be read
  directly — it is a static measurement with no judgement in it: five `readelf`
  comparisons between two files that are already hash-bound by V0.
- The condition is deliberately narrow: exact 5/5, exact hash match. Anything
  else keeps the current `not_run` string. No parsing leniency.

**2. V4 requires a receipt, and the receipt is M4's.**

```python
v4 = validate_v4_evidence(payload, candidate_sha256=…, original_sha256=…)
receipt = bundle.get("replay", {})
if v4 and receipt.get("verified_by") == "m4" and receipt.get("digest_matches"):
    V4 = "passed"
```

- `verified_by` is not M3's to write, and this proposal does not create it. The
  writer only *checks* it. A bundle without the field keeps V4 `not_run`, which is
  what every bundle built today would get.
- Simulation (`make check`) can test the branch with a fixture receipt; the
  fixture must live under `tests/`, never in `fixtures/public/`.

**3. Degrade, never upgrade.**

| situation | result |
|---|---|
| V2 file missing | `not_run` (today's behaviour) |
| V2 present but 4/5, or hashes differ | `unknown`, not `not_run` — the evidence exists and disagrees |
| V4 validates, no receipt | `not_run` (producer alone) |
| V4 validates + receipt from a non-M4 id | `unknown` and a named finding |
| V4 fails validation | `unknown` with the reason |

`unknown` is the honest label for "there is evidence and it did not satisfy the
check"; `not_run` must keep meaning "nothing was produced".

**4. Scope must travel with the result.**

`v4-symbolic.json#claimed_scope` is `model`. If V4 is admitted, the attempt's
scope is model-level, and `success_within_scope` must be read as "success within
model scope", not binary-level proof. `app/domain/scopes.py` already says a
symbolic pass is not machine-level proof; the writer should carry that string
through rather than let a bare `passed` imply more.

## Tests this change would need

1. Bundle with V2 5/5 and hashes matching → V2 counted, V4 still `not_run`, verdict
   still inconclusive (V4 is the last wall).
2. Same plus a valid M4 receipt → `success_within_scope`, and the scope reported as
   model.
3. V2 4/5 → `unknown` on V2, inconclusive, named finding.
4. V2 hashes pointing at a different binary → `unknown`, because a passing V2 about
   another file is worse than no V2.
5. Receipt with `verified_by="m3"` → `unknown`, not `passed`.
6. No gate files at all → today's behaviour exactly (regression).

## What M3 will do when this lands

Nothing new: the files are already in the bundle in the shape above, and the
bundle's own `gate-index.json` records `V2 5/5` and `V4 not_run`. If the writer
needs a different field name or nesting, say which and M3 will emit it — that is a
format change, not a re-measurement.

## What this proposal does not claim

- It does not make V4 passed. Only M4's replay plus its receipt does that.
- It does not weaken the "producer cannot self-certify" rule; it narrows where the
  rule is checked, from "no reader exists" to "the reader checks for a receipt".
- It does not decide acceptance. The Lead still accepts or rejects the evidence.
