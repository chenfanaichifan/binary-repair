# 196 — M1 GUI comparison JSON route

Date: 2026-11-08  
Branch: `m1-gui-comparison-route`

## Endpoint

```http
GET /api/jobs/{job_id}/comparison
```

Returns:

```json
{"job_id":"…","status":"not_provided|available|invalid","detail":"…","comparison":null,"artifacts":[]}
```

## Rules implemented

```text
job missing                      -> 404
no comparison artifact           -> 200 + not_provided + comparison=null
artifact bytes missing           -> 200 + invalid + comparison=null
sha256 mismatch                  -> 200 + invalid + comparison=null
invalid JSON / schema / counts   -> 200 + invalid + comparison=null
valid payload                    -> 200 + available + parsed comparison
no session                       -> 401
```

Data source is `BACKEND` (same as `/api/jobs/{id}`); mock/local without
artifact therefore returns `not_provided`.

Unknown/ambiguous `kind`/`verdict`, null detail, and same/different with
incomplete outputs are invalid at this layer (M5 owns final validation).

## Tests

```text
tests/test_gui_comparison_route.py -> 6 passed
```

Key acceptance:

```text
missing artifact -> 200/not_provided (not 404)
hash mismatch    -> 200/invalid
bad JSON         -> 200/invalid
valid payload    -> 200/available
unknown job      -> 404
no session       -> 401
```

## Receipt for M2

```text
branch: m1-gui-comparison-route
base delivery head: 1454a7e
no-artifact 200/not_provided: tested
valid/invalid: tested
```

v1.1.1 untouched. M2 can now implement the three-state UI.
