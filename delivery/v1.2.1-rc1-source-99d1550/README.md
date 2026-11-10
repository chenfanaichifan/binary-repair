# v1.2.1 source snapshot from 99d1550 — NOT public rc1

> **Boundary:** this is a source-bound snapshot, not the public
> `v1.2.1-rc1`. Public rc1 is `f5346978... -> d7d20f4`.

```text
base   94393403319a10acc00552a7ae62836699036518 (v1.2.0)
commit 67476c8010e68080c99b422f26f83f98fc0ad2bb
tag    v1.2.1-rc1-source-99d1550 (annotated)
```

This snapshot is from `release/v1.2.1@99d1550` (final 222/228 alignment) and
excludes N8/N9/N10/N11. It must not be used as evidence for public rc1 and must
not overwrite the public `v1.2.1-rc1` tag.

Verification:

```text
737 collected / 735 passed / 2 Linux-only skipped / 0 failed
browser e2e: 12 passed
```

Fetch/verify only:

```bash
git bundle verify v1.2.1-rc1-source-99d1550.bundle
git fetch ./v1.2.1-rc1-source-99d1550.bundle \
  67476c8010e68080c99b422f26f83f98fc0ad2bb:refs/heads/source-rc1-99d1550
git tag v1.2.1-rc1-source-99d1550 67476c8
```

Do not push this as `v1.2.1-rc1`; the public tag already exists at
`f5346978... -> d7d20f4`. Do not move public main `9439340` or `v1.2.0`.
