# Property ↔ contract mapping — why this query answers that sentence

The contract forbids one thing; the harness asks one question. They are not the
same sentence, and this file is the argument that they coincide *for this
fixture*, with the assumptions named so the argument can be attacked.

## The four texts

| where | text |
|---|---|
| `contract.json#forbidden_behavior` | "read a heap block after free() has released it, so stdout carries allocator residue instead of the allocated text" |
| `contract.json#valid_behavior` | "exit 0 and print the 100-byte block it allocated — 99 'A' bytes then one LF — the same 100 bytes on every run" |
| `harness-output.json#property_text` | "on every execution, no pointer passed to free() is later passed to printLine()" |
| `harness-output.json#input_domain` | "none: the entry takes no arguments, reads no stdin, opens no file; only the address returned by malloc() is symbolic" |

The contract describes a **symptom** (the bytes on stdout are residue). The
harness asks about a **cause** (a freed pointer reached the printer). A gate that
confuses the two would accept a model that proves the wrong thing, so here is the
bridge, in both directions.

## Cause ⇒ symptom

If a pointer is passed to `free()` and later to `printLine()`, then `printLine`
walks that block. It was released, so glibc's tcache has written `next` and `key`
into its first two words (`environment_assumptions`, second entry). The walk stops
at the first NUL those words contain, which is why the original prints 3 bytes
(`05040a`) instead of 100. So "freed pointer printed" produces "residue on
stdout". This is the direction the model proves.

## Symptom ⇒ cause, for this binary only

The fixture has one allocation, one `memset`, one `free`, one `printLine`, and no
other writer to stdout. Given that:

1. The 100 `'A'` bytes are written before the `free()`, so any shorter output means
   the block was read *after* it was released.
2. Nothing reallocates the block between `free()` and `printLine()` — there is no
   intervening `malloc` — so the residue cannot be a *different* live block.
3. The program never writes to the block after freeing it, so it cannot produce
   residue by writing over its own data.

Under those three conditions "residue on stdout" ⇒ "the freed pointer was printed".
Drop any of them and the reverse direction fails — a fixture with a second buffer,
a reallocation, or a partial overwrite would need a different model.

## Why the split is not a gap

The two directions are checked on different levels, and that is deliberate:

- **V3** runs the real binary and compares bytes: candidate `1/1`, original `0/1`.
  That is the symptom, measured on hardware with the real allocator.
- **V4** reasons about the target function and proves the cause holds for every
  address `malloc()` can return.

So the byte-level claim and the model-level claim are not competing for the same
work. V4 does not have to model tcache (it would only add assumptions), and V3
does not have to quantify over addresses (one frozen observation suffices because
the input domain is empty).

This is also why `not_claimed` carries "absence of the defect under a different
allocator or a different libc": the symptom depends on tcache behaviour, while the
cause does not.

## The assumptions, stated so they can be attacked

- **A1.** `printLine` is the only writer to stdout on this path.
- **A2.** No allocation happens between `free()` and `printLine()`, so the freed
  block is not recycled before it is read.
- **A3.** The allocator writes non-NUL words into the freed chunk (tcache
  `next`/`key`), which is what makes the residue observable without a sanitizer.
- **A4.** The property is about pointer identity, not about the bytes printed.
  `memset` is a no-op in the model, so a data-value defect would be invisible —
  see `hooks-audit.md`.

A1–A3 are properties of this fixture and are checkable by reading `original.c`.
A4 is a scope statement, and it is the one a reviewer should push on if the sample
is ever reused for a different defect.

## Mechanical check

```sh
python3 check_mapping.py --bundle ../T8.3-evidence-2026-11-06
```

nine field-level assertions, all of which pass:

```
[ok] target_entry matches              CWE416_Use_After_Free__malloc_free_char_01_bad
[ok] input_mode none on both sides     contract='none', harness=none: …
[ok] property is pointer-flow          pointer-flow: on every execution, no pointer passed to free()…
[ok] hooks == allowed_calls            exit, free, malloc, memset, printLine
[ok] known_good holds with unsat       eval=1 unsat=1
[ok] known_bad violated with sat       eval=1 sat=1
[ok] scope model, empty disjunction disclosed
[ok] forbidden_behavior mentions the free() and the output
[ok] required_obligations are the six gates
```

The script cannot check the ⇒ arrows above; it checks that the two sides are
talking about the same function, the same input domain, the same call set and the
same calibration. The arrows are the argument in this file, and they are the part
to disagree with if you disagree.
