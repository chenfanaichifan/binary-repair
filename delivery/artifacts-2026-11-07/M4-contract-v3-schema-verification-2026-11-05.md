# M4 — contract v3 schema verification (2026-11-05)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** **contract v3 schema only.** `fixture_intake` and V3 are out of scope
and are recorded as PARTIAL / NOT IMPLEMENTED. No gate promotion, no merge, no
tag, no live success.

---

## 0. Verdict at a glance

| Item | Result |
|---|---|
| v3 schema exists | **YES** — `4c36898 feat(m5): add v3 no-input contract mode` |
| rejection fields absent (`input_mode=none`) | **PASS (schema level)** |
| `invalid` cannot be a sentinel | **PASS (schema level)** — all five sentinel forms rejected |
| v3 `argv` still requires rejection fields | **PASS (schema level)** |
| v2 rejects `input_mode` | **PASS (schema level)** |
| CWE121 v2 hash unchanged | **PASS — `24bfe568…4e37`** |
| V3 only 1/1 no-input | **NOT VERIFIED** — intake/V3 PARTIAL / NOT IMPLEMENTED |
| The three end-to-end checks | **DEFERRED** until M1 completes intake/acceptance |

Schema-level PASS is not an end-to-end PASS. Nothing is promoted.

---

## 1. What was verified, and what was not

**Verified now (schema only):**

- `SecurityContract` v3 accepts `input_mode: "none"` and structurally omits the
  rejection fields.
- v3 `none` rejects every sentinel form of rejection evidence.
- v3 `argv` still requires the five rejection fields.
- v2 rejects `input_mode`, and the CWE121 v2 hash is unchanged.

**Not verified now (per Lead ruling):**

- `tools/fixture_intake.py` — **PARTIAL / NOT IMPLEMENTED**.
- V3 behaviour evidence (1 valid + 0 invalid) — **NOT IMPLEMENTED**.
- The three end-to-end checks: (1) rejection fields absent end-to-end,
  (2) sentinel rejected end-to-end, (3) V3 only 1/1 no-input.

These wait for M1 to finish intake/acceptance.

---

## 2. Implementation identity

| Field | Value |
|---|---|
| commit | `4c36898 feat(m5): add v3 no-input contract mode` |
| changed files | `app/domain/contracts.py`, `tests/test_contracts.py` — **2 files**, +166/−43 |
| `contracts.py` SHA-256 | `cc976f62cc79c1f98188d7cdec9bdb40abd40797e1d1c5156e7443b76ff5fd6a` |
| schema constants | `CONTRACT_SCHEMA_VERSION = 2`, `CONTRACT_SCHEMA_VERSION_NO_INPUT = 3`, `INPUT_MODES = ("argv", "stdin", "none")` |
| required-key sets | `_REQUIRED_KEYS_V3_ARGV = _REQUIRED_KEYS + ("input_mode",)`; `_REQUIRED_KEYS_V3_NONE = _BASE_KEYS + ("input_mode",)` |
| tests | `tests/test_contracts.py` → **35 passed** |

The change is confined to the schema and its tests; no intake or acceptance code
was touched in this commit.

---

## 3. Schema-level checks

### 3.1 Rejection fields must be absent — **PASS (schema level)**

A minimal v3 `none` contract serialises to:

```text
keys: allowed_calls, authorized_edits, capacity_includes_terminator,
      dest_capacity_bytes, environment_assumptions, forbidden_behavior,
      input_mode, required_obligations, schema_version, target_entry,
      target_signature, valid_behavior, valid_domain
rejection-ish keys present: []
input_mode: none
round-trip hash stable: True
```

- `to_dict()` omits `invalid_input_response`, `max_valid_input_bytes`,
  `invalid_exit_code`, `invalid_stdout`, `invalid_stderr`.
- `from_dict()` uses `_REQUIRED_KEYS_V3_NONE`, so **any** of those keys is
  `unknown contract fields`, **even when the value is `null`**:

```text
null invalid_input_response: rejected unknown contract fields: ['invalid_input_response']
```

Absence is therefore strict, not "optional with `None`".

### 3.2 `invalid` cannot be a sentinel — **PASS (schema level)**

All five sentinel forms are rejected by `__post_init__`:

