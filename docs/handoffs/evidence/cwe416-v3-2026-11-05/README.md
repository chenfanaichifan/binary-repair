# cwe416-v3-2026-11-05 — evidence for record 120

Captures taken on `m3/cwe416-v3-noinput`, cut from
`origin/m1/t30-acceptance-ab-2026-11-05` @ `8d54a06`, 2026-11-05 evening
(+08:00). Nothing here is re-typed from memory: each `.txt` is command output.

| File | What it shows |
|---|---|
| `01-contract-before.json` | the contract as committed at `6ce16ac` (schema 2, `input_mode`, `invalid_exit_code: 0`) |
| `02-contract-after.json` | the contract now (schema 3, five fields gone) |
| `03-contract.diff` | the whole change: two lines — `invalid_exit_code` deleted, `schema_version` 2 → 3 |
| `04-load.txt` | `SecurityContract.from_dict` loads it, `to_dict()` round-trips it byte-for-byte, and the three near-misses (v2 + `input_mode`, `invalid_exit_code: 0`, `max_valid_input_bytes: 0`) are rejected with the exact message |
| `05-intake.txt` | the intake rerun: canonical (plain and `--allow-same-cwe`), M1's `1b08ae5`, CWE121 baseline, and `--list` for the whole directory |
| `06-hashes.txt` | the six files compared against `6ce16ac`: five unchanged, `src.c` new; the 13-row fixture manifest verifying; the canonical contract digest |
| `07-tests.txt` | scoped pytest run (74 tests, 39 intake + 35 contracts), including why its process exit is non-zero here |
| `08-alias.txt` | `original.c` and `src.c` are byte-identical, and the build script never mentions `src.c` |

## Two things a reader should not misread

**The plain intake run fails, and it is not about this fixture.** `--list` and the
flagless `--check` both report `not_a_distinct_class` because
`fixtures/public/CWE416_Use_After_Free__malloc_free_char_01/` — the retired
synthetic directory with seven missing files — also declares `cwe: CWE-416`. The
flag is the documented escape for "the axis is the repair mechanism"; here it
covers a duplicate directory, not a second sample. Retiring that directory is a
documentation change in M1's `docs/fixtures.md`, so it was left alone.

**`src.c` exists for the checker, not for the build.** `REQUIRED_FILES` in
`tools/fixture_intake.py` hardcodes `src.c` and returns before reading anything
else. The sample's source is `original.c` — that spelling is inside the
committed ELF via `-g` — so renaming would silently fork the digest, and
rebuilding would fork a second ELF hash for one sample. The alias is
byte-identical and both names carry the same digest in `tests/SHA256SUMS`, so it
cannot drift unnoticed. Delete it the moment the intake reads the source name
from `build.json#argv`.

## What this is not

Not a repair candidate, not a V0–V5 result, not a T8.3 claim. V3 is `not_run`
with a 1/1 no-input ceiling; V4 is `not_run`; T8.3 stays blocked.
