# 42 — M4 Gate 4 independent verification checklist (JOIN-1)

**From:** Member 4 (independent verifier)
**To:** Lead, Member 5 (Gate 4 DRI), Member 3 (guest evidence producer)
**Date:** 2026-10-29 (Asia/Hong_Kong)
**Status:** **CHECKLIST READY — not a result.** Gate 4 remains **NOT RUN**. No item in this
file is `PASS` today; every row is `NOT VERIFIED` until the producer artifacts exist and I
re-measure them myself. M4 does not produce Gate 4 evidence and does not sign its own tests.
**Basis:** `docs/handoffs/34` (T3.1/T5.3 cards), `35` (handoff protocol), `37` (M5 record
rules), `BOARD.md`, `docs/analysis/VERIFICATION.md`, `docs/route-b/09`, `11`, `14`,
`docs/handoffs/evidence/README.md`, `scripts/check_handoff.py`, `routeb/gate4_runner.sh`,
`routeb/run_manifest_compare.py`, `tools/p2_acceptance.py`, `app/services/attempt_writer.py`.
**Tooling:** host-side helper `scripts/m4_verify_gate4.py` (added with this checklist; it only
reads files and JSON/URLs, never parses or executes an ELF). Its own synthetic self-test is not
Gate 4 evidence.

## 0. Independence rules I will follow (no exceptions)

1. **I recompute every hash from the bytes.** M5's / M3's recorded hash is a claim to check,
   never a value I copy. This includes the `SHA256SUMS` file hash, candidate/original ELF
   hashes, six-case row hashes, and the record hash.
2. **`check_handoff.py PASS` is necessary, not sufficient.** A package that fails the checker
   is rejected immediately; a package that passes it still has to pass every row below.
3. **Producer artifacts are read-only.** I never edit a package, a record observed value, or an
   M3/M5 signature row. I fill only my own M4 verifier row, and I pin the new record hash and
   report it.
4. **Missing is not passing.** A missing file, row, hash, isolation fact, or command is
   `NOT VERIFIED`; a measured contradiction is `FAIL`. Neither becomes `PASS`.
5. **No host execution.** I do not execute `original.elf`, any candidate, or model-generated C
   on this host. Runtime rows depend on the guest session that M3/VMer runs; if it is
   unavailable they stay `NOT VERIFIED`.
6. **Gate 4 scope only.** A Gate 4 pass says the Route B *unchanged round trip* is
   behaviour-identical to the frozen original under isolation. It is **not** a repair, not V3,
   not V4, and not a fixture freeze.
7. **I do not accept the supplementary CI run as formal Gate 4.** The committed
   `routeb/out/gate4/` (round-trip `decdcdb8…`, `gate4_pass=true`) is GitHub Actions evidence
   and remains supplementary (docs/route-b/09 §4, 11). Only a guest package `P4` can satisfy
   the formal gate.

## 1. Preconditions before JOIN-1 may start

JOIN-1 is the 2026-10-31 12:00–18:00 window. If any row below is missing when it starts, I
report the missing list and the affected rows as `NOT VERIFIED`; I do not start a partial pass.

| # | Input | Where it must exist | Owner |
|---|---|---|---|
| P1 | `P4` formal Gate 4 package (handoff.json + SHA256SUMS + logs) | `docs/handoffs/evidence/P4-2026-10-30/` | M3 |
| P2 | `P3A` Route A real executor bundle | `docs/handoffs/evidence/P3A-2026-10-30/` | M3 |
| P3 | `P3B` Route B runtime bundle | `docs/handoffs/evidence/P3B-2026-10-30/` | M3 |
| P4 | Frozen `docs/handoffs/INTERFACE-v1.md` + checker self-test line | repo | M5 |
| P5 | Gate 4 record draft with M5's observed values and M5 signature row | path named in M5's envelope | M5 |
| P6 | Real (not synthetic) `tools/p2_acceptance.py` run, **exit 0**, with the job id | recorded in the record + BOARD | M5 |
| P7 | Pinned Route B kit hash used by the guest run | envelope/record | M5/M3 |
| P8 | Envelopes `38-m3-to-m5-*` / `39/40-m5-*` with the exact checker lines | repo | M3/M5 |

Every package must have been validated by **both** sides:
`python scripts/check_handoff.py <pkg> --expect-from M3 --expect-to M5` → `PASS`.

## 2. Measured baseline (2026-10-29, this workspace)

Commands were run from `D:\BinaryRepair_Project`; only the observed lines are quoted. This is
*current state*, not Gate 4 evidence.

