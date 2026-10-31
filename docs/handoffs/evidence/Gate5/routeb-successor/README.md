# jobwrap-gate5 — Gate 5 Route B successor

The SAME successor binary that serves Gate 5 Route A, now also carrying the
Route B fixed-entry probe mode (`m4-gate5b`). Route A mode (`m4-gate5`) is
unchanged: its probe blob `f39a0302…d146cb` and isolation semantics are
bit-identical to the previously delivered successor.

## Why a recompile

The Route A successor (`90af91ef…ff20`) only knew the `m4-gate5` probe mode.
Route B needs its own M4-authored placement probe (`m4_gate5b_probe.py`,
bound to candidate `208574ab…6717`), so the successor was rebuilt once to add
the `m4-gate5b` mode and pin the Route B probe blob at compile time.

## What it runs (Route B)

```
jobwrap-gate5 probe m4-gate5b -- <repo-root> <work-dir>
```

which, after isolation, `execv`s exactly:

```
/usr/bin/python3 <repo-root>/scripts/m4_gate5b_probe.py <repo-root> <work-dir>
```

No shell string, no PATH lookup, no caller-supplied command.

## Files

- `jobwrap_gate5.c` — successor source (single source, covers both routes).
- `m4_gate5b_probe.py` — M4-authored Route B placement probe (pinned).
- `build-recipe.md` — guest-only build command and post-build hash binding.

## Isolation (identical to Route A)

root-only · no-egress netns · `setgroups`→`setgid(1003)`→`setuid(1003)` ·
`CapEff=0` · seccomp allow-list · `NoNewPrivs=1` · rlimits · `clearenv` +
minimal whitelist · fixed argv · absolute paths · probe root-owned/non-writable ·
fail-closed (probe blob pinned at compile time).

## Binding

The successor binary hash binds **Gate 5 Route B**. Route A evidence remains
bound to the Route A successor `90af91ef…ff20` and is not re-signed by this
rebuild. The two routes share one binary now, but their evidence chains are
kept separate.

## Key hashes

- successor binary: `0066973d5304e06024b56fbc1e9d969d5007eac290314935129517f931209eee`
- Route B probe blob: `05d9a2cd417880c9be51e1a4cd4608158d94b50da233b223c2f4a589850edb82`
- Route B candidate: `208574ab5b7753fab6f28860830069770622fb7b1fcb8d181fa50453f8656717`
- Route B original: `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`
