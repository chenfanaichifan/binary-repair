# CWE416 — the V4 producer, and what its numbers actually mean

- Date: 2026-11-06 (guest window 11:26–11:29 local)
- Owner: Member 3
- Binary under test: the 124 candidate `46d16e99…fcd0`; control `original.elf` `c9c2632e…23c9`
- Contract: unchanged, `input_mode: none`, file `8a2b408c…e3c3b`
- Output: `v4-evidence.json`, written **only** through `write_v4_evidence`

## 1. The property

> There exists an execution of the target function on which a pointer passed to
> `free()` is later passed to `printLine()` — i.e. a freed block is read.

The harness asks that question at every `printLine` call, against the pointers
recorded at every `free()` on that path. A repaired binary must produce **no**
satisfying answer; the unrepaired original must produce one. The second is the
negative control — without it "no violation" would be a claim about nothing.

Input domain: the contract says `none`. No arguments, no stdin, no file. The only
nondeterminism left is the address `malloc()` returns, so that address is
symbolic and everything else follows from the code. This is the honest form of
"symbolic" for this fixture; it is not a symbolic *input*, because there is no
input.

## 2. The numbers

| Case | Binary | Expected | Observed | Solver | Steps |
|---|---|---|---|---|---|
| `known_good` | candidate `46d16e99…` | holds | **holds** | 1 eval → **unsat** | 11 / 64 |
| `known_bad` | original `c9c2632e…` | violated | **violated** | 1 eval → **sat** | 14 / 64 |

```
complete            True     unexplored []
unknown             0        timeouts   0
steps               25       max_steps  128
claimed_scope       model    known_bad_rejected True
replay              2 runs, identical digests
file sha256         3a3ef672…598a — two separate process runs wrote byte-identical files
entry               0x4012aa = CWE416_Use_After_Free__malloc_free_char_01_bad
states (both cases)  2 deadended, 0 active, 0 errored, 0 unconstrained, 0 deferred
```

Each `holds`/`violated` carries a witness, so neither is a bare word:

```
known_good  {free_calls: 0, print_calls: 1, solver: "unsat"}
known_bad   {freed_index: 0, print_calls_seen: 1, solver: "sat", state: "deadended"}
```

## 3. What the candidate's `unsat` is, and is not

It is the **empty-disjunction case**: the candidate's `free()` call is five
`nop`s, so on its single path nothing is ever freed, the disjunction over freed
pointers is empty, and the question is unsatisfiable. That is a real answer to
the property question, and `free_calls: 0` in the witness is the reason.

It is **not** a deep solver result, and the evidence says so twice: in the case
`notes`, and in `not_claimed`. Anyone reading `unsat: 1` as "z3 worked hard" is
reading it wrong. What the run establishes is: on the only path this program has,
no freed pointer reaches `printLine`, because no free happens at all.

## 4. Hooks, and why each one is allowed

Recorded in `v4-evidence.json#hooks`, one justification each. Summary:

| Hook | Why | Does it assume the repair is safe? |
|---|---|---|
| `malloc` | makes the only nondeterminism explicit: return a fresh symbolic, aligned, non-null address | no |
| `memset` | no-op; the property is about pointers, not contents | no |
| `free` | records the argument instead of modelling tcache | no — it records, it does not forgive |
| `printLine` | observes the argument; the verdict is computed in the harness | no — hooking it is how the violation is *found* |
| `exit` | the malloc-null guard would otherwise jump to an unconstrained address and be counted as unexplored | no |

`printLine` being hooked also keeps its `strlen` loop out of the exploration;
that is a performance reason, stated as such, not a correctness claim.

## 5. The checklist, item by item

| Requirement | Where it is | Value |
|---|---|---|
| `cases >= 2` | `cases` | 2 |
| `known_good` / `known_bad` | `known_good`, `known_bad` | the two case ids |
| `known_bad_rejected` | `known_bad_rejected` | `true` |
| `complete=True`, `unexplored=[]` | both fields | true, `[]` |
| `unknown=0`, `timeouts=0` | both fields | 0, 0 |
| `steps < max_steps` | `steps`, `max_steps` | 25 < 128 |
| `claimed_scope="model"` | field | `model` |
| `not_claimed` excludes binary-level | `not_claimed[0]` | "a binary-level proof: …" |
| `replay runs >= 2 identical` | `replay` | 2, identical |

And the writer enforces all of it: `v4_evidence.py::write_v4_evidence` calls
`check()` first and raises `V4EvidenceError` instead of writing. It rejected two
drafts of this run — a replay digest mismatch caused by query timings, and a
`steps == max_steps` case — which is the behaviour wanted: the file cannot be
hand-assembled and cannot be written when it does not meet the checklist.

## 6. What this does **not** change

- **`gate-index.json` is untouched.** V4 is still `not_run` there, and in the
  124 bundle. A producer does not promote its own result: acceptance standard
  `docs/handoffs/62` §1 requires an independent verifier to replay it. This
  record submits evidence; it does not assign a gate verdict.
- **The pipeline still does not read it.** `routeb/attempt_writer.py:221` writes
  `"V4": "not_run"` unconditionally, and nothing in `app/` reads
  `v4-evidence.json` (record 126, `02-readers.txt`). So an attempt built from the
  124 bundle is still `REQUIRED_CHECK_NOT_RUN` → `inconclusive`, now for a
  reason that is no longer "there is no producer".
- **No second sample, no second defect class.** T8.3 stays blocked.

## 7. Reproducing

```sh
# in the gate4 guest, with angr in /opt/angr-venv
FIX=~/cwe416-sync/kit/fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput
/opt/angr-venv/bin/python v4_harness.py \
    --candidate ~/cwe416-sync/candidate.elf \
    --original  "$FIX/original.elf" \
    --contract  "$FIX/contract.json" \
    --out       v4-evidence.json
```

About 4 seconds. The harness runs both cases **twice** internally and refuses to
write unless the two digests match, so a non-deterministic result cannot be
published by accident. `01-run.txt` is that run, untrimmed, including the four
`Guessing call prototype` warnings angr emits for the hooked PLT entries.

## 8. Files

| File | What it is |
|---|---|
| `v4_harness.py` | the producer: hooks, exploration, accounting, replay, CLI |
| `v4_evidence.py` | typed `V4Evidence` + `write_v4_evidence`, with the checklist as validation |
| `v4-evidence.json` | the output, written by the writer and by nothing else |
| `01-run.txt` | the full run behind that file |