| Check | Observed today |
|---|---|
| branch / HEAD / tree | `integration/consolidation-2026-10-29`, `e0d70be`, `git status --porcelain` empty |
| evidence store | `docs/handoffs/evidence/` contains only `README.md` → **no P4/P3A/P3B delivered** |
| interface / record | `docs/handoffs/INTERFACE-v1.md` absent; no Gate 4 record exists; no real p2 job id |
| committed Gate 4 output | `routeb/out/gate4/` exists with round-trip `decdcdb8…` and `gate4_pass=true` — **CI supplementary only**, not formal |
| frozen original | `26,792` B, SHA-256 `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` (recomputed with `Get-FileHash`) |
| frozen manifests | `valid.json` `17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76`; `invalid.json` `d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d`; `tests/SHA256SUMS` 2/2 entries match |
| six case ids | `valid-empty`, `valid-smallest`, `valid-typical`, `valid-maximum`, `invalid-first`, `invalid-longer` |
| checker works (positive) | `PASS  handoff 'm3-pass' task='T3.1' from='M3' to='M5' artifacts=1 sums=2 interface=1` (exit 0) |
| checker fails closed (negative) | `FAIL  handoff 'm3-fail-hash' … errors=3` (tampered hash detected, exit 1) |

Consequence: rows **A–F below are all `NOT VERIFIED` right now**, because P1–P8 are absent.

**Verifier-helper self-test (measured 2026-10-29, synthetic only).** `scripts/m4_verify_gate4.py`
was exercised on labelled synthetic packages under `_scratch/m4_check/` (git-ignored; never
evidence): the P4-shaped synthetic package returned `29 PASS / 0 FAIL / 0 NOT VERIFIED`
(exit 0, and `36 PASS` with a synthetic blank M4 record); a tampered `environment.txt` returned
`FAIL` on the recomputed `SHA256SUMS` (exit 1); a package with a valid manifest but no isolation
attestation returned `NOT VERIFIED` (exit 2, no FAIL); the non-Gate-4 demo package returned
`NOT VERIFIED` (exit 2). The helper is therefore ready for JOIN-1, but its self-test is not
Gate 4 evidence and must never be cited as such.

## 3. Verification matrix (fill at JOIN-1; only PASS / FAIL / NOT VERIFIED)

### A. Package mechanics and custody

| ID | Check | Command / method | PASS criterion |
|---|---|---|---|
| G4-A1 | Both-side checker line | `python scripts/check_handoff.py <pkg> --expect-from M3 --expect-to M5` | exit 0, exact `PASS` line; any `FAIL` line is an automatic reject |
| G4-A2 | My own list of package files | `Get-ChildItem -Recurse <pkg> -File` (or `find <pkg> -type f`) | every file accounted for; no unexpected binary blob |
| G4-A3 | `SHA256SUMS` format and sort | own parser in `scripts/m4_verify_gate4.py` | `^[0-9a-f]{64}  <path>$`, bytewise sorted, no duplicate |
| G4-A4 | `SHA256SUMS` coverage | same | covers every package file except `SHA256SUMS`; no extra path |
| G4-A5 | every hash re-derived | `sha256sum` (guest/Linux) or `Get-FileHash` (host) | all rows equal; a mismatch is FAIL |
| G4-A6 | `handoff.json` identity | parse JSON | `from=M3`, `to=M5`, `task=T3.1/3.2/3.3`, `status=delivered`, `interface_version=1`, non-empty commands/expected/observed |
| G4-A7 | artifact roles | `handoff.json.artifacts` | every evidence file listed; each role names the artifact it carries |
| G4-A8 | package immutability | hash the directory (`SHA256SUMS` file hash + file count) at receipt and after all reads | unchanged; a delivered package is never edited (republish as a new id) |

### B. Identity hashes (Gate 4 subject)

