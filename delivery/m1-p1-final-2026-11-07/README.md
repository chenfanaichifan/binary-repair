# P1 final controller run (2026-11-07)

M4 Route A V4 marker integrated; Route A now has all six gates passed. P1
overall is still **inconclusive** because Route B V2/V4/V5 are not_run.

```
job      784f6cc0185b49edb45e2381d2fddc2a
run      e08a38435428484ebaf56690eac13b4b
route A  2117c7a4330a420dac09ac6091e9f4a7
route B  52d1fde006d74846af2867d2311d6f9f
```

- Route A candidate `2a96b108…970e`; original `c9c2632e…23c9`.
- V2 is a product `check_interface` 5/5 report, not P1's non-schema observation.
- V4 is M4's independent marker `87c0972f…38c1` with `replay.verified_by="m4"`.
- V5 Route A is passed from the real replay.json; Route B V5 remains not_run.
- p2 exit 0, `synthetic=false`; verdict `inconclusive /
  required_check_not_run / interface`, route A `success_within_scope`, route B
  `inconclusive`.

No host ELF execution. No overall success claim.
