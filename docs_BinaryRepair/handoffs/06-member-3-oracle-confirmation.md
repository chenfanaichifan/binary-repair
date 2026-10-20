# To member 3: oracle confirmation and gate 6 clarification

**Recipient:** Member 3 (fixture and execution environment)
**From:** Verification slice (Member 4)
**Date:** 2026-10-20
**Re:** your reply of 2026-10-20, "fixture, manifest and VM deliverables"
**Status:** Oracle confirmed with one execution detail; gate 6 definition corrected; two project-level risks escalated to the lead.

---

## 1. Oracle: confirmed, with one execution detail

I confirm the frozen oracle exactly as you stated:

- **valid** (`len <= 49`): reproduce the original binary's measured stdout and exit code;
- **invalid** (`len >= 50`): exit **1**, stdout **empty**, stderr exactly
  `ERROR: input exceeds destination capacity\n`.

The length rule is consistent with the contract: `DEST_CAPACITY = 50`, `strcpy` also writes
the NUL terminator, so the largest valid input is `49` and the first invalid input is `50`.

**One execution detail to keep the evidence consistent.** The original binary does **not**
exit 1 on invalid input: it crashes with SIGSEGV. The manifest's expected values describe the
**repaired** behaviour. Therefore:

- original binary vs manifest -> **4/6**, valid cases pass, invalid cases fail (SIGSEGV).
  This is the expected V0 shape for a vulnerable binary, not a manifest bug.
- repaired candidate vs manifest -> must be **6/6**, with byte-identical stderr on both routes.

I will assert exactly this. If `ERROR_STDERR` ever needs to change, it must change before the
freeze; after freeze it costs a new manifest and new approvals.

## 2. Gate 6: "manifest 4/6" is not gate 6 evidence

You asked whether "original fails the invalid cases" counts as my gate 6 evidence.
**Not on its own.** These are two different things:

- **manifest 4/6** = V0/V3 behavioural evidence that the original program violates the contract;
- **gate 6** = a verifier that *detects* the original violation.

Gate 6 evidence should be one of:

- **(a) concrete counterexample with crash evidence**: `100 x 'A' -> SIGSEGV`, plus the crash
  address, the GDB backtrace, and the record that the saved return address / stack frame was
  overwritten;
- **(b) symbolic detection**: angr finds an out-of-bounds write path on the original binary.

I can supply **(a)** now. **(b) depends on V4 tooling and is currently blocked** (see §3).
I will label gate 6 as "concrete evidence provided, symbolic detection pending V4". I will not
present the manifest 4/6 result as gate 6 passing.

**Update (2026-10-20): concrete evidence received and verified.** Member 3 supplied the crash
record, the GDB command log, a summary, and `SHA256SUMS`. M4 recomputed the hashes from the
delivered archive and they match: raw record `07-gate6-crash-evidence.txt` (3,750 bytes) =
`4bab2214e5a17272bb32c20972e3d9ccc422c93e9853cbf89346dbbdf5eb16d9`; command log =
`b2fc52f7f5964b13ef2d0375c04b474acd55075b75ae631e8a12402ca3612242`; summary =
`a398821ee1e162edf5837eec62b534d9d1bfdc8f1612dbdc4cef92c96382d8ab`. The files are stored at
`fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/`. Content check: `100 x 'A'` ->
SIGSEGV reproduced **5/5**, exit **139**; after `strcpy`, `[rbp] = [rbp+8] =
0x4141414141414141`; faulting instruction `ret` @ `0x401317`; backtrace #1
`0x4141414141414141`; guest Ubuntu 24.04.5, kernel 6.8.0-147, ASLR on. Original ELF sha256:
`aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`. This satisfies gate 6
criterion (a), the concrete counterexample. Symbolic detection (b) still depends on V4 tooling
(§3). Report gate 6 as **partial**, never complete.

## 3. Two project-level risks I am escalating to the lead

These are not solvable between us; I am reporting them, not asking you to fix them alone.

1. **V4 is fully blocked.** The guest has no angr/Claripy/Z3, no LIEF, no clang, and no
   Ghidra/JDK. V4 (bounded symbolic security) is a core F4 acceptance item, so the MVP cannot
   satisfy F4 until the toolchain is installed and smoke-tested. This needs a lead decision:
   install and when, or record V4 as `unsupported` with the missing-backend reason.
2. **The guest is not yet a compliant disposable environment.** Passwordless sudo,
   reachable outbound NAT, zero snapshots after the resize, and tools not on a read-only mount.
   These do not block fixture construction, but they block executing any candidate. Before the
   first candidate enters the guest, at least the snapshot reset, the job-time network block,
   and the unprivileged execution user must be fixed.

## 4. Confirmation you asked for

- I will run **V3 against both routes with this one manifest**, asserting identical stderr
  bytes and exit codes.
- I accept gates 1 and 2 as done (valid domain 0-49 measured; 100 x 'A' -> SIGSEGV).
- I will report the original-vs-manifest 4/6 shape as V0 evidence, separate from gate 6.

## 5. Freeze date

`2026-10-21` is acceptable **only if** gates 3-5 land first. Those are owned by member 5 and
require a real ELF, so the candidate ELF you already built should be shared with member 5 as a
**not-frozen candidate** now; freezing should follow successful feasibility, not precede it.

If gates 3-5 are not ready by 2026-10-21, freeze the fixture anyway and record the
feasibility proofs as outstanding. A frozen fixture with a recorded outstanding proof is honest;
an unfrozen fixture with a moving hash blocks everyone downstream.

## 6. Evaluation limitation

Accepted and required. The Juliet 1.3 case and its `good()` counterparts are public, so a
model may recognise the intended fix from training data. Every reported result on this fixture
must carry that limitation next to it; it is not evidence of independent binary analysis.
