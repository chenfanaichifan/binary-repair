# 61 — M4 JOIN-1 artifact verification after evidence merge (2026-10-31): artifacts PASS, formal JOIN-1 NOT VERIFIED

**From:** M4 (independent verifier)
**To:** Lead, M1, M3, M5
**Date:** 2026-10-31 13:25 (Asia/Hong_Kong)
**Scope:** Gate 4 independent verification (JOIN-1), per `docs/handoffs/42`. **Not** a Gate 5
result and not a repair claim. Gate 4 remains **`NOT RUN`**; Gate 5 record `51` unsigned;
fixture `NOT FROZEN`.
**Subject evidence:** `origin/main` = `56a7447` (`evidence: merge P2-real, P3A v6, P3B v5, P4 v3
and approval record`); packages under `docs/handoffs/evidence/`.
**Identity limitation:** M4 verifier and Lead are the same person/operator (two AI windows of
one person); the M4 row and Lead approval row are not independent two-person signatures.

## 1. Artifact verification — PASS

I re-hashed every package with my own reader (not only `check_handoff.py`) and checked the
native six-case evidence:

| Package | `check_handoff.py --expect-from M3 --expect-to M5` | Own SHA256SUMS recompute |
|---|---|---|
| `P4` | PASS (exit 0, 26 sums) | 26/26, 0 mismatches, 0 unlisted |
| `P3A` | PASS (exit 0, 26 sums) | 26/26, 0 mismatches, 0 unlisted |
| `P3B` | PASS (exit 0, 22 sums) | 22/22, 0 mismatches, 0 unlisted |
| `P2-real` | PASS (exit 0, 32 sums) | 32/32, 0 mismatches, 0 unlisted |

`P4` identity/isolation checks from the delivered bytes:

- `original.elf` = `aa428157…8393`; `candidate.elf` = `roundtrip.elf` =
  `decdcdb821bfe4c41a070b0a23a2f6497f46a92f439cb02a1e4139a82cde954b`;
  `candidate-before` = `candidate-after` = the same hash.
- `hashes.json.gate4_status.gate4 = pass`; `elf_sha256` = original; `patched_sha256` = candidate;
  `uid=1003`; `expected_uid=1003`.
- `manifest-compare.json`: `same_count=6`, `total=6`, `gate4_pass=true`; six frozen ids; per-case
  `original == patched`; frozen original shape (valid rc 0 + expected stdout; `invalid-first`
  rc 0 silent overflow; `invalid-longer` rc -11 SIGSEGV). `case-01..06.json` are explicitly
  `derived_from=manifest-compare.json, runner_native=false` — consistent with the Lead's native
  evidence policy (`manifest-compare.json` is the native six-case evidence; per-case raw files
  are not required).
- `isolation.json`: `uid=1003`, `CapEff=0000000000000000`, `NoNewPrivs=1`, `Seccomp=0`,
  `lo DOWN`, `evaluator=unreadable`, `egress=blocked`; snapshot `gate4-harness` uid 11
  (`disk-000008.vmdk`); `chain-manifest.json` sha256
  `b7ded7003da55bf25248f1969506c18ac3455a084898d72f3f55142872f04188` (file present);
  `revert-raw.log` + `post-revert-fingerprint.txt` present; wrapper
  `b232d60b20b13dc696402112dd1d970c35b41a3ee720af32cfb2df396c621fa8` and `gate4.conf`
  `a912e6b0f7a852141476032dba55b954d7637e81d25d11578990dc2d82e5a8cd` (matches `docs/handoffs/41`).

`P2-real` real-pipeline evidence:

- job1 `e2fe0f46350648a284c785254c30ee67`: `phase=finished`, `synthetic=false`,
  verdict `inconclusive/required_check_not_run`, both routes 6 obligations, `exit_code=0` in
  `job1/acceptance.txt`.
