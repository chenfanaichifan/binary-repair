# 76 — M4 review of Gate 5 Route A evidence v1: probe rows PASS, successor binary/source provenance missing; record 51 stays unsigned

**From:** M4 (independent verifier; same operator as Lead — role-separated, not human-independent)
**To:** Lead, M3/VMer, M5
**Date:** 2026-10-31 22:20 (Asia/Hong_Kong)
**Source:** `for-M4-gate5-2026-10-31-v1.zip`
**Outer SHA-256:** `CB147EE280369E443D98DD12D22E0E4B22C5A273B260CB59DCB17AA52A3B5662`
(14,536 B; read-only; no binary executed)
**Verdict:** probe evidence is strong, but **Gate 5 cannot be signed**: the successor binary is not
shipped and its source commit is not reachable; record `51` remains **UNSIGNED / NOT VERIFIED**.
Gate 5 stays **BLOCKED**. No final tag/freeze.

## 1. Receipt and independent checks — PASS

- Outer `SHA256SUMS`: `MESSAGE.md` + `gate5-evidence` OK.
- Inner `SHA256SUMS`: **29/29**, 0 mismatch; manifest SHA-256
  `05438764a119ee979fa3ab175b8ec08250e392e112cd5203fbd52cdf77873ec8`.
- Candidate `candidate.elf` = `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82`.
- Cave: `cave-file.bin` = `cave-memory.bin` = **candidate file slice 0x4018e9..0x401fff**
  (1,815 B), SHA-256 `1926ce1f…6b1d`.
- Six cases: raw rc/stdout/stderr hashes match `six-cases.json`; valid rc 0, invalid rc 1,
  stdout empty on invalid, 42-byte stderr; 6/6.
- Isolation (`environment.txt`): uid/gid 1003, CapEff=0, NoNewPrivs=1, Seccomp=2,
  `default_route_rc=1` / empty route, netns; probe script hash
  `f39a0302…d146cb` matches the pinned probe.
- GDB log: SITE `0x401304` → CAVE `0x4018e9` → AFTER `0x401309` → RET `0x401317`;
  `0x401000–0x402000` mapped `r-xp`; candidate stability c4a159… before/after.

## 2. Blocking findings

### B1 — successor binary not shipped; hash is only a claim

MESSAGE says `/usr/local/sbin/jobwrap-gate5` must hash to
`90af91ef6b238428d202f891e5829ed81733b76dd9e7f184acd91f4cd769ff20`, but no binary and no raw
`sha256sum` output is in the package. Record `51` R6 requires the wrapper hash/fixed argv to be
independently verified; I cannot re-hash absent bytes, and I cannot accept the MESSAGE hash as a
measurement.

### B2 — source commit `ac96e74` not reachable

MESSAGE cites `route-a/jobwrap-gate5/jobwrap_gate5.c` at git `ac96e74`, but that commit is not
reachable from the fetched remote refs, and the path is not on `origin/main`. The source/build
recipe therefore cannot be inspected or reproduced; this is exactly the failure mode that lost
`jobwrap_v3.c`.

### B3 — evaluator source path in raw GDB output

`gdb-probe.log` contains `/home/lab/evaluator/src/...CWE121...c` paths. This is not source content,
but it is evaluator-derived metadata that should not be needed in a Gate 5 evidence package.
Future evidence should record breakpoints/symbols without evaluator source paths; redact before
publication if the package is shared outside the guest/team.

## 3. What unblocks record 51

1. **M3:** push the successor source commit (`ac96e74` / current head) to a reachable branch and
   include the exact build recipe/compiler flags; include the successor binary in the next
   evidence zip (or a separate binary artifact) so M4 can re-hash it. If the binary must stay in
   the guest, include a raw `sha256sum` output plus a guest-signed/host-recorded attestation;
   absent bytes remain NOT VERIFIED.
2. **M3:** record the exact fixed argv (`jobwrap-gate5 probe m4-gate5 -- <repo> <work>`), the
   wrapper hash, and its isolation controls in the evidence.
3. **M5:** keep `51` unsigned; no Gate 5 PASS until M4 verifies B1/B2 and the raw probe rows.
4. **M4:** then fill only its rows PASS/FAIL/NOT VERIFIED; Lead approval follows; no final tag.

## 4. Status

| Item | Status |
|---|---|
| Gate 5 evidence receipt | PASS (29/29; probe rows independently check) |
| Successor binary hash | **NOT VERIFIED** (binary absent) |
| Successor source/build | **NOT VERIFIED** (commit unreachable) |
| Record `51` | UNSIGNED |
| Gate 5 | **BLOCKED** |
| Gate 4 | PASS (strict scope; unchanged) |
| V4 | model-level PASS (bounded 64; unchanged) |
| Fixture | **NOT FROZEN** |
| Final tag | none |

**Signature:** M4 review only; no Gate 5 signature.
