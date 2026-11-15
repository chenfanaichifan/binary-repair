# Cross-binary repair benchmark

Cases in `cases.json` are the independent evaluation set for P5–P9.  It keeps
the original hard-case binary (3 cases), the public CWE121 binary, and two
project-authored x86-64 fixtures:

- `CWE122_heap_copy`: malloc(16) + unchecked memcpy;
- `CWE787_index_write`: unchecked atoi index write.

The new fixtures are built with `x86_64-linux-gnu-gcc -O0 -g
-fno-stack-protector -fno-pie -no-pie`; `build.json` records the hash.  The
reference files are source-only and are never supplied to the AI prompt or
counted as AI verified.  PoC manifests are under `fixtures/poc/`.
