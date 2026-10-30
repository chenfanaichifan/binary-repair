# To member 3: freeze the behavioural oracle (verification-design §4.4)

**Recipient:** Member 3 (fixture and execution environment)
**From:** Verification slice (Member 4)
**Date:** 2026-10-20
**Basis:** `docs_BinaryRepair/verification-design.md` §4.4 (draft oracle)
**Needs a reply:** the four items at the end. Two are blocking: `DEST_CAPACITY` and `ERROR_STDERR`.

---

## 1. Why this must be frozen before either route runs

Route A (instruction patch) and Route B (recovered-C recompile) must produce the **same observable
behaviour** on invalid input, byte for byte. If one prints `ERROR: input too long` and the other
prints `error: input exceeds capacity`, then V3 cannot use one assertion set, and the F5 comparison
between the two routes becomes meaningless.

So the reviewer freezes the contract-level oracle once. Each route then implements it; neither route
invents its own message.

## 2. What is already frozen

These are decided and will not change:

- **Off-by-one rule.** `strcpy(dest, data)` writes `strlen(data) + 1` bytes. With a
  `char dest[N]` buffer, length `N` overflows by one byte because of the NUL terminator.
  Therefore `MAX_VALID_LEN = DEST_CAPACITY - 1`, and the first invalid input is
  `MAX_VALID_LEN + 1`. With the usual `dest[50]` that means 49 is the largest valid input,
  not 50.
- **Invalid path shape.** `return_code = 1`, `stdout` empty, exact `ERROR_STDERR` bytes.
  It must **not** crash: `return_code` must be 1, not `-11`/SIGSEGV. A crash is evidence the
  repair failed, not evidence of the invalid-input path.
- **Valid path shape.** The original observable behaviour is preserved; V3 asserts against the
  measured original values, not invented ones.

## 3. Contract constants (one TBD each)

| Constant | Meaning | Value |
|---|---|---|
| `DEST_CAPACITY` | bytes in the destination buffer declared inside the target function | **TBD** — Juliet's `char dest[50]` suggests 50, but the selected fixture decides |
| `MAX_VALID_LEN` | largest input length that must be accepted | `DEST_CAPACITY - 1` |
| `ERROR_STDERR` | exact stderr bytes on the invalid path | `"ERROR: input exceeds destination capacity\n"` — **pending confirmation** |

## 4. Test matrix the manifest must contain

| Case | argv[1] length | Expected |
|---|---|---|
| empty | 0 | valid: `return_code = 0`, original stdout, stderr empty |
| smallest | 1 | valid, same |
| typical | 10 | valid, same |
| largest valid | `MAX_VALID_LEN` | valid, same |
| first invalid | `MAX_VALID_LEN + 1` | invalid: `return_code = 1`, `stdout` empty, `stderr = ERROR_STDERR` |
| much longer | `MAX_VALID_LEN + 51` | invalid, same |

## 5. Four items I need from you

1. **`DEST_CAPACITY`** — the actual number, and the source line it comes from
   (for example `char dest[50];` at line NN of the selected `.c` file).
2. **Measured original behaviour** — run the original binary on each valid length (0, 1, 10,
   `MAX_VALID_LEN`) and record the exact `return_code`, `stdout`, `stderr`. Do not guess;
   measure on the built `original.elf`.
3. **`ERROR_STDERR`** — confirm the exact bytes above, or propose a replacement. State whether
   it ends with `\n`; the assertion is byte-exact.
4. **Harness invocation shape** — does the harness `main` call the target
   directly as `target(argv[1])`? Record the exact call so the entry address in the provenance
   matches what the tests execute.

## 6. Reply template (copy and fill in)

```text
DEST_CAPACITY = ____  (source: ____ line ____)
MAX_VALID_LEN = ____

Original behaviour (measured on original.elf):
  len=0   -> return_code=____  stdout=____  stderr=____
  len=1   -> return_code=____  stdout=____  stderr=____
  len=10  -> return_code=____  stdout=____  stderr=____
  len=MAX -> return_code=____  stdout=____  stderr=____

ERROR_STDERR = "____"   (ends with \n: yes/no)

Harness call: target(argv[1]) / other: ____

Harness choice: A (unmodified Juliet data-flow variant) / B (recorded minimal patch)
If B: patch file name ____, original SHA-256 ____, patched SHA-256 ____
```

## 7. Related decision still open (A or B)

The oracle above is independent of the harness choice, but the choice still gates the fixture:

- **A (preferred):** a Juliet 51/52/53/54 data-flow variant whose `badSink(char *data)` declares
  `char dest[N]` and copies `data` into it. NIST source stays unmodified; provenance is cleanest.
- **B (fallback):** a recorded minimal patch that replaces the fixed string in `bad()` with a
  pointer fed from `argv[1]`. Acceptable only with the patch, both hashes, and an explicit
  "evaluator-side minimal modification" statement in `provenance.md`.

Confirm which one applies when you reply.
