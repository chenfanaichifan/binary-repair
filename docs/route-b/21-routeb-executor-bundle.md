# Route B / provider executor bundle

`routeb/executor.py` turns a Route B candidate into the same style of evidence
bundle used by Route A, without turning a static bundle into a Gate 4 pass.

## Build from recovered/provider C

```bash
python -m routeb.executor \
  --original fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf \
  --func CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink \
  --c-source routeb/experiment/samples/juliet_badSink.normalized.c \
  --mode roundtrip \
  --out-dir var/jobs/routeb/roundtrip
```

The provider supplies `candidate.replacement_c`; write it to a local file and pass
that file as `--c-source`. No provider key or network is used by the executor.

## Bundle an existing candidate (no rebuild)

```bash
python -m routeb.executor \
  --original fixtures/.../original.elf \
  --candidate routeb/out/gate4/roundtrip.elf \
  --func CWE121_..._badSink --mode roundtrip \
  --out-dir var/jobs/routeb/static
```

## Reproducibility / runtime

```bash
# rebuild twice via Patcherex2 and compare bytes
python -m routeb.executor ... --c-source fixed.c --build-twice --out-dir ...

# guest-only: execute the frozen six cases and attach raw output
python -m routeb.executor ... --tests fixtures/.../tests \
  --run-manifest --out-dir ...
```

`--run-manifest` is the only path that executes the candidate. Without it the
bundle is static and `runtime_manifest.state = not_run`.

## Bundle format

```text
candidate.elf
original.elf
edit-manifest.json       # schema 2: hashes, function, changed intervals,
                         # header facts, relocation delta, tools, runtime state
audit.json               # static ELF checks: size, entry, W^X, intervals,
                         # segment/relocation inventory
reproducibility.json     # measured only with --build-twice
environment.json         # interpreter / patcherex2 / angr / z3 / LIEF / clang
independent-views/       # readelf/objdump text when available
manifest-compare.json    # only with --run-manifest, mode=roundtrip
manifest-repaired.json   # only with --run-manifest, mode=fixed
bundle-record.md
SHA256SUMS
bundle-sha256.txt
```

`edit-manifest.json` is schema 2 and records every changed file interval plus
`runtime_manifest` state. `audit.json.pass` is a **static** result; it is not a
Gate 4 pass. Gate 4 still requires the six-case raw output under the isolation
controls and M4's environment verification.

## Tested

`tests/test_routeb_executor.py` uses the frozen Gate 4 `roundtrip.elf` as an
existing candidate and verifies the static bundle, schema-2 manifest, non-runtime
state, SHA256SUMS, and bundle hash. The host run does not execute the candidate.
