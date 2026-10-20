# Verification Design — Acceptance Rules and Test Coverage

**Status:** Acceptance rules and their negative-test matrix are implemented and passing. Integration and AI-boundary suites are present as contract skeletons that activate when the owning modules land.
**Owner:** Member 4 (verification).
**Last updated:** 2026-10-18.
**Related:** Tech Design §9 (Verification and acceptance engine), Tech Design §13 (Testing and evidence replay), PRD "Result Semantics", `agent_docs/testing.md`.

> **Scope note.** This document records what the verification slice decides and
> what it needs from the other slices. It is not a replacement for the Tech
> Design. Where the two disagree, the Tech Design wins and this document is
> corrected.

---

## 1. Purpose

The acceptance engine answers exactly one question: **given the evidence that
exists for a repair attempt, may this candidate be called successful?**

It does not produce evidence, run tools, touch the database, or render HTML.
It is a pure function so that the API, the GUI, the export builder, and the
tests all reach the same verdict. Any second place that computes a success
label is a defect: the UI must render an outcome, never derive one.

The product risk this guards is specific. A demonstration is worthless, or
worse, if a candidate that was never fully verified appears green. Most of the
rules below therefore exist to make *non*-success the default.

---

## 2. Acceptance semantics

### 2.1 The six outcomes

Exactly six terminal labels exist. They are not interchangeable and they must
stay visually distinct in the GUI.

| Outcome | Meaning | Can satisfy the MVP? |
|---|---|---|
| `success_within_scope` | every required obligation passed, hashes match, scope reviewed and nonempty | yes |
| `unsupported` | a required repair/placement/interface capability is outside the supported profile | no |
| `rejected` | a generated candidate failed a required check | no |
| `inconclusive` | available evidence cannot establish a required property | no |
| `error` | a tool, provider, or system failed | no |
| `cancelled` | the operator stopped the attempt | no |

`success_within_scope` is deliberately the longest name: it is a claim about a
stated scope, never about the program as a whole.

### 2.2 Check results

Each obligation carries a result. `passed` is the only value that can
contribute to success.

| Result | Meaning |
|---|---|
| `passed` | the check completed and the property held |
| `failed` | the check completed and the property did not hold |
| `not_run` | the check was not executed or is not implemented — **never** `passed` |
| `unknown` | the solver/analysis could not decide |
| `timed_out` | the check exceeded its budget |

### 2.3 Decision precedence

Implemented in `decide_attempt_outcome`. Evaluated top to bottom; the first
matching rule wins.

1. `cancelled` → `cancelled`
2. tool/provider failure (`error_reason`) → `error`
3. capability outside the profile (`unsupported_reason`) → `unsupported`
4. any **required** obligation `failed` → `rejected`
5. any **required** obligation `not_run` / `unknown` / `timed_out` → `inconclusive`
6. candidate hash ≠ approved hash → `inconclusive` (`hash_mismatch`)
7. reviewed scope absent or empty → `inconclusive` (`empty_scope`)
8. no required obligations evaluated → `inconclusive` (`no_required_evidence`)
9. otherwise → `success_within_scope`

Two orderings are deliberate and easy to get wrong:

- **A definite failure outranks missing evidence.** If a candidate was *shown*
  dangerous, the honest label is `rejected`, even when another check never ran.
  Softening it to `inconclusive` would understate a known failure.
- **An empty obligation list is not success.** This is the guard against
  silently dropped checks: if everything is skipped, the result is
  `inconclusive`.

### 2.4 Run-level aggregation

The MVP requires both routes to succeed on the same original binary. A run
therefore succeeds only when both route verdicts are `success_within_scope`.
Otherwise the most serious observed condition is reported, in this order:
`cancelled` > `error` > `unsupported` > `rejected` > `inconclusive`.

One successful route is never a successful run.

---

## 3. Implemented artifacts

| Path | State |
|---|---|
| `app/domain/outcomes.py` | implemented — `CheckResult`, `Phase`, `Outcome`, `ReasonCode`, `NON_SUCCESS_OUTCOMES` |
| `app/domain/acceptance.py` | implemented — `Obligation`, `Verdict`, `decide_attempt_outcome`, `decide_run_outcome` |
| `tests/unit/test_acceptance.py` | implemented — 29 passing tests, negative-first |
| `tests/conftest.py` | implemented — shared synthetic ELF builders, project-root import path |
| `tests/integration/test_identity_state.py` | contract skeleton — activates when `app.services.jobs` exists |
| `tests/integration/test_ai_boundary.py` | contract suite — 17 tests pass against `origin/member-5-deepseek-schema` (`e175436`); skips on the member-4 branch until that branch lands |

Reason codes are persisted and exported, so they are part of the evidence
contract: **add values, do not rename existing ones.**

---

## 4. Interface contracts

These are proposals for the owning members to confirm or amend. They exist so
two people can work in parallel without guessing. Expected interface for the
verification slice is small on purpose. **§4.1 and §4.3 are both confirmed
(2026-10-18).**

### 4.1 Obligation — what verification consumes

Already implemented in `app/domain/acceptance.py`:

