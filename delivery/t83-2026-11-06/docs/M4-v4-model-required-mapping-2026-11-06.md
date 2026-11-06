# M4 — V4 data model and V2/V4 required mapping review (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** design and implementation review only. No code change, no gate
promotion, no merge, no tag.

---

## 0. Verdict

| Item | Result |
|---|---|
| V4 data model **design** | **sound** (Standard B checklist) but **not formalized** as a schema |
| V4 **implementation** | generic obligation + free-form `v4_evidence` artifact; **content is not validated** |
| V2 / V4 **required mapping** | **required by default and in the production path**; an override surface exists |
| 124 **outcome** | **`inconclusive` / `required_check_not_run`** — correct |

The 124 package is safe because V4 is `not_run`. The gap is what would happen if a
producer ever marked V4 `passed` with an incomplete artifact.

---

## 1. V4 data model — design

**Sources:** `docs/handoffs/62-lead-v4-acceptance-standard.md` (Standard B),
`app/domain/scopes.py`, `docs/interfaces/artifact-roles-v1.md`.

The design requires an independent replay and a **structured** evidence body:

| # | Required content (record 62 §3) |
|---|---|
| 1 | candidate + original SHA-256; angr/Claripy/Z3 versions; model/entry preconditions and input domain |
| 2 | memory-access predicate / forbidden ranges; stack/argv setup; enumerated hooks (a hook may not assume the repair safe) |
| 3 | exploration accounting: active/terminal/errored/unconstrained/deferred/resource-pruned states; solver queries decided/unknown/timeout |
| 4 | calibration: original violation counterexample; deliberately defective candidate rejected; routea/routeb results |
| 5 | raw logs/JSON with hashes; verifier's own replay commands and output; candidate hash before/after |
| 6 | explicit “what is not proven”; `inconclusive` on incomplete exploration |

**Design strengths**

- Standard B (independent replay) rejects a self-verified producer result.
- `scope_for_kind("symbolic") = "model"` is conservative: a passing V4 is never
  rendered as binary-level proof.
- The 124 artifact already carries `claimed_scope: null` and an explicit
  `not_claimed` list (binary-level proof, other paths, rest of program).

**Design gaps**

1. **No schema.** `schemas/generated/` contains only `candidate.v1`, `context.v1`,
   `template.v1`, `template-param.v1`. There is no V4/obligation schema, so the
   checklist is prose rather than a typed contract.
2. **The obligation model is too coarse.** A row is
   `kind / scope / required / result / evidence_artifact_id / detail`; it cannot
   distinguish a complete V4 artifact from a four-field stub.
3. **`claimed_scope` is not modeled.** It appears in the 124 artifact but no code
   reads or validates it.
4. **No structured accounting.** There are no fields for exploration states,
   solver queries, hooks, or calibration, so "incomplete exploration" cannot be
   detected mechanically.

---

## 2. V4 data model — implementation

| Layer | Observed | Assessment |
|---|---|---|
| `GATES` | `("V4", "symbolic", True)` | required by default |
| `build_obligations` | uses `required.get(gate, True)` | V4 required unless overridden |
| `persist_obligations` | `build_obligations(results)` — no override | all six required in production |
| `attempt_writer` | `"V4": "not_run"` default; never parses a v4 file | V4 stays `not_run` unless a bundle says otherwise |
| `verify_artifact` | job/attempt binding, size, SHA-256 | **content not validated** |
| `route_bundle_ingest` | `passed` requires at least one artifact; role `v4_evidence` | **no V4 content check** |
| `scopes.py` | symbolic → `model` | correct; a V4 row cannot claim binary scope |
| `claimed_scope` | **no code reference** | unenforced |

**Consequence.** A V4 `passed` obligation only needs an artifact whose bytes hash
to the recorded row. Nothing checks record 62's checklist. Record 62 says any
missing item means `NOT VERIFIED`; the implementation cannot enforce that today.

**What 124 actually contains.** `v4-symbolic.json` is a correct `not_run` stub:

```json
{"gate":"V4","kind":"symbolic","scope":"model","state":"not_run","ran":false,
 "reason":"no symbolic or bounded-model engine was run ...",
 "claimed_scope":null,
 "not_claimed":["binary-level proof of the repair", "..."]}
```

So 124 does not misrepresent V4. The gap is latent, not active.

---

## 3. V2 / V4 required mapping

```text
GATES: V0 True, V1 True, V2 True, V3 True, V4 True, V5 True
```

- `persist_obligations` and `worker.evaluate_attempt` pass **no** `required`
  override, so V2 and V4 are required in the production path.
- `evaluate_attempt(..., required: Mapping[str, bool] | None)` accepts an
  override and forwards it to `build_obligations`. No production caller uses it;
  unit tests use it only for optional extras.
- **Latent policy hole:** a future caller could pass `{"V4": False}` and let a
  `not_run` V4 stop blocking success. Record 62 §2 makes V4 mandatory for
  `success_within_scope`; the API should not permit that override for V2/V4 (or
  should validate the mapping against a fixed policy).

**V2 note.** `v2-interface.json` has `"pass": true`, but it is a *measured static
observation*, not a scored verdict. `gate-index.json` correctly records V2 as
`not_run`. It must not be promoted.

---

## 4. 124 outcome

Actual gate results: V0 pass, V1 pass, **V2 not_run**, V3 pass, **V4 not_run**,
V5 pass; all required.

```text
outcome = inconclusive
reason  = required_check_not_run
failing = interface          (V2, the first required not_run)
```

Counterfactuals:

```text
V2 passed, V4 not_run  -> inconclusive / required_check_not_run / failing=symbolic
all six passed         -> success_within_scope
```

So `success_within_scope` is impossible while V2 or V4 is `not_run`. The 124
outcome is correct and reproducible.

---

## 5. Recommendations (not changes)

1. Add a V4 evidence schema (or typed domain object) covering record 62 §3.
2. Validate the V4 artifact's content when a gate is marked `passed`; reject an
   incomplete artifact rather than hash-binding it.
3. Make `claimed_scope` a modeled field and reject anything above `model`.
4. Pin V2 and V4 as non-overridable required gates, or validate `required`
   against a fixed policy.
5. Keep V2's static observation labelled `not_run`; never derive a verdict from
   it.

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
| `M4-v4-model-required-evidence-2026-11-06.txt` | GATES, required override path, scope map, obligation writer, 124 V4 stub, outcome |
| `docs/handoffs/62-lead-v4-acceptance-standard.md` | the V4 design standard |
| `app/domain/scopes.py` | V4 scope = model |
| `app/services/orchestration.py` | GATES and required mapping |
| `app/services/obligations.py` | passed-requires-artifact, no content validation |
