# Member 5 reply: candidate schema and data-boundary interface confirmation (verification-design §4.3)

**Recipient:** member 4 (verification)
**From:** member 5 (candidate schema + provider)
**Date:** 2026-10-18
**Status:** implemented, ready for parallel integration
**Note:** this file supersedes the 2026-10-18 draft; it is the interface version confirmed against the implementation

---

## 0. One-page conclusion

| # | Your question | Answer |
|---|---|---|
| 4.3.1 | Do you accept the two signatures? | **Yes**, implemented exactly as you call them: `validate_candidate(payload)`, `may_leave_host(classification=..., derived=...)` |
| 4.3.2 | schema v1 top-level fields: 12 for Route A? 2 more for Route B? | **Yes. Route A has 12**; Route B adds `recovered_function_sha256` + `replacement_c` to those 12, **14 in total**. The route A payload needs no change |
| 4.3.3 | Who provides the target whitelist? | The module defaults to `{copy_input, copy_name}`; inject with `allowed_targets=`; a candidate cannot extend it |
| 4.3.4 | Where does the typed failure live and what is it called? | `app.services.provider.ProviderFailure(reason: FailureReason)` |
| 4.3.5 | How are extra fields rejected? | Pydantic `extra="forbid"` + semantic validation; **not** a hand-written dict check |
| — | Overlong string limits | **512** characters per item; **32** items per list; `replacement_c` **20,000** characters |

**What you need to change: nothing.** Your skeleton payload (`route_a`, `bounded-copy-guard`, `capacity: 64`)
passes as-is under the current implementation; your not-yet-written check 7 (overlong strings) now has definite numbers to assert.

Four differences from the draft:

1. The JSON value of `route` is fixed to **`route_a` / `route_b`** per your skeleton (we changed the DB enum in sync);
2. v1 has **14 fields** (Route A 12 + the 2 Route B-only ones); in a route A payload the two Route B fields may be omitted entirely;
3. Added "reject instruction-like text as a whole" (your check 5) and gave the 512/32 limits (your check 7);
4. `validate` is provided as an alias of `validate_candidate`, in case your skeleton used the short name.

---

## 1. Three entry points (implemented)

Module: `app/domain/candidates.py` (the name your skeleton binds via `pytest.importorskip`)

```python
def validate_candidate(
    payload: dict,
    *,
    allowed_targets: Iterable[str] | None = None,
    templates: Iterable[TemplateSpec] | None = None,
    allowed_calls: Iterable[str] | None = None,
    max_replacement_chars: int = 20_000,
) -> CandidateV1:
    """A valid payload returns a non-None CandidateV1; anything invalid raises CandidateRejected."""

def validate_candidate_for_context(payload: dict, ctx: RepairContext) -> CandidateV1:
    """Adds job binding on top of validate_candidate; failures also raise CandidateRejected."""

def may_leave_host(
    classification: str,
    derived: bool = False,
    *,
    authorized: bool = False,
) -> bool:
    """public/synthetic -> True; client -> False; unknown -> False (deny by default)."""
```

Additional notes:

- In `validate_candidate` only `payload` is a positional parameter; everything else has a default, so tests can pass just the payload;
- On failure it raises `CandidateRejected(reason_code, message)`, a subclass of `Exception`, so your
  `pytest.raises(Exception)` works directly;
- `CandidateRejected.reason_code` is a stable string (`schema_invalid` / `scope_violation` /
  `identity_mismatch`); the GUI and acceptance engine branch on it;
- `validate` is an alias: `validate is validate_candidate`.

**What it cannot do (important):** without job context it cannot prove that a hash or evidence id
was issued for this job. That binding happens in `validate_candidate_for_context(payload, ctx)`, and
the provider already performs the same context-binding check before returning a candidate (`check_candidate`). So:

| Entry point | Structure/semantics | Identity hash provenance | Evidence issuance | recovered hash |
|---|---|---|---|---|
| `validate_candidate(payload)` | ✅ | format only | format only | format only |
| `validate_candidate_for_context(payload, ctx)` | ✅ | ✅ | ✅ | ✅ |
| `require_candidate(result)` (after the provider) | ✅ | ✅ | ✅ | ✅ |

