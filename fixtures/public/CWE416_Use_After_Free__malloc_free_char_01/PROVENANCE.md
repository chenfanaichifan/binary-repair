# Provenance

- Upstream: NIST SARD / Juliet Test Suite for C/C++ version 1.3
- Mirror used: `arichardson/juliet-test-suite-c`
- Commit (resolved): `f88433e3443648a17671398797a04ea1f8e1a274` (2025-03-27, "Create LICENSE")
- Path: `testcases/CWE416_Use_After_Free/CWE416_Use_After_Free__malloc_free_char_01.c`
- `src.c` sha256 (in this repo, line endings normalised to LF):
  `262dee1d39243c944a55b4b967ab6a56524977dc88a684ff0b7150cacf0b5a61`
- upstream file sha256 (as served, CRLF):
  `fa84a6bb9df36a8a1ab4d33a7064746d9037247f7599d3cd39659478d4b7f42e`
- The two hashes differ only in line endings. Converting the upstream bytes
  from CRLF to LF reproduces this file byte for byte, so the content is
  verifiable against the pinned commit.
- License: NIST public domain; foreign rights offered under CC0 1.0. The mirror's
  LICENSE states: "Juliet Test Suite for C/C++ version 1.3 is not subject to
  copyright protection in the United States. To the extent NIST may claim Foreign
  Rights ... available to you under the CC0 1.0 Public Domain License."

## The pin the Lead supplied

`01e353d` does not resolve in this mirror (`GET /commits/01e353d` returns 422), so
it is recorded here as supplied but unresolved:

- `lead_provided_pin`: `01e353d` (unresolved)
- `resolved_pin`: `f88433e3443648a17671398797a04ea1f8e1a274`

If `01e353d` names a different source (SARD download id, an internal mirror, or a
different commit), say which; the file content may differ from this one.

## Why this fixture is incomplete

`fixtures/public/` intake requires `original.elf`, `build.sh`, `build.json`,
`contract.json` and `tests/{valid,invalid}.json`. None of them exist yet:

- the authoring host has no C compiler (`gcc`/`clang` are absent), so an
  `original.elf` cannot be produced here, and a hand-made binary would be a fake;
- `tests/invalid.json` needs at least one case that triggers the lifetime bug,
  which must be measured against a real binary;
- the contract must state the destination/ownership rules for the repaired
  build, which follows from the measured behaviour.

`tools/fixture_intake.py --check` therefore reports `missing_file` for this
directory. That is the true state, not a regression: the ELF belongs to the
guest build path (M3/VMer). Until it exists, T8.3 stays blocked.
