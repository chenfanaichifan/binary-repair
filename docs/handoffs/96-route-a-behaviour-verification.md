# 96 — Route A behaviour verification (V3), measured

**Renumbered 90 → 96 on 2026-11-05.** `90` collides with the live-bridge / M4
row (see `93-m3-bridge-package-invariants-2026-11-05.md`); any earlier reference
to `90-route-a-behaviour-verification` means this file.


**Owner:** M3 · **Date:** 2026-11-05 · **Status:** **`V3 = passed` for the Route A
candidate; `failed` for the pre-repair original.** Evidence:
`docs/handoffs/evidence/V3/`.

This closes the obligation that earlier rounds left `not_run`: does the repaired
binary actually behave differently from the original, and exactly as the
reviewed contract says?

## 1. Result

| Binary | sha256 | V3 |
|---|---|---|
| `original.elf` | `aa428157…8393` | **`failed` — 4/6** |
| `route_a/candidate.elf` | `c4a15921…aa82` | **`passed` — 6/6** |

Both measured in the same guest session (snapshot 11 / gate4-harness), against
the same frozen manifests, with the binaries placed under the exact basename the
manifests declare (`./original`).

## 2. What the original actually does (the violation, measured)

| Case | Input | Expected | Measured |
|---|---|---|---|
| `invalid-first` | 50 × `A` | exit 1, empty stdout, exact stderr | **exit 0**, stdout `50×A\n` (51 bytes), stderr empty |
| `invalid-longer` | 100 × `A` | exit 1, exact stderr | **exit 139** (128+SIGSEGV), stderr empty |

The 50-byte case is the quieter and more important half: the program exits
**successfully** while writing one byte past a 50-byte object, so nothing
signals the defect. The 100-byte case crashes, matching the fixture provenance
(`rip = 0x401317`, saved frame overwritten). Four valid cases match byte for
byte, which is why the score is 4/6 rather than 0/6 — the oracle distinguishes
"unaffected behaviour preserved" from "defect fixed".

## 3. What the candidate does

All four valid cases reproduce the original's stdout byte for byte (no
regression on the happy path), and both invalid cases now return exit 1 with
stdout empty and stderr exactly `ERROR: input exceeds destination capacity\n`
(42 bytes including the trailing newline).

## 4. Why the verdict is not a rubber stamp

`tests/v3_oracle.py` is a pure function — observations in, verdict out — and its
24 tests include the controls that a permissive verifier would fail:

- wrong return code → `failed`
- stderr missing its trailing newline → `failed`
- one extra stdout byte on the invalid path → `failed`
- a missing observation → `not_run`, never `passed`
- and `test_vulnerable_original_scores_four_of_six` — which is exactly the 4/6
  measured here

## 5. How it was produced

1. Guest observer `workers/broker/guest_behaviour.py` (stdlib only; refuses
   non-Linux, non-root, or a missing `--guest-ack`) executed every manifest case
   and recorded `(rc, stdout_hex, stderr_hex)`. A signal death is normalised to
   `128+N`.
2. Observations copied to the host; hashes verified on both ends.
3. Host evaluated them with `v3_oracle.evaluate_files`. The guest decided
   nothing.

Re-judging needs only `evidence/V3/*-observations.json` and the frozen
manifests — the command is in that package's README.

## 6. Limits, stated plainly

- **Coverage is the six frozen cases**, not the whole input space. No symbolic
  (V4) check ran, so "no other defect exists" is not claimed.
- **Not Gate 6.** Gate 6 needs a detection mechanism for the violation, which is
  a separate obligation.
- **Public fixture.** This is a NIST Juliet case; a model may have recognised the
  pattern from training data, so the result cannot establish independent
  analysis (provenance §11). That limitation travels with the result.
- The demo job directory is world-writable so uid 1003 can write its output;
  production should use group ownership instead (see record 95 §6).