| ID | Check | Method | PASS criterion |
|---|---|---|---|
| G4-B1 | frozen original in package | hash `original.elf` bytes | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`, 26,792 B |
| G4-B2 | round-trip ELF bytes | hash `roundtrip.elf` (or the package's candidate artifact) | hash equals `gate4-status.json.patched_sha256` **and** `manifest-compare.json.patched_sha256` |
| G4-B3 | before/after candidate hash | `candidate-before`/`candidate-after` files | before = after = B2; a change voids the run |
| G4-B4 | kit actually used | hash the repo files M3 says it ran (`routeb/gate4_runner.sh`, `probe_patcherex2.py`, `run_manifest_compare.py`, `verify.py`) and compare with the pinned kit hash | all equal to the pinned hashes; a mismatch is FAIL |
| G4-B5 | contract unchanged | recompute `contract.json` canonical hash | `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37` |
| G4-B6 | no repair claimed as Gate 4 | check package/record wording | only the **unchanged** round trip; no `repaired`, `V3`, or "fix verified" claim inside the Gate 4 rows |
| G4-B7 | pinned CI round trip as cross-check | compare B2 with `decdcdb821bfe4c41a070b0a23a2f6497f46a92f439cb02a1e4139a82cde954b` | if equal: documented cross-check PASS; if different: a written explanation is required, otherwise `NOT VERIFIED` (different toolchain can legitimately change patch bytes) |

### C. Six-case rows (the actual Gate 4 criterion)

| ID | Check | Method | PASS criterion |
|---|---|---|---|
| G4-C1 | exactly six frozen cases | parse `manifest-compare.json` | ids = the six frozen ids, unique, no extra case substituted |
| G4-C2 | per-case rows present | same | each row has id/kind/input_len, `original.{returncode,stdout_hex,stderr_hex}`, `patched.{…}`, `same` |
| G4-C3 | byte-exact equality | same | all six `same=true`; `same_count=6`, `total=6`, `gate4_pass=true` |
| G4-C4 | original-vs-round-trip identity | same | per case `original == patched` (rc, stdout hex, stderr hex) — this is the Gate 4 rule, independent of expected repaired behaviour |
| G4-C5 | frozen original's measured shape | compare rows to the frozen facts | valid cases rc 0 / stdout = input + `0a` / empty stderr; `invalid-first` rc 0, 50×`A`+`0a` (silent overflow, **no crash**); `invalid-longer` rc **-11** (SIGSEGV), empty output. A different original shape means wrong bytes or wrong harness → FAIL |
| G4-C6 | no timeout / no hidden skip | same | no `timeout:true` row, no missing rc, no aggregate-only claim |
| G4-C7 | rows bind to the run | `manifest-compare.json` + candidate/original hashes + record | the six rows come from the same session/hashes as B2/B3 and the isolation attestation (D); per-case raw stdout/stderr files are **not required** for this criterion |

> **Native six-case evidence policy (Lead decision, 2026-10-29):** `manifest-compare.json`
> **is** the native Gate 4 six-case evidence. Do not ask M3 to add native per-case raw
> stdout/stderr files to `P4`; the comparator JSON (with its per-case rc/stdout_hex/stderr_hex
> and `same` flags) plus the candidate/original hashes is the evidence to verify. If raw case
> files happen to be present they are supplementary only, never a pass condition and never a
> reason to mark a complete package `NOT VERIFIED`.

> **Documentation trap (recorded):** `docs/route-b/14-gate4-runner.md` §"Six cases" lists
> `invalid-first` as rc 1 + 42-byte stderr. That is the **repaired** oracle shape, not the Gate 4
> unchanged-round-trip shape. `09-gate4-evidence.md`, `run_manifest_compare.py`, and the
> committed CI `manifest-compare.json` all show the original/round-trip invalid cases as rc 0
> (silent overflow) and rc -11 (SIGSEGV). Gate 4 rows are checked against case equality and the
> frozen original shape (C4/C5); doc 14's table must not be used to fail a correct round trip.
> Flag to M5/M3 at JOIN-1.

### D. Isolation attestation (same session as C)

| ID | Check | Method | PASS criterion |
|---|---|---|---|
| G4-D1 | snapshot identity | read `isolation*`/`attestation*` artifact | snapshot name/id + chain manifest hash + timestamp recorded |
| G4-D2 | revert evidence | same + logs | raw revert command/output; **single operator** named; post-revert fingerprint |
| G4-D3 | unprivileged runner | environment/attestation text | `uid=1003`, `CapEff=0`, `NoNewPrivs=1`, `sudo -n true` fails |
| G4-D4 | no egress during run | same | netns/no-interface evidence or a failed egress attempt with its exact error |
| G4-D5 | evaluator unreadable | same | 1003 cannot read the evaluator source/path (raw `ls`/open error) |
| G4-D6 | wrapper conditions | wrapper artifact + record | root-owned, not writable by 1003, fixed `execv` argv (no shell), hash recorded |
| G4-D7 | seccomp / CET state | environment text | `Seccomp: 0` recorded (no filter added), as Gate 3 required |
| G4-D8 | tool versions | `environment.txt` | JDK 21, Ghidra 12.1.4 (or recorded), Patcherex2 0.2.14, clang/ld.lld recorded |
| G4-D9 | run was in the guest | paths/hostname/prompt in logs | no host execution, no CI runner substituted for the guest |

A run outside D1–D7 is `NOT VERIFIED` even at 6/6. A contradiction (e.g. `CapEff != 0`, egress
works, 1003 can invoke the wrapper) is `FAIL`.

### E. Gate 4 record wording and signatures

| ID | Check | Method | PASS criterion |
|---|---|---|---|
| G4-E1 | record exists and is versioned | read the record | file path, date, M5 as record owner, package id + `SHA256SUMS` file hash cited |
| G4-E2 | observed values only | read every row | each row names the command and the observed value/artifact hash; no "should pass" / predicted values |
| G4-E3 | missing rows visible | read the gate table | every `not_run` item is visible as `NOT VERIFIED`/`not_run`, not blank and not pass |
| G4-E4 | Gate 4 pass definition | read conclusion | pass = `gate4-status.json=pass` **and** 6/6 same **and** M4 accepts image/tool/isolation evidence (docs/route-b/14) |
| G4-E5 | signature order | read signature table | M5 row filled; **M4 row blank at receipt**; Lead row blank until I sign and the Lead approves |
| G4-E6 | no pre-approval | grep record | no `GATE 4 APPROVED` / `closed` before the Lead row is actually signed |
| G4-E7 | scope honesty | read conclusion | Gate 4 only; explicitly no repair/V3/V4 claim; fixture still `NOT FROZEN`; Gate 5 runtime still pending |
| G4-E8 | record hash pinned | hash the record before and after my row | hash reported; if I edited only my row, the new hash is pinned and reported; any unrecorded edit invalidates M5's signature |

> **Identity/independence note (required before any signature):** the M4 verifier and the Lead
> are the **same person/operator** (two AI windows of one person, analogous to VMer = M3). The
> Gate 4 record must annotate **both** the M4 verifier row and the Lead approval row with this
> same-person limitation before either is signed; the two rows are not independent two-person
> signatures. A record that presents them as independent is incomplete → `NOT VERIFIED`.

### F. Real p2 run (pipeline already finished on real data)

| ID | Check | Command / method | PASS criterion |
|---|---|---|---|
| G4-F1 | M5's observed p2 line | record + envelope | line `P2 ACCEPTANCE PASSED  phase=finished job=<id>` and exit 0 recorded with the command |
| G4-F2 | I re-run it myself | `python tools/p2_acceptance.py --job-id <id> --controller http://<ctrl>:<port>` | exit **0** with the same observed line; exit 1/2 is a FAIL/NOT VERIFIED, never pass |
| G4-F3 | job snapshot | `GET /api/jobs/<id>` | `phase=finished`, `demo=false`, verdict present |
| G4-F4 | routes and obligations | same | routes A and B each have a valid outcome and exactly the six obligation kinds (identity, structure, interface, behaviour, symbolic, reproducibility) |
| G4-F5 | persisted evidence | `GET /api/attempts/<id>/evidence` | `evidence: persisted` with the same rows; no static placeholder, no fabricated `passed` |
| G4-F6 | real, not synthetic | attempt bundles + record | no `synthetic: true`, no demo label; run uses the real (M3/P4-derived) data |
| G4-F7 | job identity | snapshot / DB row | job `original_sha256 = aa428157…8393`; candidate hashes match P3A/P3B/P4 artifacts |
| G4-F8 | p2 does not decide the gate | reasoning | p2 exit 0 is pipeline honesty, not the Gate 4 pass; Gate 4 needs A–E as well |

