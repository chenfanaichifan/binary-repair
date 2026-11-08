# 193 — Final project audit

Date: 2026-11-08

## Clean clone — old delivery repo

```text
branch delivery/all-hands-2026-11-07
BINARYREPAIR_BINUTILS_DIR=/opt/homebrew/opt/binutils/bin pytest -q
719 collected / 717 passed / 2 Linux-only skipped / 0 failed
```

## Clean clone — public v1.1.1

```text
repo   https://github.com/leesirleesirlee-star/Binary_Repair
main   1c762649e68fb4d64986e683c04f4eb2a26cc6ca
tag    v1.1.1
pytest 719 collected / 717 passed / 2 Linux-only skipped / 0 failed
artifacts sums 201/201 direct OK
```

## r4

```text
branch m2-r4 / 2838f7e
MANIFEST 18/18 OK
M2 tests 132 passed
```

## Other

```text
M3 executor self-test: 9/9
P2: exit 0, success_within_scope
compileall: exit 0
TODO/FIXME blocker: none
```

## Limitations kept

```text
Review 9-12 original not recovered; canonical reconstruction
M4 = Lead same operator
V4 model scope
Review 12/T7.7/T8.5 evidence levels limited
VMer record 88 NOT AVAILABLE
3 optional UI items not done
old repo main 472aa94 deliberately unchanged
```

## Release state

```text
v1.1.1 is final public release.
No new tag. No main change.
```
