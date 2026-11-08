# M4 v1.1.1 local fix

The public repository `leesirleesirlee-star/Binary_Repair` rejected push:
the current GitHub identity has no write permission.

Local commit/tag:

```text
commit 1c762649e68fb4d64986e683c04f4eb2a26cc6ca
tag    v1.1.1
base   v1.1.0 / 1e30bd5
```

Verification:

```text
pytest: 719 collected / 717 passed / 2 Linux-only skipped / 0 failed
artifacts sums: 201/201 direct
repaired ELF upload/download: included
```

Apply:

```bash
git bundle verify m4-v1.1.1.bundle
git fetch ./m4-v1.1.1.bundle main:refs/heads/m4-v1.1.1
git cherry-pick 1c76264   # or merge
git tag -a v1.1.1 -m '...'
git push origin main
git push origin v1.1.1
```
