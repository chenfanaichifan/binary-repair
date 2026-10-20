# Fixture provenance — CWE121_src_char_declare_cpy_51b

Status: **candidate, built and measured 2026-10-20; proposed freeze 2026-10-21.**
Gate proofs 1–2 are done by Member 3; 3–5 are pending with Member 5; 6 is
partial (concrete counterexample accepted, symbolic detection blocked on V4).
Freeze record and the open items that must travel with the fixture:
`docs_BinaryRepair/fixture-freeze-record.md`. The hashes below are freeze
points: any rebuild invalidates approvals and must be announced to Member 4.

## 1. Source

| Field | Value |
|---|---|
| Test suite | NIST Juliet Test Suite for C/C++ v1.3 (release 2017-10-01) |
| Distribution URL | `https://samate.nist.gov/SARD/downloads/test-suites/2017-10-01-juliet-test-suite-for-c-cplusplus-v1-3.zip` (reachability checked: HTTP 206 on a ranged request, 2026-10-20) |
| Local archive | `~/evaluator/downloads/juliet-v1.3.zip`, 152,957,342 bytes |
| Archive SHA-256 | `ada9d7e1c323d283446df3f55bdee0d00bda1fed786785fe98764d58688f38eb` |
| Path inside suite | `C/testcases/CWE121_Stack_Based_Buffer_Overflow/s09/CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b.c` |
| Case file size | 1,434 bytes |
| Case file SHA-256 | `8387d64613192b47c30658153548d111366f232a0bf03714e26643dd16ad343b` |
| CWE | 121 — Stack Based Buffer Overflow |
| Flow variant | 51 — data passed as an argument between functions in different files |

The archive's SHA-256 is **computed locally**, not compared to an official
checksum file: no official checksum was retrieved. That is a provenance
limitation, not a claim of authenticity.

## 2. Why this case (shape A, source unmodified)

The Juliet string-copy cases hard-code their long string, so an argv harness
needs an entry point that already accepts the caller's buffer. The search was:

```bash
grep -l "badSink(char \* data)" ...   # then inspect each body
```

A scripted scan of all 5,906 CWE121 `.c` files found **12** sinks that satisfy
all three conditions at once:

1. parameter is `char * data`;
2. the body declares `char dest[N]`;
3. the body calls `strcpy(dest, data)` with no length check.

All 12 have `N = 50`. Raw output: `evidence/05-shape-search.txt`. This case was
chosen from the 12 because it is a single translation unit with no call chain
(`..._51b.c`), so the tested function is exactly the NIST sink and the harness
is one small `main`.

The NIST case file is compiled **byte-for-byte unmodified**; only the harness
and the support unit are added to the link.

## 3. Capacity and contract boundary

| Field | Value |
|---|---|
| Destination | `char dest[50]` — case file **line 28** |
| `DEST_CAPACITY` | **50 bytes** |
| Copy | `strcpy(dest, data)` — case file line 30, no bound |
| Maximum valid input | **49 bytes** (`len(data) + 1 <= 50`; `strcpy` writes the terminating NUL) |
| First invalid input | **50 bytes** (`len(data) + 1 = 51 > 50`) |

The off-by-one is explicit: a 50-byte input is *not* valid, because the copy
needs 51 bytes including NUL.

## 4. Harness

- Build input: `build/harness.c`, `build/build.sh`.
- `main` takes exactly one argument and calls
  `CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink(argv[1])`.
- **`argv[1]` is passed directly** — no `strdup`, no fixed-size staging buffer,
  no truncation and no length validation. The pointer points into the process
  initial stack, and the overflow happens in the sink's own frame.
- `argc != 2` prints `usage: ...` and exits 2. This is harness behaviour and is
  **not** part of the test manifest.
- The harness does not implement the invalid-input error path. The original
  binary must remain vulnerable; the error path is what a repair candidate
  must add.

## 5. Build

