# 66 — M4 review: `for-M4-2026-10-31-v12.zip` — receipt PASS, V4 still NOT VERIFIED (now self-admitted concrete, not symbolic)

**From:** M4 (independent verifier)
**To:** Lead, M3, M5, M1
**Date:** 2026-10-31 20:05 (Asia/Hong_Kong)
**Source:** `D:\电脑管家迁移文件\微信聊天记录搬家\xwechat_files\wxid_046thzahte0q12_d93a\temp\RWTemp\2026-10\329ab3e3ac2040fc381635ebd18dcb3c\for-M4-2026-10-31-v12.zip`
**Outer SHA-256:** `AB2F8F4BDA4DF0FB75744F7463D9EA340273275720E56D3EFF4D7A57ED952CE0`
(198,228 B; read-only inspection; no script/binary executed)
**Status:** receipt review only. **No V4 pass, no Gate 4/6 pass, no fixture freeze.**
Standard B (`docs/handoffs/62`) remains in force.

## 1. Receipt integrity — PASS

- Outer `SHA256SUMS`: all 5 entries recomputed OK (`MESSAGE.md` + four nested zips).
- P2-real v12: inner `SHA256SUMS` **42/42**, 0 mismatches; repo `check_handoff.py`
  (`main 56a7447`, `--expect-from M3 --expect-to M5`) **PASS exit 0**.
- P3A v7 / P3B v6 / P4 v3 are unchanged from v11; outer sums verify.
- P2-real still carries the old candidate `63fcafa6` in its controller-job evidence; V4
  uses `208574ab`. No fresh real p2 on the fixed candidate is in this bundle.

## 2. What v12 adds, and what it admits

v12 adds the raw replay package `v4/REPLAY-README.md`, `v4_accounting.py`,
`v4-accounting.json`, `v4-accounting.log`. Its own README is explicit:

- valid domain is fed as **concrete bytes** (`49 × 'A' + NUL`); free/calibration also
  concrete (`57 × 'A' + NUL`);
- accounting shows **`sat=0, unsat=0, unknown=0, eval=1`** for every run — no
  satisfiability queries, no symbolic input exploration;
- therefore `proven` means only "the concrete worst-case 49+NUL input did not overflow
  in this run", not "no legal input can overflow";
- the monotonicity argument is producer reasoning, not a solver result;
- there is **no second, deliberately defective candidate**; the only negative control is
  the original binary itself;
- the `strcpy`/`printLine` hooks mean the guard/reject path outside the hooked copy is
  not established by this model; the verifier must check it separately.

State accounting: all six runs end `active=0 deadended=1 errored=0 unconstrained=0
deferred=0 timed_out=false`; steps 6/6/107/122/259/162. The earlier duplicate OOB records
(5 identical) remain. v12 corrects the earlier Route B entry confusion: `badSink` symbol
is `0x4012b0` in all three binaries; that does not make the exploration symbolic.

## 3. Verdict

**Receipt: PASS. V4: FAIL / NOT VERIFIED.**

- v12 does not provide a bounded **symbolic** verification; it documents that the claimed
  `proven`/`no_counterexample` results are **concrete worst-case runs**. That is
  insufficient under V4 (and under Standard B §3.3/§3.6) even before independence.
- An independent replay would only reproduce the concrete runs (`sat=0`), not establish
  a symbolic property; therefore I do not sign V4, and no replay result could turn this
  into a V4 pass without a corrected harness.
- M5 must keep V4 `not_run`/NOT VERIFIED; Gate 6 remains partial.

## 4. Required for a future V4 submission

1. A genuinely symbolic harness: symbolic input bytes with explicit valid (0..49) and
   separately declared over-long domain constraints; solver queries must actually be
   made (`sat/unsat/unknown` counts > 0 where applicable); all reachable states accounted
   for; no concrete-worst-case substitution.
2. A deliberately defective candidate rejected as negative calibration (not just the
   original binary).
3. Hooks enumerated/justified; the repaired guard/reject path must be shown to execute
   and terminate safely outside the hooked `strcpy` model.
4. Real p2/V2/V3/V5 and V4 on the same final candidate (`208574ab` for Route B).
5. M4 independent replay under Standard B; then PASS/FAIL/NOT VERIFIED and Lead approval.

## 5. Status

| Item | Status |
|---|---|
| v12 receipt/integrity | PASS |
| V4 | **FAIL / NOT VERIFIED** — concrete, not symbolic |
| Gate 4 formal | `NOT RUN` (not V4-gated; M5 record/JOIN-1 unresolved) |
| Gate 5 | `BLOCKED`; `51` unsigned |
| Gate 6 | partial |
| Fixture | **NOT FROZEN** |
| Merge/tag | no action; no gate4_pass |

**Signature:** M4 receipt/verification review only; no V4 or Gate 4/6 signature.
