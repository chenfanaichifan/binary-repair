# V4 raw evidence — replay package for independent verification (Standard B)

Date: 2026-10-31
From: M3 (producer)
To: M4 (independent verifier), Lead
Re: Lead ruling `docs/handoffs/62-lead-v4-acceptance-standard.md` (Standard B adopted)

---

## 0. What this is, and what it is not

This package publishes the **raw** V4 bounded-symbolic material so an
independent verifier can replay it. It is **not** a claim that V4 is `passed`.
Per Standard B, a self-verified single-agent result is **not sufficient**; V4
stays `not_run`/`NOT VERIFIED` until an independent role replays it and the
Lead approves. M3 does not relabel anything here.

Everything below is the producer's raw material + an honest statement of what
it does and does **not** prove. Nothing is re-summarised to look stronger than
it is.

---

## 1. Candidate and original hashes (frozen bytes)

| binary | SHA-256 | role |
|---|---|---|
| `original.elf` | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` | the defective fixture (`CWE121_..._51b`) |
| `routea-candidate.elf` | `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` | Route A candidate |
| `routeb-candidate.elf` | `208574ab5b7753fab6f28860830069770622fb7b1fcb8d181fa50453f8656717` | Route B fixed candidate |

All three binaries are 26792 bytes. `nm`/`readelf` confirm the `badSink` symbol
resolves to `0x4012b0` in **all three** — the model entry address is the same for
original, routea and routeb (an earlier note about "recompiled entry differs for
Route B" referred to the observed entry *state* during exploration, not the
`badSink` symbol address; the model entry `0x4012b0` is correct for all three).

## 2. Environment (versions the verifier must reproduce)

- angr `10.0.4.post1` (guest `/opt/angr-venv`)
- z3-solver `5.1.0`
- claripy: **angr's bundled rustylib claripy** (no standalone `claripy` pip
  package; `import claripy` fails, use `import angr.claripy as claripy`)
- guest: Ubuntu 24.04.5, kernel 6.8.0-147-generic; Python 3.x (venv `/opt/angr-venv`)

## 3. Model and domain (unchanged, from `v4_symbolic.py`)

- **entry**: `0x4012b0` (`badSink`), modelled *standalone* via
  `p.factory.call_state(0x4012b0, ...)`.
- **dest**: `rbp-0x40`, `dest_capacity_bytes=50` (contract, includes NUL).
- **data arg**: `rdi` at entry; a bounded symbolic buffer is placed at `0x500000`.
- **forbidden write**: any write past `dest[50]` (i.e. `rbp-0x40+50`) for an
  input of length >= 50.
- **valid domain**: C string of 0..49 payload bytes + NUL (worst case = 49 'A'
  + NUL, concrete).
- **library hooks**: `strcpy@plt` (0x4010d0, length-aware model that records
  every byte written), `printLine@plt` (0x401380, stub that returns).

### 3.1 Honest limitation — the exploration is concrete, not truly symbolic

This is the single most important fact for the verifier to check. The valid
domain is fed as **concrete bytes** (`'A' * 49 + NUL`), and the free/calibration
domain is also concrete (`'A' * 57 + NUL`). The supplementary accounting run
(`v4-accounting.json`) shows the solver performed **0 satisfiability queries and
1 `eval`** across every run. So:

- the "valid domain" argument is a **concrete worst-case execution**, not a
  symbolic proof over all legal inputs;
- the monotonicity claim ("49+NUL is the longest legal string, so if it does not
  overflow, no legal string does") is **producer reasoning**, not a solver-derived
  result;
- the "free domain" calibration is a **concrete over-long input**, not a symbolic
  search for a counterexample.

The verifier must treat the verdicts accordingly: `proven` here means "the
concrete worst-case 49+NUL input does not overflow in this concrete run", **not**
"no legal input can overflow" (which would require a symbolic proof the model
does not actually perform). This is a genuine gap vs Standard B §3.3/§3.6.

## 4. Exploration / state accounting (raw, per run)

From `v4-accounting.json` (state classification at termination):

| run | steps | active | deadended | errored | unconstrained | deferred | timed_out |
|---|---|---|---|---|---|---|---|
| original/valid | 6 | 0 | 1 | 0 | 0 | 0 | no |
| original/free | 6 | 0 | 1 | 0 | 0 | 0 | no |
| routea/valid | 107 | 0 | 1 | 0 | 0 | 0 | no |
| routea/free | 122 | 0 | 1 | 0 | 0 | 0 | no |
| routeb/valid | 259 | 0 | 1 | 0 | 0 | 0 | no |
| routeb/free | 162 | 0 | 1 | 0 | 0 | 0 | no |

Solver accounting (identical across all six runs): `sat=0, unsat=0, unknown=0,
eval=1`. No solver timeout occurred (all runs terminated within the 120 s / 400
step budget).

## 5. Calibration (raw)

- `original` / free domain: **counterexample** — 57 bytes written to
  `0x7ffffffeffb0` (5 recorded writes, all 57 bytes). This reproduces the real
  overflow and proves the model *can* flag an over-long copy.
- `original` / valid domain: no out-of-bounds write (49+NUL fits).

### 5.1 Gap vs Standard B §3.4

Standard B asks for a "deliberately defective candidate rejected" in addition to
the original violation. **This package does not contain a second, deliberately
defective candidate.** The only negative control is the original binary itself.
A verifier who wants the full §3.4 calibration must construct such a candidate
independently; M3 does not fabricate one now (that would be post-hoc material).

## 6. What is NOT proven (explicit, per Standard B §3.6)

- The model is **function-level** (`badSink` standalone under entry
  preconditions), **not** whole-program.
- The valid-domain result is a **concrete worst-case run**, not a symbolic proof
  over the input domain (see §3.1).
- The model **hooks** `strcpy` and `printLine`; the correctness of the repaired
  candidates rests in part on the repair rejecting over-long input *before*
  `strcpy` is reached, which is outside the hooked `strcpy` model. A hook may not
  assume the repaired operation is safe — the verifier must confirm the
  reject/rebound path independently.
- **Unresolved / incomplete exploration**: none (all runs deadended cleanly),
  but because the exploration is concrete, "deadended=1" does **not** mean the
  input space was exhaustively explored.
- `inconclusive` is the correct label if any run times out or errors; none did.

**Net: V4 is `NOT VERIFIED` under Standard B.** The producer's evidence is
published for replay, not as an acceptance claim.

## 7. Guest replay conditions

To replay, the verifier needs the guest (`binrepair-vm`, `lab@192.168.30.128`,
key `.tmp/ssh/id_ed25519`) with `/opt/angr-venv`, plus the three frozen binaries
and the scripts in this directory. Commands:

```bash
cd ~/v4
/opt/angr-venv/bin/python v4_run_all.py        # reproduces v4-evidence.json
/opt/angr-venv/bin/python v4_accounting.py 2>&1 | tee v4-accounting.log  # raw accounting
```

The verifier must re-run from the frozen bytes and record its own observed
output, then report `PASS`/`FAIL`/`NOT VERIFIED` per Standard B §3. If the guest
or angr is unavailable, the result is `NOT VERIFIED`, not waived.

## 8. Files in this package

| file | content |
|---|---|
| `v4_symbolic.py` | the model + explore logic (producer) |
| `v4_run_all.py` | the full-matrix runner + binary hash table |
| `v4-evidence.json` | the six-run verdict output (producer) |
| `v4_accounting.py` | supplementary instrumentation (solver + state accounting) |
| `v4-accounting.json` | raw accounting output |
| `v4-accounting.log` | raw step-by-step stdout log |

M3 makes no change to any of these after this publication, and does not
re-summarise the verdicts.