| Field | Value |
|---|---|
| Build date (UTC) | 2026-10-20 02:27:31 |
| Guest | Ubuntu 24.04.5 LTS, x86_64, kernel 6.8.0-147-generic |
| Compiler | gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0 |
| Complete flags | `-O0 -g -fno-stack-protector -fno-pie -no-pie -Wall` |
| Include path | `<juliet>/C/testcasesupport` |
| Link units | `harness.c`, the unmodified case `.c`, `<juliet>/C/testcasesupport/io.c` |
| Build script | `build/build.sh` (takes `JULIET_ROOT`, default `~/evaluator/src/juliet-v1.3`) |
| Harness SHA-256 | `2A1C9177A67DF3A63324704DC97F73780D85DF28D216ECCCB7066344D9FFDC14` (`build/harness.c`) |
| Build-script SHA-256 | `BD1B62B84A38C00C10EDCA5B980B255E36B1888A1F94C0D17C317A3AA4AF7ABE` (`build/build.sh`) |
| Output | `original.elf`, 26,792 bytes |
| ELF SHA-256 | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| Build ID | `a39b24de7d9fba70a130a90a7d79fa4a3a8c85ce` |

Stack protection is deliberately disabled at build time (`-fno-stack-protector`)
so the overflow can reach the saved frame. That is a fixture build decision,
not an adapter removing a protection from a supplied binary. NX and RELRO are
left at the toolchain defaults and are reported below; the CET property notes
are present.

## 6. Machine check (measured, not inferred)

| Property | Value | Evidence |
|---|---|---|
| Class | ELF64 | `readelf -h` |
| Data | 2's complement, little endian | `readelf -h` |
| Type | `EXEC` (non-PIE) | `readelf -h` |
| Machine | `Advanced Micro Devices X86-64` | `readelf -h` |
| Entry point | `0x401170` | `readelf -h` |
| PIE | No PIE (0x400000) | `checksec` |
| NX | enabled | `checksec` |
| RELRO | Partial RELRO | `checksec` |
| Stack canary | none | `checksec` |
| CET notes | SHSTK enabled, IBT enabled | `checksec` |
| Stripped | no | `checksec` / `file` |
| Debug info | yes | `checksec` / `file` |
| Process / thread model | single process, single thread; no thread creation in harness or case | source inspection |

Evidence: `evidence/02-readelf-h.txt`, `02-readelf-l.txt`, `02-checksec.txt`.

## 7. Function under test and code regions

| Symbol | Address | Size | Role |
|---|---:|---:|---|
| `CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink` | `0x4012b0` | 0x68 (104 B) | **function under test** (Juliet) |
| `main` | `0x401256` | 0x5a (90 B) | harness entry point |
| `printLine` | `0x401380` | 0x26 (38 B) | Juliet support (`io.c`) |

The harness contributes the new instruction region **0x401256–0x4012af**
(90 bytes, immediately before the sink). It is fixture infrastructure, **not**
part of the repair scope and not a candidate patch location. The sink starts
at `0x4012b0`; its disassembly is in `evidence/02-objdump-badsink.txt`.

## 8. Binary-level violation

| Input | Observed on `original.elf` |
|---|---|
| 49 × `A` | exit 0, stdout = 49 × `A` + `\n`, stderr empty |
| 50 × `A` | exit 0, stdout = 50 × `A` + `\n`, stderr empty — **silent 1-byte out-of-bounds write** (51 bytes written into a 50-byte object; the extra byte lands in frame padding) |
| 100 × `A` | **SIGSEGV, exit 139**, stdout empty, stderr empty |

Crash evidence with GDB, 100 × `A`:

```text
Program received signal SIGSEGV, Segmentation fault.
0x0000000000401317 in ..._badSink (data=0x7fffffffed36 'A' <repeats 100 times>) at ...:33
#0  0x0000000000401317 in ..._badSink ...
#1  0x4141414141414141 in ??
rbp  0x4141414141414141
rip  0x401317  <..._badSink+103>
```

The saved frame pointer is overwritten with `0x4141414141414141` and the
return path is taken from attacker bytes. Raw output:
`evidence/04-gdb-crash-100.txt`; boundary sweep: `evidence/03-run-boundary.txt`.

