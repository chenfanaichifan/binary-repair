# Fixture freeze record — CWE121_src_char_declare_cpy_51b

**Status:** pre-freeze, 2026-10-20. Planned freeze date **2026-10-21**.
This record becomes effective only when the sign-off table in §6 is complete
and gates 3–5 have passed. Until then the fixture is a candidate.

## 1. Frozen artifacts

| Artifact | Identity |
|---|---|
| Case | `CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b` (Juliet C/C++ 1.3, s09) |
| Case source SHA-256 | `8387d64613192b47c30658153548d111366f232a0bf03714e26643dd16ad343b` |
| `original.elf` | 26,792 bytes, SHA-256 `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| `tests/valid.json` | SHA-256 `17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76` |
| `tests/invalid.json` | SHA-256 `d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d` |
| Harness / build | `build/harness.c`, `build/build.sh` (hashes in `provenance.md` §5) |
| Evidence | `evidence/01`–`07` |

Changing any row above creates a new freeze record and invalidates approvals.

**Integrity check, 2026-10-20:** `SHA256SUMS` verified from the working copy —
24 entries, 24 match, 0 mismatch, 0 missing (gate 6 evidence `07` and its GDB
command record `07-gdb-commands.txt`, plus the V3 judging code
`tests/v3_oracle.py` and `tests/test_v3_oracle.py`).

The judging code is in the integrity list so that a later edit to the
assertions is visible, but it is **not** part of the frozen oracle: the frozen
expectations are `tests/valid.json` and `tests/invalid.json`, and §2's contract
is what they encode.

## 2. Contract and oracle

- `DEST_CAPACITY = 50` (`char dest[50]`, case line 28); maximum valid length
  **49**, first invalid **50**.
- valid: reproduce the original's measured stdout and exit 0.
- invalid: exit **1**, stdout empty, stderr exactly
  `ERROR: input exceeds destination capacity\n`.
- V0: the original scores **4/6** on the manifest (valid pass, invalid fail);
  this is behaviour evidence, not gate 6.
- V3: a repaired candidate must score **6/6**, with byte-identical stderr on
  both routes.

## 3. Gate status at pre-freeze

| Gate | Owner | Status | Evidence |
|---|---|---|---|
| 1. valid-input domain | Member 3 | **done** | 0–49 measured, `evidence/03-run-boundary.txt` |
| 2. binary-level violation | Member 3 | **done** | 100 × `A` SIGSEGV, `evidence/04-gdb-crash-100.txt` |
| 3. Route A patch feasibility | Member 5 | **pending** | — |
| 4. Route B unchanged round trip | Member 5 | **pending** | — |
| 5. safe placement, both routes | Member 5 + Member 3 | **pending** | — |
| 6. verifier detects original violation | Member 4 | **partial** | concrete counterexample accepted (`docs_BinaryRepair/gate6-crash-summary.md`, `evidence/07-gate6-crash-evidence.txt`); symbolic pending V4 |

Gates 3–5 run on the **candidate** ELF, not on a frozen artifact. The freeze
is the hash lock that happens after they pass; it is not a prerequisite for
the gate work. Handoff note: `docs_BinaryRepair/candidate-handoff-to-member-5.md`
(integrity list: the fixture's `SHA256SUMS`). If the candidate fails a gate,
the sample is replaced before freeze — pass/fail therefore does not invalidate
the current hashes until a new build is made.

## 4. Open items at freeze (explicit, not implied)

### O1 — V4 is blocked

Missing in the guest: angr/Claripy/Z3, LIEF, clang, Ghidra/JDK. V4 cannot run;
it must be reported `unsupported`/deferred with this reason. Owner: Member 3
for installation, Member 4 for the V4 verdict. Exit condition: all five
installed and smoke-tested on a **new** clean snapshot.

### O2 — Candidate execution is not yet isolated

1. ~~zero snapshots~~ — **resolved 2026-10-20 10:57**: `clean-toolchain`
   (uid 3) exists as a powered-off reset point, but it was taken **after** the
   10:27 fixture build, so it is a reset point, not a pre-sample baseline (see
   `vm-profile.md` §3);
2. `lab` has passwordless sudo;
3. NAT is reachable, no per-job egress block;
4. tools are not read-only to the execution user.

At minimum network cut + unprivileged user + read-only tools must be fixed
**before any candidate binary runs**. Owner: Member 3; blocks "run candidates",
not the fixture build.

### O3 — Image hash captured

Hashes taken on 2026-10-20 with the VM powered off (no `vmware-vmx` process):

```text
30068de303b2a9a9c187a3c2980f1b988b8d6b433c32402fe911eadc1899b0d2  disk.vmdk          (3,378,184,192 B)
8521f4e854d7cac4f607d0208ccd08b9d8121fe68015c7392badb3474d38ce89  disk-000001.vmdk   (3,997,696 B, delta created with the 10:57 snapshot)
9a1e3959c9f4ad9d4752101fd4ff9a43191fb7d72e61fa20e033f9fd235ce794  noble-cloudimg.vmdk
```

Limits that must travel with these values: a VMDK is a growing sparse file, so
each hash identifies **those bytes at that timestamp**, not reproducible guest
content. Re-verify immediately before freeze and again in V5; never present a
hash taken while the guest runs. Owner: Member 3.

### O4 — Backend commit unknown

`D:\BinRepair` became a Git repository on 2026-10-20 (`.git` copied from the
working copy at `%USERPROFILE%\Desktop\binary-repair`, branch
`member-3-route-a`, HEAD `e030cc2`), but **no commit exists on the D: working
copy** and `git fetch` / `push` fail with `SEC_E_NO_CREDENTIALS`. No backend
commit hash can be recorded until both are fixed. Owner: project lead /
Member 3.

## 5. Freeze conditions

The fixture freezes on 2026-10-21 only if:

1. gates 3–5 are signed by Member 5;
2. Member 4 confirms gate 6 as `partial` (concrete counterexample accepted,
   symbolic deferred) rather than complete;
3. O1 and O2 are acknowledged by the team lead as open items in the progress
   demonstration — the freeze must not read as "V4 ready" or "isolated";
4. no artifact hash in §1 has changed.

## 6. Sign-off

| Role | Name | Decision | Date |
|---|---|---|---|
| Member 3 (fixture) | | | |
| Member 5 (routes) | | | |
| Member 4 (verification) | | | |
| Team lead | | | |

V4 blocking and the isolation gaps are escalated by Member 4; this record is
the durable copy so they cannot be lost in chat.
