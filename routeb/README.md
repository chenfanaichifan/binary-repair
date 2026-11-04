# Route B: recovered C and unchanged round trip experiment manual

This directory does exactly one thing: answer the open question in the technical design,
**"Can the unchanged recovered-C round trip
and added-code mapping pass their required checks?"** (TechDesign section 16, question 7).

The answer must be an experiment record, not a judgement. Every conclusion has to carry:
the binary hash, the Ghidra version, the compile command,
the Patcherex2 version, and the actual output of the 6 oracle cases.

---

## 0. Fixed sample and contract (freeze first, then act)

| Item | Value |
|---|---|
| Binary | `fixture/vuln`, built from `vuln.c` by `fixture/build.sh` |
| Compile | `-O0 -g0 -fno-stack-protector -fno-builtin -fno-pie -no-pie` |
| Target function | `copy_name(char *dst, const char *src, unsigned int n)` |
| Valid input | 0–15 bytes, copied as-is, `guard=ok`, exit code 0 |
| Invalid input | ≥16 bytes, must `return -1` and write nothing at all to the destination buffer |
| Overflow detection | in `struct record`, a `guard` canary (0xDEADBEEF) directly follows `name[16]` |
| Verdict tool | `verify.py` (three modes: vulnerable / fixed / roundtrip) |

Run the original binary once first to confirm that the vulnerability really reproduces:

```bash
cd routeb
./fixture/build.sh
python3 verify.py --binary fixture/vuln --mode vulnerable
# 6/6 passed: 4 valid inputs normal, 2 oversized inputs guard=CORRUPT
```

If this step fails (for example, 16 bytes does not trigger CORRUPT), fix the fixture first, do not continue.

---

## 1. Export the function with Ghidra

```bash
export GHIDRA_HOME=$HOME/ghidra_11.4_PUBLIC   # change to the actual directory
./ghidra/export.sh fixture/vuln copy_name
```

Outputs:

- `out/copy_name.c`: **raw decompiler output, read-only evidence, do not edit it directly**
- `out/copy_name.c.meta.txt`: entry address, byte size, signature, calling convention, callees

Check the meta: `size_bytes` should be a small number (a few dozen bytes), and `callees=` should be empty.
If it says `NOT FOUND`, the symbol was stripped or has a different name; open it in the Ghidra GUI to
confirm the function name, or look the symbol up first with `nm fixture/vuln | grep copy_name`.

**Observation due today**: paste the raw output into the experiment record and list "which places I changed to make it compile".

---

## 2. Normalize, without changing semantics

Create `out/copy_name.normalized.c` and make only type/name level changes:

| Common Ghidra output | After normalization | Why it is safe |
|---|---|---|
| `undefined4` / `undefined8` | `int` / `unsigned int` | just type names with an explicit width |
| `param_1, param_2, param_3` | `dst, src, n` | names, which must match the binary signature |
| `uVar1`, `local_10` | `i` | local variable renaming |
| `(char *)0x...` | leave as-is or change to a named constant | do not change address constants out of thin air |
| `code *`, `__return_storage_ptr__` | should not appear in this sample; if they do, record it as a blocker | struct returns / indirect calls are outside MVP scope |

Rules:

1. **Change only types and names; do not change control flow, do not change array indices, do not add checks.**
2. For every change, write one line of reason in the experiment record.
3. Save the normalized file separately; do not overwrite the raw output.
4. The reference implementation is in `experiment/samples/normalized_reference.c`; **do it yourself first, then compare**.

Compile self-check (this step only proves that the C syntax and the interface hold, not that the patch-back succeeded):

```bash
cc -O0 -g0 -fno-stack-protector -fno-builtin -c out/copy_name.normalized.c -o /tmp/copy_name.o
```

---

## 3. unchanged round trip (the key gate)

Recompile the **unfixed** normalized C and patch it back into a copy of the original ELF, then require it to behave
exactly like the original binary.

