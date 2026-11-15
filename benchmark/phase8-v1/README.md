# Ground-truth benchmark v1 (Phase-8A)

Generated deterministically by `scripts/build_ground_truth_benchmark.py`
from committed fixtures and contracts. No network, no git commands, no
wall clock, and PoC manifests are loaded for schema validation only (never
executed by the builder).

- benchmark_id: `phase8-v1`
- generated_at: `2026-11-16T00:00:00Z` (fixed deterministic constant for a reproducible manifest; this is not the build time and no wall clock is read)
- samples: 12 (dev 8, validation 4)
- hidden split: available=False, commitment=None; no hidden benchmark split exists in this repository; hidden_available is always false and hidden_commitment_sha256 is null. No hidden-set claim is made and no commitment is fabricated.
- sample contract: `contracts/benchmark-sample.schema.json` -> status=`validated`, validator=`jsonschema 4.26.0`

Artifact files: `manifest.json` (wrapper + typed samples), `README.md`
(this file), `SHA256SUMS` (covers both; never itself).

## Samples

| sample_id | split | scope | format/arch | class | target | oracle | reference fix |
|---|---|---|---|---|---|---|---|
| `cwe121-public` | dev | function | elf/x86_64/64 | CWE-121 stack buffer overflow (unchecked strcpy) | CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink | external_poc | `fixtures/hard-cases/cwe121_fix.c` |
| `hard-multicall` | dev | function | elf/x86_64/64 | CWE-121 non-template semantic/multi-layer copy | multicall_bad | external_poc | `fixtures/hard-cases/multicall_fix.c` |
| `hard-nonconst` | validation | function | elf/x86_64/64 | CWE-121 non-constant-length copy | nonconst_bad | external_poc | `fixtures/hard-cases/nonconst_fix.c` |
| `hard-sprintf` | validation | function | elf/x86_64/64 | CWE-121 non-template sprintf/format expansion path | sprintf_bad | external_poc | `fixtures/hard-cases/sprintf_fix.c` |
| `heap-canary` | validation | function | elf/x86_64/64 | CWE-121 heap buffer overflow / guard corruption | heap_bad | external_poc | `fixtures/hard-cases/heap_canary_fix.c` |
| `heap-capacity-x86_64` | dev | function | elf/x86_64/64 | CWE-131/697/787 capacity-check confusion (destination validated against payload-pool size) | va_range 4202713..4202729 | external_poc | `(none)` |
| `inline-loop` | dev | function | elf/x86_64/64 | CWE-121 non-template inline byte-copy loop | vuln_copy | external_poc | `fixtures/hard-cases/loop_fix.S` |
| `negative-control` | dev | analysis_only | pe/i386/32 | none (negative control: out-of-matrix PE/i386) | analysis_only | static | `(none)` |
| `stack-memcpy-x86` | dev | analysis_only | elf/i386/32 | CWE-121 immediate-length memcpy overflow (i386) | analysis_only | static | `(none)` |
| `stack-strcpy-x86` | validation | analysis_only | elf/i386/32 | CWE-121 stack buffer overflow (unbounded strcpy, i386) | analysis_only | static | `(none)` |
| `stack-strcpy-x86_64` | dev | function | elf/x86_64/64 | CWE-121 stack buffer overflow (unbounded strcpy) | vuln_copy | external_poc | `(none)` |
| `uaf-noinput` | dev | analysis_only | elf/x86_64/64 | CWE-416 use-after-free (heap lifetime) | analysis_only | static | `fixtures/hard-cases/uaf_fix.c` |

## Per-sample ground-truth details

### cwe121-public

- binary: `fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf` sha256 `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`
- expected analysis: root_cause=`strcpy into char[50] without validating the input length`, function=`CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink`, sink=`strcpy into stack destination`, capacity=50
- oracle: kinds=['external_poc'], manifest_path=fixtures/poc/cwe121.json
- expected_original: {"exit_code":0}
- expected_candidate: {"exit_code":1,"stderr":"ERROR: input exceeds destination capacity\n","stdout":""}
- negative cases: ['cwe121-valid-0', 'cwe121-valid-1', 'cwe121-valid-10', 'cwe121-valid-49']
- evidence: ['fixtures/hard-cases/cases.json#cases[id=cwe121-unchecked-strcpy]', 'fixtures/poc/cwe121.json#poc/regression', 'fixtures/hard-cases/cwe121_fix.c#length-reject']
- note: contract: reject length+1>50 with exit 1 and exact stderr; valid inputs preserved (fixtures/hard-cases/cases.json)

