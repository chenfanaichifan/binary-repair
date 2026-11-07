# M4 — M5 v3 schema vs M1 fixture_intake consistency (2026-11-05)

> **Update 2026-11-05 22:35 — superseded in part.** Intake commit
> `1b08ae5 feat(intake): accept the CWE416 no-input contract shape` resolves the
> two divergences recorded below: it now calls `SecurityContract.from_dict` and
> enforces exactly one valid case for `input_mode=none`. The analysis below is
> retained as the pre-fix record; the current status is in
> `M4-v3-end-to-end-status-2026-11-05.md`.

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** consistency review only. This record does **not** accept the intake or
V3; it records where the two implementations agree and where they diverge.

---

## 0. Verdict

**Partially consistent.** The mode/rejection vocabulary agrees, but there are two
concrete divergences:

| # | Divergence | Effect |
|---|---|---|
| 1 | Intake does not validate against the M5 v3 schema — it requires only 4 contract keys | a contract missing 8 base fields passes intake, then fails `SecurityContract.from_dict` |
| 2 | Intake allows **more than one** valid case for `input_mode=none` | the required **1/1** shape is not enforced; only 0 is rejected |

V3 behaviour evidence remains pending.

---

## 1. Objects compared

| Layer | Path | Identity |
|---|---|---|
| M5 v3 schema | `_m1-work/m5-schema/app/domain/contracts.py` | commit `4c36898`, SHA-256 `cc976f62…fd6a` |
| M1 intake | `_m1-work/live-bridge/tools/fixture_intake.py` | branch `m1/t30-acceptance-ab-2026-11-05`, HEAD `4c73f87` |

---

## 2. Where they agree

| Aspect | M5 v3 schema | M1 intake | Verdict |
|---|---|---|---|
| input modes | `("argv","stdin","none")` | `CONTRACT_INPUT_MODES = ("argv","stdin","none")` | **consistent** |
| no-input omitted fields | `_INVALID_FIELDS` = `invalid_input_response`, `max_valid_input_bytes`, `invalid_exit_code`, `invalid_stdout`, `invalid_stderr` | `NO_INPUT_OMIT_FIELDS` = `invalid_input_response`, `invalid_exit_code`, `invalid_stdout`, `invalid_stderr` + `max_valid_input_bytes` | **consistent** (same five) |
| v2 + `input_mode` | `unknown contract fields: ['input_mode']` | `contract_input_mode_not_allowed_v2` | **consistent** |
| v3 none with a rejection field present | `sentinel values are not allowed` | `no_input_invalid_fields_present` | **consistent** (both reject presence) |
| invalid cases for none | not a schema concern | `tests/invalid.json` optional; **0** cases if present | **consistent** with 0-invalid |
| `trigger_case` for none | not a schema field | must be absent or null (`no_input_trigger_case_present`) | **consistent** |
| v3 `argv`/`stdin` | requires the five rejection fields | keeps the 4 + 2 matrix | **consistent** |

The core vocabulary is aligned. This is not two incompatible designs.

---

## 3. Divergence 1 — intake does not use the schema validator

M1's intake performs a **shallow** contract check:

```python
_require_keys(data, ("schema_version", "required_obligations",
                     "forbidden_behavior", "valid_domain"), "contract.json", findings)
```

There is no `SecurityContract` import and no `from_dict` call in
`tools/fixture_intake.py`. The M5 schema requires a much larger key set.

**Measured.** Take a valid no-input contract, delete `dest_capacity_bytes`,
regenerate `tests/SHA256SUMS`, and run intake:

```text
intake findings: []
```

The same contract through the M5 schema:

```text
ValueError: missing contract fields:
['allowed_calls','authorized_edits','capacity_includes_terminator',
 'dest_capacity_bytes','environment_assumptions','target_entry',
 'target_signature','valid_behavior']
```

So a contract can be **accepted by intake and rejected by the schema**. Until
intake calls `SecurityContract.from_dict` (or mirrors its required-key sets), the
two layers can disagree about whether a contract is well-formed.

---

## 4. Divergence 2 — intake allows more than one valid case for `none`

The no-input branch checks only that the valid list is non-empty:

```python
if not valid_ids:
    findings.append(Finding("no_input_valid_case_missing", ...))
```

**Measured.** `valid_count=2` for `input_mode=none`:

```text
intake findings: []
```

The required shape is **1 valid + 0 invalid = 1/1**. Intake rejects 0 valid and
rejects any invalid, but it does not reject 2 or more valid. The exact-1
constraint is therefore not enforced.

---

## 5. V3 — still pending

- The intake validates fixture **layout**; it does not produce V3 behaviour
  evidence.
- The 1/1 no-input V3 path (one execution, no invalid cases, exact bytes)
  remains unimplemented.
- This is the part the Lead flagged as “intake/V3 仍待”.

The intake's own tests pass (`36 passed`), but that only exercises the implemented
subset, not V3.

---

## 6. What “consistent” would require

1. Intake calls the M5 schema validator (or imports its required-key sets), so a
   contract cannot pass intake and fail `from_dict`.
2. Intake enforces **exactly one** valid case and **zero** invalid cases for
   `input_mode=none`.
3. V3 records the single no-input execution as 1/1, with the expected exit code,
   stdout bytes and stderr bytes, and does not present it as 4 + 2.

---

## 7. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |
| 118 | **VERIFIED (rebuild evidence package)** — separate record |

---

## 8. Evidence

| File | Content |
|---|---|
| `M4-118-and-schema-consistency-evidence-2026-11-05.txt` | manifest checks, conformance comparison, canonical blob checks, intake probe |
| `probe_intake_consistency.py` | `valid_count=2` and missing-field probes |
| `contract-missing-cap.json` | the contract that passes intake but fails the schema |
| `_m1-work/m5-schema/app/domain/contracts.py` | v3 schema |
| `_m1-work/live-bridge/tools/fixture_intake.py` | M1 intake |
