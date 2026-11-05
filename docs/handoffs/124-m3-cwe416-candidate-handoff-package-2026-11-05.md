# 124 — the CWE416 candidate exists; here is the package that carries it

- Date: 2026-11-05 (guest window 23:44–23:47 local)
- Owner: Member 3 (guest execution / evidence)
- Branch: `m3/cwe416-v3-noinput` at `b8fed8a`, **87 commits ahead of `origin/main`**
- Package: `dist/M3-124-cwe416-candidate-handoff-2026-11-05.zip`
  — 114,311 B, 63 entries, top-level sha256 `58ed53401dbc…e3cc`
- Contract: unchanged, `schema_version: 3`, `input_mode: "none"`
- Not claimed: any gate pass, Gate 4, T8.3 relief, binary-level V4

## 0. Status

| Item | State |
|---|---|
| Candidate | `46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0`, 25,344 B |
| Edit | 5 bytes at offset 4869: `call free@plt` → 5 × `nop` |
| V3 | `1/1`, `invalid: not_applicable`, `passed=1 total=1`, exit 0 |
| Control | `0/1`, exit 1 |
| V4 | `not_run`, `claimed_scope: null` |
| V5 | passed — `c9c2632e…` twice, `46d16e99…` twice |
| Unsupported | **not applicable** — the candidate was produced (see §5) |
| T8.3 | blocked |

## 1. Why the blocker is not on this side

The candidate was produced in the 122 window and has not changed since: same
bytes, same hash, same five-byte edit. It is not "not started" or "blocked on
something" — it exists.

The likely reason it still reads as missing: it lives on
`m3/cwe416-v3-noinput`, which is **87 commits ahead of `origin/main`**. Anyone
working from `main` cannot see the fixture, the contract, or the candidate at
all. If the consumer is on `main`, the fix is a merge or a checkout of this
branch, not another candidate.

## 2. V3, measured three times from three different starting points

The number is worth what its independence is worth, so it was re-derived rather
than repeated:

| Window | What was on disk | Result |
|---|---|---|
| 122 (23:15–23:20) | kit unpacked from the branch working tree | `1/1`, exit 0 |
| 123 (23:38–23:41) | kit re-packed from the tree, new guest dir `~/cwe416-sync` | `1/1`, exit 0 |
| 124 (this) | zip **extracted on the guest**, `~/pkg124/…` | `1/1`, exit 0 |

The control (same runner, same `valid.json`, unrepaired original) failed all
three times, with residue `4ba2020a`, `6937030a`, `2fdd010a` — three different
values. That is the point: the residue is allocator state, not a constant, and
the fixture freezes its observation under `setarch -R` for that reason. The
candidate prints the same 100 bytes in every run; the original never does.

## 3. The package, and the four checks that make it usable

```
dist/M3-124-cwe416-candidate-handoff-2026-11-05.zip
  INDEX.md
  122-…-candidate-….md, 123-…-contract-sync-….md
  evidence/cwe416-candidate-2026-11-05/        31 files
  evidence/cwe416-contract-sync-2026-11-05/    12 files
  fixture/CWE416_…_noinput/                    14 files
  SHA256SUMS                                   62 rows
```

The zip carries `INDEX.md` as its travelling summary; this record is the
repo-side one and is deliberately **not** inside the package, so the package
hash does not have to chase its own description.

After extracting to a clean directory:

```
outer        62/62
candidate    31/31
contract-sync 10/10
fixture      13/13
```

Then, in the guest, with the **package's own** fixture and candidate:

```
$ python3 routeb/run_manifest_repaired.py \
      --binary /tmp/c.elf --tests $FIX/tests --contract $FIX/contract.json
input_mode=none  invalid=not_applicable  valid=1/1  passed=1 total=1  repaired_pass=True
runner exit=0
```

and the control at `0/1`, exit 1. So the package is not a pile of files that
verifies its own hashes — it runs.

## 4. What a consumer should read, and what not to

Read `fixture/CWE416_…_noinput/` from **this** package. Do not read the copy
inside the 120 package: that is the `0936ac6` snapshot, and `defect.json` moved
after it (`trigger_note` now opens with `not_applicable: input_mode is none …`).
The contract is identical in both, at `8a2b408c…` file / `c1684f15…` canonical,
so nothing about the mode changes — only the note that used to read like a
missing case.

## 5. `unsupported` is a real category, and this is not it

The request allows for "if the candidate cannot be produced, record
`unsupported` instead of faking a pass". That clause is worth keeping sharp, so
this record states what would have counted, and why none of it happened:

- `unsupported` would mean: every option in `authorized_edits` fails before V3 —
  the patch either cannot be expressed inside the 128-byte bound, or it changes
  the program past V1 (headers, segments, relocations, size), or it does not
  build to a stable digest under V5.
- Here option 0 is one instruction wide: `call free@plt` → `nop ×5`, same size,
  same section and segment layout, same digest on rebuild. V1, V3, V5 all pass.
- So the honest status is **produced and measured**, and `unsupported` is not
  used. If a second, harder sample is ever attempted and option 0 does not fit,
  that sample gets an `unsupported` record with the failing option named — not a
  bare `1/1` borrowed from this one.

## 6. What still does not move

`contract.json#required_obligations` still lists `symbolic`. An attempt assembled
from this bundle is `REQUIRED_CHECK_NOT_RUN` → `inconclusive`, not `pass`.
`repaired_pass: true` is the runner's judgement over one case.

V4 stays `not_run` with `claimed_scope: null`. angr 10.0.4.post1 and z3 5.1.0
are installed in `/opt/angr-venv` on the guest, so this is not "no engine
available" — no symbolic run was performed, because a claim without per-run
solver accounting is worse than `not_run` (and the earlier V4 submissions were
rejected for exactly that, `docs/handoffs/63`, `64`, `66`, `67`).

T8.3 stays blocked: one sample, one repair, one observation.
