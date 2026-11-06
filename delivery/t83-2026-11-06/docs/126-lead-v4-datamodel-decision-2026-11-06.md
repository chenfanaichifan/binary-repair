# 126 — Lead: V4 stays `not_run`; it is a data-model gap, not a missing engine, and it is not hand-runnable

- **Owner:** Lead (decision and assignment only; no code in this record)
- **Date:** 2026-11-06
- **Status:** binding for 124 and for T8.3; changes no gate, no verdict, no merge, no tag
- **Basis:** M3's record 124 analysis, verified against the tree (commands and outputs in
  `126-lead-v4-datamodel-evidence-2026-11-06.txt`)
- **Supersedes:** the wording "no engine ran" in M4's 124 row. The verdict does not move.

---

## 0. Decision

| Item | Decision |
|---|---|
| M3's V4 analysis | **Accepted.** V4 `not_run` is a data-model gap, not "there is no engine". |
| Hand-running a V4 harness | **Rejected as evidence.** It cannot enter the bundle and would not change the attempt. |
| 124 outcome | **`inconclusive` / `required_check_not_run`**, unchanged |
| 124 gate results | V0/V1/V3/V5 **passed**, V2/V4 **not_run**, unchanged |
| 118 | **VERIFIED**, independent of 124 and of T8.3 |
| T8.3 | **BLOCKED**, unchanged |
| Route B V4 landing spot | The **only** admissible path; an independent change, not a patch to make a verdict appear |
| Merge / tag / live success | **Not authorized** |

This record endorses M3's refinement rather than reversing anything: the earlier
position "V4 is not_run" was correct but under-explained. The explanation matters,
because "not_run because no engine exists" invites the wrong fix (install or run
an engine), while "not_run because the pipeline has no place to put a V4 result"
names the actual work.

## 1. What was verified, not repeated

Every claim below was re-derived from the tree; the file and line are given so a
reader can check them without trusting this record. Line numbers are from
`origin/m3/cwe416-v3-noinput` (the branch 124 came from); where a second writer
exists, both are named.

| # | Fact | Location | Consequence |
|---|---|---|---|
| 1 | `"symbolic": "model"` — and the module says a passing V4 is `model`, "never machine code" | `app/domain/scopes.py:27`, docstring `:13-15` | A V4 pass can never be reported as binary-level proof |
| 2 | `"V4": "not_run"` is a literal in the Route B writer's results dict | `routeb/attempt_writer.py:221`, detail `:233` | The bundle cannot carry a V4 verdict, whatever a solver produced |
| 3 | The same literal exists in the controller-side writer | `app/services/attempt_writer.py:179` | Ingest cannot repair what the writer never learned |
| 4 | The producer stub hardcodes it too: `v4-symbolic.json` `state: not_run`, `ran: false`, and `gates[V4].result: not_run` | `docs/handoffs/evidence/cwe416-candidate-2026-11-05/tools/write_bundle_meta.py:136-153, 182-184` | The gap is at **both ends**: producer and consumer |
| 5 | No code assigns V4 from an artifact; `v4-symbolic.json` is written and listed, never read into a result | `git grep 'results\["V4"\]'` on the 124 branch: no hits | A hand-run harness has no landing spot even if it is perfect |
| 6 | V4 is a **required** obligation | `app/services/orchestration.py:29` (`("V4", "symbolic", True)`) | Required + not_run is decisive, not advisory |
| 7 | Required `NOT_RUN` maps to `INCONCLUSIVE` / `REQUIRED_CHECK_NOT_RUN` | `app/domain/acceptance.py:74-79` | The attempt outcome is forced by the data model |
| 8 | The documented bundle schema says so in words: "V4 symbolic \| `not_run` \| not implemented" | `docs/route-b/22-routeb-attempt-bundle.md:100` | The limitation is specified, not accidental |

The chain, in one line:

```text
harness run --(no bundle field)--> writer writes "not_run" --> required NOT_RUN
            --> REQUIRED_CHECK_NOT_RUN --> inconclusive
```

Steps 2-4 are why a hand-run result cannot be "pasted in": there is nothing to
paste into that the acceptance engine reads. This is a stronger statement than
"the harness was weak" and a weaker one than "V4 is impossible".

## 2. Engine status, stated precisely

Both halves of the earlier wording are true and neither is the blocker:

