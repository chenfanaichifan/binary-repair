# delivery/ - shared hand-off directory

This directory is tracked by git on purpose. Its contents must be readable by
every member, not just the worktree that produced them.

## Why it is tracked

Historically `delivery/` sat in `.gitignore`, so a bundle written here existed
only on one host. Records 27/30/44/47 all describe a member asking another for a
file that was "in `delivery/`" but unreachable, and gate evidence that could not
be re-verified for the same reason. A file that no one else can fetch is not a
delivery.

The ignore rule was removed. If you add a large artifact here, commit it.

## Rules

1. **Every artifact ships with a hash.** Put its SHA-256 next to it, either in a
   sibling `.sha256` file or in this directory's `SHA256SUMS`.
2. **The directory is not a scratch area.** Work-in-progress belongs in
   `_scratch/` (ignored). Only files another member must read go here.
3. **Do not split a package across two roots.** Historical packages already live
   under `dist/` and stay there; new shared hand-offs go here and are listed in
   `MANIFEST.md`.
4. **No secrets.** Tokens, keys, and private host paths do not belong in a
   tracked directory.

## What is already shared

`dist/` is also tracked and holds the earlier evidence packages
(`m5-evidence/P3A-routea-2026-10-31-v7.zip`,
`m5-evidence/P3B-package-v6-2026-10-31.zip`, the Route B kits). Those keep their
current location; `MANIFEST.md` records both roots so a reader does not have to
guess which one is authoritative.

## Verification

`tests/test_delivery_visibility.py` fails if a `/delivery/` ignore rule comes
back, or if this file stops being part of the tree.
