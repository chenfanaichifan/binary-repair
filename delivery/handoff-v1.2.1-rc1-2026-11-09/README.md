# v1.2.1 source snapshot from 99d1550 — NOT public rc1

Status: **source handoff snapshot, not the public `v1.2.1-rc1` release.**

```text
public base   94393403319a10acc00552a7ae62836699036518 (v1.2.0)
source        release/v1.2.1 @ 99d1550
snapshot      67476c8 (handoff snapshot label only; no public tag)
public rc1    v1.2.1-rc1 -> f5346978... -> d7d20f4 (different commit)
```

This snapshot is from `99d1550` and **excludes** the later N8/N9/N10/N11
alignment in `ab25c17` / public candidate `d7d20f4`.

Do not use this snapshot as evidence for the public `v1.2.1-rc1` tag. The
public rc1 handoff is the delivery branch package, not this branch.

Verification recorded at source 99d1550:

```text
737 collected / 735 passed / 2 skipped / 0 failed
e2e 12 passed
```

No tag was created or moved by this note.
