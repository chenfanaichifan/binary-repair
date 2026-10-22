# Gate 3 evidence bundle — Route A (CWE121 `..._cpy_51b`)

**Status: NOT RUN.** This directory is the committed index for the formal gate-3 evidence.
No item below has been measured yet. Do not add a result, hash, or pass label before the
corresponding raw output exists. Missing evidence is `NOT VERIFIED`, never `passed`
(`AGENTS.md`; handoff 11 §3).

Owner after 2026-10-22: **Member 4** (reassigned from Member 5 by
`13-route-a-ownership-handoff.md`). Method: `12-m4-acceptance-evidence-plan.md`.

## What belongs here (committed)

Only material that is small, reviewable, and safe to commit:

- `gate3-record.md` — the per-item record with `PASS` / `FAIL` / `NOT VERIFIED`, the command
  actually run, the observed value, and the evidence filename for each of the six handoff-11
  items;
- `SHA256SUMS` — SHA-256 of every committed file in this directory (and of the bundle hash);
- the environment session header (guest fingerprint, tool versions, image chain hash);
- the per-case result table (expected vs observed, bytes in hex) referencing raw files.

Raw logs, ELF copies, gdb output, and `objdump`/`readelf` dumps are runtime artifacts: keep
them under `var/jobs/` (excluded from source control) and reference them by filename and
SHA-256. The committed record must let a reviewer replay the run without trusting prose.

## Required item mapping (handoff 11 §3)

| # | Item | Evidence file(s) expected | Status |
|---|---|---|---|
| 1 | Separate candidate copy; original untouched; `valid.json` / `invalid.json` / set hash unchanged | session hashes; original hash in guest | `not_run` |
| 2 | Candidate identity and reproducibility; complete edit manifest (intervals, header fields, detour, displaced bytes) | rebuild log; candidate hash before/after; edit manifest | `not_run` |
| 3 | Structural audit: cave mapped R-X; page-congruent `p_filesz`/`p_memsz`; no overlap; flags/NX/RELRO/canary/W^X; independent `readelf` + LIEF; no relocation/import/GOT/PLT edit | `readelf -l/-S/-r/-h/-d`, LIEF dump, header diff, byte-residue audit | `not_run` |
| 4 | Six-case run: 4 valid + 2 invalid, byte-exact stdout/stderr and exit codes, no crash, 42-byte stderr, candidate hash recorded before the run, reverted snapshot | per-case stdout/stderr/rc files + summary table | `not_run` |
| 5 | Isolation evidence for that run (snapshot revert, egress block, unprivileged uid 1003, wrapper attestation) | isolation attestation block, revert log | `not_run` |
| 6 | Evidence bundle: raw outputs + hashes for every item above | this directory's `SHA256SUMS` + bundle hash | `not_run` |

## Frozen values this bundle checks against (must not change)

| Value | Frozen value |
|---|---|
| original ELF SHA-256 | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` (26,792 B) |
| `valid.json` SHA-256 | `17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76` |
| `invalid.json` SHA-256 | `d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d` |
| manifest set SHA-256 | `a564f0397a741b1a4fc386a3149d54550c1bfe7c02958309e021fb6f03333a78` |
| `DEST_CAPACITY` / `MAX_VALID_LEN` | 50 / 49 |
| invalid path | rc 1, stdout empty, stderr exactly 42 bytes `ERROR: input exceeds destination capacity\n`, no crash |

An oracle mismatch is a `FAIL`; it is never fixed by editing a manifest, a constant, or this
table.

## Pass labels

The record uses exactly one of: **`GATE 3 PASS`** (all six items pass, independent replay
matches), **`GATE 3 FAIL`** (a concrete failing fact reported), **`GATE 3 NOT VERIFIED`** (a
required item, hash, or isolation precondition is missing). Gate 3 pass is feasibility
evidence for fixture selection only — not V0-V5 acceptance, not V3, not repair proof.
