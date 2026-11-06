# 137 — V0/V1/V5 re-derived, and the wiring proposal that is the real last mile

- Date: 2026-11-06 (17:37–17:58 local)
- Owner: Member 3 (guest execution / evidence)
- Branch: `m3/cwe416-v3-noinput` at `2533780`
- New directory: `T8.3-refresh-2026-11-06/` (5 files, own `SHA256SUMS`), installed
  read-only at `/opt/binrepair-handoff/T8.3-refresh-2026-11-06`
- Gate status assigned here: **none**. V4 `not_run`, no `verified_by`, T8.3 blocked.

## 1. What was re-derived, and what it proves

Record 133 said V5 was *carried* from record 122. That footnote is now retired: V0,
V1 and V5 were measured again in this window, on the bundle's own inputs.

| gate | measurement | result |
|---|---|---|
| V5 | `build.sh` twice → `c9c2632e…` twice; `patch_candidate.py` twice → `46d16e99…` twice | passed |
| V1 | `audit_interface.py`: 37 sections (identical layout), 14 relocations, 5 changed bytes, entry `0x4011b0` unchanged | passed |
| V0 | candidate = this original + the recorded five-byte edit; both replays reproduce the shipped bytes | passed |

**V1 and V5 came back byte-identical** to the copies inside the sealed bundle. Not
"the same numbers" — the same files. V0 differs only by an added `measured_here`
block that records this window's four digests, so a reader can see they were
produced now rather than restated.

The sealed bundle keeps its bytes; the refresh directory supersedes those three
files *for provenance*, and says so in its README.

## 2. A gap the re-derivation exposed

The sealed bundle's `fixture/` has `original.elf`, `original.c`, `contract.json`,
`defect.json`, `tests/` and `support/` — the list T8.3 asked for. It does **not**
have `build.sh`, `src.c` or `harness.c`. So:

- M4 **can** replay the harness, check V2 and V3, and verify every hash in the
  bundle;
- M4 **cannot** rebuild the original from the bundle, because the recipe and one of
  its inputs are missing.

This window had to copy those three files from `fixtures/public/CWE416_…_noinput/`
before V5 could run. Closing it means three files and a new bundle version, not a
quiet edit to a published one — a published hash that changes silently is worse
than a gap that is written down.

## 3. The wiring proposal

`v2-v4-wiring-proposal.md`. The point, in one paragraph: `attempt_writer.py` sets
`"V2": "not_run"` (line 219) and `"V4": "not_run"` (line 221), and
`orchestration.py` makes all six gates required. So **no bundle can reach
`success_within_scope` while those lines stand**, however good the evidence is.
For this sample V2 is 5/5 and V4's producer evidence validates, and the attempt
still lands `inconclusive`.

The proposal keeps the "producer cannot self-certify" rule by moving it rather than
removing it:

- **V2** may be read directly — it is a static comparison between two hash-bound
  files, with no judgement in it — but only at exactly 5/5 with both hashes matching
  the bundle's binaries. Anything else stays `not_run`.
- **V4** may be read only with a receipt: `replay.verified_by == "m4"`. The field
  is checked, never written, by the writer. A bundle without it keeps `not_run`,
  which is every bundle that exists today.
- Failures degrade to `unknown`, not `not_run`: "evidence exists and disagreed" is a
  different fact from "nothing was produced".
- Scope travels: `claimed_scope: model` must survive into the attempt, so a V4 pass
  is not read as binary-level proof.

Six tests are listed in the proposal, including two negative ones (V2 4/5; a receipt
signed by anyone other than M4) because the failure mode of this change is a gate
that quietly starts passing.

## 4. Where this leaves the distance to T8.3

Unchanged, and now with the last mile named:

1. M4's public key (`m4_guest_key.pub`, `SHA256:bRq28b6J…`) — still not on this
   host;
2. M4's replay, and its own `replay.verified_by="m4"`;
3. the wiring above (M1 / contract owner), without which step 2 changes nothing in
   the product's verdict;
4. the Lead's acceptance, then the branch question (101 commits ahead of `main`).

Steps 1 and 2 are other people's. Step 3 is a code change M3 must not make. Step 4
is the Lead's. What M3 can do alone is now done.

## 5. Boundaries

- No `verified_by`.
- V4 `not_run`; `gates/gate-index.json` untouched.
- One second sample (CWE-416), as decided; CWE-122 is not part of T8.3.
- No new package: 133 remains the transferable archive and was not rebuilt, because
  no file inside it changed.
