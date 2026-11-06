# M4 — contract v3 schema PASS; end-to-end still PARTIAL (2026-11-05)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** status lock only. No gate promotion, no merge, no tag, no live success.

---

## 0. Status lock

| Layer | Status | Basis |
|---|---|---|
| contract v3 schema | **PASS** | `4c36898` (m5-schema) / `7c279a1` (live-bridge); `contracts.py` `cc976f62…fd6a` in both |
| `fixture_intake` | **IMPLEMENTED (1b08ae5)** — the two prior divergences are fixed | probes below |
| acceptance / V3 | **NOT IMPLEMENTED / pending** | no no-input change in `app/domain/acceptance.py`; no 1/1 V3 evidence |
| **end-to-end** | **PARTIAL / NOT IMPLEMENTED** | the third layer (V3) is still missing |
| CWE121 v2 hash | **PASS — `24bfe568…4e37`** | recomputed on both schema copies |

**End-to-end is not promoted.** The schema and intake now agree; the behaviour
layer does not exist yet.

---

## 1. What changed since the consistency review

| Commit | Change |
|---|---|
| `1b08ae5 feat(intake): accept the CWE416 no-input contract shape (M5 option A)` | intake now imports `SecurityContract`, calls `from_dict`, and enforces exactly one valid case for `none` |
| `7c279a1 feat(m5): add v3 no-input contract mode` | the v3 schema is now present in `live-bridge` too; `contracts.py` is byte-identical to `m5-schema` (`cc976f62…fd6a`) |

Both divergences recorded in
`M4-m5-v3-vs-m1-intake-consistency-2026-11-05.md` are **resolved in intake**.

---

## 2. Probe re-run against `1b08ae5`

| Probe | Before | After |
|---|---|---|
| `valid_count=2` for `input_mode=none` | `[]` (accepted) | **`no_input_valid_case_count_mismatch`** — exactly 1 enforced |
| contract missing `dest_capacity_bytes`, sums regenerated | `[]` (accepted) | **`contract_schema_invalid`** — schema now authoritative |

Intake and schema are now consistent on these two points. Intake's own tests
pass with the new cases.

---

## 3. Why end-to-end is still PARTIAL

- `app/domain/acceptance.py` has no no-input change; its last relevant commits
  predate this work.
- No V3 evidence exists for a 1/1 no-input case (one execution, expected exit
  code, stdout bytes, stderr bytes).
- Intake validates layout; it does not produce behaviour evidence.

The three end-to-end checks therefore remain **deferred** until M1 completes
acceptance/V3:

| # | Deferred check | Current state |
|---|---|---|
| 1 | rejection fields absent through contract **and** intake **and** V3 | schema PASS, intake PASS, V3 absent |
| 2 | sentinel rejected through contract **and** intake **and** V3 | schema PASS, intake PASS, V3 absent |
| 3 | V3 is exactly **1/1** no-input (1 valid, 0 invalid) | not implemented |

---

## 4. CWE121 v2 hash re-check

Recomputed on both schema copies:

```text
CWE121 v2 hash: 24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37
match          : True
input_mode in payload: False
```

The CWE121 `contract.json` file hash is still
`15f6b492608e8c137f2612058bf43b90173284aec86d8c51b25d09903d0ad8df`. The v3
addition has not disturbed the reviewed v2 hash.

---

## 5. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |
| Record 118 | **VERIFIED (rebuild evidence package)** — separate record |

---

## 6. Evidence

| File | Content |
|---|---|
| `M4-v3-status-evidence-2026-11-05.txt` | git identity, intake grep, probe re-run, CWE121 hash |
| `probe_intake_consistency.py` | the two probes |
| `_m1-work/live-bridge/tools/fixture_intake.py` | intake `1b08ae5` |
| `_m1-work/m5-schema/app/domain/contracts.py` | v3 schema |
