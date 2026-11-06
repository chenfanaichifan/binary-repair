# 131 — evidence endpoint exposes ordered gates and V3 counts

- Date: 2026-11-06
- Owner: Member 1 (host backend)
- Branch: `m1/t30-acceptance-ab-2026-11-05`
- Patch: `m1-evidence-gates-2026-11-06.patch` (M5)
- Scope: API evidence rendering only. No gate result, no V4 change.

## 1. Applied change

`GET /api/attempts/{id}/evidence` now also returns:

```
gates: V0..V5, sorted by gate
v3:    V3 summary with gate/kind/result/input_mode/valid/invalid/invalid_applicable
```

`v3.invalid_applicable` is derived from the V3 artifact's total invalid cases;
an absent/unknown count is `None`, never an invented zero.

## 2. Tests

```
tests/test_evidence_endpoint.py   9 passed
M1 full suite                     504 passed / 2 skipped / 0 failed
```

## 3. Actual controller curl

Data: real controller job/run/attempt created from the 124 provisional bundle
(`9e811363…`, `23e693e0…`, `7ce38f28…`), served by uvicorn with
`BINARYREPAIR_DATA_DIR=/tmp/m1-curl-data`.

```
$ curl -s http://127.0.0.1:8876/api/attempts/7ce38f28…/evidence
gates              ["V0","V1","V2","V3","V4","V5"]
V3.gate            "V3"
v3.valid           1/1
v3.invalid         0/0
v3.invalid_applicable false
```

The same response shows the unchanged 124 result:

```
V0 passed V1 passed V2 passed V3 passed V4 not_run V5 passed
attempt inconclusive / required_check_not_run / symbolic
```

The API change does not promote V4; the M4 replay marker is still missing.

## 4. Constraints

CWE121 v2 hash and the 120 contract gate are unchanged. T8.3 blocked. No merge,
tag or live-success claim.
