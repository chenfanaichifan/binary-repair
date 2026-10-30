# 23 — Gate 4 record (Route B: restore C and re-integrate)

Status: **OBSERVED ONLY — NOT PASSED**. This file records what was measured. It
does not contain a `gate4_pass`, an M4 verifier signature, or a Lead approval.

Observed on 2026-10-30 by the M3+M5 merged agent. Verification mode:
**self-verified (single agent)**; M4 independent verification was waived by the
Lead on 2026-10-30 and appears below as waived, not as passed.

## Observed values

| item | value | source |
|---|---|---|
| Fixture | `CWE121_src_char_declare_cpy_51b` | `fixtures/public/…` |
| Original sha256 | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` | `P4/original.elf`, `P3B/original.elf`, job record |
| Route B candidate | `63fcafa6ed01d2db7d5d8a1af460af994e65da853c0c250b05c3eb761f616d01` | `P3B/candidate.elf` |
| Route A candidate | `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` | `P3A/route_a/candidate.elf` |
| Native round-trip cases | 6/6 `repaired_pass` | `P4/manifest-compare.json` |
| Unmodified round-trip candidate | `decdcdb8…954b` (= `roundtrip.elf`) | `P4/candidate.elf` |
| Guest snapshot for gate4 work | uid 11 `gate4-harness`, `.vmsd snapshot.current = "11"` | `P4/chain-manifest.json` |
| Wrapper sha256 | `b232d60b…` MATCH | `P4/post-revert-fingerprint.txt` |
| `gate4.conf` sha256 | `a912e6b0…` MATCH | `P4/post-revert-fingerprint.txt` |
| P4 checker | PASS 26/26 | `scripts/check_handoff.py` |

## real p2 acceptance (end-to-end through controller + worker)

| job | id | `p2_acceptance.py` exit | verdict | failing obligation |
|---|---|---|---|---|
| job1 | `e2fe0f46350648a284c785254c30ee67` | 0 | `inconclusive` / `required_check_not_run` | route_a V2 `not_run` |
| job2 | `8b0f2856086c4fe69117374e09d376bf` | 0 | `rejected` / `regression_failed` | route_b V2 `failed` |

Obligations as persisted by the worker for job2:

| gate | Route A | Route B |
|---|---|---|
| V0 identity | passed | passed |
| V1 structure | passed | passed |
| V2 interface | passed | **failed** |
| V3 behaviour | passed | passed |
| V4 symbolic | `not_run` | `not_run` |
| V5 reproducibility | passed | passed |

## Why this is not a Gate 4 pass

1. V4 bounded symbolic is `not_run` for both routes. No solver output exists in
   this checkout, and a timeout is not a pass.
2. Route B fails V2 interface as measured: the candidate adds 2 PT_LOAD segments
   where `contract.json` `authorized_edits[2]` allows at most one new R-X
   PT_LOAD, as a fallback only. Raw `readelf` dumps are in
   `docs/handoffs/evidence/P2-real/readelf/`.
3. Gate 5 remains **BLOCKED** (no fixed-script `jobwrap` mode), and the fixture
   stays **NOT FROZEN**.

## Signature rows

| role | name | state |
|---|---|---|
| Producer (M3) | M3+M5 merged agent | observed values recorded 2026-10-30 |
| Verifier (M4) | — | **waived by Lead 2026-10-30 — not performed** |
| Approver (Lead) | — | *(blank — not signed)* |

`gate4_pass`: **absent on purpose.** Only the Lead can add it.
