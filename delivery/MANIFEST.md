# Shared delivery manifest

Two tracked roots hold hand-off artifacts. Neither is authoritative by
position; the hash is authoritative.

| Path | What it is | Consumer |
|---|---|---|
| `dist/m5-evidence/P3A-routea-2026-10-31-v7.zip` | Route A evidence package used by the ingest tests | M1, M5 |
| `dist/m5-evidence/P3B-package-v6-2026-10-31.zip` | INTERFACE-v1 package without `result-bundle.json` (all gates `not_run`) | M1, M3, M5 |
| `dist/m5-evidence/SHA256SUMS` | Hashes for the two packages above | all |
| `dist/m5-routeb-kit-2026-10-22-v6.zip` | Route B kit (older interface) | M3 |
| `dist/m5-routea-c4a159-2026-10-22.zip` | Route A artifact for the c4a159 candidate | M4, M5 |
| `dist/p3b-fixed-c-2026-10-29.zip` | Fixed C source for P3B | M3 |
| `dist/README.md` | Original description of the `dist/` packages | all |
| `delivery/t30-rebuild-2026-11-05/M3-t30-rebuild-evidence-2026-11-05.zip` | Record 118 evidence: 00–07, `collect.sh`, `SHA256SUMS`; top-level hash in the sibling `.sha256` | M4, M5 |
| `delivery/t30-rebuild-2026-11-05/PROVENANCE.md` | T30 canonical path (`docs/handoffs/evidence/T30/build/original.elf`) and the `c274893` git binding | M4, M5 |
| `delivery/t30-rebuild-2026-11-05/README.md` | Delivery/verification instructions and the upgrade boundary | M4, M5 |

## Adding an entry

1. Put the artifact in `delivery/` (new hand-offs) or leave it in `dist/`
   (historical packages keep their location).
2. Add its SHA-256 to `delivery/SHA256SUMS`.
3. Add a row to the table above with the consumer names.
4. Commit all three in the same commit.

A package that is not in this table and not hashed is not considered delivered,
regardless of which host it sits on.
