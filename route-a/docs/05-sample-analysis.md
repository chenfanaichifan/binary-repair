# 05 — Shared public sample and vulnerable function

Work items 5–6. Status: **candidate selected and analysed (2026-10-20);
not frozen** — planned freeze 2026-10-21 after gates 3–5 pass. The durable
record is `docs_BinaryRepair/fixture-freeze-record.md`.

## Purpose

Pick the one public sample the whole team will use for both routes, then explain
the vulnerability at the binary level.

## Sample selection record

| Field | Value |
|---|---|
| Sample name / case ID | `CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b` |
| Source | NIST Juliet Test Suite for C/C++ v1.3 (2017-10-01), path `C/testcases/CWE121_Stack_Based_Buffer_Overflow/s09/` |
| Suite archive SHA-256 | `ada9d7e1c323d283446df3f55bdee0d00bda1fed786785fe98764d58688f38eb` (`juliet-v1.3.zip`, 152,957,342 B, computed locally; not compared against an official manifest) |
| Case file SHA-256 | `8387d64613192b47c30658153548d111366f232a0bf03714e26643dd16ad343b` (1,434 B) |
| Build command | `build/build.sh`, gcc `-O0 -g -fno-stack-protector -fno-pie -no-pie -Wall`, linking `harness.c` + the unmodified case `.c` + `testcasesupport/io.c` |
| Compiler / libc at build time | gcc 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1), libc6 2.39-0ubuntu8.9 |
| Build date and builder | 2026-10-20 02:27:31 UTC, Member 3, in guest `binrepair-vm` |
| SHA-256 of the ELF | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` (26,792 B) |
| Build ID | `a39b24de7d9fba70a130a90a7d79fa4a3a8c85ce` |
| Evidence the defect is reachable | length 50 → silent out-of-capacity write, exit 0; length 100 → SIGSEGV, saved `rbp` and return slot overwritten with `0x41…41` (`evidence/03-run-boundary.txt`, `04-gdb-crash-100.txt`) |
| Team decision reference | freeze record §6 sign-off table (open); gates 3–5 owned by Member 5 |

Selection gate from the technical design — a candidate sample is usable only if
all of these hold:

- [x] It has a meaningful valid-input domain — lengths 0–49, measured, with
      stdout echoing the input. Rejecting every input is not a fix.
- [x] The violation is observable at the binary level — silent overwrite at 50,
      crash at 100, saved frame in the backtrace.
- [ ] Route A patch feasibility is plausible — **pending, gate 3 (Member 5)**.
- [ ] Route B unchanged round trip is plausible — **pending, gate 4 (Member 5)**.
- [x] A verifier can detect the original violation — concrete counterexample
      accepted by Member 4; symbolic detection pending V4 (gate 6 is
      `partial`, not complete).

## Vulnerability analysis

- **Vulnerable function:**
  `CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink`
  at `0x4012b0`, 104 bytes. Case source is compiled **byte-for-byte
  unmodified**; the case file has no `main`, and `build/harness.c` supplies one.
- **What the code does:** copies the `data` argument into a local
  `char dest[50]` with `strcpy`, then prints the **source** string through
  `printLine`.
- **Copied data / destination buffer size:** unbounded caller string → 50 bytes.
- **Missing or insufficient check:** there is no length check before
  `call strcpy@plt` at `0x401304`.
- **Overwrite distance to the saved frame:** `&dest` → saved `rbp` = 64 bytes;
  → saved return address = 72 bytes (see `04-instruction-inspection.md`).
- **Deterministic crash input (length):** 100 bytes of `A` → SIGSEGV.
- **Observable effect:** length 50 exits 0 with a silent one-byte-over-capacity
  write; length 100 exits 139 (SIGSEGV) with `rbp = 0x4141414141414141` and
  `rip = 0x401317` (`ret`).

### Contract sketch (reviewed by Member 4, frozen in the manifests)

| Element | Value |
|---|---|
| Valid-input domain | `argv[1]` length 0–49 inclusive; no character constraint found in the case |
| Expected behaviour on valid input | exit 0, stdout = the input bytes followed by `\n`, stderr empty — **measured on `original.elf`**, not invented |
| Forbidden behaviour | any out-of-bounds write for length ≥ 50 |
| Required response to invalid input | exit **1**, stdout empty, stderr exactly `ERROR: input exceeds destination capacity\n` |

The invalid path is a **post-repair contract**: the original has no rejection
path, so it fails both invalid cases (length 50 exits 0; length 100 dies with
SIGSEGV). Running the manifests against the original therefore yields **4/6**
and that is V0 behaviour evidence, **not** gate 6 and not a repair result.

## Honesty rules applied here

- Every figure above points at a captured file under
  `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/` or at
  `provenance.md`.
- The rehearsal fixture (`route-a/build/rehearsal-01/`, `char buffer[16]`) was a
  separate local exercise. It is **not** evidence for this fixture and none of
  its figures appear above.
- **Evaluation limitation:** Juliet 1.3 is public and the `good()` counterparts
  are public, so a model may recognise the case and its intended fix from
  training data. Results on this fixture cannot support a claim of independent
  binary analysis, and this sentence must appear next to any reported result.

## Evidence

- `fixtures/public/CWE121_src_char_declare_cpy_51b/provenance.md`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/SHA256SUMS` (20 entries,
  verified 2026-10-20)
- `fixtures/public/CWE121_src_char_declare_cpy_51b/tests/README.md`,
  `valid.json`, `invalid.json`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/03-run-boundary.txt`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/03-no-arg.txt`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/04-gdb-crash-100.txt`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/06-manifest-vs-original.txt`
- `docs_BinaryRepair/fixture-freeze-record.md`
- `docs_BinaryRepair/candidate-handoff-to-member-5.md`
