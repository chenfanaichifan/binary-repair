# M4 — status lock: contract/intake PASS, end-to-end PARTIAL (2026-11-05)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** status lock only. No new verification claim, no merge, no tag, no live
success.

---

## 0. Status

| Layer | Status | Basis |
|---|---|---|
| contract v3 schema | **PASS** | `4c36898` / `7c279a1`; `contracts.py` `cc976f62…fd6a` |
| `fixture_intake` | **PASS** | `1b08ae5`; calls `SecurityContract.from_dict`, enforces exactly 1 valid |
| acceptance / V3 | **NOT IMPLEMENTED** | `acceptance.py` has no no-input handling; last commit `1406f11` |
| **end-to-end** | **PARTIAL** | V3 layer missing |
| CWE121 v2 hash | **PASS — `24bfe568…4e37`** | recomputed |
| Record 118 | **VERIFIED (rebuild evidence package)** — independent record | five gates passed |
| T8.3 | **BLOCKED** | 118 does not relieve it |

---

## 1. What is confirmed

- **contract/intake PASS.** The v3 schema and the intake agree on the
  `input_mode=none` shape, and intake now delegates contract validity to
  `SecurityContract.from_dict`.
- **No regression on CWE121.** The reviewed v2 hash is still
  `24bfe568…4e37`; `input_mode` is absent from the v2 canonical payload.
- **No new acceptance/V3 work.** `app/domain/acceptance.py` has no
  `input_mode`/`no_input` handling; its last relevant commit predates this work.

---

## 2. End-to-end — still PARTIAL

The three checks remain **deferred** until M1 completes acceptance/V3:

| # | Deferred check | Current state |
|---|---|---|
| 1 | rejection fields absent across **contract + intake + V3** | contract PASS, intake PASS, **V3 absent** |
| 2 | sentinel rejected across **contract + intake + V3** | contract PASS, intake PASS, **V3 absent** |
| 3 | V3 exactly **1/1** no-input (1 valid, 0 invalid) | **not implemented** |

The missing layer is behaviour evidence, not schema or intake.

---

## 3. Record 118 is separate — it does not relieve T8.3

- `118 = VERIFIED (rebuild evidence package)` concerns the **T30 rebuild
  evidence**: build, trigger, window, conformance.
- It is an independent record. It does **not** promote V0–V5, does **not**
  produce a candidate, and does **not** satisfy T8.3's second-public-sample
  obligation.
- T8.3 stays **BLOCKED** regardless of 118's status.

---

## 4. CWE121 v2 hash — re-checked

```text
24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37  match=True
```

No change; the v3 work has not disturbed the reviewed v2 contract.

---

## 5. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 6. Evidence

| File | Content |
|---|---|
| `M4-status-lock-evidence-2026-11-05.txt` | git identities, acceptance grep, CWE121 hash |
| `_m1-work/live-bridge/app/domain/contracts.py` | v3 schema |
| `_m1-work/live-bridge/tools/fixture_intake.py` | intake `1b08ae5` |
| `_m1-work/live-bridge/app/domain/acceptance.py` | unchanged, no no-input handling |
