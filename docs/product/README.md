# docs/product - product material index

Product-layer documents for the BinaryRepair delivery (M3 productization,
2026-11-17). All files under `BT`docs/`BT` are ASCII-English by repository policy
(`BT`scripts/check_markdown_language.py`BT`). Chinese versions live under
`BT`delivery/zh/product/`BT` and are not scanned by that gate.

| Document | Purpose |
|---|---|
| `BT`PRODUCT-POSITIONING-2026-11-17.md`BT` | product positioning, ICP, capability matrix, SLOs, not-claimed list, competitor differences |
| `BT`DEMO.md`BT` | 10-minute demo script (3 fixtures, expected output, acceptance criteria) |
| `BT`CUSTOMER-REPORT-TEMPLATE.md`BT` | customer report structure and manual engagement fields |
| `BT`DELIVERY-PACKAGE.md`BT` | what a customer receives and the inclusion rules |
| `BT`DEPLOYMENT-AND-PACKAGING.md`BT` | three deployment forms, packaging/pricing prototype, compliance boundaries, 90-day roadmap |
| `BT`TRIAL-GUIDE.md`BT` | five trial tasks, success/failure criteria, feedback template |

Canonical limitation text (never rewritten by product docs):

- `BT`docs/acceptance/LIMITATIONS.md`BT`
- `BT`docs/status/claims.json`BT`

Product facts that every material must state:

- public benchmark: **2/24 verified (8.3%)**;
- hidden benchmark: **0/8 verified**;
- repair scope: one target function/sink per candidate; deterministic matrix only;
- verification: deterministic unified gate + independent verifier, not a
  whole-program proof;
- not-run items are listed explicitly with reasons.

Tools and demo output:

- `BT`tools/product/run-demo.sh`BT` - one-command demo (deterministic, no key, no network);
- `BT`tools/product/README.md`BT` - tool usage and guarantees;
- `BT`scripts/product/demo_repair.py`BT` / `BT`scripts/product/export_report.py`BT` -
  pipeline and bilingual report export;
- `BT`tests/test_product_demo.py`BT` - CLI structure and fail-closed tests;
- demo artifact: `BT`artifacts/m3-product-2026-11-17/demo/`BT`.

## Related follow-up (M3, 2026-11-17)

- artifacts/m3-product-2026-11-17/ is evidence-only (no original/candidate
  binaries; about 0.5 MB). Regenerate the full run with
  tools/product/run-demo.sh all <outdir>.
- scripts/product/build_delivery_package.py builds a portable delivery zip
  (reports + textual evidence + limitations + README + manifest + SHA256SUMS, no
  binaries) and verifies every digest after writing. See DELIVERY-PACKAGE.md.
