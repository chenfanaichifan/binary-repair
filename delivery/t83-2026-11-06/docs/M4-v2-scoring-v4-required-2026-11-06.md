# M4 — V2 scoring, typed V4, and required lock (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** review of M1's committed `f57a051` / `e73dafc` plus the uncommitted
V2 work. No code change, no gate promotion, no merge, no tag.

---

## 0. Verdict

| Item | Result |
|---|---|
| 124 outcome | **`inconclusive` / `required_check_not_run` / `interface`** — unchanged |
| Typed V4 validation | **committed and passing** (16/16 + 2/2) |
| Required lock | **committed and passing** (3/3; direct probe) |
| V2 static scoring | **NOT in the committed state** — the scorer is untracked and unwired |
| V2 capability | **works** in the working tree: 5/5 on the 124 ELFs; validator rejects the observation |

The key distinction: typed V4 and the required lock are **committed**; the V2
scorer is a **working-tree-only** implementation and therefore does not count yet.

---

## 1. 124 outcome — unchanged

Committed gate results: V0 pass, V1 pass, **V2 not_run**, V3 pass, **V4 not_run**,
V5 pass; all required.

```text
outcome = inconclusive
reason  = required_check_not_run
failing = interface          (V2, first required not_run)
```

`tests/integration/test_cwe416_124_ingest.py` passes on the committed tree, so
the 124 outcome is a code-level result, not just a reading of the package.

---

## 2. Typed V4 — committed

`app/domain/v4.py` (committed in `f57a051`) defines `V4Evidence` with:

- `candidate_sha256` / `original_sha256`;
- `tool_versions`, `preconditions`, `memory_predicates`, `forbidden_ranges`,
  `hooks`;
- `exploration_accounting` (states explored/pruned, max depth, complete,
  unexplored);
- `solver_accounting` (engine, version, queries, sat/unsat/unknown/timeouts,
  complete);
- `calibration` (suite, cases, passed, failed, complete);
- `replay` (command, runs ≥ 2, identical, evidence hash);
- `claimed_scope`, `not_claimed`.

`obligations.py` validates it on a V4 `passed` claim; an incomplete claim becomes
`unknown` with `"V4 evidence not verified: …"` — never a pass from hash binding
alone. `tests/test_v4_evidence.py` **16 passed**; `tests/integration/
test_v4_bundle_gate.py` **2 passed** on the committed tree.

## 3. Required lock — committed

```python
FORCED_REQUIRED_GATES = frozenset({"V2", "V4"})
is_required = True if gate in FORCED_REQUIRED_GATES else required.get(gate, True)
```

Direct probe on the committed tree:

```python
build_obligations({"V2": "not_run", "V4": "not_run"},
                  required={"V2": False, "V4": False})
# every obligation: required=True
```

`tests/test_orchestration_required.py` **3 passed**. `required={"V4": False}` is
therefore **not a production path**: the gate stays required, and a `not_run` V4
still blocks success.

## 4. V2 static scoring — not committed

**Committed state (`e73dafc`):**

- `app/domain/interface.py` **does not exist** in the commit;
- `obligations.py` has **no** `validate_interface_report` / `target_entry` code;
- `routeb/attempt_writer.py` hardcodes `"V2": "not_run"`;
- the 124 artifact is `scored: false`, `state: measured_observation`;
- no interface test is committed.

So in the committed production path V2 **cannot score**; `not_run` is correct.

**Working tree (uncommitted):**

- `app/domain/interface.py` and `tests/test_interface_check.py` are **untracked**;
- `interface.py` implements `check_interface` (five checks) and
  `validate_interface_report`, which rejects a measured observation;
- `tests/test_interface_check.py` **4 passed**;
- on the 124 ELFs it returns **passed, 5/5**, and the validator **accepts** the
  scored report while **rejecting** the 124 observation (`not a schema-1 V2
  report`);
- wiring into `obligations.py` / `attempt_writer.py` / `route_bundle_ingest.py`
  is also uncommitted (working-tree tests pass; an earlier transient `a.job_id`
  typo is now `r.job_id`).

**Conclusion:** V2 *can* score — the check is real and gives 5/5 on this
candidate — but it is **not committed, not wired into the committed pipeline, and
not tested in the committed tree**. Until it is committed and wired, V2 stays an
observation and `not_run`.

---

## 5. If V2 were wired, 124 still would not succeed

A scored 5/5 V2 would change the gate row to `passed`, but V4 remains `not_run`:

```text
V2 passed, V4 not_run  -> inconclusive / required_check_not_run / failing=symbolic
```

So wiring V2 alone does **not** produce `success_within_scope`; V4 must also
produce typed, validated evidence. This is the correct policy outcome.

---

## 6. Record 118 and T8.3

`118 = VERIFIED (rebuild evidence package)` remains independent: it does not
promote V0–V5, does not produce a candidate, and does not relieve T8.3.
T8.3 stays **BLOCKED**.

---

## 7. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 8. Evidence

| File | Content |
|---|---|
| `M4-v2-v4-required-evidence-2026-11-06.txt` | commits, committed/uncommitted split, tests, required probe, V2 scorer result, 124 outcome |
| `probe_v2_validator.py` | scored report accepted / observation rejected |
| `_m4-verify/e73dafc/` | clean committed tree used for the gate tests |
