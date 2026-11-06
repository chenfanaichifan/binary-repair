# M4 — decision separation: 116 synthetic Fix A/B vs T8.3 no-input contract (2026-11-05)

**Purpose:** keep two independent decisions from being conflated.
**Owner of both:** Lead / contract owner, not M4. M4 records the separation only.

---

## Decision 1 — record 116 synthetic fixture: Fix A or Fix B

Record 116 measured a **synthetic** fixture (`src.c` + `harness.c`) whose
committed recipe does not link: both translation units define `main`.

| | Fix A | Fix B |
|---|---|---|
| Change | drop `harness.c` from `build.json#argv` and `build.sh` | remove `main` from `src.c`; keep `harness.c` as the only entry |
| Effect | `src.c`'s existing unguarded `main` becomes the entry point | `src.c` becomes a library (`duplicate`, `badSink`, `goodSink`); harness owns `main` |
| Cost | loses the `MAX_INPUT_BYTES 4096` guard and the `argc > 3` usage branch, so `valid_domain` is not enforced by the binary | source edit; `tests/SHA256SUMS` must be regenerated |
| M3 preference | — | yes (record 116 §8) |
| Scope | **116's link failure only** | **116's link failure only** |

**Neither A nor B**:

- makes the synthetic sample *public*;
- satisfies T8.3's second-public-sample requirement;
- resolves the no-input contract gap;
- touches T30 or its rebuild.

---

## Decision 2 — T8.3 / CWE416: the no-input contract problem

T8.3 requires a **second public sample of a different defect class** plus a
build path and an unchanged acceptance model.

CWE416's `bad()` takes **no input**: it `malloc`s 100 bytes, fills them, frees
the block, and reads it back. The use-after-free is unconditional.

`SecurityContract` requires input-rejection fields —
`invalid_input_response`, `invalid_stderr`, `invalid_stdout`,
`max_valid_input_bytes`. Writing them for CWE416 means **inventing a rejection
path the program does not have** (record 113; record 118 §8 measured six
required edits, four of them input-rejection fields).

This is a **contract-model expressiveness** question:

- does the acceptance schema admit a case with no input at all; or
- does CWE416 need a distinct contract shape; or
- is CWE416 the wrong second sample for T8.3?

It is not a build-shape question, and A/B does not answer it.

---

## Why the two must stay separate

| Statement | Consequence |
|---|---|
| A/B is a **build-shape** decision for a synthetic fixture | choosing B does not make the contract loadable |
| The no-input contract is a **model** decision | choosing A or B does not make the sample public |
| A verified T30 rebuild is a **fixture identity** result | it changes neither decision |
| T8.3 needs a **public** sample + a representable contract | it stays blocked until both exist |

**Correction to M4's earlier framing.** M4 previously wrote that contract/V0–V5
verification waits on the Lead's A/B decision. That was wrong: V0–V5 waits on the
**no-input contract decision**, which is separate. A/B only settles how the
synthetic 116 fixture links.

---

## Status after this separation

| Item | Status |
|---|---|
| Record 116 | diagnostic / build-trigger evidence — **not** a T8.3 fixture |
| Fix A / Fix B | **open**, Lead owns |
| No-input contract decision | **open**, contract owner owns |
| T8.3 | **blocked** — no second public sample, no representable contract |
| V0–V5 | **NOT VERIFIED** |
| T30 rebuild (118) | **REPORTED, NOT VERIFIED** until the evidence directory is readable |

---

## Boundaries

Record 91 unchanged · same operator (M4 = Lead, role-separated, not independent
two-person) · review items 9/10/11/12 separate · no merge, no tag, no live
success.
