# Phase-8C hidden corpus (C4)

Status: implemented by C4 (`scripts/build_phase8c_hidden.py`).  The hidden
corpus itself is **private** and is not committed; the only committed artifact
is the opaque public commitment `benchmark/phase8c/hidden-commitment.json`.

## Purpose and boundary

The public Phase-8C corpus (`benchmark/phase8c/manifest.json`, C3) is visible to
every reader, so a model/agent evaluated on it can in principle overfit.  C4
builds a small private hidden corpus of variants derived from the public
repair-benchmark sources and publishes an *opaque pre-commitment* before any
hidden campaign runs.  The hidden benchmark lane itself is executed separately
by the Lead/C6; this document does not claim any hidden run result.

Private root (Lead-provisioned):

- default: `$HOME/.binaryrepair/phase8c-hidden`
- override: `PHASE8C_HIDDEN_ROOT`
- mode `0700`; every subdirectory is owner-only; the builder refuses to write
  into a root with group/other permissions.

Isolation is **operational, not cryptographic**: same-UID and root processes can
read the private root (see
`artifacts/phase8c-baseline-2026-11-16/phase8c-hidden-isolation-plan.md`).  The
commitment prevents accidental public leakage and accidental post-hoc changes,
not a determined host-level reader.

## Private layout

```
$PHASE8C_HIDDEN_ROOT/
  hidden-manifest.json      # private wrapper consumed by the C6 hidden lane
  bin/<opaque>.bin          # 8 hidden binaries
  poc/<opaque>.json         # 6 rebound external-PoC manifests (runtime samples)
  reference/<opaque>.c      # 6 private reference-fix copies
  reports/build-report.json # private build/validation evidence (not committed)
  reports/SHA256SUMS        # private tamper-detection sums
```

`hidden-manifest.json` follows the Lead/C6 integration contract:

```json
{
  "kind": "phase8c_private_hidden_manifest",
  "schema_version": 1,
  "benchmark_id": "phase8c-hidden",
  "public_manifest_sha256": "<sha256 of benchmark/phase8c/manifest.json>",
  "commitment_sha256": "<commitment digest>",
  "samples": ["<ground-truth-sample-v2 objects with opaque sample ids>"],
  "material": {
    "<opaque sample id>": {
      "binary_path": "bin/<opaque>.bin",
      "oracle_path": "poc/<opaque>.json" | null,
      "reference_fix_path": "reference/<opaque>.c" | null
    }
  },
  "limitations": ["..."]
}
```

Each entry of `samples` validates against
`contracts/ground-truth-sample-v2.schema.json` (same fields as the public v2
corpus: identity, compiler/build facts, vulnerability taxonomy, target, root
cause, oracle, reference fix, expected behavior, semantic regression, split,
evidence refs, confidence, limitations).  Sample ids are domain-separated
SHA-256 hashes of private variant slugs; the public tree never sees the slugs.
Private split values are `dev`/`validation` only, assigned deterministically.
Material paths are relative to the private root; `--check` rejects absolute
paths and `..` traversal.

## Corpus contents

Six runtime samples, one validated variant per public repair-benchmark source.
The builder tries the primary specification for a source first and falls back to
the next specification only when the original oracle behavior cannot be
reproduced:

| public source | primary variant chain (admitted configuration is the first that validates) | private split |
| --- | --- | --- |
| CWE122 heap overflow | `x86_64-linux-gnu` `-O0`, dynamic, no-strip; fallback: musl `-O2` static | dev |
| CWE125 OOB read | `x86_64-linux-gnu` `-O1`, dynamic, stripped | validation |
| CWE134 format string | `x86_64-linux-musl` `-O3`, static, no-strip | dev |
| CWE190 integer overflow | `x86_64-linux-gnu` `-O2`, PIE; fallback: gnu `-O2` no-pie | validation |
| CWE476 null dereference | `x86_64-linux-gnu` `-O0`, dynamic, no-strip | dev |
| CWE787 OOB write | musl `-O0` static stripped; fallback: gnu `-O0` dynamic no-strip | validation |

