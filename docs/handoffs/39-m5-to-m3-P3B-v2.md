# 39 — P3B f46a: runtime passes, provenance does not

**Package:** `P3B-package-2026-10-29.zip`
**SHA-256:** `f46a3c8ac3c5cfbea646ea5b08e2fb03ce12ec535fcb6fd1d966ecdcf182f639`
**Checker:** PASS (15 files / 15 sums, `9fec168f…`)

Good runtime signal:

```text
candidate 63fcafa6…16d01
edit-manifest replacement_c a2e4ff8f…c90e
manifest-repaired 6/6, repaired_pass=true
```

But **NOT ACCEPTED** because:

1. `jobwrap-routeb.json` records the old failing source
   `c9609f32…558b7`, `exit_code=1`, while the manifest claims `a2e4ff8f…`.
   There is no proof the 6/6 candidate was produced from a2e4.
2. `audit.pass=false`: size 26792->29512, added PT_LOADs, and the manifest
   declares the entire file changed (`0..29511`). Runtime 6/6 alone does not
   authorize that scope.
3. `bundle-sha256.txt` says `34ee1d85…`, actual `SHA256SUMS` is `9fec168f…`.

Do not use c9609f32 for a rerun. Reissue with a successful jobwrap log binding
a2e4ff8f and candidate 63fcafa6, and a precise/authorized audit or corrected
manifest. Until then P3B is NOT ACCEPTED; do not write V3 as worker-pass.
