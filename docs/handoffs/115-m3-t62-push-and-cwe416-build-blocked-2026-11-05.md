# 115 — T6.2 pushed and `8c77fcd` is now reachable; the CWE416 build cannot run here

**Owner:** M3 · **Date:** 2026-11-05 · **Status:** `member-3/t62-host-safe`
pushed, `8c77fcd` verified fetchable from a clean remote clone. The CWE416
`original.elf` is **not built** — there is no compiler and no guest route from
this workspace, and `AGENTS.md` forbids building here. Two defects in
`build.sh` would also make the recorded digest non-reproducible. T8.3 stays
**blocked**.

## 1. Done — the push, and why it was the blocker

`member-3/t62-host-safe` had never been pushed: `origin` had no such ref at all.
That is why `8c77fcd` was unfetchable — it is an ancestor of `96a0a20` and lived
only in this worktree.

```text
git push -u origin member-3/t62-host-safe
 -> 96a0a20, 11 commits ahead of origin/main
```

Verified the way it matters, from an empty repository that fetches only from the
remote (no local objects to borrow):

```text
git init; git remote add origin <url>
git fetch --depth=20 origin member-3/t62-host-safe
git cat-file -t 8c77fcd                  -> commit
96a0a20 docs(t62): review request to M1 …
bdce3ca feat(broker): host-safe T6.2 executor …
8c77fcd docs: record T6.0 baseline migration status
79a416f docs: establish T6.0 live-bridge baseline …
```

Audited before pushing: none of the 11 commits adds anything under
`.workbuddy/`, `.tmp/`, `worklogs/` or `dist/`, and the largest added file is
1,122 lines of C (`route-a/jobwrap-gate5/jobwrap_gate5.c`). Nothing private or
binary went out.

So you do not need a bundle. `git fetch origin member-3/t62-host-safe` is enough,
and `8c77fcd` comes with it.

## 2. Not done — the build, and the three independent reasons

| Reason | Evidence |
|---|---|
| No compiler on this host | `gcc`, `cc`, `clang`, `tcc`, `x86_64-linux-gnu-gcc` all absent |
| No WSL fallback | `wsl.exe` is refused by the sandbox program blacklist; the block is policy, not a missing install, and I am not permitted to route around it |
| Building here is prohibited | `AGENTS.md:46`: never compile model-generated C on the host; if the guest is unavailable, "leave execution unavailable … do not 'just try it locally'" |
| No guest access from this workspace | `docs/handoffs/43-m4-gate5-gate6-plan.md:129` records the same for M4 |

There is a fourth, structural reason: **the fixture is not on my branch.** It
exists only on the integration line. `member-3/t62-host-safe` has the CWE121
fixture in its reverted state and no `CWE416_Use_After_Free__malloc_free_char_01/`
at all. Even with a compiler, committing `original.elf` and the `build.json`
edit would mean importing the fixture onto my branch first, which would put a
fixture from the integration line into a handoff branch — a provenance move I
will not make unilaterally.

## 3. Two defects in `build.sh` that would make the digest mean less than it looks

### 3a. `-g` without a prefix map: the digest encodes the build directory

This repository already measured this, in T30, and T30's recipe fixes it. The
comment in `docs/handoffs/evidence/T30/build/build.sh` records three builds of
the same source with the same gcc:

```text
relative paths, cwd = source dir   -> fc40085c…87e0   (stable)
absolute paths, same cwd           -> 0a26a805…07ec   (stable)
relative + prefix-map              -> c9c2632e…23c9   (stable)
```

Each style is internally reproducible; the digest differs **between** styles.
T30 therefore adds `-fdebug-prefix-map` and `-ffile-prefix-map`.

The fixture's `build.sh` has `-g -O0` and neither flag. So the `sha256=` it
prints is a function of the directory the guest happened to build in. Record it,
and a second build in `/tmp/xyz` produces a different digest — which then reads
as "reproduction failed" when nothing is actually wrong.

If the digest is meant to be portable, the recipe needs the two prefix-map flags
and `build.json#flags` must say so, because they change the binary. That is a
fixture decision; I am not editing it.

### 3b. `build.sh` needs `python3` before it prints anything

```sh
EXPECTED=$(python3 -c '…build.json…["output"]["sha256"]…')
```

Under `set -eu`, a guest without `python3` exits here — before the `sha256=`
line is printed. The instruction "run it and copy the printed sha256=" then
produces nothing, and the natural misreading is "the build is broken" rather
than "the reader is missing". `sha256sum` alone would do; the JSON read is the
only reason python is involved.

### 3c. Recording the printed digest is self-attestation

The script prints the hash of the binary it just produced. Writing that value
back into `build.json` makes the script "reproduce" it forever afterwards,
including on a machine that would produce something else. What gets recorded is
"this build happened once in this directory", not "this source yields this
binary". The second claim needs a second, independent build to agree — which
3a currently prevents.

This is not an argument against recording it. It is an argument against calling
the result reproduced. I would record it as `measured_by: M3, single build,
<dir>, <gcc version>` and leave the reproduction claim open until a second build
matches.

## 4. There is already a built CWE416 binary — for a different program

Worth stating because "we have no CWE416 ELF" is not true:

| | T30 evidence | This fixture |
|---|---|---|
| source | `original.c`, 3,198 B, `fa84a6bb…f42e` (upstream at `01e353d`) | `src.c`, 2,742 B, `9a909296…` (synthetic) |
| binary | `build/original.elf`, 25,344 B, `c9c2632e…23c9` | absent |
| extras | `readelf.txt`, trigger observed, 10/10 sums | 9/9 sums, no binary |

Same CWE id, different program. T30's digest cannot fill this fixture's
`output.sha256`, and this fixture cannot inherit T30's trigger measurement. But
if the goal is "a measured use-after-free sample", T30 already is one, and it is
built from upstream source rather than synthetic text — which makes it the
stronger artifact for T8.3 regardless of how this build goes.

## 5. The exact guest sequence

Run on the Linux x86-64 guest, from a checkout of the integration line, not from
my branch:

```sh
git fetch origin
git worktree add /tmp/cwe416 origin/integration/live-bridge-2026-11-03
cd /tmp/cwe416/fixtures/public/CWE416_Use_After_Free__malloc_free_char_01

gcc --version                       # record it; build.json says ">= 9, C11"
pwd                                 # record it; it goes into the digest under 3a
sh build.sh                         # expect: sha256=<64 hex>
sha256sum original.elf
readelf -h original.elf | grep -E 'Class|Machine|Type'
```

Return: the `sha256=` line, `pwd`, `gcc --version`, the three `readelf` lines.
I will do the `build.json` edit and the `SHA256SUMS` regeneration only after I
have those, and I will state the directory the digest belongs to.

If the guest has no `python3`, run the compiler line from `build.json#argv`
directly and `sha256sum` the result — that is the same build, and it avoids 3b
without editing anything.

## 6. What would unblock me

A guest session with `gcc`. That is the only missing input; everything else
(sources, hashes, recipes, provenance) is already in the tree and verified.
