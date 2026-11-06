# Provenance

## Source

`original.c` is a byte-for-byte copy of the SARD test case:

```
corpus        NIST SARD Test Suite 112 (Juliet C/C++ v1.3)
archive       2017-10-01-juliet-test-suite-for-c-cplusplus-v1-3.zip
path          C/testcases/CWE416_Use_After_Free/
              CWE416_Use_After_Free__malloc_free_char_01.c
sha256        fa84a6bb9df36a8a1ab4d33a7064746d9037247f7599d3cd39659478d4b7f42e
```

It is not edited. `build.json#source.sha256` pins the same digest, so a change to
the file is detectable without trusting this note.

## Support files

`support/std_testcase.h`, `support/std_testcase_io.h` and `support/io.c` are
verbatim copies from the same archive's `C/testcasesupport/`. They are needed
because the upstream case includes `std_testcase.h` and calls `printLine`.

## What this fixture does not contain

- No `src.c`. The earlier synthetic source was removed; it was authored in this
  repository and cannot stand in for the upstream case.
- No `original.elf`. It is produced only by `build.sh` on a host with a Linux
  gcc. Nothing named `original.elf` may be borrowed from a variant build: a
  different source or flag set has a different digest, and `tests/SHA256SUMS`
  would then attest to the wrong artefact.

## Rebuild status

`build.json#output.sha256` and `tests/*.json#original_sha256` stay `null` until a
Linux gcc build runs. The authoring host has no ELF compiler, so the digest and
the test expectations are recorded as pending rather than predicted.