### 1.1 Full signature of `validate_candidate_for_context` (assert against it directly)

```python
def validate_candidate_for_context(
    payload: dict,
    ctx: RepairContext,
) -> CandidateV1
```

- Both parameters are **positional-or-keyword**; the two forms below are equivalent:
  `validate_candidate_for_context(payload, ctx)` /
  `validate_candidate_for_context(payload=payload, ctx=ctx)`;
- Returns `CandidateV1` (non-None); raises `CandidateRejected` on failure;
- Only three `reason_code` values can occur:
  `schema_invalid` (structure/route fields inconsistent), `scope_violation` (target/evidence/call out of bounds),
  `identity_mismatch` (the three hashes or the recovered hash do not match);
- `RepairContext`, `TemplateSpec`, `TemplateParam` are re-exported from `app.domain.candidates`,
  so tests do not need to import the implementation package.

It performs 5 additional bindings on top of `validate_candidate`:

| Check | On failure |
|---|---|
| `candidate.route == ctx.route` | `schema_invalid` |
| `original/contract/analysis_sha256` each equal the ctx values | `identity_mismatch` |
| `target_entry == ctx.target_entry` | `scope_violation` |
| `evidence_ids ⊆ ctx.allowed_evidence_ids` | `scope_violation` |
| Route B: `recovered_function_sha256 == ctx.recovered_function_sha256` | `identity_mismatch` |

Route A's template and parameter ranges come from `ctx.templates` (not the module defaults); Route B's
`allowed_calls` / `max_replacement_chars` also come from ctx.

**Cases you can drop straight into `tests/integration/test_ai_boundary.py`:**

```python
import pytest
from app.domain.candidates import (
    CandidateRejected,
    RepairContext,
    TemplateParam,
    TemplateSpec,
    validate_candidate_for_context,
)

SHA = "a" * 64
SCOPE = "b" * 64


def ctx() -> RepairContext:
    return RepairContext(
        route="route_a",
        original_sha256=SHA,
        contract_sha256=SCOPE,
        analysis_sha256=SCOPE,
        target_entry="copy_input",
        contract_summary="Valid: 0..63 bytes. Invalid: >=64 returns -1.",
        allowed_evidence_ids=["evidence-1"],
        templates=[
            TemplateSpec(
                template_id="bounded-copy-guard",
                description="Reject input at or above capacity.",
                parameters={"capacity": TemplateParam(min_value=1, max_value=4096)},
            )
        ],
    )


def payload(**over) -> dict:
    base = {
        "schema_version": 1,
        "original_sha256": SHA,
        "contract_sha256": SCOPE,
        "analysis_sha256": SCOPE,
        "route": "route_a",
        "target_entry": "copy_input",
        "evidence_ids": ["evidence-1"],
        "template_id": "bounded-copy-guard",
        "parameters": {"capacity": 64},
        "expected_effects": ["overlong input rejected"],
        "assumptions": ["capacity is 64 bytes"],
        "uncertainties": [],
    }
    base.update(over)
    return base


def test_context_binding_accepts() -> None:
    assert validate_candidate_for_context(payload(), ctx()) is not None


@pytest.mark.parametrize(
    "field,bad,reason",
    [
        ("original_sha256", "c" * 64, "identity_mismatch"),
        ("evidence_ids", ["evidence-2"], "scope_violation"),
        ("target_entry", "copy_name", "scope_violation"),
    ],
)
def test_context_binding_rejects(field, bad, reason) -> None:
    with pytest.raises(CandidateRejected) as exc:
        validate_candidate_for_context(payload(**{field: bad}), ctx())
    assert exc.value.reason_code == reason
```

These three already pass next to `test_context_bound_validation_rejects_unissued_evidence` in my local
`tests/test_ai_boundary_contract.py`; if they fail when you add them,
send me the `reason_code` and I can locate it.

---

## 2. schema v1 fields (final)

The valid payload for `route_a` is exactly 12 fields; `route_b` uses 10 of them (dropping `template_id` / `parameters`) plus 2 more, also 12.