### hard-multicall

- binary: `fixtures/hard-cases/vuln-hardcases-c-x86_64.elf` sha256 `7e915860fce0d54c0c06ec0211f933dd85a4212af88e6e312362db232f1dfd4f`
- expected analysis: root_cause=`input copied into a 16-byte destination through a non-template path`, function=`multicall_bad`, sink=`semantic/multi-layer copy`, capacity=16
- oracle: kinds=['external_poc'], manifest_path=fixtures/poc/hard-multicall.json
- expected_original: {"crashed":true}
- expected_candidate: {"crashed":false,"exit_code":0}
- negative cases: ['multicall-short']
- evidence: ['fixtures/hard-cases/cases.json#cases[id=hard-multicall]', 'fixtures/poc/hard-multicall.json#poc/regression', 'fixtures/hard-cases/multicall_fix.c#length-reject']
- note: hard-case contract recorded in fixtures/hard-cases/cases.json (hard-multicall, capacity 16, baseline rejected)

### hard-nonconst

- binary: `fixtures/hard-cases/vuln-hardcases-c-x86_64.elf` sha256 `7e915860fce0d54c0c06ec0211f933dd85a4212af88e6e312362db232f1dfd4f`
- expected analysis: root_cause=`input copied into a 16-byte destination with non-constant length`, function=`nonconst_bad`, sink=`non-constant-length copy`, capacity=16
- oracle: kinds=['external_poc'], manifest_path=fixtures/poc/hard-nonconst.json
- expected_original: {"crashed":true}
- expected_candidate: {"crashed":false,"exit_code":0}
- negative cases: ['nonconst-short']
- evidence: ['fixtures/hard-cases/cases.json#cases[id=hard-nonconst]', 'fixtures/poc/hard-nonconst.json#poc/regression', 'fixtures/hard-cases/nonconst_fix.c#length-reject']
- note: hard-case contract recorded in fixtures/hard-cases/cases.json (hard-nonconst, capacity 16, baseline rejected)

### hard-sprintf

- binary: `fixtures/hard-cases/vuln-hardcases-c-x86_64.elf` sha256 `7e915860fce0d54c0c06ec0211f933dd85a4212af88e6e312362db232f1dfd4f`
- expected analysis: root_cause=`input copied into a 16-byte destination through a non-template sprintf path`, function=`sprintf_bad`, sink=`sprintf/format expansion copy`, capacity=16
- oracle: kinds=['external_poc'], manifest_path=fixtures/poc/hard-sprintf.json
- expected_original: {"crashed":true}
- expected_candidate: {"crashed":false,"exit_code":0}
- negative cases: ['sprintf-short']
- evidence: ['fixtures/hard-cases/cases.json#cases[id=hard-sprintf]', 'fixtures/poc/hard-sprintf.json#poc/regression', 'fixtures/hard-cases/sprintf_fix.c#length-reject']
- note: hard-case contract recorded in fixtures/hard-cases/cases.json (hard-sprintf, capacity 16, baseline rejected)

### heap-canary

- binary: `fixtures/hard-cases/vuln-heap-canary-x86_64.elf` sha256 `d0e5a2a4ed1e06e8bb494fbc0010da815a89b109092e1649bc1fe75adbc6cb0b`
- expected analysis: root_cause=`unbounded copy into a 16-byte heap buffer followed by a guard word`, function=`heap_bad`, sink=`heap buffer copy / guard corruption`, capacity=16
- oracle: kinds=['external_poc'], manifest_path=fixtures/poc/heap-canary.json
- expected_original: {"exit_code":1,"stderr_contains":"HEAP GUARD CORRUPT"}
- expected_candidate: {"exit_code":0}
- negative cases: ['heap-short']
- evidence: ['fixtures/hard-cases/cases.json#cases[id=heap-canary]', 'fixtures/poc/heap-canary.json#poc/regression', 'fixtures/hard-cases/heap_canary_fix.c#capacity-reject']
- note: hard-case contract recorded in fixtures/hard-cases/cases.json (heap-canary, capacity 16, baseline rejected)