Running the frozen manifest against the original (`build/run_manifest.py`) gives
**4/6 passed**: the four valid cases pass byte for byte, both invalid cases
fail (length 50 exits 0 with the wrong stdout; length 100 is killed by
SIGSEGV). That is the expected V0 shape — the manifest is not supposed to pass
on the vulnerable binary. Raw output: `evidence/06-manifest-vs-original.txt`.

The 50-byte case is the important negative: the program **has no error path**
for an out-of-capacity copy and exits successfully, which is exactly the
defect. A crash is not the only violation evidence; the absence of a defined
rejection is the other half.

## 9. Behaviour table used by the manifest

Valid inputs reproduce the original program's behaviour (measured):

| Length | exit | stdout | stderr |
|---:|---:|---|---|
| 0 | 0 | `\n` | empty |
| 1 | 0 | `A\n` | empty |
| 10 | 0 | `AAAAAAAAAA\n` | empty |
| 49 | 0 | 49 × `A` + `\n` | empty |

For length > 49 the **required repaired behaviour** (frozen contract) is:
exit 1, stdout empty, stderr exactly
`ERROR: input exceeds destination capacity\n`. The original does not meet it
(length 50 exits 0; length 100 crashes). The manifest's invalid cases encode
the target behaviour, not the original's observed behaviour; see
`tests/README.md`.

## 10. Evaluator-only boundary

The following are evaluator-side and must **not** enter the repair input or a
model prompt:

- `build/harness.c` and `build/build.sh`;
- the NIST case `.c` (stays in `~/evaluator/src/juliet-v1.3`, never copied
  into the repair workspace);
- `evidence/` and this provenance record.

The repair input is `original.elf` plus the reviewed contract and the frozen
test manifest only.

## 11. Evaluation limitation (public source)

This is a public NIST Juliet case with public `good()` counterparts. A model
may recognise the suite, the template family, or the intended fix pattern
from training data. Any repair result on this fixture therefore cannot
establish that the model independently analysed the binary. This limitation
must be stated wherever the fixture's results are reported; it is an
evaluation limitation, not a correctness claim about the patch.

## 12. Reproduce

```bash
export JULIET_ROOT=~/evaluator/src/juliet-v1.3
cd build
bash build.sh ./original.elf
sha256sum ./original.elf   # aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393
```

Any change to the case hash, flags, harness, or compiler version produces a
different ELF and therefore a new freeze point.

## 13. Open items that must travel with the frozen fixture

These are **not** satisfied by the fixture build. They are recorded here so a
freeze cannot be read as "V4 ready" or "isolated execution ready".

### 13.1 V4 is blocked

The guest has no angr/Claripy/Z3, no LIEF, no clang, and no Ghidra/JDK.
Capstone and pyelftools are present but only import-tested. Bounded symbolic
verification (V4) cannot run today; it must be reported as `unsupported` or
deferred with this reason, never as passed.

### 13.2 Isolation must be repaired before any candidate runs

Current guest gaps, measured:

1. **zero snapshots** — the 2026-10-20 resize deleted `clean-toolchain`; there
   is no reset point;
2. `lab` has passwordless sudo — jobs are not unprivileged;
3. NAT is reachable and there is no per-job egress block;
4. tools are not on a read-only mount separate from the job workspace.

At minimum, (1) a fresh snapshot, (2) network cut, and (3) an unprivileged
execution user must be in place before a candidate binary is executed. These
block "run a candidate", not the fixture build.

### 13.3 Gate 6 is partial

The manifest run against the original (4/6) is **V0/V3 behaviour evidence**
that the original is vulnerable. It is **not** gate 6. Gate 6 needs a detection
mechanism:

- accepted partial: the concrete counterexample and crash record
  (100 × `A` → SIGSEGV, `rip = 0x401317`, saved `rbp`/return slot overwritten
  with `0x4141414141414141`, `evidence/04-gdb-crash-100.txt`);
- pending: symbolic detection of the out-of-bounds write on the original,
  which depends on 13.1.

Member 4 owns gate 6 and is escalating 13.1/13.2 to the team lead.
