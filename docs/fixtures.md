# Public fixtures: what makes one usable

A sample in `fixtures/public/` is evidence only when four things are present and
consistent: its **source**, its **build recipe**, its **defect classification**
and its **test manifest**. Anything less is a binary nobody can rebuild and a
claim nobody can check.

`tools/fixture_intake.py` enforces that mechanically. It reads text and hashes
bytes; it never runs `build.sh`, never executes `original.elf`, and never touches
the network.

```bash
python tools/fixture_intake.py --check fixtures/public/<name>
python tools/fixture_intake.py --list  fixtures/public
python tools/fixture_intake.py --check fixtures/public/<name> --baseline-cwe CWE-121
```

Exit code `0` means every check passed, `1` means at least one finding was
printed. There is no "warning" state: a partial fixture fails.

## Required layout

```
fixtures/public/<name>/
  src.c                 original C source
  original.elf          the built binary, committed
  build.sh              offline build recipe
  build.json            provenance + exact command + expected output hash
  defect.json           defect class and which invalid case triggers it
  contract.json         obligations, forbidden behaviour, valid domain
  tests/valid.json      at least 4 valid cases
  tests/invalid.json    at least 2 invalid cases
  tests/SHA256SUMS      every file, relative to <name>/
```

## What each check is for

| Finding | Why it fails the fixture |
|---|---|
| `missing_file` | A fixture without a recipe cannot be reproduced; M4 would be verifying a binary of unknown origin. |
| `sums_incomplete` | `SHA256SUMS` must cover **every** file. A sums file that skips the binary lets the binary change unnoticed. |
| `sums_hash_mismatch` | The committed bytes are not the ones the sums describe. |
| `build_output_hash` | `build.json#output.sha256` disagrees with `original.elf`: the recipe does not describe the committed binary. |
| `build_json_network` / `build_script_network` | The guest build must work offline. A `curl`, `apt-get`, `pip` or `https://` in the recipe means it does not. |
| `empty_provenance` | `source.url`, `source.commit` and `source.license` must be non-empty. "It was on a website" is not provenance. |
| `defect_trigger_unknown` | `defect.json#trigger_case` must name a case that exists in `tests/invalid.json`. A prose claim that the class is covered is not accepted; the pointer has to resolve. |
| `not_a_distinct_class` | T8.3 needs a second defect class. Pass `--baseline-cwe CWE-121`, and the fixture fails if it uses that class. |
| `too_few_valid` / `too_few_invalid` | Fewer than 4 valid or 2 invalid cases leaves "the repair works" unproven. |
| `case_sha_mismatch` | The test manifest cites a different binary than the committed one. |

## The `defect.json` file

```json
{
  "schema_version": 1,
  "cwe": "CWE-416",
  "title": "use after free: freed data is read by the sink",
  "mechanism": "lifetime",
  "baseline_mechanism": "bounds-check",
  "trigger_case": "invalid-first"
}
```

`cwe` is the machine-readable class. `trigger_case` is a pointer into
`tests/invalid.json`, not a description. This is deliberate: the project rule is
that prose in notes is never parsed into a gate, so the class is a field and the
trigger is an ID.

`mechanism` is the axis a second class has to differ on: `bounds-check` means the
repair adds a length check, `lifetime` means it changes ownership so freed memory
is not read. `baseline_mechanism` records what the first class does; if the two
match, intake fails with `not_a_distinct_class`. Two CWEs that are both repaired
with a bounds check are the same exercise with a different label.

## Current state

```
$ python tools/fixture_intake.py --list fixtures/public
CWE121_src_char_declare_cpy_51b            OK (1 warning(s))
CWE416_Use_After_Free__malloc_free_char_01 FAILED (7)
```

### CWE121: complete, not reproduced

The baseline fixture now has `src.c`, `harness.c`, `build.sh`, `build.json`,
`defect.json` and a `SHA256SUMS` that covers `original.elf`. The `.elf` itself was
not rebuilt: there is no compiler on the authoring host and the upstream Juliet
`testcasesupport` tree is not vendored.

`src.c` and `harness.c` were reconstructed from the committed binary, and the
file says so at the top. The evidence is exact rather than guessed:

- `DW_AT_producer`: `GNU C17 13.3.0 ... -g -O0 -fno-stack-protector -fno-pie`
- `.debug_line_str`: `juliet-v1.3/.../CWE121_..._src_char_declare_cpy_51b.c`
- `badSink` at `0x4012b0`: `char dest[50]` zero-initialised, `strcpy` at
  `0x401304`, then `printLine(data)` - it prints `data`, not `dest`
- `main` at `0x401256`: `fprintf(stderr, "usage: %s <input>")` and `return 2`

`build.json#reproduction.status` is `unverified`, so intake prints
`reproduction_unverified` as a **warning**. It does not fail the fixture and it
does not pretend the build ran. Run the fixture's `build.sh` inside the guest and
compare with `output.sha256` to clear it.

### CWE416: source pinned, binary still missing

`fixtures/public/CWE416_Use_After_Free__malloc_free_char_01/` holds the upstream
`src.c` and `defect.json` (`mechanism: lifetime`,
`baseline_mechanism: bounds-check`). `original.elf`, `build.sh`, `build.json`,
`contract.json` and `tests/` do not exist yet, because producing them needs a
compiler. The intake reports seven `missing_file` findings; that is the true
state, not a regression.

`PROVENANCE.md` records the resolved commit
`f88433e3443648a17671398797a04ea1f8e1a274` and notes that the pin the Lead
supplied (`01e353d`) does not resolve in that mirror. If it names a different
source, the file may differ.

## readelf and objdump

`tests/test_routeb_executor.py` needs both for the Route B static audit. If they
are installed outside `PATH` (a MinGW or LLVM tree), point
`BINARYREPAIR_BINUTILS_DIR` at that directory:

```
set BINARYREPAIR_BINUTILS_DIR=D:\tools\mingw64\bin
```

`tests/conftest.py` prepends it, so no PATH edit is needed.

## What a second-class fixture still needs from the Lead

The checker can be run today, but the fixture content cannot be chosen by M1
alone:

1. **Which class.** CWE-787 (cheap to build and verify) or CWE-416 (stronger
   generic proof, longer path). Until this is decided, any sample M1 finds may
   be thrown away.
2. **What "different" means.** A different CWE, or a different repair mechanism
   within the same CWE? This is exactly what `--baseline-cwe` versus
   `--allow-same-cwe` encodes, so the decision is a flag, not a rewrite.
3. **Which corpus is allowed.** `README.md` here permits team-built samples,
   public CTF/teaching binaries and historical CVE binaries, and forbids
   client-confidential content and unauthorized third-party binaries. The Lead
   should name the specific source so the license is unambiguous.

## Rules for this directory

- A synthetic fixture built inside a test (`tmp_path`) must never be written
  under `fixtures/public/`. A generated sample that looks real is worse than a
  missing one: M3 would package it and M4 would verify it.
- Large binaries need team confirmation before committing (Git LFS may be
  required).
- `PROVENANCE.md` in this directory is still pending; until it exists,
  `build.json#source` carries the provenance per sample.
