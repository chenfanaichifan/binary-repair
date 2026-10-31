# 60 - Final evidence merged into main (2026-10-30)

## Lead approval record

Lead approved merging the final evidence packages into `main` on 2026-10-30
(owner-relayed instruction). This approval covers the evidence merge only.

It is **not** a Gate 4 approval:

- `gate4_pass` remains absent;
- Gate 4 remains `NOT RUN`;
- the M4 independent verification was waived by the Lead on 2026-10-30 and is
  recorded as waived in `docs/handoffs/38-m3-to-m5-2026-10-30.md`;
- no acceptance tag is created by this change.

`mvp-integration-2026-10-31` remains an integration snapshot only.

## Evidence packages

The following directories were copied byte-for-byte from
`origin/member-3-route-a` (`5751984`) and verified against their own
`SHA256SUMS` after checkout:

| Package | Directory | SHA256SUMS entries | Verified |
|---|---|---|---|
| P2-real | `docs/handoffs/evidence/P2-real/` | 32 | 0 mismatches |
| P3A v6 | `docs/handoffs/evidence/P3A/` | 26 | 0 mismatches |
| P3B v5 | `docs/handoffs/evidence/P3B/` | 22 | 0 mismatches |
| P4 v3 | `docs/handoffs/evidence/P4/` | 26 | 0 mismatches |

Supporting records:

- `docs/handoffs/38-m3-to-m5-2026-10-30.md`
- `docs/handoffs/39-m3-v2-v5-p2-2026-10-30.md`
- `docs/handoffs/41-gate5-d3-status-2026-10-30.md`

`docs/handoffs/evidence/**` is pinned with `-text` in `.gitattributes` so the
hash-bound bytes survive checkout.

## Bound state

- P2-real job 1 route verdicts: A `inconclusive`, B `inconclusive`.
- P2-real job 2 route verdicts: A `inconclusive`, B `rejected`
  (`extra_load_segments_within_contract`).
- Gate 5 remains blocked; the shipped `jobwrap` has no `gate5` mode.
- No gate status is changed by this merge.
