# M4 — `input_mode=none` contract semantics verification (2026-11-05)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** contract semantics only. No candidate, no gate promotion, no merge,
no tag, no live success.

---

## 0. Verdict at a glance

| Requested check | M4 result |
|---|---|
| `input_mode=none` implemented | **NO — spec only, code absent** |
| rejection fields must be absent | **Spec correct; implementation still requires them → NOT SATISFIED** |
| `invalid` cannot be a sentinel | **Spec correct; implementation still accepts sentinels → NOT SATISFIED** |
| V3 only 1/1 no-input (1 valid + 0 invalid) | **Spec correct; intake still requires 4 + 2 → NOT SATISFIED** |
| CWE121 default argv not broken | **INTACT today; design constraint recorded** |
| no-input V0–V5 | **NOT VERIFIED / inconclusive; V4 `not_run` → inconclusive confirmed** |

**Bottom line:** the semantics are **specified and coherent**, but they are
**not implemented**. M4 cannot certify behaviour that does not exist. Nothing is
promoted.

---

## 1. The specified semantics

Source: `M1-T30-acceptance-and-AB-2026-11-05/106-…md` §4.1 (Option A).

For `input_mode = "none"`:

1. the contract carries `input_mode: "none"` and `input_rejection: null`;
   **no `invalid_*` keys**;
2. `valid_domain` is "no program input"; the valid set is **exactly one case**
   (no argv beyond `argv[0]`, no stdin);
3. the invalid set is **not applicable** — not "empty with invented cases";
   no `invalid_*` behaviour may be written;
4. V3 for a no-input case is **1 valid + 0 invalid = 1/1**, never 4 + 2.

M1's own probe already showed the current v2 loader cannot express this:
`contract-probe.txt` records `input_mode` rejected, omitted rejection fields
rejected, and sentinel-filled values loading. M4 reproduced all three
independently (§3).

---

## 2. Implementation status: absent

| Evidence | Result |
|---|---|
| `grep -rn 'input_mode' app/ tools/` in `_m1-work/canonical` | **no match** |
| `git log --all -S 'input_mode'` | docs commits only (`27cc77f`, `6e99442`, `f115ee9`, `502ef41`) |
| `status.json` | `ab_decision.status = "OPEN"`, `chosen = null`; `cwe416_contract.status = "ABSENT_UNLOADABLE"` |
| `app/domain/contracts.py` | v2 `_REQUIRED_KEYS` still lists `invalid_input_response`, `invalid_exit_code`, `invalid_stdout`, `invalid_stderr`, `max_valid_input_bytes`; **no** `input_mode`, **no** `input_rejection` |
| `tools/fixture_intake.py` | `REQUIRED_FILES` includes `tests/invalid.json`; `MIN_VALID_CASES = 4`; `MIN_INVALID_CASES = 2`; `defect.json#trigger_case` must be an invalid case |

The three `contracts.py` copies (canonical, live-bridge, binary-repair) are
byte-identical: `ba35c57b3712f3b442a9d10aa7a69241715d6be3b17f3cad31cb45afec74fe06`.

So the A/B decision is still **open** and no implementation exists on any
branch. Any claim that `input_mode=none` “works” today would be unsupported.

---

## 3. Requirement-by-requirement against the current code

### R1 — rejection fields must be absent → **NOT SATISFIED**

A no-input body omitting the four `invalid_*` keys:

```text
ValueError: missing contract fields:
['invalid_exit_code', 'invalid_input_response', 'invalid_stderr', 'invalid_stdout']
```

The only way to load a no-input contract today is to **put the rejection fields
back**, which is exactly what the semantics forbid.

### R2 — `invalid` cannot be a sentinel → **NOT SATISFIED**

A body with sentinel values loads:

```text
LOADED hash=568c43aa6ea924a89c982aa2719ce13f3a3c0b382031c46e1c05a843ead4ebd5
invalid_input_response='not applicable: the program takes no input'
invalid_exit_code=0 invalid_stdout='' invalid_stderr=''
```

`invalid_input_response` is validated only as non-empty printable ASCII;
`invalid_stdout`/`invalid_stderr` accept empty strings. There is **no sentinel
detection** anywhere in `app/` or `tools/`. The forbidden path is open: a
sentinel-filled body would bind invented rejection semantics into the contract
hash.

### R3 — V3 only 1/1 no-input → **NOT SATISFIED**

A no-input fixture (1 valid, 0 invalid) cannot pass intake:

- `MIN_VALID_CASES = 4` → `too_few_valid`;
- `MIN_INVALID_CASES = 2` → `too_few_invalid`;
- `tests/invalid.json` is a **required file**;
- `defect.json#trigger_case` must name an **invalid** case (`defect_trigger_unknown`
  otherwise).

So V3 cannot be represented as 1/1. The intake model is still 4 + 2.

