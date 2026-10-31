# jobwrap-gate5 — Gate 5 Route A successor

A NEW, independently-built isolation executor for **Gate 5 Route A only**. It
runs M4's fixed runtime-placement probe inside the disposable guest under
isolation, so M4 can classify the result PASS / FAIL / NOT VERIFIED.

## Why it exists

The original `jobwrap_v3.c` source is permanently lost (host disk, git history,
and guest `/home/runner` were all checked). But Lead 52 §3 does not require
rebuilding the same deployed `jobwrap`: it allows a fixed-argv probe mode, or a
documented equivalent. Handoff 66 approves this successor path.

## What it runs

```
jobwrap-gate5 probe m4-gate5 -- <repo-root> <work-dir>     # Route A (c4a159…)
jobwrap-gate5 probe m4-gate5b -- <repo-root> <work-dir>    # Route B (208574ab…)
```

which, after isolation, `execv`s exactly:

```
/usr/bin/python3 <repo-root>/scripts/m4_gate5_probe.py  <repo-root> <work-dir>   # Route A
/usr/bin/python3 <repo-root>/scripts/m4_gate5b_probe.py <repo-root> <work-dir>   # Route B
```

No shell string, no PATH lookup for python3, no `m4_gate5_fixed.sh`, no
caller-supplied command. Each mode pins its own probe blob at compile time
(fail-closed).

## Files

- `jobwrap_gate5.c` — the successor source (M5-authored, this is the recovered
  source that the old jobwrap never had in git).
- `build-recipe.md` — guest-only build command and post-build hash binding.

## Isolation (semantically equivalent to the old jobwrap run_argv)

root-only · no-egress netns · `setgroups`→`setgid(1003)`→`setuid(1003)` ·
`CapEff=0` · seccomp allow-list · `NoNewPrivs=1` · rlimits · `clearenv` +
minimal whitelist · fixed argv · absolute paths · probe root-owned/non-writable ·
fail-closed (probe blobs pinned at compile time: Route A `f39a0302…d146cb`,
Route B `e635d646…80ed7`).

Byte-equivalence to the lost source is **not** claimed; semantic equivalence +
independent verifiability of each isolation item is the bar.

## Binding

The successor binary hash binds **only Gate 5**. Gate 4 stays bound to the old
`jobwrap b232d60b`; P4 and the Gate 4 evidence chain are not re-signed. Record
`51` remains unsigned until M4 independently verifies the probe run.
