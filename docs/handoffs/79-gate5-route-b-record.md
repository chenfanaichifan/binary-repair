# 79 — Gate 5 Route B record from existing P3B v6 evidence

**Status: NOT VERIFIED / NOT RUN.** No Gate 5B pass. No new VM was started.
**Subject:** Route B candidate `208574ab…6717`; original `aa428157…8393`.
**Evidence source:** `dist/m5-evidence/P3B-package-v6-2026-10-31.zip` (checker PASS 25/25).

## R1–R8

| ID | Check | Observed | Verdict |
|---|---|---|---|
| R1 | identity / binding | candidate/original hashes present; Route B probe now committed and frozen at `05d9a2cd…edb82`; **successor built with this pin not yet recorded** | **PARTIAL** |
| R2 | runtime mapping / no W+X | `audit.json` reports 4 PT_LOAD, no W+X; actual candidate header parse: 13 phdrs / 4 PT_LOAD. **However** `independent-views/readelf-program-headers.txt` is stale (15 phdrs, offset `0x7000`) and does not describe this candidate. | **NOT VERIFIED** |
| R3 | added code memory = file | no runtime memory read / no `memory=file` hash | **NOT VERIFIED** |
| R4 | entry / redirect markers | probe design frozen: `gdb x/2i 0x4012b0`, target must be in `0x4018e9–0x402000`; **no guest run yet** | **NOT VERIFIED** |
| R5 | six cases | `manifest-repaired.json`: 6/6, rc/stdout_hex/stderr_hex all match; no separate raw `.rc/.stdout.bin/.stderr.bin` files | **PASS (compact JSON; raw files absent)** |
| R6 | isolation | `jobwrap-routeb.json`: uid 1003, CapEff 0, NoNewPrivs 1, netns empty, exit 0; this is the **Route B routeb harness**, not the fixed-argv Gate 5 successor | **PARTIAL** |
| R7 | candidate stable | `reproducibility.json`: 2 runs, byte-identical, candidate `208574ab…6717` | **PASS** |
| R8 | manifest | P3B `SHA256SUMS` LF, checker PASS 25/25; but manifest contains the stale independent readelf above | **PASS (manifest integrity only)** |

## Probe separation (non-negotiable)

- P3B's `executor/probe_patcherex2.py` / `jobwrap-routeb` is **V2/interface
  evidence** for the repair bundle. It is **not** Gate 5 Route B placement
  evidence and cannot fill R1–R8.
- The Route A probe `scripts/m4_gate5_probe.py` (`f39a0302…46cb`) is bound to
  candidate `c4a159…aa82`; it cannot be reused to run Route B candidate
  `208574ab…6717`.
- Gate 5 Route B requires its own M4/M3-defined probe (candidate `208574ab…`,
  mode `m4-gate5b`, probe hash frozen before successor build).

## Probe freeze verified (2026-10-31)

```text
scripts/m4_gate5b_probe.py
SHA-256 05d9a2cd417880c9be51e1a4cd4608158d94b50da233b223c2f4a589850edb82
source pin PROBE_B_SHA256_HEX = 05d9a2cd…
build recipe = 05d9a2cd…
candidate 208574ab…6717; original aa428157…8393
R4: entry 0x4012b0 -> runtime jmp target in 0x4018e9–0x402000
```

`e635d646…80ed7` is superseded by `05d9a2cd…edb82`.

## Missing items

```text
new successor binary built with probe 05d9… and recorded binary hash
fixed-argv successor run / raw placement evidence
runtime mapping readelf that actually matches candidate 208574ab
memory=file hash for added code
entry/redirect runtime markers
fresh isolation under Gate 5 fixed-entry successor
fail-closed tampered-probe raw log
separate six-case raw files (if required beyond compact JSON)
```

## Why this is not a pass

The existing P3B v6 package is repair evidence, not a Gate 5 fixed-entry run. It
does not bind a Route B probe or successor, its independent readelf is stale, and
it has no runtime memory/entry/isolation proof for Gate 5.

## Required window (only for missing items)

One guest window is sufficient; do not rerun the full Gate 5 suite:

```text
successor + Route B probe + candidate 208574ab
-> fresh readelf/mapping, memory=file, entry/redirect
-> six raw cases, isolation, fail-closed
-> 29-file bundle + real SHA256SUMS
```

Then M4 re-hashes and fills R1–R8; Lead decides Gate5B. No final MVP tag.

## Boundary

```text
Gate 5 Route A: PASS (final)
Gate 5 Route B: NOT RUN / NOT VERIFIED
Gate5B pass: absent
fixture: FROZEN (candidate scope only)
final-acceptance tag: NOT CREATED
```
