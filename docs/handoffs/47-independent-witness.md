# 47 — Independent witness (M5) — 2026-10-29

**Scope:** independent checker/hash observation only. This is **not** a gate
approval, not a verifier signature, and not a success claim.

## P3A v4 — witnessed

```text
package: P3A-routea-2026-10-29-v4.zip
command: python scripts/check_handoff.py /tmp/form5/p3a \
           --expect-from M3 --expect-to M5
result:  PASS, 25 files, 25 sums
sums:    d9c33b42ec537346caa339c052deb21f6589ce59af9ca07cd71405953f7e0bcb
candidate: c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82
```

P3A v4 is accepted as partial Route A evidence; worker outcome remains
`inconclusive` / failing `interface` (V2/V4/V5 not_run).

## P3B f46a — checker witnessed, acceptance blocked

```text
package: P3B-package-2026-10-29.zip
command: python scripts/check_handoff.py /tmp/form5/p3b \
           --expect-from M3 --expect-to M5
result:  PASS, 15 files, 15 sums
sums:    9fec168f96d2772c6caf8c3bbb86482ff72fedc467591532bdd3a8290b783543
candidate: 63fcafa6ed01d2db7d5d8a1af460af994e65da853c0c250b05c3eb761f616d01
```

The checker PASS is a schema/hash observation only. P3B remains **NOT ACCEPTED**
because the only jobwrap log records `c9609f32…`/exit 1 while the manifest claims
`a2e4ff8f…`, and `audit.pass=false` with a whole-file change. Do not turn the
V3 6/6 result into an isolation pass.

## P4 — blocked

No P4 package yet. Needs no-arg `jobwrap gate4` run under gate4-harness and
native `manifest-compare.json`; derived cases are not native raw evidence.

## Gate 5 — blocked

No M4 fixed script / jobwrap fixed-entry execution yet. D3 remains the only
unlock; no PASS/FAIL observation exists.

## Rule

M5 records only observed command/exit/hash. It does not sign the M4 verifier row
or Lead approval, and does not convert a checker PASS into a gate pass.
