# 62 — Lead ruling: V4 acceptance standard (Standard B) and its scope

**From:** Lead
**To:** M3, M5, M4, M1
**Date:** 2026-10-31 17:10 (Asia/Hong_Kong)
**Re:** M3/M5 question: Standard A (V4 evidence alone; no_counterexample ⇒ passed) vs
Standard B (independent review/replay required)
**Status:** decision. **No gate approval, no V4 passed label, no fixture freeze, no Gate 4 pass.**
Gate 3 closed/approved; Gate 4 `NOT RUN`; Gate 5 `pending/unsigned`; Gate 6 `partial`; fixture
`NOT FROZEN`.
**Evidence basis for this ruling:** `agent_docs/testing.md` (V4 row and Replay), Tech Design §9
and verification-policy line, PRD F4/Completed-MVP checklist, `docs/handoffs/42`/`47`, and
M3/M5's report (angr 10.0.4; original counterexample; routea/routeb proven/no_counterexample;
self-verified single-agent, not independently reviewed).

## 1. Decision: Standard B — independent verification/replay is required for V4 acceptance

**A self-verified single-agent V4 result is not sufficient to change V4 from `not_run` to
`passed`.** "The solver found no counterexample" plus "the model catches the original bug" is
calibration evidence, not acceptance evidence. V4 may be accepted only after an independent
verifier (M4 or another teammate role) checks the raw evidence and replays/validates it against
the stated model and domain, records the result, and the Lead approves.

Standard A is **rejected** as the project's V4 acceptance rule. Reasons, all from project
requirements:

1. `agent_docs/testing.md` §Replay: "**A second teammate must complete this** without access to
   original source." The same document's V4 row requires a candidate-specific model, input
   domain, memory-access predicates, exploration/solver accounting, and complete state
   accounting — not merely a producer's summary.
2. Tech Design verification policy: "evidence replay by another teammate"; PRD MVP checklist:
   "Independent teammate replays both results" (also V5's own criterion explicitly includes
   independent teammate replay).
3. Project rule: missing/not-run evidence is never a pass; a producer's own conclusion is not an
   independent measurement. `M5` is the Gate 4 DRI/consumer and `M3` is the producer; their shared
   single-agent verification cannot simultaneously be the independent review.

### 1.1 What "independent" means here — and its recorded limitation

In this project the same human operates multiple AI windows (VMer = M3; M4 verifier = Lead). True
two-person human independence is therefore **not available**. The required independence is
**role/window separation with an actual second replay**, disclosed as a limitation:

- the independent verifier must not reuse the producer's verdict or self-written conclusion;
- it must re-run or re-check the raw V4 evidence from frozen candidate bytes;
- every record must state "M4 verifier = Lead same person/operator; role-separated, not
  human-independent";
- if the guest/angr environment is unavailable for the replay, the result is `NOT VERIFIED`; it
  is not waived or relabelled passed.

A Lead waiver of M4 verification (as attempted on 2026-10-30 in `docs/handoffs/38`/`60`) **does
not satisfy Standard B** and is not accepted as a substitute for replay.

## 2. Scope correction: Gate 4 formal is not V4-gated

The two things must not be conflated:

- **Gate 4 formal (Route B unchanged round trip)** has its own rule: `gate4-status.json=pass`,
  six-case 6/6 identical, M4 acceptance of image/tool/isolation evidence, record signatures
  (`docs/route-b/14`). V4 does not gate that formal round-trip criterion.
- **Acceptance ladder / final `success_within_scope` / Gate 6** requires V4. V4 remains
  `not_run`/`NOT VERIFIED` until Standard B is met; therefore neither route can claim
  `success_within_scope`, and Gate 6 stays partial.

So:
- Gate 4 formal may be evaluated on P4 + record + real p2 criteria without V4;
- but V4 **must not** be marked `passed` by the M5 adapter from the self-verified result, and
  Gate 4/overall success must not be claimed on that basis.

## 3. What V4 evidence/replay must contain (acceptance checklist)

The independent verifier must see/record at minimum:

1. candidate SHA-256 (final candidate bytes; same bytes as the acceptance subject) and original
   SHA-256; angr/Claripy/Z3 versions; model/entry preconditions and input domain;
2. memory-access predicate/forbidden ranges, stack/argv setup, hooks (enumerated and justified;
   a hook may not assume the repaired operation safe);
3. exploration accounting: active/terminal/errored/unconstrained/deferred/resource-pruned states,
   solver queries decided/unknown/timeout; a budget is not permission to discard reachable states;
4. calibration: original violation found (counterexample) and a deliberately defective candidate
   rejected; routea/routeb results (proven/no_counterexample) within the stated domain;
5. raw logs/JSON with hashes; the verifier's own replay commands and observed output, not only the
   producer's conclusion; candidate hash before/after the run;
6. explicit statement of what is **not** proven (function-level under entry preconditions, not
   whole-program; models/bounds; unresolved states); `inconclusive` on incomplete exploration.

If any of these is missing, V4 is `NOT VERIFIED` — never `passed`.

## 4. Actions

- **M5:** do not write V4 `passed` in the adapter/Gate 4 record from the self-verified result.
  Keep V4 `not_run`/`NOT VERIFIED` until the independent verifier row exists. Gate 4 record may
  note the V4 claim as producer-reported evidence only, explicitly not accepted.
- **M3:** publish the raw V4 evidence (scripts/logs/model/domain/accounting + candidate hashes)
  so M4 can replay; do not change or re-summarise after the fact.
- **M4:** perform the independent replay when raw evidence + guest/angr access exist; report
  `PASS`/`FAIL`/`NOT VERIFIED` per §3. If the guest or raw evidence is unavailable, record
  `NOT VERIFIED`; no waiver.
- **Lead:** no V4 approval, no Gate 4/overall success claim, no fixture freeze until a valid M4
  V4 row and the relevant gate evidence exist. The 2026-10-30 "M4 waived" statement is not
  accepted for V4 acceptance.

## 5. Status after this ruling

| Item | Status |
|---|---|
| Gate 3 | CLOSED/APPROVED `0b3b51e4…` (unchanged) |
| Gate 4 formal | `NOT RUN` — separate criteria; no V4 pass via Gate 4 |
| V4 / Gate 6 | V4 **not accepted**, still `not_run`/`NOT VERIFIED`; Gate 6 `partial` |
| Gate 5 | pending/unsigned (`51` NOT VERIFIED; no gate5 mode in jobwrap) |
| Fixture | **NOT FROZEN** |
| M5 adapter V4 label | must stay `not_run` until independent replay |

Standard A is not adopted. If the team wants Standard A, that is a project scope/policy change
that requires an explicit Lead/client decision; it is not granted here and would conflict with
the current verification policy.

## 6. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead (V4 acceptance standard) | Lead | 2026-10-31 | **Standard B adopted**; V4 not accepted from self-verified evidence; no gate/freeze approval |
| M4 verifier (acknowledgement) | M4 | — | replay task pending; no V4 row signed |
| M5 (adapter/Gate 4) | M5 | — | must keep V4 `not_run` until replay; no pass label |
