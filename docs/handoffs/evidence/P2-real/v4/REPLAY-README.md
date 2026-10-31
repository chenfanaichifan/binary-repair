# V4 raw evidence — TRUE symbolic replay package (Standard B)

Date: 2026-10-31 (rework v3, after M4 review 63)
From: M3 (producer)
To: M4 (independent verifier), Lead
Re: Lead ruling `docs/handoffs/62-lead-v4-acceptance-standard.md` (Standard B)

---

## 0. What changed since the rejected v12 harness

The v12 harness (rejected by M4 review 63, confirmed by M5 v12 consume) had two
defects.  This rework fixes both, from first principles:

| Defect (M4 §2) | v12 harness | This rework |
|---|---|---|
| "symbolic" input was concretized | `'A'*49+NUL` / `'A'*57+NUL` concrete bytes | `claripy.BVS` kept symbolic; only "a NUL occurs somewhere" constrained |
| solver did no real work | sat=0, eval=1, one concrete run | angr explores every possible NUL position → 50 distinct symbolic states per route |
| strcpy hook masked the repair | `strcpy@plt` hooked with a length model | only libc boundaries (strcpy/printLine/fprintf) hooked; the repair's own hand-written strlen + guard runs as REAL symbolic code |
| no per-route entry map | fixed `0x4012b0` for all | `nm`-measured entry + recorded redirect (Route A `call@0x401304->0x4018e9`, Route B `jmp@0x4012b0->0x4018ec`) |
| incomplete accounting | thin | found/avoided/active/deadended/errored + solver tally + distinct_strlen |

This package does **not** claim V4 is `passed`.  Per Standard B, an independent
role must replay this and the Lead must approve.  M3 publishes the raw material
and an honest statement of what it does and does not prove.

---

## 1. Candidate and original hashes (frozen bytes)

