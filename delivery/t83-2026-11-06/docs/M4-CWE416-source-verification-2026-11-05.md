# M4 — CWE-416 source four-tuple verification (2026-11-05)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator, not an independent two-person signature. **Scope:** source/repo/commit pin only; no guest build, no trigger execution, no merge/tag/live-success claim.

## Verified four-tuple

| Field | Value |
|---|---|
| repo URL | `https://github.com/dsp-testing/samate-c-cpp` |
| full commit SHA | `01e353daa3d28a4ce2ae68904cbcde5e03e3519d` |
| source path | `C/testcases/CWE416_Use_After_Free/CWE416_Use_After_Free__malloc_free_char_01.c` |
| source SHA-256 | `fa84a6bb9df36a8a1ab4d33a7064746d9037247f7599d3cd39659478d4b7f42e` |
| size | 3,198 bytes |
| raw URL | `https://raw.githubusercontent.com/dsp-testing/samate-c-cpp/01e353daa3d28a4ce2ae68904cbcde5e03e3519d/C/testcases/CWE416_Use_After_Free/CWE416_Use_After_Free__malloc_free_char_01.c` |

Observed: the raw bytes at that commit/path hash to the stated SHA-256 and size; the source contains
`malloc(100)` -> `free(data)` -> `printLine(data)`, i.e. a use-after-free shape.

**Rejected mixing:** `arichardson/juliet-test-suite-c` commit
`f88433e3443648a17671398797a04ea1f8e1a274` is a different repository and is not part of this
four-tuple. Using it would require a separate four-tuple; the two must not be combined.

## License

NIST Juliet Test Suite 1.3 is public domain; foreign rights per CC0 1.0. The fixture must keep
`LICENSE` / `PROVENANCE.md` with the repo/commit/path/hash and the license statement.

## CWE-121 baseline

Live-bridge `integration/live-bridge-2026-11-03` @ `8c77fcd`:

```text
git diff --stat 1da22ff..HEAD -- fixtures/public
-> (empty)
```

The CWE121 fixture is byte-identical to the post-final baseline; it has no `defect.json` and no
`reproduction_unverified` / `reproduction_verified` field. It remains **source reproduction
unavailable / NOT VERIFIED**; M1's feature-branch change `fba137e` is not in live-bridge and must
not be used to flip the warning.

## Pending

CWE-416 trigger/build is **NOT RUN**: it needs M3/VMer guest-build evidence (original.elf,
deterministic trigger, toolchain/build recipe, isolation/reset evidence) and then M4 independent
verification. Lead has amended task-29 from CWE-787 to CWE-416; T8.3 stays blocked until the exit
criteria are met.

Record 91 remains independent; review 9-12 out of scope; no merge, no tag, no live success.
