# Obligation evidence field contract (M1, 2026-11-05)

Scope: `GET /api/attempts/{id}/evidence` and the per-route block of
`GET /api/jobs/{id}` (snapshot). Both are rendered from the same stored rows and
now share one shape.

Evidence honesty is unchanged: the controller only renders rows the worker
persisted. An attempt with no rows returns `evidence: "not_persisted"` and six
empty groups; it never invents a `passed` row.

## Top level

```json
{
  "attempt_id": "…",
  "run_id": "…",
  "route": "route_a",
  "sequence": 1,
  "outcome": null,
  "reason": null,
  "failing_obligation": null,
  "detail": null,
  "evidence": "persisted",
  "summary": { … },
  "obligations": { "A": [ … ], "B": [ … ] }
}
```

`obligations` stays keyed by route for older consumers
(`scripts/demo_e2e.py`); only the attempt's own route carries rows.

## `summary`

```json
{
  "total": 6,
  "required_total": 6,
  "by_result": {"passed": 1, "failed": 0, "not_run": 5, "unknown": 0, "timed_out": 0},
  "gate_ids": ["V0", "V1", "V2", "V3", "V4", "V5"],
  "invalid": {"total": 0, "items": []}
}
```

* Every key is always present. `by_result` always carries all five
  `CheckResult` values, including zeros.
* `invalid` is always an object with `total` and `items`. When nothing is wrong
  it is exactly `{"total": 0, "items": []}` — never `null`, never omitted.
  A row lands there only when its `kind` is not one of V0–V5 or its `result` is
  not a `CheckResult` value; the raw values are echoed in `items`, never coerced.
* `gate_ids` lists the required gate rows that were persisted, in numeric order.

## `obligations[A][]`

```json
{
  "id": "V3",
  "kind": "behaviour",
  "scope": "replay",
  "required": true,
  "gate": true,
  "result": "not_run",
  "evidence_artifact_id": null,
  "detail": "V3 behaviour: not_run"
}
```

| field | meaning |
|---|---|
| `id` | gate number, `V0`–`V5`; `null` when the kind is not a gate |
| `kind` | stored obligation kind (`identity`, `structure`, …) |
| `scope` | layer the check observes, from `app/domain/scopes.py` |
| `required` | the stored `required` bit |
| `gate` | `id != null and required` — the row the acceptance decision treats as a gate |
| `result` | stored `CheckResult` value |
| `evidence_artifact_id` | artifact backing a `passed` row; `null` otherwise |
| `detail` | stored detail text |

Rows are ordered `V0`…`V5`; rows without a gate id come last. This is display
order only (`_gate_order`); the acceptance decision is untouched.

## V3 is a gate row

`app/services/orchestration.py` defines:

```python
GATES = (("V0","identity",True), ("V1","structure",True), ("V2","interface",True),
         ("V3","behaviour",True), ("V4","symbolic",True), ("V5","reproducibility",True))
```

So a persisted `V3` row is `required: true`, `gate: true`, `scope: "replay"`.
`round_trip` and `repaired_behaviour` are writer-level kinds that also map to
`id: "V3"`; a `round_trip` row keeps its own `required` bit from storage and is
therefore not forced into the gate.

## Verbatim HTTP response

Reproduced on `integration/live-bridge` @ `0233d34`, port 8200, data dir
`D:\brtmp\ev_demo\var` (a throwaway store; not the matrix database).

```bash
curl -s http://127.0.0.1:8200/api/attempts/58fde776f143449a82c0bbfa20472fed/evidence
```

```json
{"attempt_id":"58fde776f143449a82c0bbfa20472fed","run_id":"cfed8923e0cc4f14ae42fd796ee462cb","route":"route_a","sequence":1,"outcome":null,"reason":null,"failing_obligation":null,"detail":null,"evidence":"persisted","summary":{"total":6,"required_total":6,"by_result":{"passed":1,"failed":0,"not_run":5,"unknown":0,"timed_out":0},"gate_ids":["V0","V1","V2","V3","V4","V5"],"invalid":{"total":0,"items":[]}},"obligations":{"A":[{"id":"V0","kind":"identity","scope":"metadata","required":true,"gate":true,"result":"passed","evidence_artifact_id":"0593238ba8c84b1ba8152b2a413f2a15","detail":"V0 identity: passed"},{"id":"V1","kind":"structure","scope":"binary","required":true,"gate":true,"result":"not_run","evidence_artifact_id":null,"detail":"V1 structure: not_run"},{"id":"V2","kind":"interface","scope":"binary","required":true,"gate":true,"result":"not_run","evidence_artifact_id":null,"detail":"V2 interface: not_run"},{"id":"V3","kind":"behaviour","scope":"replay","required":true,"gate":true,"result":"not_run","evidence_artifact_id":null,"detail":"V3 behaviour: not_run"},{"id":"V4","kind":"symbolic","scope":"model","required":true,"gate":true,"result":"not_run","evidence_artifact_id":null,"detail":"V4 symbolic: not_run"},{"id":"V5","kind":"reproducibility","scope":"replay","required":true,"gate":true,"result":"not_run","evidence_artifact_id":null,"detail":"V5 reproducibility: not_run"}],"B":[]}}
```

The snapshot's per-route block carries the same `summary` and the same
`obligations` rows:

```json
{"total": 6, "required_total": 6,
 "by_result": {"passed": 1, "failed": 0, "not_run": 5, "unknown": 0, "timed_out": 0},
 "gate_ids": ["V0", "V1", "V2", "V3", "V4", "V5"],
 "invalid": {"total": 0, "items": []}}
```

## Tests

`tests/integration/test_obligation_summary_shape.py` pins:

* `summary.invalid == {"total": 0, "items": []}` on a healthy attempt;
* `total == 6`, `required_total == 6`, `gate_ids == V0..V5`;
* `V3` is `kind=behaviour`, `required=true`, `gate=true`, `scope=replay`;
* `obligations.B` is empty for a route A attempt;
* an unmappable kind is reported under `invalid` instead of being coerced.

## Not yet on the 8000 controller

Port 8000 serves the canonical checkout (`ce36d6f`) and does not have these
fields until this branch is merged there. Verify against this branch, not 8000.