---

## 4. CWE121 default argv — intact today

| Check | Result |
|---|---|
| `tests/valid.json` argv | `["./original", ""]`, `["./original", "A"]`, `["./original", "AAAAAAAAAA"]`, `["./original", 49×"A"]` |
| `tests/valid.json` hash | `17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76` — **identical** in canonical and live-bridge |
| `contract.json` hash | `15f6b492608e8c137f2612058bf43b90173284aec86d8c51b25d09903d0ad8df` — **identical** in both |
| contract load | **OK**, canonical `sha256 = 24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37` |
| contract / intake / fixture-contract tests | **52 passed** |
| status-honesty / attempt-writer tests | **8 passed** |

CWE121's argv cases are unchanged because no code changed. **The regression is
not yet exercised**, because nothing was implemented.

**Design constraint for any implementation.** `input_mode` must **not** default
to `"none"`. If it is optional with a `"none"` default, every existing v2
contract — including CWE121 — would be silently reclassified as input-bearing
or no-input incorrectly, and its argv cases would stop being applied. The safe
forms are:

- require `input_mode` (schema revision), and migrate/re-review every v2
  contract; or
- default to an explicit input-bearing mode (e.g. `"argv"`) and treat only
  `"none"` as no-input.

Also note: adding the discriminator to `canonical_payload` changes **every v2
contract hash**, so CWE121's reviewed hash must be re-reviewed (M1 §4.1).

---

## 5. No-input V0–V5 — inconclusive, never success

With no contract and no candidate, all six gates are `not_run`.

| Gate | Status | Basis |
|---|---|---|
| V0 identity | `not_run` | no candidate |
| V1 structure | `not_run` | no candidate |
| V2 interface | `not_run` | no contract |
| V3 behaviour | `not_run` | no candidate; 1/1 no-input cannot be expressed |
| V4 symbolic | `not_run` | no symbolic run |
| V5 reproducibility | `not_run` | no candidate |

`app/services/orchestration.py` declares all six gates **required**; missing
results default to `not_run`. `decide_attempt_outcome` maps a required
`NOT_RUN` to:

```text
outcome = inconclusive
reason  = required_check_not_run
```

Measured directly:

```text
all not_run        -> inconclusive / required_check_not_run / failing=identity
V4 not_run only    -> inconclusive / required_check_not_run / failing=symbolic
all passed         -> success_within_scope
```

So **V4 `not_run` can only produce `inconclusive`**, exactly as required. A
no-input case cannot reach `success_within_scope` while V4 is `not_run`, and
cannot produce a 1/1 V3 until `input_mode` is implemented.

---

## 6. What would have to exist before M4 can pass this

1. **Schema**: an explicit `input_mode` discriminator, with a conditional
   `input_rejection` block; when `input_mode = "none"`, the four `invalid_*`
   keys are **forbidden**, not merely optional.
2. **Sentinel rejection**: no `"not applicable"` / empty-string placeholder may
   be accepted as rejection evidence; absence must be represented structurally
   (`input_rejection: null`), not textually.
3. **Intake/V3**: mode-aware minimums — `none` → 1 valid, 0 invalid;
   input-bearing → 4 + 2; `tests/invalid.json` optional or absent for `none`;
   `defect.json#trigger_case` semantics updated.
4. **CWE121 regression**: default remains input-bearing; v2 hashes re-reviewed;
   the four argv cases still execute.
5. **Tests**: new mode cases, with the existing 4 + 2 assertions retained for
   input-bearing modes.

Until then the three semantics are **NOT SATISFIED**, no-input V0–V5 are
**inconclusive**, and nothing is promoted.

---

## 7. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work**; no verdict here |
| Merge / tag / live success | **none** |
| Record 118 | **REPORTED, NOT VERIFIED** — the evidence package has now arrived at `M1-T30-118-evidence-2026-11-05/`, but the five-gate check is a separate task and is not performed or claimed here |
| T8.3 | **BLOCKED** |

---

## 8. Evidence

| File | Content |
|---|---|
| `M4-input-mode-none-evidence-2026-11-05.txt` | commands and outputs for §§2–5 |
| `probe_input_mode.py` | independent A/B/C contract probe |
| `probe_decide.py` | V4 `not_run` → `inconclusive` demonstration |
| `M1-T30-acceptance-and-AB-2026-11-05/106-…md` | the specified semantics |
| `contract-probe.txt` | M1's original probe, reproduced by M4 |

```text
Result: input_mode=none is specified but not implemented.
R1 rejection-absent: NOT SATISFIED. R2 no-sentinel: NOT SATISFIED. R3 V3 1/1: NOT SATISFIED.
CWE121 argv intact today; must not default to "none".
No-input V0–V5 = inconclusive; V4 not_run -> inconclusive.
No merge, no tag, no live success.
```