The admitted configuration is recorded in the private build report; chain
entries that fail compilation, target resolution, original-oracle validation or
the hidden/public dedup guard are dropped with their measured reason.  A
variant verdict must also be reproducible across two independent guest runs;
an unstable verdict is dropped rather than admitted, so the commitment stays
deterministic.

The private reference-fix copies carry a private header comment so their file
digests differ from the public reference-fix sources.

Two analysis-only cross-format samples (no runtime oracle, no verified-repair
claim): a PE32+ x86_64 build (CWE122 source) and a Mach-O arm64 build (CWE787
source).  Analysis-only samples use `expected_scope=analysis_only`,
`target.kind=analysis_only`, `oracle.kind=analysis_only`, a null oracle
manifest and a null reference fix.

Targets: unstripped runtime samples declare the public target symbol
(`{"kind": "symbol", "symbol": ...}`).  Stripped runtime samples declare an
explicit `{"kind": "va_range", "va": ..., "end": ..., "function": ...}` range
resolved from an identical unstripped companion build; the builder verifies
that the stripped and unstripped executables have byte-identical `.text`
before admitting the range.

## Hidden/public non-duplication

The hidden corpus is derived from the same sources as the public corpus, so the
builder enforces exact-hash separation before admitting anything:

- every compiled candidate variant's binary digest is compared with the public
  material index (public manifest `binary_sha256` values, every file in
  `benchmark/phase8c/bin/`, public reference-fix digests, public oracle manifest
  file digests, and public source-ref file digests); a duplicate is dropped and
  the chain continues;
- the private reference-fix copy is rewritten with a private header so it is
  never byte-identical to public source;
- before writing `hidden-manifest.json` the whole material set is re-checked for
  duplicates against the public index and for duplicate material between hidden
  samples; if any duplicate remains the corpus is not admitted (`blocked`, no
  manifest, no commitment, partial payloads removed);
- `--check` repeats the non-duplication check, so a tampered or contaminated
  private root cannot pass offline verification.

## Oracle validation (Lima guest, serialized)

For every candidate runtime variant the builder:

1. compiles the variant with Zig and verifies the container identity is
   `elf`/`x86_64`/64/little via `app.services.containers.detect_container`;
2. rebinds the public PoC manifest to the hidden binary digest
   (`fixture_sha256`) and keeps the committed PoC/regression cases and
   expected original/candidate behavior;
3. executes the rebound manifest through `app.services.poc_runner.run_poc`
   with the original bytes on both sides, so a vulnerable original must fail
   the fixed-candidate expectations while all original-side PoC and regression
   cases match.  `run_poc`/`run_path` hold the C11 Lima guest lock for the
   whole staging + execution window, so concurrent benchmark users cannot
   interleave;
4. admits the variant only when the differential is an executed `fail` with a
   native/emulated tier, at least one original PoC case observed as a crash,
   and every original PoC/regression expectation satisfied; the validation is
   executed twice and must produce the identical deterministic verdict (a
   transient guest/lock problem is retried a bounded number of times).

A missing runner, missing lock, or missing guest is `not_run`: the variant is
dropped and never faked.  Measured invalid configurations (for example
`-O2` builds where the optimizer eliminates the undefined-behavior store) are
recorded in the private build report with their measured reason and are not
admitted.  If fewer than six runtime variants validate, the builder returns
`blocked`, writes no private manifest and no public commitment, and
`hidden_available` stays false.

## Public commitment

`benchmark/phase8c/hidden-commitment.json` validates against
`contracts/hidden-benchmark-commitment.schema.json`.  It contains:

- `benchmark_id=phase8c-hidden`, `hidden_version=phase8c-hidden-v1`,
  `created_at=2026-11-16T00:00:00Z` (fixed);
- `sample_count`, `runtime_count`, `analysis_only_count`;
- `public_manifest_sha256`: SHA-256 of the exact public C3 manifest bytes;
- `commitment_sha256`: domain-separated commitment digest;
- `samples`: sorted `{opaque_sample_id, opaque_binary_sha256}` pairs;
- `limitations`: no paths and no hidden content.

Commitment digest definition (canonical, deterministic):

```
commitment_sha256 = sha256(
    b"phase8c-hidden-commitment-v1\n" +
    canonical_json(hidden_manifest_without_commitment_sha256)
)
```