### heap-capacity-x86_64

- binary: `fixtures/elf/vuln-capacity-confusion-x86_64.elf` sha256 `72fb53cbac09f576e037f730b07a7850ce8e129fb8c9a72c2c707c121d54b0d5`
- expected analysis: root_cause=`span destination range is validated against data_size instead of out_size`, function=`render`, sink=`OP_SPAN destination range check (CWE-131/697/787)`, capacity=None
- oracle: kinds=['external_poc'], manifest_path=fixtures/poc/marcx-capacity.json
- expected_original: {"crashed":true}
- expected_candidate: {"crashed":false,"exit_code":1,"stderr_contains":"span destination outside the output"}
- negative cases: ['benign', 'benign-sparse', 'benign-crc', 'ctrl-span-equal-sizes', 'ctrl-span-no-sparse', 'ctrl-span-src-oob', 'ctrl-literal-dst-oob', 'bad-crc']
- evidence: ['docs/architecture/capacity-check-repair.md#verified-fix-site', 'fixtures/poc/marcx-capacity.json#poc/regression', 'fixtures/hard-cases/capacity_confusion.c#span-check']
- note: the fixture is stripped, so the target is the reviewed site VA range from docs/architecture/capacity-check-repair.md (not a symbol claim)
- note: no committed reference-fix file exists; the documented 16-byte rewrite and patched sha256 are the expected patch properties

### inline-loop

- binary: `fixtures/elf/vuln-loop-x86_64.elf` sha256 `c9c9c26b7621c841807764ad214cda92768399b0d46f2bbbbe0c6f6c17aa0acf`
- expected analysis: root_cause=`inlined byte-copy loop into a 16-byte stack buffer without a bound`, function=`vuln_copy`, sink=`inline byte-copy loop`, capacity=16
- oracle: kinds=['external_poc'], manifest_path=fixtures/poc/elf-x86_64-loop.json
- expected_original: {"crashed":true}
- expected_candidate: {"crashed":false,"exit_code":0}
- negative cases: ['loop-short', 'loop-boundary']
- evidence: ['fixtures/poc/elf-x86_64-loop.json#poc/regression', 'fixtures/hard-cases/loop_fix.S#bounded-loop', 'fixtures/src/vuln_copy_loop_x86_64.S#deliberately-not-strcpy']
- note: hard-case contract is recorded in fixtures/hard-cases/cases.json (inline-byte-loop, capacity 16, baseline rejected)

### negative-control

- binary: `fixtures/pe/i386-control.exe` sha256 `3a5cb2cda02a81f9fde920d0621cd23b091c8cdf684d72f47a49cf6b0f45c789`
- expected analysis: root_cause=`None`, function=`None`, sink=`None`, capacity=None
- oracle: kinds=['static'], manifest_path=None
- expected_original: None
- expected_candidate: None
- negative cases: []
- evidence: ['fixtures/PROVENANCE.json#fixtures[name=pe-i386-control]', 'fixtures/src/control_i386.c#negative-control-comment']
- note: negative control selected from the fixture set: the committed PE/i386 control fixture (fixtures/pe/i386-control.exe) is explicitly outside the repair matrix; the pipeline must report unsupported / analysis-only and never write a verified candidate

### stack-memcpy-x86

- binary: `fixtures/elf/vuln-memcpy-x86.elf` sha256 `0bbe1c86f88d06469ccd2847d57be17c43d34f34a60b4ec2387e0d148cab6410`
- expected analysis: root_cause=`memcpy with immediate length 64 into a 16-byte stack destination (i386)`, function=`vuln_copy`, sink=`memcpy immediate-length copy into stack buffer`, capacity=16
- oracle: kinds=['static'], manifest_path=None
- expected_original: None
- expected_candidate: None
- negative cases: []
- evidence: ['fixtures/src/vuln_memcpy_elf32_x86.S#capacity-comment', 'fixtures/PROVENANCE.json#fixtures[name=elf-x86-memcpy]']
- note: no committed PoC manifest matches this i386 fixture, so no runtime oracle exists; analysis-only coverage, never a verified expectation

