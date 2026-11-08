# Artifacts — shared hand-off directory

This directory is tracked by Git on purpose. Its contents must be readable by
every member, **not just the worktree** that produced them.

## Rules

1. Every artifact ships with a hash: a sibling `.sha256` file or an entry in a
   `SHA256SUMS` file.
2. This is not a scratch area. Work-in-progress belongs in an ignored temporary
   directory; only files another member must read go here.
3. Do not split a package across roots. Historical `dist/` packages stay in the
   source repository; new shared hand-offs go here and are listed in
   `MANIFEST.md`.
4. No secrets. Tokens, keys, client binaries and private host paths do not
   belong in a tracked directory.

## Verification

Every `artifacts/**/SHA256SUMS` must verify in a clean checkout. The four
original V5 replay logs are tracked evidence; do not regenerate or rewrite them
to make a checksum pass.
