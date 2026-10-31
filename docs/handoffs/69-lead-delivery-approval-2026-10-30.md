# Lead approval — 2026-10-30 delivery package

**Package:** `lead-delivery-2026-10-30.zip`, 197,516 B,
SHA-256 `d4e79bdd2e7501ff0a956bbbbce834c72d4e3393611d5341af1f045bd3f4f386`
**Source anchor in package:** member-3 HEAD `5751984b304aea8c4fdea4f5bdd70d1297fffb9d`
**Verification window:** 2026-10-30 23:33–23:55 +08 (Lead).

## 0. Integrity check — PASS

- Root `SHA256SUMS`: **118/118 entries match**; no missing files.
- `checker/check_handoff.py` on the four evidence packages:
  - `evidence/P3A` — PASS, 26 files / 26 sums, sums `023b94fa…2115`
  - `evidence/P3B` — PASS, 22 files / 22 sums, sums `a312949c…dfd8`
  - `evidence/P4` — PASS, 26 files / 26 sums, sums `e4b81b34…6c5e`
  - `evidence/P2-real` — PASS, 31 files / 32 sums, sums `a3c3fdf4…ec74`
- No pre-filled `gate4_pass`, M4 row, or Lead row was found in the package;
  the Gate 4 record is explicitly `OBSERVED ONLY — NOT PASSED`.

## 1. Gate 4 (strict scope) — PASS

`docs/handoffs/42` defines Gate 4 as the **unchanged round trip** only; it is
not V2, not V4, not a repair, and not the overall MVP acceptance.

Evidence accepted:

| Check | Observed |
|---|---|
| P4 native six cases | `gate4_pass=true`, `same_count=6`, `total=6`; all six `same=true` |
| Original / round trip | `aa428157…8393` / `decdcdb8…954b`; both present in P4 |
| `gate4-status.json` | `gate4=pass`, 6/6 behaviour-identical, uid 1003 |
| P4 checker | PASS 26/26 |
| Snapshot / chain | uid 11 `gate4-harness`, `disk-000008.vmdk`; chain manifest SHA-256 `b7ded700…4188` |
| Isolation | uid/gid 1003, CapEff 0, NNP 1, seccomp 0, lo DOWN, egress blocked |
| Revert | raw `vmrun stop` + `revertToSnapshot` exit 0; post-revert fingerprint at 19:38 |
| Harness / config bytes | `jobwrap` `b232d60b…1fa8`; `gate4.conf` `a912e6b0…8cd`; kit v6 `499f510c…`; runner `515c4d60…` |
| Scope honesty | P4/record do not claim a repair or V3/V4 success |

**Gate 4 approval:** `gate4_pass = true` **for the unchanged round trip only**.
The delivered `23-gate4-record.md` remains observation-only; add this Lead row
and the waiver row below when merging. This approval does **not** convert V2/V4
or the overall MVP into a pass.

**Verifier limitation:** M4 independent verification was waived (same operator;
not an independent two-person review). The M4 row is **waived — not performed**,
not passed. Lead approval is therefore an **acting approval by the same
operator**, with the limitation disclosed.

## 2. Overall MVP — NOT APPROVED / NOT PASS

| Item | Status | Reason |
|---|---|---|
| Route A | 5/6 | V2/V5 now pass; **V4 symbolic `not_run`** |
| Route B | rejected | **V2 failed**: 2 extra PT_LOAD segments vs contract allowance of 1 |
| Gate 5 Route A | BLOCKED | `jobwrap` has no `gate5` mode; no `GATE5_SCRIPT_SHA256` pin |
| real p2 | pipeline PASS (exit 0 twice) | verdicts are `inconclusive` / `rejected`; exit 0 is not repair success |
| fixture | NOT FROZEN | gates 3–5 not all signed |

No route reaches `success_within_scope`; the MVP acceptance is not met.

## 3. Route B V2 decision — do not amend the contract

**Decision:** keep `contract.json` `authorized_edits[2]` unchanged. The candidate
`63fcafa6…6d01` adds two PT_LOAD segments (`0x4058a8` R-E, `0x407000` R); the
contract allows at most one new R-X PT_LOAD and only as a fallback. Re-judging
the contract to fit the candidate would weaken the verification criterion.

**Required:** fix the Route B candidate to remove the extra segment, or record
Route B as `rejected` on V2. Do not mark Route B as success.

## 4. Gate 5 / D3 — still blocked

The exported `jobwrap` (22120 B, SHA-256 `b232d60b…1fa8`) supports only
`gate3 | probe | gate4`; `jobwrap gate5` fails before any script runs. The shell
wrapper exists but does not pin `GATE5_SCRIPT` by hash. Required:

1. a `jobwrap` build with a fixed `gate5` mode, and
2. `GATE5_SCRIPT_SHA256` verification in `jobwrap_gate5.sh`, fail-closed.

Until both exist: Gate 5 remains **BLOCKED**; no PASS/FAIL may be written.

## 5. V4 / real p2 / tag notes

- **V4:** `not_run` for both routes; no raw solver output in the package. A
  timeout is not a pass. This is the only Route A gap.
- **real p2:** accepted as **pipeline** evidence only (two real jobs, exit 0,
  verdicts computed by the pipeline). It is not a repair success and not a
  substitute for Gate 4/V4.
- **Tag `mvp-integration-2026-10-31`:** it points to the M2 integration merge,
  not to this final evidence package, and is **not** an MVP acceptance tag. Do
  not cite it as MVP completion. Do not delete it; treat it as an integration
  snapshot. Create the final acceptance tag only after the final evidence is
  merged and the remaining gates are signed.

## 6. Approved / withheld summary

| Item | Decision |
|---|---|
| Package integrity / checker | **APPROVED** |
| P3A v6 / P3B v5 / P4 v3 / P2-real evidence | **ACCEPTED as observed evidence** |
| Gate 4 (strict round trip) | **PASS — approved with same-operator waiver** |
| Route A V4 | **NOT PASSED — not_run** |
| Route B V2 | **FAILED / rejected; contract unchanged** |
| Gate 5 | **BLOCKED** |
| Overall MVP | **NOT APPROVED** |
| `gate4_pass` | **true for strict Gate 4 only** |
| Fixture freeze | **NOT APPROVED / NOT FROZEN** |

## 7. Signature rows

| Role | Name | State |
|---|---|---|
| Producer | M3+M5 merged agent | observed values recorded 2026-10-30 |
| Verifier (M4) | — | **waived by Lead 2026-10-30 — not performed** |
| Approver (Lead) | Lead | **Gate 4 strict: approved; overall MVP: withheld** (same operator as M4; not independent) |

**Disclosure:** this is not an independent two-person approval. If the client
requires independent human review, that requirement is not satisfied by this
sign-off.