| Field | Type | Route A | Route B | Notes |
|---|---|---|---|---|
| `schema_version` | `1` | required | required | contract version |
| `original_sha256` | 64-hex | required | required | original ELF |
| `contract_sha256` | 64-hex | required | required | reviewed contract |
| `analysis_sha256` | 64-hex | required | required | analysis bundle |
| `route` | `"route_a"` / `"route_b"` | required | required | matches the skeleton |
| `target_entry` | C identifier or `0x…` | required | required | must be in the whitelist |
| `evidence_ids` | string[], 1–16 | required | required | format checked; issuance needs context |
| `template_id` | string? | **required** | must be absent/`null` | must be among the templates provided for this call |
| `parameters` | object<string,int>? | **required** | must be absent/`null` | keys must match exactly, values within range |
| `recovered_function_sha256` | 64-hex? | must be absent/`null` | **required** | must equal the recovered hash in the request |
| `replacement_c` | string?, ≤20,000 | must be absent/`null` | **required** | complete function definition; call whitelist |
| `expected_effects` | string[], 1–32, each ≤512 | required | required | for display; not evidence |
| `assumptions` | string[], 0–32, each ≤512 | optional | optional | for display |
| `uncertainties` | string[], 0–32, each ≤512 | optional | optional | for display |

Top level is `additionalProperties: false`. Keys inside `parameters` are determined by the template declaration; the "extra top-level field" rule does not apply there.

**route values:** only `route_a` / `route_b` appear in JSON; "Route A/B" in documents is just prose.
The database `CHECK` on `attempts.route` has been synced to these two values.

---

## 3. How your 8 checks are satisfied

Local contract tests: `tests/test_ai_boundary_contract.py` (all 64 tests green).

| # | Your check | Implementation site | Local test |
|---|---|---|---|
| 1 | valid payload passes, return value non-None | `validate_candidate` | `test_valid_payload_returns_candidate` |
| 2 | extra field (`requested_permissions`) rejected | `extra="forbid"` | `test_extra_field_is_rejected` |
| 3 | invalid route (`route_z`) rejected | `Literal["route_a","route_b"]` | `test_invalid_route_is_rejected` |
| 4 | malformed hash rejected | `StringConstraints(pattern=...)` + validator | `test_malformed_hash_is_rejected` |
| 5 | instruction-like text rejected (as a whole, not filtered and then accepted) | text scan `_INSTRUCTION_RE` | `test_instruction_like_text_is_rejected` |
| 6 | target outside the contract rejected | whitelist | `test_target_outside_whitelist_is_rejected` |
| 7 | overlong strings rejected | 512 / 32 | `test_overlong_text_is_rejected` |
| 8 | `may_leave_host` three-state | deny by default | `test_data_boundary` |

Wording for check 5: the rejection reason reads `text contains instruction-like or URL content`. It covers
`ignore previous instructions`, `run:`, `rm -rf`, `sudo`, `http(s)://`,
`</untrusted`, `tool_call`, and so on. It is a backstop; the real guarantee is that "a candidate can never change permissions, tools, or scope".

The concrete numbers for check 7 (you asked for them):

```text
Free-text item: 512 characters
expected_effects / assumptions / uncertainties: 32 items each
replacement_c: 20,000 characters (the context of a single request is tightened further to 8,000 by default, configurable up to 20,000)
```

---

## 4. typed provider failure (4.3.4)

Module: `app/services/provider.py`

```python
class FailureReason(str, Enum):
    TIMEOUT = "provider_timeout"
    QUOTA = "provider_insufficient_balance"
    BUDGET = "budget_exceeded"
    EMPTY = "empty_content"
    MALFORMED_JSON = "invalid_json"
    SCHEMA = "schema_invalid"
    RATE_LIMIT = "provider_rate_limited"
    AUTH = "provider_auth_failed"
    NETWORK = "provider_network_error"
    SERVER = "provider_server_error"
    CONTEXT_TOO_LARGE = "context_too_large"
    IDENTITY = "identity_mismatch"
    SCOPE = "scope_violation"
    UNKNOWN = "unknown_provider_failure"

class ProviderFailure(Exception):
    reason: FailureReason
    retryable: bool
    details: dict
```

Mapping of the four failure classes (assert directly when you add tests):