## 4. Fail-closed reject list (any one = no acceptance)

Reject and report to M5 (do **not** fix the package) if any of these is true:

1. `check_handoff.py` prints any `FAIL` line, or the package was edited after delivery.
2. Any recomputed hash differs from the record/package (candidate, original, manifest, sums).
3. A six-case row is missing, duplicated, substituted, timed out, or `same=false`.
4. The isolation attestation is missing, outside the same session, or contradicts the controls.
5. A `passed` appears without a command and an evidence id.
6. `synthetic: true` (or the demo label) appears in the real-run evidence.
7. The record pre-fills the M4 or Lead row, or claims Gate 4 approved before those rows exist.
8. The only "Gate 4" evidence is the CI run, `audit.json.pass`, the static bundle, or M3's prose.
9. Host execution is used instead of the disposable guest for any Gate 4 row.
10. Any secret/credential/client binary is in the package.

## 5. Exact command set for JOIN-1

Host (this workspace, read-only on packages; no ELF execution):

```powershell
git log --oneline -1; git status --short
python scripts/check_handoff.py docs/handoffs/evidence/P4-2026-10-30 --expect-from M3 --expect-to M5
python scripts/m4_verify_gate4.py --package docs/handoffs/evidence/P4-2026-10-30 `
  --record docs/handoffs/evidence/P4-2026-10-30/GATE4-RECORD.md