- **The engine is installed.** The 124 guest carries angr 10.0.4.post1 and z3 5.1.0
  (M3 record 124 §6, restated in M1's 125 §2).
- **No engine ran in the 124 window**, and `v4-symbolic.json` says exactly that:
  `state: not_run`, `ran: false`, `claimed_scope: null`.
- **Even a run would not have changed the attempt**, because of §1 rows 2-5.

So "M4's row 'no engine ran'" is a true observation about that window, and the
Lead position is: do not use it as the explanation. The explanation is the missing
landing spot. This distinction is the whole point of record 126.

## 3. What is forbidden

1. **Do not change the writer's `"V4": "not_run"` to `"passed"`** to relieve T8.3.
   That fabricates a gate result and is the defect this record exists to prevent.
2. **Do not run angr/ad-hoc symbolic analysis and paste the result into the V4
   field** (or into a bundle by hand). Unsolicited evidence with no accounting is
   not reviewable, and a hand-edited bundle cannot be bound to the run.
3. **Do not describe a `model`-scope V4 as binary-level proof.** `scopes.py` forbids
   the claim even on a pass.
4. **Do not let V3's 1/1 stand in for V2 or V4.** V3 passing one no-input
   observation says nothing about interface or symbolic obligations.
5. **Do not weaken the obligation list** (for example dropping `symbolic`) to make
   the inconclusive verdict disappear. That is a contract-policy change, not a
   fixture or writer fix, and it is not on this table.

## 4. The only admissible path

If V4 is to exist for Route B, it is an **independent Route B change** with all six
parts landed and reviewed together. Any subset leaves V4 `not_run`, which is a
correct outcome, not a failure to fix.

| Step | Change | Owner | Exit criterion |
|---|---|---|---|
| 1 | V4 scope definition (what a bounded symbolic run must observe; `model`, never `binary`) | M3 | Reviewed text in `app/domain/scopes.py` semantics and the Route B bundle doc |
| 2 | Bundle schema: a V4 payload that carries the run, not just a status string | M3 | Schema doc + producer writes it from a real run |
| 3 | Producer: `write_bundle_meta.py` derives V4 from that payload | M3 | `state`/`ran`/`claimed_scope` no longer literals |
| 4 | Writer: `routeb/attempt_writer.py` reads the payload into `results["V4"]` | M3 | No hardcoded `"not_run"` remains on that path |
| 5 | Acceptance mapping: `model` scope passes only with complete state/solver accounting; unknown/timeout stay inconclusive | M1/M5 (acceptance owner) | Unit tests for pass / unknown / timeout / pruned |
| 6 | M4 independent review and replay on the **same candidate** | M4 | A review record; no self-certification |

Minimum content of the accounting (from the earlier v11 review, records 63/64, which
rejected a harness for exactly these gaps): solver-query counts, state counts,
resource-pruned counts, complete-exploration proof, and the exact candidate and
entry actually analysed. Missing any of them means `unknown`/`not_run`, never
`passed`.

**A passing V4 remains `scope: model`.** Even fully implemented, V4 does not
become binary-level proof, and `success_within_scope` still needs every required
obligation on matching final hashes.

## 5. Assignment (effective on publication)

**M3 — Route B / guest.**
Keep V4 `not_run`. Do not run an ad-hoc V4 harness for 124. If V4 is pursued, open
the Route B change as §4 (scope, payload, producer, writer, accounting) and do not
describe any V4 result as binary-level. T8.3 stays blocked; invent no second defect
class.

**M1 — host backend.**
Accept M3's V4 `not_run`. Do not edit the writer's hardcoded V4 to manufacture
evidence. Keep 124's ingest at `inconclusive` / `required_check_not_run`. Keep the
CWE121 v2 contract hash `24bfe568…4e37` and the 120 contract gate as they are.
Keep T8.3 blocked; no merge to `main`, no tag, no live-success text.

**M4 — verification.**
124 stays `inconclusive` / `required_check_not_run`. Record the reason as a
data-model gap, not "no engine". 118 stays VERIFIED, independent of T8.3. Record 91
is unchanged; same operator; the 9-12 review is counted separately; no merge, no
tag, no live-success text.

**M2 — console.**
Continue T8.2 (`assistant_llm.py`, `test_assistant_llm.py`). Result screens must
render `input_mode=none`, V3 1/1, and invalid as `N/A` — never as "2/2 passed" for
zero invalid cases. Keep partial usage visible.

## 6. State carried forward (unchanged by this record)

| Item | Value |
|---|---|
| 124 candidate | `46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0` |
| 124 edit | 5 bytes at offset 4869: `call free@plt` → `nop ×5` |
| 124 gates | V0/V1/V3/V5 passed; V2/V4 not_run |
| 124 outcome | `inconclusive` / `required_check_not_run` |
| 118 | VERIFIED (rebuild evidence package), independent |
| T8.3 | BLOCKED |
| Merge / tag / live success | none |

## 7. Precedent

This is not a new rule invented for 124. Records 63 (M4 review) and 64 (Lead
adjudication) already rejected a hand-built V4 harness for the v11 evidence: the
input was concretised rather than symbolic, the free domain was code-bounded, the
accounting could report "proven" from a step-limited run, and the harness analysed
a different candidate than the bundle. 126 applies the same rule to Route B: a V4
result is admissible only when the pipeline can carry it, bind it to one candidate,
and account for its exploration.

## 8. Not claimed

- No gate status changed; no V4 work was performed or authorized by this record.
- No claim that V4 is impossible, or that a future V4 would be worthless.
- No claim that 124 is a success in any sense.
- No claim about 118's content beyond "VERIFIED, independent".
- No code, test, fixture, contract, or branch was modified to publish this record.

## 9. Signature

| Role | Name | Date | State |
|---|---|---|---|
| Lead | Lead | 2026-11-06 | published |
| M3 | — | — | pending acknowledgement |
| M1 | — | — | pending acknowledgement |
| M4 | — | — | pending acknowledgement |
| M2 | — | — | pending acknowledgement |
