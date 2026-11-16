# M3 product demo artifact (2026-11-17)

This directory is the recorded output of the product demo command:

    tools/product/run-demo.sh all artifacts/m3-product-2026-11-17/demo

It is delivered as **pure evidence** (about 0.44 MB): reports, textual/JSON
evidence, the evidence index and checksums. Original/candidate binary bytes are
**not included** (a full run is about 11 MB); the demo command above regenerates
them.

## Included

`BT``BT``BT`text
README.md                  this file
demo/REPORT.md             English customer report
demo/report.html
demo/REPORT.zh.md          Chinese customer report
demo/report.zh.html
demo/demo-run.json         run metadata + per-fixture product records
demo/EVIDENCE-INDEX.json   SHA256 of every evidence file in demo/
demo/SHA256SUMS            checksums for every file in demo/ (except itself)
demo/evidence/<fixture>/scan.json
demo/evidence/<fixture>/engine-evidence/
    results.json, README.md, SHA256SUMS
    samples/<sample_id>/{outcome,metadata,plan,verifier-report}.json
`BT``BT``BT`

## Excluded on purpose

- `BT`original.bin`BT` / `BT`candidate.bin`BT` per sample (about 9.7 MB for the two
  positive fixtures). They are byte-identical regenerations of the committed
  fixtures plus the verified patch; regenerate with the command above.
- the portable delivery zip (`BT`demo/delivery-package/*.zip`BT`): it duplicates the
  evidence and is rebuilt on demand with
  `BT`.venv/bin/python scripts/product/build_delivery_package.py artifacts/m3-product-2026-11-17/demo`BT`;
- no customer binary, credential or API key is present.

Because the binaries and the zip were removed, `BT`EVIDENCE-INDEX.json`BT` and
`BT`SHA256SUMS`BT` were regenerated over the trimmed file set; the SHA256 values in
the reports therefore describe this evidence-only snapshot. The candidate digests
of the removed bytes are still recorded in `BT`demo-run.json`BT` and in the
`BT`verifier-report.json`BT` evidence.

## Result summary

| fixture | verdict | disposition | independent verification | oracle | runtime tier |
|---|---|---|---|---|---|
| strcpy-stack-x86_64 | VERIFIED_WITHIN_SCOPE | verified_patch | verified | pass | emulated_run |
| marcx-capacity | VERIFIED_WITHIN_SCOPE | verified_patch | verified | pass | emulated_run |
| unsupported-bigendian | REFUSED | unsupported | not_run | not_run | - |

Elapsed seconds: 45.71. Boundary: public benchmark **2/24 verified (8.3%)**,
hidden **0/8 verified**; one target function/sink per candidate; not a
whole-program proof.

## Verify

`BT``BT``BT`bash
cd demo
shasum -a 256 -c SHA256SUMS
`BT``BT``BT`

## CI note

CI runs structural/fail-closed tests only
(`BT`tests/test_product_demo.py`BT`); it has no guest runtime oracle, so CI is not
expected to produce a `BT`verified`BT` result. This artifact was produced on a host
with the guest oracle available and records `BT`emulated_run`BT` evidence.

## Delivery package

The portable delivery package (reports + textual evidence + limitation documents
+ README + manifest + SHA256SUMS, no binaries) is **not committed**; build it on
demand:

    .venv/bin/python scripts/product/build_delivery_package.py artifacts/m3-product-2026-11-17/demo

The builder verifies every digest after writing the zip and exits 1 on mismatch.
