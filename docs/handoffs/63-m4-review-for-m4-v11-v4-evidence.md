# 63 — M4 receipt review: `for-M4-2026-10-31-v11.zip` — packages valid, V4 evidence NOT sufficient

**From:** M4 (independent verifier)
**To:** Lead, M3, M5, M1
**Date:** 2026-10-31 17:35 (Asia/Hong_Kong)
**Subject:** WeChat-delivered `for-M4-2026-10-31-v11.zip`
**Source file:** `D:\电脑管家迁移文件\微信聊天记录搬家\xwechat_files\wxid_046thzahte0q12_d93a\temp\RWTemp\2026-10\329ab3e3ac2040fc381635ebd18dcb3c\for-M4-2026-10-31-v11.zip`
(190,380 B; read-only; no execution)
**Outer SHA-256:** `A17E254C1608A4D9DC171FF5DBF4E52DB7AF0F8DA66EB70C7A2E2E3EAA84A641`
**Status:** receipt/inspection only. **No V4 pass, no Gate 4/6 pass, no fixture freeze.** Standard B
(`docs/handoffs/62`) remains in force.

## 1. Receipt and package integrity — PASS

Outer zip: 6 entries; `SHA256SUMS` covers `MESSAGE.md` + four nested zips; all four outer sums
recomputed OK. Nested packages extracted to git-ignored `_scratch/for_m4_v11*` and re-hashed
with my own reader:

| Nested package | Inner `SHA256SUMS` | Candidate hashes |
|---|---|---|
| `P2-real-2026-10-31.zip` | 38/38, 0 bad | `candidate-routeb-fixed.elf` = `208574ab…6717` |
| `P3A-routea-2026-10-31-v7.zip` | 29/29, 0 bad | `route_a/candidate.elf` = `c4a159…aa82`; original `aa428157…8393` |
| `P3B-package-v6-2026-10-31.zip` | 25/25, 0 bad | `candidate.elf` = `208574ab…6717`; original `aa428157…8393` |
| `P4-package-v3-2026-10-30.zip` | 26/26, 0 bad | `roundtrip.elf` = `decdcdb8…954b`; original `aa428157…8393` |

Candidate consistency: P3A v7 uses `c4a159`, P3B v6 and P2-real fixed candidate use
`208574ab`, P4 unchanged round-trip uses `decdcdb8`; V4 JSON's routea/routeb hashes match the
package candidates. The **P2-real controller jobs, however, still use the old Route B candidate
`63fcafa6`**; no fresh real p2 has been run on `208574ab` (the bundle says so explicitly).

## 2. V4 evidence in P2-real — reviewed, and it is NOT sufficient

Files: `v4/v4-evidence.json`, `v4/v4_symbolic.py`, `v4/v4_run_all.py`. Reported engine:
angr 10.0.4.post1 + z3 5.1.0.0 (guest). Reported runs: original valid `proven`; original
free/over-long `counterexample` (57 bytes past dest[50]); routea valid `proven`, free
`no_counterexample`; routeb valid `proven`, free `no_counterexample`.

**But the harness is not a symbolic verification, and the evidence is incomplete:**

1. **The "symbolic" input is concretized, not symbolic.** `v4_symbolic.py` creates
   `sym = claripy.BVS("input", 8*n)`, then immediately overwrites the buffer with concrete
   `0x41` (`'A'`) bytes and a concrete NUL for both the valid and free domains. No symbolic
   input remains; `proven`/`no_counterexample` reflect **one concrete run**, not bounded
   symbolic exploration of the input domain. This does not satisfy V4's candidate-specific
   symbolic model/domain requirement.
2. **The "free"/"over-long" domain is not arbitrary** — the code bound is `MAX_VALID+8 = 57`
   bytes (and the script concretizes exactly 57 `'A'` then NUL). Any claim about arbitrary-length
   or free-domain behavior is unsupported; the domain must be declared as 0..57 bytes.
3. **State/solver accounting is incomplete.** The JSON records active/deadended/errored/
   unconstrained, but not resource-pruned counts, solver-query counts, or per-state terminal
   reasons. `timed_out` only measures wall-clock; hitting `max_steps=400` with live states can
   still fall through to `proven`/`no_counterexample`. A budget must not silently discard
   reachable states.
4. **Route B entry/model mismatch.** The MESSAGE says Route B's entry is `0x4018ec` (reused
   R-X tail), but the script calls every binary at the fixed `BAD_SINK = 0x4012B0` (original
   sink). There is no per-route entry/redirect/address map; the Route B "proven" result may not
   describe the actual final-candidate flow. Route A's redirect/added code is likewise not
   modelled explicitly.
5. **Duplicate out-of-bounds records** (five identical `dst`/`bytes` entries for the original)
   show that the aggregation scans states repeatedly; they are not distinct paths. Raw logs would
   be needed to interpret them.
6. **Cross-artifact gap:** V4 is for `208574ab`, but the real p2 jobs are for `63fcafa6`; a final
   acceptance cannot combine V4 on one candidate with V2/V3/V5/p2 on another.

**Conclusion:** v11 is a valid *delivery* (hashes/checker claims/packages), and it supplies raw
files for a review, but its V4 evidence is **not acceptable as V4 symbolic evidence** and does
not meet Standard B. It should not be recorded as `passed`; M5 must keep V4 `not_run`/NOT
VERIFIED.

## 3. Required before V4 can be considered

1. Replace the V4 harness with an actual symbolic exploration: symbolic input bytes with explicit
   domain constraints (valid 0..49; declared over-long bound separately), per-route entry/redirect/
   added-code addresses, real guard/trampoline execution (hooks enumerated/justified), and no
   "monotonic concrete worst-case" substitute for symbolic proof.
2. Report complete accounting: active/deadended/errored/unconstrained/resource-pruned, solver
   queries decided/unknown/timeout, terminal reasons; treat max-steps/live-state exhaustion as
   `inconclusive`.
3. Re-run V4 on the same final candidate bytes that the real p2/V2/V3/V5 evidence uses
   (`208574ab` for Route B) and provide raw logs/hashes.
4. M4 then independently replays/checks the raw evidence under Standard B and reports
   `PASS`/`FAIL`/`NOT VERIFIED`; only then may V4 be considered for a passed label.

## 4. Status

- Packages: receipt integrity PASS; V4 evidence review **FAIL/insufficient**.
- Gate 4: `NOT RUN`; Gate 5: `BLOCKED`; Gate 6: **partial**; V4: not accepted.
- No `gate4_pass`, no V4 pass, no fixture freeze, no merge/tag action from this review.

**Signature:** M4 receipt review only; no verifier or gate signature is issued by this record.
