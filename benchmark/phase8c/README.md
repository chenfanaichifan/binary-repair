# Phase-8C public ground-truth corpus v2 (2026-11-16)

Deterministic public corpus built by `scripts/build_phase8c_corpus.py` from committed fixtures, PoC manifests and reference fixes. No AI, no network, no wall clock. Hidden contents are never read or claimed.

- benchmark_id: `phase8c-public-v2`
- generated_at: `2026-11-16T00:00:00Z` (fixed)
- samples: **32** (dev 18 / validation 14)
- oracle kinds: **24 runtime-oracle** samples, **8 analysis-only** samples (core 28: 20 runtime / 8 analysis-only)
- hidden_available: `false`; hidden commitment is owned by C4/C6 and is not created or read by this builder.

## Split assignment

| group | dev | validation | rule |
|---|---|---|---|
| v1 migrated (12) | 8 | 4 | v1 split preserved losslessly |
| hard cases (6) | 3 | 3 | loop8/loop16/loop32 -> dev; loop64/reverse/heap-malloc -> validation |
| repair-benchmark (6) | 3 | 3 | cwe122/cwe125/cwe134 -> dev; cwe190/cwe476/cwe787 -> validation |
| cross-arch analysis-only (4) | 2 | 2 | Mach-O arm64/x86_64 -> dev; PE arm64/x64 -> validation |
| compiler variants (validated only) | 2 | 2 | CWE122 -O2 dynamic (not-stripped/stripped) + CWE125 -O3/-Os static (strip) -> 2 dev / 2 validation |

## Samples

| sample_id | split | format/arch | scope | oracle |
|---|---|---|---|---|
| `cwe121-public` | dev | elf/x86_64/64 | function | external_poc |
| `hard-loop16` | dev | elf/x86_64/64 | function | external_poc |
| `hard-loop32` | dev | elf/x86_64/64 | function | external_poc |
| `hard-loop64` | validation | elf/x86_64/64 | function | external_poc |
| `hard-loop8` | dev | elf/x86_64/64 | function | external_poc |
| `hard-multicall` | dev | elf/x86_64/64 | function | external_poc |
| `hard-nonconst` | validation | elf/x86_64/64 | function | external_poc |
| `hard-reverse` | validation | elf/x86_64/64 | function | external_poc |
| `hard-sprintf` | validation | elf/x86_64/64 | function | external_poc |
| `heap-canary` | validation | elf/x86_64/64 | function | external_poc |
| `heap-capacity-x86_64` | dev | elf/x86_64/64 | function | external_poc |
| `heap-malloc` | validation | elf/x86_64/64 | function | external_poc |
| `inline-loop` | dev | elf/x86_64/64 | function | external_poc |
| `negative-control` | dev | pe/i386/32 | analysis_only | static |
| `repair-cwe122` | dev | elf/x86_64/64 | function | external_poc |
| `repair-cwe125` | dev | elf/x86_64/64 | function | external_poc |
| `repair-cwe134` | dev | elf/x86_64/64 | function | external_poc |
| `repair-cwe190` | validation | elf/x86_64/64 | function | external_poc |
| `repair-cwe476` | validation | elf/x86_64/64 | function | external_poc |
| `repair-cwe787` | validation | elf/x86_64/64 | function | external_poc |
| `stack-memcpy-x86` | dev | elf/i386/32 | analysis_only | static |
| `stack-strcpy-x86` | validation | elf/i386/32 | analysis_only | static |
| `stack-strcpy-x86_64` | dev | elf/x86_64/64 | function | external_poc |
| `uaf-noinput` | dev | elf/x86_64/64 | analysis_only | static |
| `variant-cwe122-O2` | dev | elf/x86_64/64 | function | external_poc |
| `variant-cwe122-O2-stripped` | validation | elf/x86_64/64 | function | external_poc |
| `variant-cwe125-O3-static` | dev | elf/x86_64/64 | function | external_poc |
| `variant-cwe125-Os-static-stripped` | validation | elf/x86_64/64 | function | external_poc |
| `xarch-macho-arm64` | dev | macho/arm64/64 | analysis_only | static |
| `xarch-macho-x86_64` | dev | macho/x86_64/64 | analysis_only | static |
| `xarch-pe-arm64` | validation | pe/arm64/64 | analysis_only | static |
| `xarch-pe-x64` | validation | pe/x86_64/64 | analysis_only | static |

## Variants (C8)

| variant | source | compiler/flags | binary sha256 |
|---|---|---|---|
| `variant-cwe122-O2` | `repair-cwe122` | zig -O2 -g0 -fno-stack-protector -fno-pie -no-pie | `d4bc0b47675366053efabcb9c36faa15f91d78eae273b6b6e5bf364610cf4955` |
| `variant-cwe122-O2-stripped` | `repair-cwe122` | zig -O2 -g0 -fno-stack-protector -fno-pie -no-pie -s | `507a818ac1d2ca7b184fba6614b8a6ef8fb9ce8f54c73d0d41deec7924c536cf` |
| `variant-cwe125-O3-static` | `repair-cwe125` | zig -O3 -g0 -fno-stack-protector -fno-pie -no-pie -static | `2eb966a6cb1642e025150e840dc7ca1bf22b98e6c02a42ce305a5249ba94774d` |
| `variant-cwe125-Os-static-stripped` | `repair-cwe125` | zig -Os -g0 -fno-stack-protector -fno-pie -no-pie -static -s | `5b5f5887fddca7428012d4db7f88d1afb8856cf32b602019082c57d6c2902bfa` |

Measured negative variant probes (explicitly dropped):

- `attempt-cwe122-musl-O2-static` (x86_64-linux-musl -O2): variant build does not reproduce the committed PoC's expected vulnerable original behavior (original PoC case did not crash); variant dropped rather than admitting an unvalidated build
- `attempt-cwe787-musl-O3-static` (x86_64-linux-musl -O3): variant build does not reproduce the committed PoC's expected vulnerable original behavior (original PoC case did not crash); variant dropped rather than admitting an unvalidated build
- `attempt-cwe122-gnu-static` (x86_64-linux-gnu -O2): cross-compiler build failed: error: libc of the specified target requires dynamic linking

## Provenance and validation

- builder: `scripts/build_phase8c_corpus.py`
- source digest: `b0fae6893740898f1ff185650e3c41590c3b68a9cd2e585ca8502830f0485b9a`
- migration report sha256: `a93de5e867ce100aced48232c0c04440d4654b6a2069b4e738e80da204719b85`
- v1 migration: 12 samples, lossless=True
- Zig toolchain: `available`
- every runtime sample validates `poc.fixture_sha256 == binary sha256`; every reference fix digest is recomputed; analysis-only samples never declare a runtime oracle.

## Limitations

- public corpus only: hidden_available=false and hidden_commitment is null. The hidden commitment file benchmark/phase8c/hidden-commitment.json is owned by the C4/C6 hidden workflow; this builder never creates, reads or fabricates hidden contents.
- compiler/ABI/linking/stripping/ranges unknown for some checked-in fixtures are explicit null/empty with per-sample limitations, never guessed.
- the public split assignment for the new hard/repair/cross-arch groups is deterministic (hard 3/3, repair 3/3, cross-arch 2/2); the 12 v1 samples keep their v1 split.
- runtime-oracle samples are 20 and analysis-only samples are 8 among the 28 core samples; variants add only independently validated compiler/flag builds.
- no network and no AI provider are used by the builder; generated_at is the fixed Phase-8C timestamp.
