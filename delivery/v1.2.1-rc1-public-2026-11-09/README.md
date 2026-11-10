# v1.2.1-rc1 public candidate

Local public candidate:

```text
base   94393403319a10acc00552a7ae62836699036518 (v1.2.0)
commit d7d20f4ff2f920b5cfec5e81e3c4377529a9885a
tag    v1.2.1-rc1 (annotated)
```

Verification:

```text
737 collected / 735 passed / 2 Linux-only skipped / 0 failed
browser e2e 12 passed
```

Push was denied for `huajinyao`; no public tag/release was created. M4 must
push with an authorized identity:

```bash
git bundle verify v1.2.1-rc1.bundle
git fetch ./v1.2.1-rc1.bundle d7d20f4:refs/heads/v1.2.1-rc1
git push origin d7d20f4:refs/heads/v1.2.1-rc1
git push origin refs/tags/v1.2.1-rc1
```

Do not push main; keep public main at v1.2.0.