# sha256 of the package manifest and of the record (pin both)
Get-FileHash -Algorithm SHA256 docs/handoffs/evidence/P4-2026-10-30/SHA256SUMS
Get-FileHash -Algorithm SHA256 <gate4-record>.md
# real p2, after the controller is up (no binary execution: p2 only reads job state)
python tools/p2_acceptance.py --job-id <real-job-id> --controller http://127.0.0.1:8801
```

Guest (executed by M3/VMer, observed/verified by me; needed for the runtime part of Gate 5,
not to create Gate 4 — Gate 4 rows come from the package):

```bash
sha256sum original.elf roundtrip.elf
routeb/run_manifest_compare.py --original original.elf --patched roundtrip.elf \
  --tests fixtures/public/CWE121_src_char_declare_cpy_51b/tests --out manifest-compare.json
```

`scripts/m4_verify_gate4.py` prints one row per check with `PASS`, `FAIL`, or `NOT VERIFIED`
and exits `0` (all PASS), `1` (any FAIL), or `2` (no FAIL but missing items). It does not
replace the byte-level commands above; it makes the missing/contradiction distinction explicit.
Its synthetic self-test lives in `_scratch/m4_check/` (git-ignored) and is labelled
`SYNTHETIC SELF-TEST — NOT GATE 4 EVIDENCE`; it must never be moved under
`docs/handoffs/evidence/` or cited as a package.

## 6. Result table to fill at JOIN-1 (all `NOT VERIFIED` at checklist time)

| Gate 4 item | Verdict | Observed value | Evidence file + SHA-256 | Command |
|---|---|---|---|---|
| A package mechanics | NOT VERIFIED | no package delivered | — | — |
| B identity hashes | NOT VERIFIED | no package delivered | — | — |
| C six-case rows | NOT VERIFIED | no package delivered | — | — |
| D isolation attestation | NOT VERIFIED | no package delivered | — | — |
| E record wording/signatures | NOT VERIFIED | no record exists | — | — |
| F real p2 exit 0 | NOT VERIFIED | no real job id exists | — | — |
| **Overall M4 verifier row** | **NOT VERIFIED** | Gate 4 stays NOT RUN | — | — |

## 7. What I will and will not do at JOIN-1

- **Will:** re-run the checker, re-hash every byte, read the six-case rows one by one, read the
  isolation evidence against D1–D9, re-run p2 on the recorded real job, fill **only** the M4
  verifier row with commands and observed values, pin the new record hash, update BOARD, notify
  the Lead.
- **Will not:** produce or edit Gate 4 evidence, accept M5's hash without re-measuring, accept a
  package that fails the checker, sign an `M4` row before all items are measured, approve my own
  test, or extend a Gate 4 row to a repair/V3/V4 claim.

## 8. Open items and flags for M3/M5/Lead

1. **INTERFACE-v1 is not published yet.** The package file names/roles in this checklist come
   from `34`/`37`/`check_handoff.py`; if `INTERFACE-v1.md` names files differently, I adapt the
   checklist (content checks stay the same) — no interface change may weaken A–F.
2. **`docs/route-b/14` six-case table conflicts with the Gate 4 criterion** (repaired-oracle rc 1
   vs original/round-trip rc 0 / SIGSEGV). C4/C5 are the authority; flag to M5/M3 so a false
   `FAIL` is not recorded.
3. **The committed `routeb/out/gate4` CI run is supplementary.** It must not be relabelled as
   P4; a real guest package is required.
4. **M4 cannot start the gate on M5's word alone.** If P1–P8 are incomplete at 12:00 on
   2026-10-31, JOIN-1 stays `NOT VERIFIED` and the Lead gets the exact missing list.

**Signature block (blank by design — filled only at JOIN-1):**

| Role | Name | Date | Signature |
|---|---|---|---|
| M4 verifier | M4 | — | — (none; checklist only) |
