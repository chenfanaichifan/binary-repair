# M5 delivery — 2026-10-22

This directory is the M5 handoff for independent agent-side verification. It is
**not** a Gate 3 or Gate 4 pass.

- `routea/` — c4a159 candidate, original, canonical contract, schema-2 edit
  manifest, audit, 6/6 result, readelf view, stdlib regenerator.
- `bundles/` — the two distribution zips and their `.sha256` files.
- `gate3-record.md` — M5 build/hash replay row filled; M4 verifier and Lead
  approval rows remain blank.
- `docs/` — M4 patch review, Route B executor bundle, Route B attempt writer.

Verify:

```bash
shasum -a 256 -c SHA256SUMS
```

Recompute contract:

```python
from app.domain.contracts import contract_sha256
# 24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37
```

Do not treat this delivery as Gate 3/4 evidence. Formal Gate 4 needs M3's
isolation run; Gate 3 items 3–6 still need the formal VM bundle.