| Your class | Trigger | `FailureReason` |
|---|---|---|
| timeout | request timed out (one bounded retry already done) | `TIMEOUT` |
| quota | HTTP 402 | `QUOTA`; a local budget block is `BUDGET` |
| empty | 200 but `content` is empty | `EMPTY` |
| malformed JSON | content is not JSON | `MALFORMED_JSON`; valid JSON with wrong fields is `SCHEMA` |

Two usage styles, pick one:

```python
# value style (used by the job controller)
result = provider.request_candidate(ctx)
if not result.ok:
    show(result.failure.reason_code, result.failure.message)

# exception style (used by workers / tests)
from app.services.provider import require_candidate, ProviderFailure
try:
    cand = require_candidate(result)
except ProviderFailure as exc:
    stage_outcome = "error" if exc.reason is not FailureReason.SCHEMA else "rejected"
```

Key behavior: **failures never fabricate a candidate**; `require_candidate` returns only when `result.ok`.

---

## 5. Data boundary (4.3.2 / appendix 1)

```python
may_leave_host("public")                                  # True
may_leave_host("synthetic")                               # True
may_leave_host("client")                                  # False
may_leave_host("client", derived=True)                    # False
may_leave_host("client_authorized")                       # False (default)
may_leave_host("client_authorized", authorized=True)      # True (caller has recorded authorization)
may_leave_host("")                                        # False
may_leave_host("unknown")                                 # False
```

`derived` is only for signature compatibility; it never relaxes the client rule. Unknown classifications are always False.

---

## 6. How to activate it on your side

Put the two directories at the repository root (as siblings of `app/`):

```text
app/domain/candidates.py
app/services/provider.py
binaryrepair_ai/            # implementation dependency of the two modules above
```

Then:

```bash
python -m pytest tests/integration -q -p no:cacheprovider -rs
```

Expected: no more skips; all 8 of your checks pass. If something fails, send me the payload and the `reason_code`,
and we locate it by the three classes `schema_invalid` / `scope_violation` / `identity_mismatch`.

My local copy of the same assertions is in `tests/test_ai_boundary_contract.py`, currently `64 passed`.

---

## 7. Six replies for member 4 (ready to paste)

```text
Overall  Signatures: accepted.
4.3.1 validate_candidate(payload) (single positional parameter) / may_leave_host(classification, derived=False)
      (keyword call): accepted, implemented as specified.
4.3.2 v1 top-level fields: Route A 12; Route B adds recovered_function_sha256 + replacement_c,
      14 in total. The route A payload needs no change.
4.3.3 target whitelist: the module default contract (including copy_input, copy_name), plus allowed_targets=None;
      tests pass only the payload and are not required to pass a whitelist.
4.3.4 typed failure: app.services.provider.ProviderFailure(reason: FailureReason);
      timeout/quota/empty content/malformed JSON map to TIMEOUT / QUOTA (or BUDGET) / EMPTY /
      MALFORMED_JSON (wrong structure is SCHEMA).
4.3.5 overlong limits: free text 512 characters per item; expected_effects / assumptions / uncertainties
      32 items each; replacement_c 20,000 characters. Extra fields use pydantic extra="forbid".
Other  route values route_a / route_b (consistent with the skeleton); instruction-like text is rejected as a whole, not filtered and then accepted;
      validate_candidate without context does not check hash provenance/evidence issuance; that is
      supplied by validate_candidate_for_context.
```

## 8. Known limitations (no reply needed, but please put them into the acceptance evidence)

- `validate_candidate(payload)` does not bind a job: a candidate with correct hash formats that does not belong to this job
  can only be rejected by `validate_candidate_for_context`. If the skeleton only tests the former, it covers the structural boundary.
- JSON Schema expresses structure only; Route A/B cross-field rules are handled by Pydantic; that is layering, not an omission
  (the local test `test_json_schema_does_not_encode_route_semantics` records this boundary).
- All provider tests use a fake transport: no real API calls, no key needed, no cost.
- The first real API call needs a key and is a manual step, not part of CI.

---

## 9. Security line (unchanged)

- Deny by default: `may_leave_host` returns `False` when the classification cannot be determined.
- A candidate payload is untrusted data: strings must never become instructions, permissions, or scope changes.
- Validation failure = typed failure / raised exception; never "guess a legal candidate".
- Do not loosen the schema for testing convenience; prefer rejection.
