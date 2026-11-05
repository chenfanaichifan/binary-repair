# T7.3 — screening-test comparison evidence (2026-11-05)

Side-by-side behaviour comparison across routes, built from **measured** guest
observations rather than from route summaries.

## 1. Result

| Route | Candidate sha256 | V3 | Valid behaviour preserved | Invalid cases repaired | Still failing |
|---|---|---|---:|---:|---|
| **A** | `c4a15921…aa82` | **`passed` 6/6** | yes | both | — |
| **B_roundtrip** | `decdcdb8…954b` | **`failed` 4/6** | yes | none | both |

Per case (exit codes as executed by the guest):

| Case | Kind | Contract | original | A | B_roundtrip | changed by |
|---|---|---:|---:|---:|---:|---|
| `valid-empty` | valid | 0 | 0 | 0 | 0 | — |
| `valid-smallest` | valid | 0 | 0 | 0 | 0 | — |
| `valid-typical` | valid | 0 | 0 | 0 | 0 | — |
| `valid-maximum` | valid | 0 | 0 | 0 | 0 | — |
| `invalid-first` | invalid | 1 | **0** | **1** | **0** | A |
| `invalid-longer` | invalid | 1 | **139** | **1** | **139** | A |

## 2. Why this matters: round-trip consistency is not a repair

The `B_roundtrip` binary is the Gate 4 unchanged round trip
(`decdcdb8…954b`). It reproduces the original's behaviour **exactly** — same
exit codes, same outputs, valid cases byte-identical.

That is precisely what a round trip is supposed to do, and it is precisely what
Nick's audit (item 3) warned must not be read as a repair: the round trip
proves the binary still behaves like the original, i.e. **the defect is still
there**. The comparison shows this without interpretation — `changed_by` is
empty for the round trip on every case, including the two that matter.

A comparison that ranked routes by diff size or by pass count alone could
present the round trip's "4/6 preserved" as reassuring. It is not.

## 3. How it was produced

1. Guest observer `workers/broker/guest_behaviour.py` executed each binary
   against the frozen manifests and recorded raw `(rc, stdout, stderr)`.
   Two separate runs, two fresh scratch dirs.
2. Observations copied to the host; hashes verified on both ends (values in
   `comparison.json` and the three `*-observations.json` files).
3. Host `workers.broker.comparison.compare` judged each route with the **same**
   frozen oracle (`tests/v3_oracle.py`) and assembled the per-case rows.

Nothing in the comparison module executes, and it produces no ranking —
`ranking` is `null` by construction, with the note attached to the record.

## 4. Rules the module enforces

- A route with no observations is `not_run`, never "behaves like the original".
- `changed_by` is decided by the **observed exit code** differing from the
  original's, not by a result label; a route that fails the same way moved
  nothing.
- `still_failing_invalid_cases` is reported even when the route's diff is
  smaller.
- If the original does not fail the invalid cases, the record says the
  vulnerability is not demonstrated, because a "repair" would be meaningless.

12 unit tests cover exactly these properties
(`tests/unit/test_broker_comparison.py`).

## 5. Files

| File | Content |
|---|---|
| `comparison.json` | The full `ComparisonRecord` (cases, summaries, limitations, `ranking: null`) |
| `original-observations.json` | Raw guest observations, `aa428157…8393` |
| `route-a-observations.json` | Raw guest observations, `c4a15921…aa82` |
| `route-b-roundtrip-observations.json` | Raw guest observations, `decdcdb8…954b` |
| `SHA256SUMS` | Hashes of the above |

Re-derive the comparison from the observation files alone: the command is in
`docs/handoffs/96-route-a-behaviour-verification.md` §4, substituting the three
payloads.

## 6. Limits

- **Six frozen cases**, not the whole input space; no symbolic (V4) check.
- `B_roundtrip` is the *unchanged* round trip on purpose. It is a control, not a
  Route B repair candidate — no Route B repair candidate exists in this session.
- The Route A candidate is the documented `c4a159…aa82`; its provenance and the
  public-fixture limitation (NIST Juliet, recognisable from training data) apply
  as stated in record 96 §6.