### stack-strcpy-x86

- binary: `fixtures/elf/vuln-strcpy-x86.elf` sha256 `a739546885fcb31ef5936bcab3270bbb597ffffe60eb1c10c107a858554aad0d`
- expected analysis: root_cause=`unbounded strcpy into a 16-byte stack destination (i386)`, function=`vuln_copy`, sink=`strcpy call into stack buffer`, capacity=16
- oracle: kinds=['static'], manifest_path=None
- expected_original: None
- expected_candidate: None
- negative cases: []
- evidence: ['fixtures/src/vuln_copy_elf32_x86.S#capacity-comment', 'fixtures/PROVENANCE.json#fixtures[name=elf-x86]']
- note: no committed PoC manifest matches this i386 fixture (no fixture_sha256 match), so no runtime oracle exists; the sample is retained as analysis-only coverage and must never be promoted to a verified expectation
- note: the task draft suggested an emulated/static oracle, but the committed contract forbids runtime oracle kinds for analysis_only expectations and no emulated oracle runner exists; schema wins

### stack-strcpy-x86_64

- binary: `fixtures/elf/vuln-strcpy-x86_64.elf` sha256 `c81017fafff3f57fee32331a6de9a3c77b702069a92f3b19eab77798416295a4`
- expected analysis: root_cause=`unbounded strcpy into a 16-byte stack destination`, function=`vuln_copy`, sink=`strcpy call into stack buffer`, capacity=16
- oracle: kinds=['external_poc'], manifest_path=fixtures/poc/elf-x86_64-strcpy.json
- expected_original: {"crashed":true}
- expected_candidate: {"crashed":false,"exit_code":0}
- negative cases: ['short-hi', 'boundary-15']
- evidence: ['fixtures/poc/elf-x86_64-strcpy.json#poc/regression', 'fixtures/src/vuln_copy_elf_x86_64.S#capacity-comment', 'fixtures/PROVENANCE.json#fixtures[name=elf-x86_64]']
- note: no committed reference-fix file exists for this fixture; the PoC manifest is the oracle and the patch expectations are behavioural

### uaf-noinput

- binary: `fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/original.elf` sha256 `c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9`
- expected analysis: root_cause=`read of a heap block after free() (use-after-free)`, function=`CWE416_Use_After_Free__malloc_free_char_01_bad`, sink=`use-after-free heap read`, capacity=100
- oracle: kinds=['static'], manifest_path=None
- expected_original: None
- expected_candidate: None
- negative cases: []
- evidence: ['fixtures/hard-cases/cases.json#cases[id=uaf-noinput]', 'fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/contract.json', 'fixtures/hard-cases/uaf_fix.c#read-before-free']
- note: expected baseline is analysis_only (fixtures/hard-cases/cases.json); the committed task expects no verified claim for this class
- note: the sample keeps its PoC manifest in the benchmark for reference, but the oracle declaration is static because the expectation is analysis_only (contract forbids runtime oracle kinds here)

## Validation

```bash
python scripts/build_ground_truth_benchmark.py --check
python -m pytest -q tests/test_ground_truth_benchmark.py
```

`--check` rebuilds the manifest in memory, compares `manifest.json`, `README.md` and `SHA256SUMS` byte-for-byte, re-validates every sample against the committed contract and the semantic oracle rules, and exits 1 on any mismatch.

## Limitations

- 12 candidate samples; samples with insufficient oracle evidence are declared analysis_only and are never promoted to a verified expectation.
- two i386 fixtures have no committed matching PoC manifest; they are retained as analysis-only coverage (explicitly noted per sample).
- no hidden split exists; hidden_available=false and hidden_commitment_sha256=null, with an explicit limitation.
- the benchmark measures deterministic repair readiness only; it does not call an AI provider or the network.
- reference_fix is null where no committed reference-fix file exists; expected patch properties are behavioural/documented instead.