```python
@dataclass(frozen=True)
class Obligation:
    kind: str            # stable identifier, e.g. "structure", "regression", "symbolic"
    required: bool       # does the reviewed contract require this evidence?
    result: CheckResult  # passed / failed / not_run / unknown / timed_out
    detail: str = ""     # human-readable context, shown next to the result
```

The caller (job controller / acceptance orchestration) builds the list of
obligations from persisted evidence and calls:

```python
decide_attempt_outcome(
    obligations=...,
    candidate_sha256=...,     # hash of the final candidate actually validated
    expected_sha256=...,      # hash the approval was bound to
    reviewed_scope_sha256=...,# hash of the reviewed verification scope
    cancelled=...,            # operator stop
    error_reason=..., error_detail=...,
    unsupported_reason=..., unsupported_detail=...,
) -> Verdict
```

A `Verdict` carries `outcome`, `reason`, `failing_obligation`, and `detail`.
The caller persists those fields; it must not translate them into its own
labels.

**Confirmed by member 1 on 2026-10-18.**

- 4.1.1: the four fields are sufficient. Gate number, evidence id, and
  timestamps live in the database row or in `detail`; they are not added to the
  dataclass.
- 4.1.2: the job controller calls the keyword-only function directly. A thin
  adapter in the jobs service is allowed only if it maps a job record to
  arguments; it contains no decision logic and no second `if all_passed:`.
- 4.1.3: the contract row holds the hash written at review/freeze time; run
  creation copies it into `run.reviewed_scope_sha256` in the same transaction
  and asserts equality. The decision reads **only** the run row. A later
  contract re-review produces a new hash, and existing runs keep their pinned
  value, so an old verdict is never rewritten.
- 4.1.4: the V0–V5 kind list is accepted (`identity`, `structure`, `interface`,
  `behaviour`, `symbolic`, `reproducibility`).
- `reviewed_scope_sha256` is **opaque to the engine**: the decision only checks
  that it is present and non-empty. Verification never parses, recomputes, or
  compares it, so no canonical serialization format is required from this
  slice. Correctness of the value is owned by the contract/approval layer; a
  wrong but non-empty hash would not be detected here.

### 4.2 Job/run identity — what member 1 provides

Consumed by `tests/integration/test_identity_state.py`. Exact names may change;
the behaviours may not.

| Need | Behaviour it must support |
|---|---|
| create a job from input bytes | returns a job id and the SHA-256 of the original; stores an immutable copy |
| read a job by id | returns phase, hashes, and the current contract revision |
| record a reviewer approval | binds input hash, contract revision, test-manifest hash, and scope hash |
| start a run | idempotency key; a duplicate start does not create a second charged attempt |
| restart recovery | an interrupted run cannot accept partial output as evidence |

### 4.3 Candidate schema and provider — what member 5 provides

Consumed by `tests/integration/test_ai_boundary.py`.

| Need | Behaviour it must support |
|---|---|
| validate a candidate payload | rejects extra fields, wrong hashes, illegal route, out-of-contract target, oversized strings |
| expose allowed data boundary | a way to ask whether given content may leave the host externally |
| typed provider failure | timeout / quota / empty content / malformed JSON produce a typed failure, never a fabricated candidate |

**Confirmed by member 5 on 2026-10-18.** The accepted contract:

- `app.domain.candidates.validate_candidate(payload, *, allowed_targets=None,
  templates=None, allowed_calls=None, max_replacement_chars=20_000)` — one
  positional payload, the rest keyword overrides. It returns a validated
  candidate object and raises on any invalid payload; it never repairs or
  defaults one. The default target allowlist is module-level contract data
  containing `copy_input` and `copy_name`; a candidate may reference it, never
  extend it.
- Schema v1 defines 14 fields, but the route-specific pairs are mutually
  exclusive. Route A requires `template_id` and `parameters` and must not carry
  Route B fields; Route B requires `replacement_c` and
  `recovered_function_sha256` and must not carry template fields. The `12 + 2 =
  14` phrasing in member 5's reply is the schema total, not a single payload.
- Route B content checks: `replacement_c` must define the target function,
  contain no NUL byte, contain no forbidden construct (`#include`, `#pragma`,
  `asm`, `__attribute__`, `system`, `popen`, `exec*`, `fork`, `dlopen`,
  `socket`, `open`), and call only identifiers on the allowed-callee list.
- `app.domain.candidates.validate_candidate_for_context(payload, ctx)` — adds
  the job binding the context-free call deliberately omits: route match, the
  three identity hashes, evidence issuance, and the recovered-function hash.
  Signature confirmed against the pushed branch.
- `app.domain.candidates.may_leave_host(classification, derived=False, *,
  authorized=False)` — `public` / `synthetic` -> `True`; `client` and any
  confidential derived content -> `False`; anything unrecognised -> `False`
  (deny by default). `authorized=True` is only meaningful with a recorded
  `client_authorized` classification.
