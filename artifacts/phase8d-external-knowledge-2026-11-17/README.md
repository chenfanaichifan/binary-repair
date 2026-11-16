# Phase-8D external CWE 5.0 knowledge scan (2026-11-17)

Generated deterministically from the committed normalized
`data/external/cwe-5.0/` snapshot. External entries are capability
*candidates*, not evidence of local support.

- catalog: CWE 5.0 (2026-10-28), schema namespace `http://cwe.mitre.org/cwe-8`
- external weaknesses: 984
- mapped binary-relevant candidates: 232
- unmapped entries: 752
- version drift status: `current`; new ids 15, removed 0
- support_claimed: `False`
- capability_promotion: `False`

## Candidate groups

| group | candidates |
|---|---|
| arithmetic | 9 |
| control_flow | 10 |
| file_handling | 66 |
| initialization | 18 |
| input_validation | 21 |
| logging | 2 |
| memory_safety | 37 |
| resource | 61 |
| string_safety | 8 |

Every candidate carries a deterministic `GAP-KSRC-...` id, a proposed
experiment, `support_claimed=false`, and public-corpus exposure counts.
None is promoted to verified/resolved/open.

## Schema drift

- prior: CWE 4.19
- 4.19 -> 5.0 changed the XML namespace to `cwe-8`, removed Categories
  from the weakness catalog layout, added 431 Groupings, and added 15 new
  weakness ids. The briefing's approximate 16 is not asserted.

## Limitations

- external CWE entries are discovery candidates only; no local repair support is claimed
- the normalized snapshot stores description digests, not full CWE prose
- the measured new-id count is 15 versus CWE 4.19; the briefing's approximate 16 is not asserted
- live fetch is optional and not used by tests; a committable snapshot remains the evidence source

## Reproduce

```bash
python scripts/scan_external_knowledge.py --write
python scripts/scan_external_knowledge.py --check
python -m pytest -q tests/test_phase8d_external_knowledge.py
```