| binary | SHA-256 | role |
|---|---|---|
| `original.elf` | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` | defective fixture |
| `routea-candidate.elf` | `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` | Route A candidate |
| `routeb-candidate.elf` | `208574ab5b7753fab6f28860830069770622fb7b1fcb8d181fa50453f8656717` | Route B fixed candidate |

All three are 26792 bytes.  `nm` confirms `badSink` = `0x4012b0` in all three.

## 2. Environment (versions the verifier must reproduce)

- angr `10.0.4.post1` (guest `/opt/angr-venv`)
- z3-solver `5.1.0`
- claripy: angr's bundled rustylib claripy (`import angr.claripy as claripy`)
- guest: Ubuntu 24.04.5, kernel 6.8.0-147-generic; Python 3.12 (venv `/opt/angr-venv`)

## 3. Measured repair semantics (the model is derived from these facts)

`nm`/`readelf`/`objdump`/`xxd` on the frozen bytes (2026-10-31):

- **original**: `badSink` = `endbr64; push rbp; ...; call strcpy@plt(0x4010d0);
  call printLine; ret` — **no length guard**, so over-long input overflows dest[50].

- **Route A** (`c4a159…aa82`): badSink body unchanged; the `call strcpy@plt` at
  `0x401304` is rewritten to `call 0x4018e9`.  At `0x4018e9`:
  ```
  mov r8, rsi            ; data
  xor ecx, ecx           ; len = 0
  L: cmp byte [r8+rcx],0 ; je done
     inc rcx; jmp L
  done: cmp rcx, 49      ; jbe strcpy_path
        ; error path: write(2,"ERROR: input exceeds destination capacity\n",42);
        ;            exit_group(1)
  strcpy_path: jmp 0x4010d0  ; strcpy@plt
  ```

- **Route B** (`208574ab…6717`): badSink entry `0x4012b0` overwritten with
  `jmp 0x4018ec`.  At `0x4018ec` a full replacement function:
  ```
  mov [rbp-8], rdi       ; data
  mov [rbp-0x48], 0      ; len = 0
  L: cmp len, 50 ; jge after
     c = data[len]; if c==0 -> after
     len++; jmp L
  after: cmp len, 50 ; jl valid
         ; error: fprintf(stderr, "ERROR:..."); exit(1)
  valid: memset(dest, 0, 50); strcpy(dest, data); printLine(data); ret
  ```

The two repairs are both "compute strlen, reject/exit if len would overflow,
else copy".  The safety property to prove is therefore about the **guard**, not
about strcpy's internals.

## 4. What is actually proved (and how)

The harness (`v4_symbolic.py:run_guard`) drives angr with a **fully symbolic**
input buffer and only a "a NUL occurs somewhere" constraint, then explores.

- **P1 (valid domain, strlen 0..49)**: `explore(find=strcpy@plt)` with the input
  constrained to have its NUL by index 49.  Result: strcpy is reached, and the
  distinct strlen values recovered at the call site are exactly `0..49`
  (50 symbolic states) for both routes.  Since strcpy writes strlen+1 bytes and
  strlen<=49, the write is <= 50 bytes = dest capacity → no overflow.

- **P2 (over-long domain, strlen 50..63)**: `explore(find=error_site,
  avoid=strcpy@plt)` with the input constrained to have no NUL before index 50.
  Result: strcpy is **unreachable** for both routes; control diverts to the
  error path (Route A distinct strlen `50..63`, 14 states; Route B one state).

- **Calibration (original)**: the same P2 run on `original.elf` reaches
  strcpy@plt (`avoided=[0x4010d0]`) → **counterexample**, proving the model can
  catch the defect.  (This is the negative control; the original *is* the
  deliberately-defective reference.)

The structural evidence of symbolic exploration is `distinct_strlen`: for the
valid domain both routes produce exactly `0..49`, which is only possible if angr
symbolically split the input on every possible NUL position.  The rejected v12
harness produced one concrete run with no such split.

### 4.1 Honest note on the solver tally

The `solver_accounting.sat` field reads 0 even on the symbolic runs.  This is an
instrumentation limitation, not evidence of concreteness: angr's branch engine
resolves queries at the read-only rust `SolverComposite` backend, which cannot
be monkey-patched from Python.  The structural evidence (`distinct_strlen` =
`0..49`, i.e. 50 distinct symbolic states) is the reliable indicator, and it is
recorded per run.  A verifier may re-instrument at the rust level if they want a
raw query count.

## 5. What is NOT proven (explicit, Standard B §3.6)

- Function-level only (`badSink` under entry preconditions), **not** whole-program.
- The exact semantics of `strcpy`/`printLine`/`fprintf` are **hooked** (libc
  boundary models), not the real libc.  The proof is about the repair's guard,
  not about strcpy's byte-by-byte behaviour.
- Inputs longer than the declared 63-byte over-long bound are outside the stated
  domain (the contract's `max_valid_input_bytes` is 49; 63 is the declared
  over-long exploration bound).
- This is **not** a proof that the repair is correct under CET/IBT enforcement
  or any non-Linux-x86-64 environment.

Net: this is stronger evidence than v12, and it is the correct *form* of the
V4 proof.  Whether it is **accepted** is for M4 to decide by independent replay
and the Lead to approve.  M3 does not relabel it `passed`.

## 6. Guest replay conditions

The verifier needs the guest (`lab@192.168.30.128`, key `.tmp/ssh/id_ed25519`)
with `/opt/angr-venv`, the three frozen binaries, and the two scripts.  Commands:

```bash
cd ~/v4
/opt/angr-venv/bin/python v4_run_all.py        # full matrix -> v4-evidence.json
/opt/angr-venv/bin/python v4_symbolic.py routeb valid     # single run (P1)
/opt/angr-venv/bin/python v4_symbolic.py routeb over_long # single run (P2)
```

The verifier must re-run from the frozen bytes and record its own observed
output, then report `PASS`/`FAIL`/`NOT VERIFIED` per Standard B §3.  If the
guest or angr is unavailable, the result is `NOT VERIFIED`, not waived.

## 7. Files in this package

| file | content |
|---|---|
| `v4_symbolic.py` | the TRUE symbolic model + guard proof (producer) |
| `v4_run_all.py` | full-matrix runner + byte-hash re-verification |
| `v4-evidence.json` | the six-run verdict output with distinct_strlen |
| `original.elf` | defective fixture — SHA-256 `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| `routea-candidate.elf` | Route A candidate — SHA-256 `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` |
| `routeb-candidate.elf` | Route B fixed candidate — SHA-256 `208574ab5b7753fab6f28860830069770622fb7b1fcb8d181fa50453f8656717` |
| `v4_accounting.py` | (legacy, v12) supplementary instrumentation — superseded |
| `v4-accounting.json` | (legacy, v12) — superseded by v4-evidence.json |
| `v4-accounting.log` | (legacy, v12) — superseded |

The three `.elf` files are the frozen bytes the harness operates on; a verifier
**must** confirm their SHA-256 matches §1 before trusting any replay output.
`v4_run_all.py` re-verifies these hashes at start and refuses to run on a
mismatch.

The legacy `v4_accounting.*` files are retained for provenance only; the
authoritative output of this rework is `v4-evidence.json`.