Use Patcherex2 (first reproduce its add example as described in the docs):

```bash
python3 -m venv .venv-patcherex
.venv-patcherex/bin/pip install patcherex2

# 3a. first prove that the toolchain itself works (docs example: addition becomes multiplication, 5 -> 6)
.venv-patcherex/bin/python probe_patcherex2.py --demo

# 3b. patch back the unmodified recovered C
.venv-patcherex/bin/python probe_patcherex2.py \
    --mode roundtrip \
    --c-source out/copy_name.normalized.c \
    --out out/vuln_roundtrip

# 3c. compare with the original binary case by case (stdout + exit code)
python3 verify.py --binary out/vuln_roundtrip --reference fixture/vuln --mode roundtrip
```

**Pass criteria (round trip only holds when all of them are met):**

- [ ] stdout and exit code of 6/6 cases are byte-identical to the original binary
- [ ] 16/17-byte inputs still give `guard=CORRUPT` (the defect was not "fixed along the way")
- [ ] the segment count/permissions from `readelf -lW` did not change unexpectedly; if a segment was added, record it
- [ ] the changed byte range is explainable (function body ± relocations) and written into the edit manifest
- [ ] Patcherex2 version, compiler version, and commands are all recorded

**What to do on failure:**

| Symptom | Meaning | Action |
|---|---|---|
| program crashes / does not start after patch-back | problem with relocations, entry point, or segment permissions | record `unsupported`, keep the candidate and the logs, locate the cause before switching approach |
| valid input output differs | normalization changed semantics | go back to step 2 and diff line by line |
| 16 bytes no longer CORRUPT | recompiling changed the loop/write | **not a successful repair**, it is a behaviour change; record as round-trip failure |
| Patcherex2 will not install / does not support this ELF | backend unavailable | record the version and the error; this is "unsupported", not "not done" |

> A passing round trip only proves "behaviour is consistent within this test domain"; it does not prove function
> equivalence. Every report must carry this caveat.

---

## 4. Structured repair proposal (DeepSeek)

Only after the round trip passes is the model allowed to modify this function.

```bash
cd ..
.venv/bin/python scripts/demo_candidate.py \
    --recovered routeb/out/copy_name.normalized.c \
    --out-c routeb/out/copy_name.model.c
```

The output is a candidate that passes schema validation (`replacement_c` is the complete function).

Then:

```bash
.venv-patcherex/bin/python routeb/probe_patcherex2.py \
    --mode fixed --c-source routeb/out/copy_name.model.c --out routeb/out/vuln_fixed

python3 routeb/verify.py --binary routeb/out/vuln_fixed --mode fixed
```

Only when `verify.py --mode fixed` passes 6/6 may you say "this candidate fixed the defect within the test domain".
**A successful compile, the model saying "fixed", and Patcherex2 not erroring do not count.**

---

## 5. Experiment record template (copy straight into the report)

```markdown
### Route B feasibility — <date>

- Host / OS / arch:
- Ghidra version / JDK:
- Fixture sha256:
- Recovered function size:
- Normalization edits (count + one line each):
- Patcherex2 version:
- Round trip: PASS / FAIL / UNSUPPORTED — evidence: <verify json path>
- Defect still observable after round trip: yes / no
- Model candidate: accepted_by_schema / rejected:<reason>
- Fixed candidate: 6/6 pass / fail:<case>
- Layout changes: <segments added? bytes changed?>
- Blockers:
- What I would try next:
```

---

## 6. What is explicitly out of scope (MVP boundary)

- Do not recover the whole program; recover only the one function being repaired.
- Samples with PIE / shared libraries / exceptions / C++ / multi-threading / TLS are not supported.
- Do not hand-write a relocation engine; if Patcherex2 cannot do it, record unsupported and wait for the team's decision.
- Do not put "it compiles" or "it did not crash" into the evidence.
