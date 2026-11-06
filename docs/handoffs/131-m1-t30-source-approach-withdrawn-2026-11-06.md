# M1: T30 source approach withdrawn in favour of the shipped `src.c`

- Date: 2026-11-06
- Owner: Member 1 (host backend)
- Supersedes: the previous handoff 112 (`112-m1-t30-upstream-source-2026-11-05.md`)
- Boundary: CWE-121 NOT VERIFIED; T8.3 blocked; no merge to `main`, no tag, no live success

## Why this is a withdrawal

An earlier pass on `integration/live-bridge` replaced the fixture's `src.c` with
a verbatim SARD `original.c` and built from
`original.c + harness.c + support/io.c`. That approach is withdrawn.

The reason is ordering, not correctness. By the time it was written, another M1
line (`m1/t30-acceptance-ab-2026-11-05`) had already:

- accepted M3's record-120 no-input fixture and wired it to controller/worker;
- produced record-124 with a real `original.elf` (`c9c2632e…b123c9`) built from
  the fixture sources;
- delivered `delivery/cwe416-124-*` bundles whose `SHA256SUMS` bind those
  sources by hash.

Swapping the main fixture's source would fork the build identity behind those
deliveries. The 124/120 gates take precedence, so the shipped layout wins.

## What the shipped layout actually contains

Two different files, both from the same upstream bytes:

| File | sha256 | Line endings | Used by |
|---|---|---|---|
| `CWE416_…_01_noinput/original.c` | `fa84a6bb…b7f42e` | CRLF | `tests/SHA256SUMS`, `PROVENANCE.md` |
| `CWE416_…_01_noinput/src.c` | `fa84a6bb…b7f42e` | CRLF | build input, same bytes |
| `CWE416_…_01/src.c` | `262dee1d…0b5a61` | LF | main fixture, newline-normalised |

`PROVENANCE.md` records the upstream pin,
`dsp-testing/samate-c-cpp@01e353d`, and explains that `262dee1d…` is the CRLF
source converted to LF byte for byte. Both hashes are stated, so neither is a
guess.

## The one real defect this pass found and fixed

`.gitattributes` applied `*.c text eol=lf` to the no-input fixture, so a fresh
clone would store `original.c` as `262dee1d…` while `tests/SHA256SUMS` still
expects `fa84a6bb…`. The sums file would then fail on every clean checkout.

Fixed by marking the directory byte-stable:

```
fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/** -text
```

Verified on this checkout: `original.c`, `src.c` and `original.elf` all match
their `SHA256SUMS` entries, CRLF counts included (`original.c` 107, ELF 0).

## What was removed

The withdrawn experiment added `original.c`, `support/`,
`build.sh`, `build.json`, `contract.json`, `harness.c` and `tests/` to the main
fixture. All are gone; the directory is back to
`PROVENANCE.md`, `defect.json`, `src.c`.

The intake rule that accepted either `original.c` or `src.c` is also gone — the
shipped intake requires `src.c` again, which is what the no-input fixture and the
CWE-122 fixture both provide.

## State after the merge

| Item | State |
|---|---|
| Branch | `integration/live-bridge`, merged with `3f21d31` |
| V4 gate | `replay.verified_by == "m4"` required on the production path |
| 124 | `inconclusive` / `required_check_not_run` / `symbolic` |
| angr / guest | absent on this host → V4 stays `not_run` |
| CWE121 v2 | `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37` |
| 120 contract | v3, `input_mode: "none"`, `c1684f15…b4f7c` |
| T8.3 | BLOCKED |

No candidate was produced here and no obligation was promoted.
