# v1.2.1-rc1 public candidate

```text
base   94393403319a10acc00552a7ae62836699036518 (v1.2.0)
commit 67476c8010e68080c99b422f26f83f98fc0ad2bb
tag    v1.2.1-rc1 (annotated) -> 67476c8
```

This is the refreshed prerelease candidate built from
`release/v1.2.1@99d1550` (final 222/228 alignment). It is not a stable release.

Verification:

```text
737 collected / 735 passed / 2 Linux-only skipped / 0 failed
browser e2e: 12 passed
```

Push (M4 only, after verification):

```bash
git bundle verify v1.2.1-rc1.bundle
git fetch ./v1.2.1-rc1.bundle \
  67476c8010e68080c99b422f26f83f98fc0ad2bb:refs/heads/v1.2.1-rc1
git push origin 67476c8010e68080c99b422f26f83f98fc0ad2bb:refs/heads/v1.2.1-rc1
git push origin refs/tags/v1.2.1-rc1
```

Do not push `main`; keep public main at `9439340` and `v1.2.0` at `9439340`.
Create a GitHub prerelease (`prerelease=true`), not a stable release.


