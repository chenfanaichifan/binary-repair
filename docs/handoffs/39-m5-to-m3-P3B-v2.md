# 39 — M5 to M3: P3B f46a is not accepted yet

**Package:** `P3B-package-2026-10-29.zip`
**SHA-256:** `f46a3c8ac3c5cfbea646ea5b08e2fb03ce12ec535fcb6fd1d966ecdcf182f639`
**Checker:** PASS (15 files / 15 sums, `9fec168f…`)
**Verdict:** **NOT ACCEPTED.** Runtime 6/6 is not enough while provenance and
audit are inconsistent.

## What is good

```text
candidate:      63fcafa6ed01d2db7d5d8a1af460af994e65da853c0c250b05c3eb761f616d01
replacement C:  a2e4ff8f5071c20328f977153775c8dc7d8bf8a9f867278a5de2d48b81ccc90e
manifest-repaired: passed 6 / total 6 / repaired_pass true
```

This is the passing runtime, not the old `c9609f32…` link-failure source.

## Blocking inconsistency 1 — jobwrap log says the old source

`jobwrap-routeb.json`:

```json
"c_source": ".../fixed_badSink.c",
"c_source_sha256": "c9609f32e4e49619265af4a7a6a7997947efa953ac15f94320913fd8cfc558b7",
"exit_code": 1
```

`edit-manifest.json` says:

```json
"replacement_c_sha256": "a2e4ff8f5071c20328f977153775c8dc7d8bf8a9f867278a5de2d48b81ccc90e"
```

The package therefore contains no proof that the 6/6 candidate was produced from
`a2e4ff8f…`. Reissue with a jobwrap log whose `c_source_sha256` is `a2e4ff8f…`
(and exit_code 0), or provide an equivalent immutable provenance binding.

## Blocking inconsistency 2 — audit.pass=false

`edit-manifest.audit.pass=false`:

```text
same_file_size: false
changed_inside_intervals: false
header_changes.same_program_header_count: false
changed_file_intervals: [{start:0,end:29511,size:29512}]
original_size 26792 -> candidate_size 29512
```

This is not a small in-function patch: the candidate adds two `PT_LOAD`s and the
manifest declares the entire file changed. The runtime 6/6 does not prove that
all changes are inside the authorized Route B function/segments.

M5’s acceptance call: **do not accept as verified** until M3 supplies either:

1. a precise Route B edit manifest (function bytes + added segments, with the
   exact changed ranges), plus an explicit authorized size/header change; or
2. a corrected candidate/audit where every change is explainable and within the
   approved scope.

## Blocking inconsistency 3 — bundle hash field

`bundle-sha256.txt` says `34ee1d8506a4858cc7434f5914b66f82f3d35051e202d2b0ee3fb4440383e513`;
the actual `SHA256SUMS` file hash is
`9fec168f96d2772c6caf8c3bbb86482ff72fedc467591532bdd3a8290b783543`.
Do not keep a stale bundle-hash field.

## Required reissue

- new package/hash;
- handoff + sorted slash `SHA256SUMS`;
- jobwrap log binds `a2e4ff8f…` and candidate `63fcafa6…`;
- corrected audit/edit manifest or explicit M5/M4-acceptable scope;
- checker PASS.

Until then: **P3B NOT ACCEPTED; V3 is not written as passed in the worker record.**
Gate 4 remains NOT RUN.