```text
invalid_input_response=''  rejected  sentinel values are not allowed
invalid_exit_code=0        rejected  sentinel values are not allowed
invalid_stdout=''          rejected  sentinel values are not allowed
invalid_stderr=''          rejected  sentinel values are not allowed
max_valid_input_bytes=0    rejected  sentinel values are not allowed
```

The guard is `any(getattr(self, field) is not None for field in _INVALID_FIELDS)`,
so any non-`None` value — including empty string and zero — is refused. There is
no textual "not applicable" back door.

### 3.3 v3 `argv` and v2 boundaries — **PASS (schema level)**

```text
v3 argv missing rejection fields:
  rejected missing contract fields:
  ['invalid_exit_code','invalid_input_response','invalid_stderr','invalid_stdout','max_valid_input_bytes']

v2 + input_mode:
  rejected unknown contract fields: ['input_mode']
```

- v3 `argv` keeps the five-field requirement; `stdin` shares the same branch
  (`mode != "none"`) by code inspection, not by a separate probe.
- v2 is preserved as the historical argv contract; `input_mode` is rejected.
- The v3 `input_mode` default is `"argv"`, so a v3 contract constructed without
  it does not silently become `none`.

---

## 4. CWE121 v2 hash — **PASS**

Recomputed with the v3-capable code:

```text
CWE121 v2 hash: 24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37
expected      : 24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37
match         : True
input_mode in to_dict: False
```

The CWE121 `contract.json` file hash is unchanged at
`15f6b492608e8c137f2612058bf43b90173284aec86d8c51b25d09903d0ad8df`, and the
canonical payload of a v2 contract does not gain `input_mode`. The v3 addition
does not disturb the reviewed v2 hash.

---

## 5. Observations (not failures)

1. **No explicit `input_rejection` member.** M1 §4.1 sketched
   `input_mode` + `input_rejection: null`. The implementation represents absence
   by omitting the keys instead. This satisfies "rejection fields must be
   absent", but it is not the tagged-union form; a future reader sees no positive
   "no rejection" marker.
2. **`_BASE_KEYS` duplicates `required_obligations`** (it appears in
   `_LIST_FIELDS` and is appended again). Harmless because the required-key
   checks use sets, but it is a code smell worth cleaning.
3. **v3 `none` still requires input-buffer fields.**
   `dest_capacity_bytes` and `capacity_includes_terminator` remain required
   because they sit in `_BASE_KEYS`. A no-input case must still declare a
   destination capacity it does not use. Not a semantic failure, but a modelling
   oddity.
4. **The schema cannot enforce V3 1/1.** Case-count rules live in intake and
   acceptance, which are out of scope here.
5. **`live-bridge/tools/fixture_intake.py` references `input_mode` 24 times** —
   this is the partial intake work the Lead flagged. M4 did **not** verify it in
   this round.

---

## 6. Deferred — the three end-to-end checks

Once M1 completes intake/acceptance, M4 will verify, end-to-end:

| # | Check | Why it is deferred |
|---|---|---|
| 1 | rejection fields absent through contract **and** intake | intake is PARTIAL |
| 2 | sentinel rejected through contract **and** intake | intake is PARTIAL |
| 3 | V3 is exactly 1/1 no-input (1 valid, 0 invalid) | V3 not implemented |

Schema-level results for 1 and 2 are already PASS (§3); item 3 is not a schema
property.

---

## 7. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work**; no verdict here |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted**; unchanged by this record |
| Record 118 | **REPORTED, NOT VERIFIED** until its five gates are run separately |

---

## 8. Evidence

| File | Content |
|---|---|
| `M4-contract-v3-evidence-2026-11-05.txt` | commands and outputs for §§2–4 |
| `probe_v3_schema.py` | schema-only probe (A–F) |
| `_m1-work/m5-schema/app/domain/contracts.py` | the v3 implementation |
| `_m1-work/m5-schema/tests/test_contracts.py` | 35 schema tests |

```text
Result: contract v3 schema PASS for the two schema-expressible semantics.
CWE121 v2 hash PASS (24bfe568...4e37).
fixture_intake/V3 PARTIAL / NOT IMPLEMENTED; the three end-to-end checks are deferred.
No merge, no tag, no live success.
```
