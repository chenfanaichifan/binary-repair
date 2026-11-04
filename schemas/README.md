# Schema contract (candidate v1)

This layer answers three questions:

1. **What may the model return?** — `candidate.v1.json`
2. **What is the server allowed to send?** — `context.v1.json`
3. **How do the GUI / verification / database stay aligned?** — through the same fields and enums

There is only one source: the Pydantic models in `binaryrepair_ai/schemas.py`. The JSON Schema is
its export; hand-editing `schemas/generated/*.json` is not allowed.

```
schemas.py (Pydantic, the source)
      │  python schemas/generate.py
      ▼
generated/*.json (JSON Schema, for non-Python consumers/docs/CI)
      │
      ├── GUI: field names, types, enums, without importing Python
      ├── verification: structural checks on the candidate
      └── DB: model_calls / candidate field mapping
```

Why "JSON mode is enough" does not hold: JSON only guarantees parseability; identity, route fields,
parameter ranges, and the call allowlist are **semantics** and must be checked by `check_candidate()`.
JSON Schema can express structure but cannot express cross-field rules such as
"Route A must not carry replacement_c" — the test
`test_json_schema_does_not_encode_route_semantics` exists to record that boundary.

---

## 1. Candidate v1 fields

| Field | Type | Required | Description | Semantic validation |
|---|---|---|---|---|
| `schema_version` | `1` (const) | yes | contract version; changing a field requires a version bump | — |
| `original_sha256` | 64-hex | yes | the frozen original ELF | must equal the job's input hash |
| `contract_sha256` | 64-hex | yes | the reviewed contract revision | must equal this run's contract |
| `analysis_sha256` | 64-hex | yes | the binary analysis bundle | must equal the analysis the server sent |
| `route` | `"route_a"` / `"route_b"` | yes | repair route | must equal the requested route |
| `target_entry` | identifier or `0x…` | yes | the function that may be modified | must equal the reviewed target |
| `evidence_ids` | string[], 1–16 | yes | the evidence referenced | must be an id the server has sent |
| `template_id` | string? | required for Route A | template id | must be in the `templates` list |
| `parameters` | object<string,int>? | required for Route A | template parameters | keys must match exactly, values within range |
| `recovered_function_sha256` | 64-hex? | required for Route B | hash of the recovered C | must equal the recovered hash in the request |
| `replacement_c` | string? | required for Route B | complete function definition | length, target function name, forbidden constructs, call allowlist |
| `expected_effects` | string[], 1–32, each ≤512 | yes | claimed effects | shown to humans only, **never used as evidence** |
| `assumptions` | string[], 0–32, each ≤512 | no | conditions relied on | for display |
| `uncertainties` | string[], 0–32, each ≤512 | no | known uncertainties | for display; they do not block verification by themselves |

`additionalProperties: false`. One extra field rejects the whole document — this is the core of the
protection against "quietly widening scope".

The free-text fields (the three lists) have two more rules: each entry ≤ **512 characters**, each list
≤ **32 entries**; if instruction-like text such as "ignore previous instructions / run: / rm -rf / URL"
appears, **the whole candidate is rejected**, not filtered and then accepted. This is a backstop, not a
security boundary — the real boundary is that a candidate can never change permissions, tools, or scope.

Public entry points (the verification skeleton binds to these names):

```python
from app.domain.candidates import validate_candidate, may_leave_host

cand = validate_candidate(payload)       # valid returns CandidateV1; invalid raises CandidateRejected
may_leave_host("public")                 # True
may_leave_host("client", derived=True)   # False (deny by default)
```

## 2. Context v1 fields (server → model)

| Field | Description |
|---|---|
| `route` | the route of this request; the model cannot change it |
| `original_sha256` / `contract_sha256` / `analysis_sha256` | the identity triple, which the model must echo back verbatim |
| `target_entry` / `target_signature` | the only function that may be modified, plus its signature |
| `contract_summary` | excerpt of the reviewed contract; the sole authority on scope |
| `allowed_evidence_ids` | a closed set; the model may only reference ids from it |
| `templates` | Route A templates and parameter ranges (closed set) |
| `recovered_c` / `recovered_function_sha256` | the Route B input function (**untrusted data**) |
| `allowed_calls` | external functions Route B may call; anything else is a scope violation |
| `max_replacement_chars` | upper bound on output length |

## 3. Versioning and change process

v1 is a **closed** contract (`additionalProperties: false`), therefore:

- adding a field = breaking change → a new file `candidate.v2.json`; old code keeps reading v1;
- changing semantics (e.g. the `evidence_ids` limit) = new version;
- changing only descriptions/titles = allowed directly, but regenerate and run the drift test anyway;
- every change must notify both **GUI (member 2)** and **verification (member 4)**, and log one line in `CHANGELOG.md`;
- "quietly loosening it in production" is not allowed: a failed validation is a failure.

Process:

```bash
# 1. edit binaryrepair_ai/schemas.py
# 2. regenerate
python schemas/generate.py
# 3. confirm that nothing in generated/ was hand-edited
git diff --stat schemas/
# 4. run the contract tests (this is also the CI command)
pytest tests/test_schema_contract.py
python schemas/generate.py --check
```

A `--check` failure in CI means someone changed the models without committing the generated output, or
hand-edited the generated output.

## 4. Mapping to the database

| Candidate field | Where it lands |
|---|---|
| `original_sha256` | `jobs.original_sha256` (already written when the job was created) |
| `route` | `attempts.route` |
| `replacement_c` / `template_id` + `parameters` | stored as a file artifact (`artifacts.role='proposal'`), hash into `attempts.candidate_sha256` |
| `expected_effects` / `assumptions` / `uncertainties` | the full candidate JSON is stored as an artifact, for replay |
| model call metadata | `model_calls` (see `db/README.md`) |

**Do not stuff the candidate body into a SQLite row**: large text goes to a file, and the row keeps only
the hash and the relative path (a requirement of technical design §6).

## 5. Examples

- `examples/candidate.routeA.json` — template + parameters
- `examples/candidate.routeB.json` — recovered C + the complete repaired function
- `examples/context.routeB.json` — the context the server sends to the model

These examples are covered by both the JSON Schema and the Pydantic tests, so a schema change makes them
fail together, reminding you to update the examples.
