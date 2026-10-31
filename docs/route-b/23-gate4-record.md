# 23 — Gate 4 record (Route B: restore C and re-integrate)

Status: **Gate 4 PASS (strict unchanged round-trip scope only)**. This file
records what was measured and the Lead's approval of the *narrow* Gate 4 scope.
It does **not** mean a repair succeeded, V2/V4 passed, or the MVP is complete.

Observed on 2026-10-30 by the M3+M5 merged agent. Verification mode:
**self-verified (single agent)**; M4 independent verification was waived by the
Lead and appears below as waived, not as performed.

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

## Why this is a Gate 4 pass and what it does NOT cover

Gate 4's strict scope is the *unchanged* round-trip: six cases, 6/6 `same`, the
original and the round-trip candidate byte-verified against the recorded
hashes, the isolation uid and snapshot/chain manifest present, and the raw
revert + post-revert fingerprint matching. That scope is met.

`gate4_pass=true` applies **only** to that strict scope. It does **not** mean:

1. A repair succeeded — no route has reached `success_within_scope`.
2. V2 passed — Route B fails V2 as measured: the candidate adds 2 PT_LOAD
   segments where `contract.json` `authorized_edits[2]` allows at most one new
   R-X PT_LOAD, as a fallback only. Raw `readelf` dumps are in
   `docs/handoffs/evidence/P2-real/readelf/`.
3. V4 passed — bounded symbolic is `not_run` for both routes.
4. Gate 5 passed — it remains **BLOCKED** (no fixed-script `jobwrap` mode).
5. The fixture is frozen — it stays **NOT FROZEN** (gates 3–5 not all signed).
6. The MVP is complete — the overall MVP verdict is **NOT APPROVED**.

## Signature rows

| role | name | state |
|---|---|---|
| Producer (M3) | M3+M5 merged agent | observed values recorded 2026-10-30 |
| Verifier (M4) | *(waived)* | **waived by Lead — not performed** |
| Approver (Lead) | Lead | **approved 2026-10-31 (Gate 4 strict scope only)** |

`gate4_pass`: **true — Gate 4 strict unchanged round-trip scope only.**

## Lead approval note (2026-10-31)

- Package integrity APPROVED: `SHA256SUMS` 118/118 match; checker P3A 26/26,
  P3B 22/22, P4 26/26, P2-real 31/32, all PASS.
- Gate 4 PASS: P4 v3 six cases 6/6 `same`; original `aa428157…`, roundtrip
  `decdcdb8…`; isolation uid 1003; snapshot uid 11 / chain `b7ded700…`; raw
  revert + post-revert fingerprint; wrapper `b232d60b…`, `gate4.conf`
  `a912e6b0…`, kit v6 `499f510c…`, runner `515c4d60…`.
- M4 independent verification waived; this approval is by the same operator
  (proxy approval), **not** an independent two-person review.
- `gate4_pass=true` is limited to the strict Gate 4 scope above; it does not
  imply repair success, V2/V4 pass, or MVP completion.

## Overall MVP: NOT APPROVED (2026-10-31)

- Route A is 5/6; V4 symbolic remains `not_run`.
- Route B V2 was `failed` on the 10-30 candidate 63fcafa6 (2 extra PT_LOAD where
  the contract allows one R-X fallback); the fixed candidate 208574ab reuses the
  R-X PT_LOAD tail (0 new segments) and passes V2 16/16. See
  `docs/handoffs/evidence/P2-real/v2-routeb-fixed.json`. Route B V4 still
  `not_run`.
- Gate 5 remains BLOCKED.
- real p2 twice exit 0 is pipeline-only; verdicts `inconclusive`/`rejected` are
  not repair success (those runs used the 10-30 candidate 63fcafa6; the fixed
  candidate has not yet been driven through a fresh real p2).
- fixture remains NOT FROZEN.

## Open decisions from the Lead (2026-10-31)

1. **Route B V2**: do **not** change `authorized_edits[2]`. Fix the Route B
   candidate to remove the extra segment(s); otherwise Route B is formally
   recorded `rejected on V2`, with no `success` written.
   → **Actioned 2026-10-31**: candidate fixed to 208574ab (0 new segments,
   V2 16/16) without changing the contract. A fresh real p2 run with this
   candidate is the remaining step before Route B can claim V2 success.
2. **Gate 5**: still BLOCKED. Needs a `jobwrap` build with a `gate5` mode **and**
   `jobwrap_gate5.sh` `GATE5_SCRIPT_SHA256` verification — both, not one.
3. **tag**: `mvp-integration-2026-10-31` is an M2 integration snapshot only; it
   does not contain this package's final P4/P2-real evidence and is not an MVP
   acceptance tag. Keep it, do not claim MVP from it. The final tag waits for
   final evidence merge and the remaining gates.