where `canonical_json` is `json.dumps(indent=2, sort_keys=True,
ensure_ascii=True) + "\n"`.  The private manifest carries the same
`commitment_sha256` and the same `public_manifest_sha256`; `--check` recomputes
both and fails closed on any mismatch.

Because the digest binds the public-manifest bytes, regenerating the public
manifest (C3) invalidates the commitment until C4 is rebuilt.  The public C3
manifest currently keeps `hidden_commitment: null`; wiring that field is owned
by the C3 builder/Lead, not by this builder (C4 never edits the public
manifest).  The commitment file itself is the source of truth for the hidden
counts/digest.

## Modes and commands

```
# Build/validate/admit the private corpus and publish the commitment
.venv/bin/python scripts/build_phase8c_hidden.py \
    --root "$HOME/.binaryrepair/phase8c-hidden" \
    --validate-oracles --write-commitment --json

# Offline verification only (no compile, no guest): secure root, hashes,
# samples-vs-v2 schema, private sums, public commitment, leak scan
.venv/bin/python scripts/build_phase8c_hidden.py --check --json
```

Options:

- `--root PATH` (default `$PHASE8C_HIDDEN_ROOT` or
  `$HOME/.binaryrepair/phase8c-hidden`)
- `--public-manifest PATH` (default `benchmark/phase8c/manifest.json`)
- `--commitment PATH` (default `benchmark/phase8c/hidden-commitment.json`)
- `--validate-oracles`: execute the rebound PoCs in the Lima guest under the
  shared guest lock.  Without it runtime samples cannot be admitted, so the
  builder returns `blocked` and writes no manifest/commitment.
- `--write-commitment`: publish the public commitment after a successful build
  (otherwise the private corpus is built but `hidden_available` stays false).
- `--json`: public-safe JSON summary.

Exit codes: `0` success / verified `--check`; `2` not_run/blocked (including a
missing private root) with `hidden_available=false`; `1` violation detected by
`--check` (tamper, insecure root, inconsistent commitment).  A failed build
never writes a partial manifest or commitment and cleans partial payloads.

## Determinism and verification

- fixed timestamp, canonical JSON, sorted commitment samples;
- the compiler is invoked from the output directory with a stable *relative*
  output name so path-embedding formats stay deterministic (Mach-O embeds the
  output path in its UUID; an unstripped PE embeds link timestamp/GUID debug
  data).  The PE analysis-only variant is therefore linked with `-s`; the
  resulting `stripping_status` is reported honestly as `stripped`;
- binary builds, the private manifest bytes and the public commitment bytes are
  reproducible for a given compiler/version/flags/guest: two consecutive
  rebuilds of the same tree must produce byte-identical outputs;
- `reports/SHA256SUMS` covers the private manifest and every material file;
  `--check` also rejects unexpected extra files in `bin/`, `poc/`, `reference/`
  and verifies each oracle manifest's rebound digest and reference-fix digest;
- `scripts/check_contract_schemas.py` validates the committed commitment as a
  whole artifact (`phase8c-hidden-commitment` integration).

## What this does not claim

- No hidden benchmark run result is claimed by this builder (the Lead/C6 runs
  the hidden lane).  `hidden_available` in the public commitment means the
  commitment exists and the private corpus passed C4 admission, not that any
  model succeeded on it.
- Analysis-only samples have no runtime evidence and must never be scored as
  verified repairs.
- The runtime evidence is bound to this host's Lima guest and Zig 0.17.1; the
  private build report records the toolchain and runner/tier, and other hosts
  must not reuse it as their own measurement.
- Operational isolation protects against accidental public leakage and
  untrusted CI/fork access only.

## Tests

`tests/test_phase8c_hidden.py` covers deterministic/opaque commitments, C2
schema/semantics validation, the Lead private-manifest shape, rebound oracle
manifests, fake-compiler/fake-guest builds (admission, fallback/drop handling,
blocked <6 runtime, no-write modes), tamper/missing/insecure-root fail-closed
`--check` behavior, public-manifest binding, leak scans, no-network/no-AI
imports, and the absence of hidden material in the repository tree.  All tests
use `tmp_path` fake roots and never read or write the real private root or the
committed commitment.
