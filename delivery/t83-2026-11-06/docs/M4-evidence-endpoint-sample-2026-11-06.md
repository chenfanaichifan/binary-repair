# M4 — evidence endpoint sample cleared for M2 (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** shape check of the actual `/api/attempts/{id}/evidence` response. No
gate promotion, no merge, no tag.

---

## 0. Verdict

The actual response passes all four requested checks; it is **cleared as an M2
sample**.

| Check | Result |
|---|---|
| top-level `gates` is an **array** | **PASS** — `type=list` |
| V3 row has `gate == "V3"` | **PASS** — sequence `V0,V1,V2,V3,V4,V5` |
| `invalid.total == 0` | **PASS** |
| `invalid.passed == 0` | **PASS** |
| `invalid_applicable == false` | **PASS** |
| 124 | **`inconclusive` / `required_check_not_run` / `symbolic`** |
| 118 | **VERIFIED** — independent of T8.3 |

---

## 1. Source

Committed as:

```text
fdc083da747ff305457bb7f8096ad35431ba4e08
feat(api): expose ordered gates and V3 valid/invalid summary
git status --short: (empty)
```

Endpoint: `GET /api/attempts/{attempt_id}/evidence`. The probe seeds a V3
artifact with **one valid case and no invalid case**, then reads the response
over `TestClient` (HTTP 200). The nine endpoint tests pass.

This is a **shape sample**, not a repair result: no candidate was executed, and
the seed is synthetic. It is not the 124 attempt.

---

## 2. Actual response (excerpt)

```json
{
  "gates": [
    {"gate": "V0", "...": "..."},
    {"gate": "V1", "...": "..."},
    {"gate": "V2", "...": "..."},
    {
      "gate": "V3",
      "kind": "behaviour",
      "scope": "replay",
      "required": true,
      "result": "passed",
      "detail": "input_mode=none valid 1/1 invalid not_applicable",
      "evidence_artifact_id": "art-v3-probe"
    },
    {"gate": "V4", "...": "..."},
    {"gate": "V5", "...": "..."}
  ],
  "v3": {
    "gate": "V3",
    "kind": "behaviour",
    "result": "passed",
    "input_mode": "none",
    "valid": {"passed": 1, "total": 1},
    "invalid": {"passed": 0, "total": 0},
    "invalid_applicable": false
  }
}
```

Measured criteria:

```text
gates_is_array: True
v3_row_gate_is_V3: True
invalid_total_zero: True
invalid_passed_zero: True
invalid_applicable_false: True
```

---

## 3. What M2 may use it for

- The top-level `gates` is a **list**, ordered `V0..V5`; render it as an array,
  not a map.
- The V3 row is identified by `gate == "V3"`; `kind` stays `"behaviour"`.
- For `input_mode="none"`, `invalid_applicable=false` means the invalid column
  is **N/A**, not “0/0 passed”. Render `invalid` as `N/A` and show `valid 1/1`.
- Do not present this sample as a live 124 result. 124's V4 is still `not_run`,
  and its own gate index is V2/V4 `not_run`.

---

## 4. 124 — unchanged

```text
V0 passed, V1 passed, V2 not_run, V3 passed, V4 not_run, V5 passed
outcome = inconclusive
reason  = required_check_not_run
failing = symbolic
```

The current-code ingest view (V2 5/5) is also
`inconclusive / required_check_not_run / symbolic`. The endpoint sample does not
change any gate.

---

## 5. Record 118 and T8.3

`118 = VERIFIED (rebuild evidence package)` remains independent: it does not
promote V0–V5, does not produce a candidate, and does not relieve T8.3.
T8.3 stays **BLOCKED**.

---

## 6. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 7. Evidence

| File | Content |
|---|---|
| `M4-evidence-endpoint-sample-evidence-2026-11-06.txt` | commit, clean status, actual endpoint response, criteria, nine tests, 124 gate index |
| `probe_evidence_gates.py` | seeds the V3 artifact and prints the actual response |
| `_m1-work/live-bridge/app/controller_api.py` | the endpoint implementation |
