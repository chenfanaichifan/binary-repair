# t30-rebuild-2026-11-05 — second-window build of the T30 CWE-416 case

This directory is the evidence for record
`docs/handoffs/118-m3-t30-baseline-rebuild-2026-11-05.md`.

It re-runs `docs/handoffs/evidence/T30`'s build and trigger in a **baseline-clean
window** (snapshot uid 11, `gate4-harness`) and checks the result against
`T30/build.json` field by field. The first build ran on snapshot uid 14 and said
so; this is the baseline run that record left open.

## Result in one line

The rebuild reproduces `c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9`,
25,344 bytes, byte-identical to `T30/build/original.elf`. Twenty of the
twenty-one compared `build.json` fields match exactly; the twenty-first
(`window.is_baseline`) differs because this run is the baseline one. What counts
as a compared field, and why the prose fields are excluded, is stated in
`07-rebuild.json#conformance_scope`.

## Files

| File | Origin | What it is |
|---|---|---|
| `01-window-and-isolation.txt` | guest | Window identity, toolchain, baseline evidence, input hashes |
| `02-build.txt` | guest | `sh build.sh` stdout, stderr and exit status, verbatim |
| `03-readelf.txt` | guest | Full `readelf -h -l -S -d -n` plus a derived machine check |
| `04-trigger.txt` | guest | Trigger observation, 251 deterministic runs, ASLR-on contrast |
| `05-asan.txt` | guest | AddressSanitizer confirmation — a diagnostic, not the artefact |
| `06-SHA256SUMS` | guest | Digests of `01`–`05`, computed inside the guest |
| `07-rebuild.json` | host | Structured conformance record: 21 tabulated fields against `T30/build.json` |
| `collect.sh` | host | The script the guest ran to produce `01`–`06` |
| `SHA256SUMS` | host | Digest of every file here except itself |

Two manifests on purpose, and they cover different sets:

- `06-SHA256SUMS` is what the guest hashed, over `01`–`05`, before anything left
  the machine. It is the transport check.
- `SHA256SUMS` is the whole directory, including the three files added on the
  host after export (`07-rebuild.json`, `collect.sh`, `README.md`).

Neither is a result-bundle manifest. Nothing here is a bundle input.

## Where `T30/` actually lives

`docs/handoffs/evidence/T30` is **not** in this branch's tree. This branch was cut
from `origin/integration/live-bridge-2026-11-03` at `bcb7a30`; the T30 evidence
landed afterwards on `member-3/t62-host-safe` at `c274893`, which is not an
ancestor here. Every `T30/...` path in this directory therefore points at that
commit, not at a sibling folder — a reviewer holding only this branch can still
check the central claim:

```sh
git cat-file -p c274893:docs/handoffs/evidence/T30/build/original.elf | sha256sum
# c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9
git cat-file -s c274893:docs/handoffs/evidence/T30/build/original.elf
# 25344
```

Both were run on the host on 2026-11-05. Carrying T30 onto this line is a
delivery decision, not an evidence one; this directory does not make it.

## What is deliberately not here

**No second `original.elf`.** The rebuilt binary is byte-identical to
`T30/build/original.elf`, which is already in git at commit `c274893`. Shipping a
copy would create two paths for one hash and invite someone to bind the wrong
one. The equality is the evidence; the file is redundant.

**No `original.asan.elf`.** The ASan build is a different binary by design
(`-fsanitize=address` is not in `build.json#build.complete_flags`). Its output is
in `05-asan.txt`; the artefact itself is not shipped, because the only reason to
ship a binary is to have it ingested, and that one must never be ingested.

**No fixture edit.** `build.json`, `contract.json`, `tests/`, `harness.c` and
`original.c` are byte-identical to T30 at `c274893`. This directory adds
measurement, not change.

## How to re-run

Inside the guest, after reverting to `gate4-harness`:

```sh
mkdir -p /var/tmp/cwe416 && cd /var/tmp/cwe416
# copy build.sh original.c harness.c trigger.sh collect.sh in
sh build.sh                      # expect sha256=c9c2632e...23c9 size=25344
sh collect.sh                    # writes evidence/01..06
```

`build.sh` defaults `JULIET_ROOT` to `$HOME/evaluator/src/juliet-v1.3`, which the
baseline snapshot provides with a complete `C/testcasesupport` (8 files) and a
`C/testcases` tree that contains CWE121 only — so the case source is supplied
explicitly and the support unit is not, exactly as `build.json` describes.

## The one thing to carry forward

`original.c`'s `main` is guarded by `#ifdef INCLUDEMAIN` and the T30 gcc line
does not define it, so the case contributes no entry point and `harness.c` is the
only one. The synthetic `src.c` that record 116 measured had an unguarded `main`,
which is why it failed to link. That failure was a fixture-authoring defect, not
a toolchain or window problem — see record 118 §1.