- Size limits: free-text strings 512 characters each; `expected_effects`,
  `assumptions`, and `uncertainties` 32 entries each; `replacement_c` 20,000
  characters; `evidence_ids` 16. Extra top-level fields are rejected through
  pydantic `extra="forbid"`, and instruction-like or URL text rejects the whole
  candidate.
- `route` is `route_a` or `route_b`.
- Provider failures are `app.services.provider.ProviderFailure(reason:
  FailureReason, message: str, *, retryable=False, details=None)`;
  `FailureReason` is a superset containing at least `TIMEOUT`, `QUOTA`,
  `BUDGET` (local budget cap, distinct from the provider's own quota), `EMPTY`,
  `MALFORMED_JSON` (unparseable), and `SCHEMA` (parseable JSON, wrong fields).
  `require_candidate(result)` raises the typed failure and never fabricates a
  candidate.

**Integration status (2026-10-18).** Member 5 moved the code to the shared
repository root in commit `e175436` (`app/domain/candidates.py`,
`app/services/provider.py`, `binaryrepair_ai/`, `schemas/`). Running the
contract suite in an isolated worktree of that branch
(`origin/member-5-deepseek-schema`) gives **17 passed, 0 skipped, 0 failed**.
The member-4 working branch still lacks those files, so its own integration run
keeps skipping until the branch is merged; that skip is not a pass.

The boundary tests deliberately do **not** call the real API: a test suite must
never spend money or require a key. They test the local validation layer, which
is where the data-boundary guarantees actually live.

---

## 5. Test coverage matrix

Maps the verification ladder (Tech Design §9) to where each gate is checked.

| Gate | Covered by | Status |
|---|---|---|
| V0 identity / preconditions (hashes, approval, required inputs) | acceptance unit tests + identity/state skeleton | unit done, integration pending |
| V1 structure / placement | repair-integration tests (member 3 + verification) | pending |
| V2 interface / compatibility | repair-integration tests | pending |
| V3 concrete behaviour | behaviour suite (valid/invalid domain) | pending fixture |
| V4 bounded symbolic security | verifier calibration suite | pending environment |
| V5 reproducibility | replay procedure (member 1 / proposal) | pending |

The acceptance engine itself is required by every gate: it is the component
that turns V0–V4 evidence into one of the six labels.

---

## 6. Required negative scenarios (PRD)

The PRD names these scenarios. Each must receive the correct label, and they
are the acceptance criteria for this slice.

| Scenario | Expected label | Covered by |
|---|---|---|
| valid public-case request | `success_within_scope` (when all evidence passes) | acceptance unit tests |
| malformed candidate | `rejected` or `error` per origin | AI boundary + repair integration |
| wrong architecture / wrong input identity | `inconclusive` (`hash_mismatch`) or screening rejection | acceptance unit + identity |
| insufficient safe placement | `unsupported` | route tests |
| failing regression | `rejected` | acceptance unit |
| solver timeout / unknown | `inconclusive` | acceptance unit |
| provider failure | `error` | acceptance unit + AI boundary |
| embedded strings attempting permission change | no permission change; candidate rejected | AI boundary |
| client-data transfer without authorization | refused before any call | AI boundary |
| unsuccessful retry sequence | `error`/`inconclusive`, never success | AI boundary |
| cancellation | `cancelled`, distinct from `error` | acceptance unit |

---

## 7. Current gaps

Honest list of what is **not** verified yet.

1. **`pytest` cannot write its cache** in this development sandbox (permission
   denied on `.pytest_cache`). Tests run clean with `-p no:cacheprovider`;
   this is a local environment issue, not a product issue.
2. **No Ruff or mypy installed**, and the package index is unreachable from
   this machine, so lint/type gate has not run.
3. **Python 3.14.6 on Windows** locally; the target is Python 3.12 on Ubuntu.
   The modules avoid version-specific syntax, but they have not run on the
   target interpreter.
4. **The AI-boundary contract suite is verified against member 5's branch**
   (17 passed on `e175436` in an isolated worktree), but it still skips on the
   member-4 branch because the owning module lives on `member-5-deepseek-schema`.
   The identity/state suite is still unrun: `app.services.jobs` has not landed
   on any checked branch. A skip is never reported as passing.
5. **No fixture, no VM, no symbolic tool** in this environment, so V1–V4
   cannot be exercised at all yet.

---

## 8. Open questions for the team

1. ~~Does member 1 accept the `Obligation` shape and the `Verdict` fields as the
   integration boundary, or does the job controller need a different call
   shape?~~ **Resolved 2026-10-18: accepted as-is; see §4.1.**
2. ~~Who stores `reviewed_scope_sha256` — the contract row, the run row, or both?
   The acceptance call needs exactly one authoritative value.~~ **Resolved
   2026-10-18: both rows store it, the run row is authoritative, and the
   decision reads only the run row; see §4.1.**
3. Should an attempt whose screening was rejected before any candidate existed
   produce `rejected`, or a distinct pre-run state? The current engine can
   express `rejected` with `failing_obligation="screening"`; confirm that is
   acceptable to the GUI.
4. Where does the evidence replay record live (member 1 / proposal), and does
   it reference acceptance verdicts by hash? V5 requires that link.
