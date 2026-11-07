# M4 — record 127 V4 producer: readable, not ingestible (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** shape review of M3's V4 producer evidence against the product
`V4Evidence` model. No gate promotion, no merge, no tag.

---

## 0. Verdict

| Item | Result |
|---|---|
| Producer evidence readable | **yes** — the five facts are present and legible |
| Ingestible by product `V4Evidence` | **NO** — `V4EvidenceError`, 35 validation errors |
| V4 in 124 | **`not_run`** — `gate-index.json` untouched, `v4-symbolic.json` still `not_run` |
| 124 outcome | **`inconclusive` / `required_check_not_run` / `symbolic`** |
| Next step | M3 rewrites with the **product** `V4Evidence` writer, then M4 checks five points |

The producer is not wrong; it is a **different schema**. The product cannot read
it, so it cannot become a V4 pass.

---

## 1. What the producer evidence says (readable)

`v4-evidence.json` (27 keys) contains the facts the review will need:

| Check | Producer value |
|---|---|
| negative control | `known_good: "known_good"`, `known_bad: "known_bad"`, `known_bad_rejected: true`, `cases` list of 2 |
| accounting | `states {active:0, deadended:2, deferred:0, errored:0, initial:2, pruned:0, unconstrained:0}`, `solver {eval:2, sat:1, unsat:1, unknown:0, timeouts:0}`, `unexplored: []`, `steps:25 < max_steps:128` |
| replay | `{runs:2, identical:true, digests:[cb2137a2…, cb2137a2…]}` |
| claimed_scope | `"model"` |
| empty-disjunction | `cases[0].notes`: “unsat comes from an empty disjunction: no free() occurs on this path…”; also in `not_claimed` |

So the substance is there. The problem is the **shape**, not the claim.

---

## 2. Why it cannot be ingested

The product `V4Evidence` (fdaaa7b) requires:

`kind`, `scope`, `state`, `ran`, `tool_versions`, `preconditions`,
`memory_predicates`, `forbidden_ranges`, `hooks` (list of strings),
`exploration_accounting`, `solver_accounting`, `calibration`, `replay`,
`claimed_scope: Literal["model"]`, `not_claimed`.

The producer has none of the first ten in that form, and:

- `state` / `kind` / `scope` / `ran` are **missing**;
- `tool_versions`, `preconditions`, `memory_predicates`, `forbidden_ranges` are
  **missing**;
- `hooks` is a list of **objects** `{symbol, why}`, not strings;
- `known_good` / `known_bad` are **strings** (`"known_good"` / `"known_bad"`),
  not booleans;
- `replay` has `digests` but no `command` or `evidence_sha256`;
- `exploration_accounting` / `solver_accounting` / `calibration` are replaced by
  flat `states` / `solver` / `cases`;
- the product forbids extra fields, so `cases`, `complete`, `contract_sha256`,
  `engine`, `entry_address`, `generated_by`, `input_domain`, `known_*`,
  `max_steps`, `property_text`, `solver`, `states`, `steps`, `target_entry`,
  `timeouts`, `unexplored`, `unknown` are all errors.

Measured: **35 validation errors**, starting with missing `state`,
`tool_versions`, `preconditions`, `memory_predicates`, `forbidden_ranges`, and
`hooks.0` not being a string.

---

## 3. Two writers with the same name

| Writer | Signature | Shape |
|---|---|---|
| M3 `v4_evidence.py` | `write_v4_evidence(path, evidence: V4Evidence)` | its own model (`V4Case`, `StateAccounting`, `SolverAccounting`, `Replay`) |
| product `app/domain/v4.py` | `write_v4_evidence(path, data: object, …)` | `V4Evidence` with `exploration_accounting` / `solver_accounting` / `calibration` |

Record 127 says the product writer did not exist in M3's repository when the
producer was written, so M3 defined one. At `fdaaa7b` the product writer exists;
the rewrite should call **that** one, not a second model with the same name.

---

## 4. Five points M4 will check after the rewrite

| # | Check | What must be present |
|---|---|---|
| 1 | **negative control** | `known_good`, `known_bad`, `known_bad_rejected` as booleans; `cases ≥ 2`; `passed ≥ 1`; `failed ≥ 1`; the known-bad candidate is the **original** and is rejected |
| 2 | **accounting** | `exploration_accounting` (`states_explored`, `states_pruned`, `resource_pruned`, `max_depth`, `complete`, `unexplored == []`); `solver_accounting` (`engine`, `version`, `queries ≥ 1`, `sat`, `unsat`, `unknown == 0`, `eval`, `timeouts == 0`, `steps < max_steps`, `complete`); `calibration` complete |
| 3 | **replay** | `command`, `runs ≥ 2`, `identical: true`, `evidence_sha256`; two independent runs byte-identical |
| 4 | **claimed_scope = model** | `claimed_scope: "model"`; `not_claimed` includes a binary-level exclusion |
| 5 | **empty-disjunction disclosure** | the candidate's `unsat` is stated to be the empty-disjunction case (no `free()` on the path), not a solved constraint; in the product shape this must live in `not_claimed` (or a new typed field), because there is no `cases[].notes` slot |

Point 5 is the one the product shape does not model explicitly: the disclosure
must be carried in text (`not_claimed`) or the schema needs a dedicated field.
M4 will not accept an `unsat: 1` without that disclosure.

---

## 5. 124 — unchanged

```text
V0 passed, V1 passed, V2 not_run, V3 passed, V4 not_run, V5 passed
outcome = inconclusive
reason  = required_check_not_run
failing = symbolic
```

The producer record itself changed no gate; this review changes none.

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
| `M4-127-v4-producer-evidence-2026-11-06.txt` | producer keys, 35-error product validation, five facts, writer signatures, 124 gate index and outcome |
| `probe_v4_ingest.py` | product `validate_v4_evidence` against the producer JSON |
| `v4-evidence.json` | the producer artifact |
| `_m4-verify/fdaaa7b/` | the product schema used for validation |