- job2 `8b0f2856086c4fe69117374e09d376bf`: `phase=finished`, `synthetic=false`, verdict
  `rejected/regression_failed` (route B V2 failed by measurement), both routes 6 obligations,
  `exit_code=0` in `job2/acceptance.txt`.
- These are genuine p2 exit-0 results (not a repair success; V4 remains `not_run`).

**Artifact verdict: PASS.** The packages and evidence are internally consistent and
hash-bound.

## 2. Formal JOIN-1 — still NOT VERIFIED

The Gate 4 **record** required for JOIN-1 is still stale and unsigned:

- `docs/route-b/23-gate4-record.md` on `main` still says **DRAFT / NOT RUN**, lists P4 as
  incomplete and real p2 as "not run" (both superseded by the evidence above), and its
  signatures table still has **M5 Gate 4 record blank ("wait for real p2 exit 0")**, M4 blank,
  Lead blank.
- No updated M5 record exists with observed values from P4 v3/P3A v6/P3B v5/P2-real.
- `docs/handoffs/38`/`60` state that "M4 independent verification was waived by the Lead on
  2026-10-30". **This M4 does not accept a waiver:** the verification above was performed, but a
  waiver cannot substitute for the M5 record/signature order, and it does not close Gate 4.
- I cannot re-execute `tools/p2_acceptance.py --job-id …` here: the controller/data directory for
  jobs `e2fe0f46…`/`8b0f2856…` is not in this checkout and no controller is running. The
  `acceptance.txt` logs are hash-verified raw evidence, but independent **re-execution** is
  `NOT VERIFIED`.

**JOIN-1 result: NOT VERIFIED.** No M4 verifier row is signed; Gate 4 remains `NOT RUN`.

## 3. Process discrepancy (again recorded)

The last synced remote state shows:

- `main` contains PR #10 head `aab162a`; tag `mvp-integration-2026-10-31` (`fbe2fdb…`) points at
  older main `bcf2537`;
- `docs/handoffs/60-final-evidence-main-2026-10-30.md` records a Lead "owner-relayed" approval
  for the evidence merge only, not a Gate 4 approval;
- there is **no M4 PR-head PASS row for `aab162a`** and **no written Lead approval in this
  record chain**; the tag message itself says "Lead approval owner-reported verbal".

This remains a written-approval-process discrepancy. It does not make Gate 4 pass and does not
authorize any gate action.

## 4. Required next steps for a real JOIN-1 signature

1. **M5** updates `docs/route-b/23-gate4-record.md` with the observed values from P4 v3/P3A v6/
   P3B v5/P2-real (P4 gate4 pass 6/6, isolation, P2 job ids/exit 0, P3A/P3B checker PASS) and
   signs the M5 Gate 4 row; correct the stale "P4 incomplete / real p2 not run" text.
2. Provide a controller/data dir or a replayable job directory so M4 can independently re-run
   `tools/p2_acceptance.py --job-id e2fe0f46…` / `8b0f2856…` (or record it as `NOT VERIFIED`).
3. M4 then fills only the M4 verifier row (PASS/FAIL/NOT VERIFIED) and pins the record hash.
4. Gate 5 `51` remains unsigned until an M3/VMer guest probe returns raw evidence (`docs/handoffs/
   41` confirms current `jobwrap` has no `gate5` mode; `GATE5_SCRIPT` hash check still missing).

## 5. Status

| Gate/artifact | Status |
|---|---|
| Gate 3 | CLOSED/APPROVED `0b3b51e4…` |
| Gate 4 | **NOT RUN** — artifacts PASS, formal JOIN-1 **NOT VERIFIED** (M5 record stale/unsigned; p2 re-execution unavailable) |
| Gate 5 | pending/unsigned; `jobwrap` lacks `gate5` mode; record `51` NOT VERIFIED |
| Gate 6 | partial; V4 `not_run` |
| Fixture | **NOT FROZEN** |

**Signature:** none. M4 verifier row remains blank; no pass is claimed.
