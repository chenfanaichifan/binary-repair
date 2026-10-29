# 43 — Fixed C with no new imports

**Source:** `routeb/experiment/samples/fixed_badSink_existing_imports.c`  
**SHA-256:** `a2e4ff8f5071c20328f977153775c8dc7d8bf8a9f867278a5de2d48b81ccc90e`

This replaces the `strlen`/`exit` version for the guest rerun:

- no `strlen`: bounded NUL scan stops at 50;
- no `exit`: `exit_group(1)` via inline syscall 231;
- only existing imports: `fprintf`, `stderr`, `strcpy`, `printLine`.

Cross-target compile check (macOS host, x86_64 object):

```text
clang -target x86_64-apple-darwin -c ... -> rc 0
nm -u: ___stderrp, _fprintf, _printLine, _strcpy
```

No `strlen`, no `exit`, no new runtime symbol. On Linux the `stderr` symbol is
the existing `stderr` COPY relocation.

## Guest rerun

```text
--func CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink
--c-source fixed_badSink_existing_imports.c
--mode fixed
--run-manifest
```

Require:

```text
candidate_sha256 != decdcdb821bfe4c41a070b0a23a2f6497f46a92f439cb02a1e4139a82cde954b
c_source_sha256  == a2e4ff8f5071c20328f977153775c8dc7d8bf8a9f867278a5de2d48b81ccc90e
manifest-repaired.json.repaired_pass == true
```

Until the guest produces that, P3B remains **NOT ACCEPTED**; no fixed candidate
or success claim.
