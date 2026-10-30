# 42 — P3B fixed C: static verification only

**Package:** `P3B-fixed-C-2026-10-29.zip`
**SHA-256:** `2f7691bef93209a44789b72ead6461faa1adaea4713d2fc63eff82042ca054b8`
**Size:** 2,459 B

## Verified

| Item | Value |
|---|---|
| failing fixed C | `c9609f32e4e49619265af4a7a6a7997947efa953ac15f94320913fd8cfc558b7` (link failure; do not rerun) |
| passing fixed C | `a2e4ff8f5071c20328f977153775c8dc7d8bf8a9f867278a5de2d48b81ccc90e` |
| old normalized C | `0e5da0423d68518933f0fb910e8732d58f73ca9cc8323b1dae7bc82694753990` |
| ZIP inner sums | 3/3 OK |
| syntax check | `cc -fsyntax-only fixed_badSink.c` rc 0 |
| stderr literal | 42 bytes exactly |

Diff against normalized C adds, before `strcpy`:

```c
if (strlen(data) >= sizeof(dest)) {
    fprintf(stderr, "ERROR: input exceeds destination capacity\n");
    exit(1);
}
```

This is a real source change, not the old normalized file.

## Not yet accepted

- No guest rerun with this C.
- No new candidate hash.
- No `repaired_pass=true` / `manifest-compare.json`.
- P3B remains **NOT ACCEPTED**.
- Do not write fixed candidate, success, or Gate 4 pass.

## Required rerun

```text
--func CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink
--c-source fixed_badSink.c
--mode fixed
--run-manifest
```

Require:

```text
candidate_sha256 != decdcdb821bfe4c41a070b0a23a2f6497f46a92f439cb02a1e4139a82cde954b
c_source_sha256  != 0e5da0423d68518933f0fb910e8732d58f73ca9cc8323b1dae7bc82694753990
manifest-repaired.json.repaired_pass == true
```

Then package with `handoff.json`, slash `SHA256SUMS`, sorted paths, checker PASS;
M5 will run adapter/worker and real p2 only after that.

Old `p3b-2026-10-29.zip` defects remain confirmed: no `handoff.json`,
backslash sums, and `bundle-sha256` mismatch.


**Correction:** `c9609f32…` is the failed source; the r2 package uses `a2e4ff8f…`. See `39-m5-to-m3-P3B-v2.md` and `50-p3b-v3-adapter.md`.
