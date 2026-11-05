# Provenance

- Upstream: NIST SARD / Juliet Test Suite for C/C++ version 1.3
- Repository: https://github.com/dsp-testing/samate-c-cpp
- Pin: `01e353d` (`01e353daa3d28a4ce2ae68904cbcde5e03e3519d`, 2025-09-30,
  "Update one more LDAP test")
- Path: `C/testcases/CWE416_Use_After_Free/CWE416_Use_After_Free__malloc_free_char_01.c`
- Source hash (as served, CRLF): `fa84a6bb9df36a8a1ab4d33a7064746d9037247f7599d3cd39659478d4b7f42e`
- `src.c` in this repo (newline-normalised to LF): `262dee1d39243c944a55b4b967ab6a56524977dc88a684ff0b7150cacf0b5a61`
- License: NIST public domain; foreign rights under CC0 1.0

The pin resolves and the file it serves hashes to `fa84a6bb9df36a8a1ab4d33a7064746d9037247f7599d3cd39659478d4b7f42e`, which is the hash
the Lead supplied for this source. The two hashes above differ only in line
endings; converting the upstream bytes from CRLF to LF reproduces `src.c` byte for
byte.

`arichardson/juliet-test-suite-c` at `f88433e3443648a17671398797a04ea1f8e1a274`
carries the same bytes and was used for the first retrieval. It is not the pin:
where the two disagree, `dsp-testing/samate-c-cpp@01e353d` is authoritative.

## Why this fixture is incomplete

`fixtures/public/` intake requires `original.elf`, `build.sh`, `build.json`,
`contract.json` and `tests/{valid,invalid}.json`. None of them exist yet:

- the authoring host has no C compiler, and a hand-made ELF would be a fake;
- `tests/invalid.json` needs at least one case that triggers the lifetime bug,
  which must be measured against a real binary;
- the contract must state destination/ownership rules for the repaired build,
  which follows from the measured behaviour.

`tools/fixture_intake.py --check` therefore reports `missing_file` for this
directory. That is the true state: the ELF belongs to the guest build path
(M3/VMer). Until it exists, T8.3 stays blocked.
