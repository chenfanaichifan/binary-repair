# 51 — Gate 5 Route A runtime placement record (UNSIGNED — NOT VERIFIED)

**Record owner:** M4 (independent verifier; Route A half of Gate 5)
**Gate:** Gate 5 — safe placement, Route A runtime
**Date opened:** 2026-10-29 (Asia/Hong_Kong)
**Status:** **UNSIGNED — NOT VERIFIED.** The probe window has been requested (`docs/handoffs/50`)
but has not happened. No result is claimed here; Gate 5 remains `pending`.
**Subject:** candidate `routea/out/cave-probe.elf` (Route A), SHA-256
`c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82`; original
`fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf`, SHA-256
`aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`.
**Probe:** M4-authored `scripts/m4_gate5_probe.py`, executed by M3/VMer inside the disposable
guest under jobwrap (uid 1003, CapEff=0, NoNewPrivs=1, no egress).
**Scope:** Gate 5 Route A runtime placement only. Not Gate 4, not V3/V4 acceptance, not a repair
claim; fixture remains `NOT FROZEN`.

**Identity/independence limitation (recorded per Lead instruction, 2026-10-29):** the M4
independent verifier and the Lead are the **same person/operator** (two AI windows of one person,
analogous to the already-recorded VMer = M3 in a separate AI window). The M4 verifier row and the
Lead approval row are therefore **not independent two-person signatures**; this record must not
be presented as independent human review. If the client requires a genuinely independent second
person for approval, that requirement is **not satisfied** by the current setup.

**Invocation status:** M5's `routeb/jobwrap_gate5.sh` (reported SHA-256 `859ac8fe…`) and M4's
fixed launcher `scripts/m4_gate5_fixed.sh` (SHA-256
`B751BB7FB0A03596C750E8BFD8F43EF4B87FB68A96E2A65F62B2BB8F66E313C5`) are available, but **no
guest run has happened**. The wrapper's caller-supplied `GATE5_SCRIPT` must be hard-coded or
hash-validated by M5; until then the invocation is not fully fixed. Direct execution is
forbidden; a missing controlled invocation is `NOT VERIFIED`.

**P3B note:** the P3B provenance hold (`docs/handoffs/53` §1) does not change this Gate 5 record;
Gate 4 P3B rows stay `NOT VERIFIED`/not accepted, and no P3B pass is written here.

## 1. Result rows (fill only after the probe; only PASS / FAIL / NOT VERIFIED)

| ID | Check | Expected | Observed | Verdict | Evidence (file + SHA-256) |
|---|---|---|---|---|---|
| R1 | identity hashes | candidate `c4a159…aa82`, original `aa428157…8393`, script hash matches | — | NOT VERIFIED | — |
| R2 | runtime mapping | `0x401000–0x401fff` mapped `r-xp` | — | NOT VERIFIED | — |
| R3 | memory = file | cave `0x4018e9–0x401fff` memory bytes equal candidate file bytes (1815 B) | — | NOT VERIFIED | — |
| R4 | breakpoints / execution | `0x401304` → `0x4018e9` → `0x401309` → `0x401317` reached; cave decode; no early crash | — | NOT VERIFIED | — |
| R5 | six frozen cases | 6/6 byte-exact rc/stdout/stderr per frozen manifests | — | NOT VERIFIED | — |
| R6 | isolation attestation | snapshot/revert, uid 1003, CapEff 0, NoNewPrivs 1, no egress, evaluator unreadable, wrapper fixed argv | — | NOT VERIFIED | — |
| R7 | candidate stable | candidate SHA-256 before = after | — | NOT VERIFIED | — |
| R8 | evidence manifest | returned `SHA256SUMS` verifies every file; evidence-manifest SHA-256 recorded | — | NOT VERIFIED | — |

**Overall:** NOT VERIFIED (no probe window executed).

## 2. Exact commands / evidence custody (fill at run time)

```text
window: snapshot=<name/id> chain_manifest=<sha256> revert=<raw log file + sha256>
jobwrap: <path> <sha256>; invocation=<exact command>
workdir: <path>
candidate_before=<sha256> candidate_after=<sha256>
probe script: scripts/m4_gate5_probe.py sha256=<sha256>
SHA256SUMS sha256=<sha256> (evidence-manifest hash)
```

- M4 re-hashes every returned file; M3's/VMer's summary is not used as the result.
- Raw evidence is not committed to the repo; the record cites filenames + hashes.
- A missing control (R6) makes the whole record `NOT VERIFIED` even if R2–R5 look correct.
- A measured contradiction (memory ≠ file, breakpoint missing, case mismatch, hash change) is
  `FAIL`, diagnosed with the exact case/bytes, never "adjusted".

## 3. Signature and closure order

| Role | Name | Date | Signature |
|---|---|---|---|
| M4 verifier | M4 | — | — (blank; not signed) |
| Lead approval (Gate 5) | Lead | — | — (blank) |
| M5 (Route B half of Gate 5) | M5 | — | — (separate record; does not sign this one) |

Gate 5 may be called `PASS` only when this record has all rows PASS, M4's verifier row is signed,
and the Lead approves. Until then it stays `pending` and **unsigned**. Gate 4 JOIN-1 stays
separate and waits for `P4` + M5's record + a real p2 exit 0.
