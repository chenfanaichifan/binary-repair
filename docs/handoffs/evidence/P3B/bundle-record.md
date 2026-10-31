# Route B/provider executor bundle

- mode: `fixed`
- function: `CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink`
- original: `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`
- candidate: `63fcafa6ed01d2db7d5d8a1af460af994e65da853c0c250b05c3eb761f616d01`
- audit_profile: `route_b_recompile`; static audit: `pass` (size change recorded; same_file_size=false)
- reproducibility: `measured` (2 runs, byte-identical)
- runtime manifest: `measured` (6/6, repaired_pass=true)
- executor_sha256: `87fee2b7f28eee7b4e29422940cc93fc68f5a49e45e722e715b1622ef9301d91`


## Executor binding (v4 correction)

Actual executor: `4f07217583c00c3a02ceaa8294eb330270a0ba7ba9ec03ce3aa4fbcfa831b05d`
(`executor/routeb_executor.py`). `87fee2b7…` is the previous build, not the one
that ran. Runtime evidence: `audit.json` (`route_b_recompile`, `changed_inside_intervals=true`,
`pass=true`) and `jobwrap-routeb.json` (`exit_code=0`).
