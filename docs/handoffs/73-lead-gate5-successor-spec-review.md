# 73 — Lead/M4 review of Gate 5 successor spec (`66-gate5-successor-spec-draft-2026-10-31.md`)

**From:** Lead / M4 (same operator; role-separated, not human-independent)
**To:** M3, M5, M3/VMer, M4
**Date:** 2026-10-31 21:50 (Asia/Hong_Kong)
**Re:** `66-gate5-successor-spec-draft-2026-10-31.md` (DRAFT, SHA-256 not yet pinned)
**Status:** **DRAFT approved for implementation with required corrections**; not implemented,
not compiled, not a Gate 5 pass. Gate 4 old chain untouched.

## 1. Decision

Path 4 is correct: keep old `jobwrap b232d60b…` for Gate 4; build a separate fixed-argv
`jobwrap-gate5` successor bound only to Gate 5; no P4 re-run/re-sign. The draft's architecture is
accepted, subject to the corrections below.

## 2. Corrections required before implementation

### 2.1 B2 is already resolved on current main

The draft says `routeb/jobwrap_gate5.sh` lacks `GATE5_SCRIPT_SHA256` validation. That is stale:
on `main 99db9c9`, the wrapper **already has** fail-closed `GATE5_SCRIPT_SHA256` validation
(64-hex format check + mismatch exit 1). Exact current blob hashes:

| File | SHA-256 (git blob, main 99db9c9) |
|---|---|
| `scripts/m4_gate5_probe.py` | `F39A0302DD1AA42635DA80FA4E9160D37A221F5AC383270ADD3EAEDCFFD146CB` |
| `scripts/m4_gate5_fixed.sh` | `B751BB7FB0A03596C750E8BFD8F43EF4B87FB68A96E2A65F62B2BB8F66E313C5` |
| `routeb/jobwrap_gate5.sh` | `FB5FD90B50D912E6F646F7390D5015C5206ABA81E6AF38D7FAB91CE06B14C4F0` |

(B2 is still relevant only if the successor uses the shell wrapper; the direct-probe design in
§2.2 avoids the double chain.)

### 2.2 Open point 1: pin the exact probe script at compile time — option (a)

**Choose (a): compile-time pin of `scripts/m4_gate5_probe.py` =
`F39A0302DD1AA42635DA80FA4E9160D37A221F5AC383270ADD3EAEDCFFD146CB`.**

- Successor executes **absolute** `/usr/bin/python3 <repo-root>/scripts/m4_gate5_probe.py
  <repo-root> <work-dir>`; no shell, no PATH lookup, no `GATE5_SCRIPT` environment variable.
- The hash is a `const` in `.rodata`; verify the script bytes **before** dropping privileges and
  before exec; mismatch/missing → non-zero exit, no fallback.
- If the wrapper is retained instead, pin **both** `m4_gate5_fixed.sh` (`B751…`) and make the
  wrapper hash-check the probe; direct-probe pin is simpler and preferred.
- Reject option (b) (env variable) — caller-controlled, weakens fail-closed.
- Option (c) root-owned pin file is acceptable as a secondary mechanism, but not needed for the
  first implementation; if used, it must itself be root-owned and hash-bound.

M4 freezes `m4_gate5_probe.py` at the hash above for this successor. Any later probe change
requires a new successor build/hash and a new Gate 5 record.

### 2.3 Open point 2: semantic equivalence, not byte-equivalence

Accepted: the successor must implement the **same controls** (root-only launch, netns/no egress,
setgroups→setgid(1003)→setuid(1003), CapEff=0, seccomp filter, NoNewPrivs=1, rlimits, minimal
clearenv, fixed argv) and expose raw isolation attestation. Byte-for-byte equivalence to the lost
old wrapper is impossible and is **not required**.

Additional hardening required:

- require `euid==0` for the successor; refuse otherwise;
- canonicalize `<repo-root>`/`<work-dir>`; reject symlink tricks; record absolute paths;
- script must be root-owned/not writable by uid 1003; hash before privilege drop;
- avoid hash-then-exec TOCTOU where feasible (same fd / `fexecve`, or root-owned immutable file);
- no `system()`, `sh -c`, `popen`, or caller command; fixed argv only;
- no inherited dangerous env; `clearenv` + minimal whitelist;
- fail closed on missing/mismatch hash, wrong argv, non-root, or failed isolation setup;
- do not overwrite/delete `/usr/local/sbin/jobwrap` (old hash for Gate 4).

### 2.4 Open point 3: source in git — yes

The successor source and an exact build recipe (compiler version, flags, guest build commands)
must be committed to git; derived `jobwrap_v3_reconstructed.c` is archival only and must not claim
hash equivalence. No host compilation; guest only.

### 2.5 Deliverables/records

- Successor binary hash computed from guest bytes, then recorded in Gate 5 record `51` and
  `SHA256SUMS`; never inferred from chat.
- Gate 5 evidence binds the new binary + frozen probe hash; Gate 4 record continues to bind
  `b232d60b…`; no P4 re-sign.
- Add failure-mode evidence: missing hash, mismatch, non-root, wrong argv, script swap attempt.
- `51` remains unsigned until M4 independently verifies raw guest output and Lead approves.
- No final MVP tag/fixture freeze from this spec.

## 3. Approval

**Approved for implementation only after M3/M5 revise the draft per §2.1–§2.5.** This is not a
Gate 5 pass and not a signature on implementation.

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead (spec review) | Lead | 2026-10-31 | **conditional approval for implementation**; direct-probe pin F39A…D146CB; no Gate 5 pass |
| M4 (independent verification) | M4 | — | pending raw guest evidence |
| M3/VMer (guest build/run) | M3/VMer | — | pending revised spec/build |
| M5 (source/build recipe) | M5 | — | pending revised spec/source |
