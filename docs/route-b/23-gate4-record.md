# Gate 4 record — Route B formal

**Status: DRAFT / NOT RUN.** This is a record skeleton, not a pass claim.

## Inputs required

| Input | Required | Observed |
|---|---|---|
| M3 P4 package (`gate4-status.json`, six-case raw rows, isolation attestation) | yes | missing |
| M3 P3B Route B runtime bundle (`candidate.elf`, `edit-manifest.json`, `manifest-compare.json`) | yes | missing |
| checker PASS | yes | not run |
| real `tools/p2_acceptance.py` exit 0 | yes | not run |
| M4 independent verifier | yes | blank |
| Lead approval | yes | blank |

## V0–V5

| Gate | Result | Evidence |
|---|---|---|
| V0 identity | `not_run` | — |
| V1 structure | `not_run` | — |
| V2 interface | `not_run` | — |
| V3 behaviour | `not_run` | — |
| V4 symbolic | `not_run` | — |
| V5 reproducibility | `not_run` | — |

## Signatures

| Role | Name | Date | Signature |
|---|---|---|---|
| M5 Gate 4 record | — | — | wait for real p2 exit 0 |
| M4 verifier | — | — | blank |
| Lead approval | — | — | blank |

Do not fill any row from a synthetic run, a static bundle, a CI-only 6/6, or a
verbal approval. Synthetic p2 is labelled `synthetic: true` and is not Gate 4
evidence.
