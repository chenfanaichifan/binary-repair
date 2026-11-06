# 34 — M3 ↔ M5 task split, single-owner gates, and handoff contract (2026-10-29)

**From:** Lead
**To:** Member 3 (guest execution / evidence producer), Member 5 (contract, adapter, replay, Gate 4 record)
**CC:** Member 4 (independent verifier), Member 1 (main), Member 2 (GUI)
**Status:** binding for Gate 4 and the real-execution path. Gate 3 is **closed** (approved 2026-10-22, record `0b3b51e4…f2da`); this document does not reopen it.

## 1. What actually went wrong

The verification work was not the blocker. The **boundary between M3 and M5** was.

Reproduced from the handoffs and the current tree:

| Observation | Where |
|---|---|
| Gate 4 was recorded as `NOT RUN (guest access + M5 routeb/ scripts)` — each side waiting for the other | `docs_BinaryRepair/handoffs/14-next-actions-by-owner.md` |
| The critical path was written as a chain in which every step needs the next person: `M3 guest → M4 run → record → M5 contract/manifest → Lead` | same file |
| M3 could not fetch `origin` (`SEC_E_NO_CREDENTIALS`) and there was no shared filesystem; the evidence bundle transfer was left as a human copy step | handoffs 15, 16 |
| The bundle was ruled "not required", then v1 was not required, then v2 existed only in a WeChat folder; M5's replay was `PARTIAL/BLOCKED` because the inputs never reached it | handoffs 21, 23–31 |
| The support manifest used a non-standard `filename UPPERCASE_HASH` format, so `sha256sum -c` rejected it; reviewers could not settle "is this package valid?" | handoff 32 |
| The Gate 3 loop only ended when the Lead issued a written ruling (cross-input, hash-bound replay) — the technical work had already been done; the **decision and delivery contract** were missing | handoffs 32, 33 |
| Today the pipeline still cannot finish: `tools/p2_acceptance.py` exits `2 BLOCKED`, no real result bundle has ever reached the worker | measured on `integration/consolidation-2026-10-29` |

Structural causes:

1. **No shared artifact plane.** Evidence lived on different hosts, so every step needed a synchronous copy and a chat message.
2. **Each side treated the other's action as a prerequisite.** "M3 waits for the kit, M5 waits for the guest" is a loop with no owner.
3. **No frozen package format.** Every exchange re-negotiated what a bundle is, which hash is authoritative, and which file is included.
4. **Producer and verifier roles were mixed.** The same gate changed hands between M3, M4, and M5, so "who signs?" stayed open.
5. **Status lived in chat.** No board said who holds the ball, what is the next action, and when it is overdue.
6. **"VMer" was ambiguous** (M3? a separate window? M4?), so snapshot/evidence ownership kept moving.

## 2. The rule change: 3 artifacts, 2 owners, 1 DRI per gate

| Artifact | Produced by | Consumed by | Format |
|---|---|---|---|
| **A. Attempt bundle** (worker input) | M3 (guest executor) | M5 (adapter), worker | JSON, schema in `app/services/worker.py` lines 15–21 |
| **B. Evidence package** | M3 | M5 (verify), M4 (independent check) | directory + `handoff.json` + `SHA256SUMS`, validated by `scripts/check_handoff.py` |
| **C. Gate record** | M5 (Gate 4 record) | M4 verification row, Lead approval row | markdown record with observed values only |

Ownership:

- **M3** owns the *producer* side: guest execution, per-case raw rows, package B, and publishing package A for every route run. M3's definition of done ends at "package PASS + board updated". M3 does **not** need M5 to start.
- **M5** owns the *consumer + record* side: adapter A → worker JSON, replay/verification, Gate 4 record C, and the interface contract. M5's definition of done ends at "p2 exit 0 + Gate 4 record signed by M5". M5 does **not** need M3's live session.
- **Lead** owns the join: approval row, reassignment if a package is overdue, and the only person allowed to change scope.
- **M4** is the independent verifier and does not produce Gate 4 evidence.

Hard rules (no exceptions):

1. **Nobody waits for a reply to publish.** Each owner publishes their artifact first and notifies second.
2. **A question without an artifact is not accepted.** Every message either delivers a package (with `check_handoff.py` PASS) or reports a blocked package with the exact external condition.
3. **One DRI per gate.** Gate 4 DRI = **M5**; M3 is the execution service. Gate 3 is closed and must not be reopened.
4. **No host execution, ever.** All execution is in the disposable guest under the broker; `var/` is not a delivery channel.
5. **Missing is not passing.** A missing file, a missing row, or a skipped case is `not_run`/`NOT VERIFIED`, never `passed`.

## 3. M3 task card — guest execution and evidence producer

DRI: **M3**. Gate: Gate 4 execution half + real Route A/B bundles.
Write scope: guest snapshot, `routeb/` runs, `docs/handoffs/evidence/<id>/`, own handoff files. Do not edit `app/`, `tests/`, `tools/`.

### T3.0 — Access + snapshot confirmation (first action, 30 minutes)
- Confirm the guest is reachable, the snapshot `toolchain-v4-ready`/`gate3-harness` exists, and the runner user is uid 1003 with no sudo and no egress.
- Record: snapshot name, image/chain manifest hash, tool versions, date/time, operator.
- Output: 10-line section in your handoff file. If the guest is **not** reachable, publish a **blocked package** by 2026-10-30 12:00 with the exact error and who can unblock (Lead/VM owner). Do not silently wait.

### T3.1 — Gate 4 formal run (DRI: M5's record needs this)
- Run, inside the guest: `routeb/gate4_runner.sh <repo-root> <writable-work-dir>` on the frozen `original.elf` (`aa428157…8393`) and the `routeb/` scripts from the integrated branch. Follow the kit `dist/m5-routeb-kit-*` version pinned by M5; record the exact kit hash you used.
- Capture per-case rows: case id, command, exit code, stdout/stderr hash, artifact ids.
- Run the original binary on the six frozen cases once, and the unchanged round-trip candidate once; record both tables. Do not run the **repaired** candidate for Gate 4.
- Output package `P4` with `gate4-status.json`, raw logs, candidate hash, `original.elf` hash, six-case rows, isolation attestation (uid/caps/no-egress/snapshot-reverted).
- DoD: `python scripts/check_handoff.py docs/handoffs/evidence/P4 --expect-from M3 --expect-to M5` → `PASS`; every expected value has an observed value; no `passed` without a command.
- Deadline: **2026-10-30 18:00**.

### T3.2 — Route A real executor bundle
- Produce one Route A candidate with the executor authorized by handoff 09/13 (strategy C) in the guest; capture edit-manifest, static audit, six-case run on the final bytes, and the candidate hash.
- Output package `P3A` containing `result-bundle.json` in the shape `tools/routea_bundle_to_attempt.py` consumes (`gates.V0..V5`), plus raw logs and hashes.
- DoD: `check_handoff.py` PASS; candidate hash stable across two builds; run rows byte-exact on the hashed final bytes; every gate result carries its evidence id or `not_run`.
- Deadline: **2026-10-30 18:00** (or a blocked package by 12:00 naming the missing tool/host condition).

### T3.3 — Route B runtime bundle
- Produce `candidate.elf` + `edit-manifest.json` (must contain `original_sha256`, `candidate_sha256`) + `manifest-compare.json` for one Route B candidate, using `routeb/executor.py`.
- Output package `P3B` with those files and logs.
- DoD: `check_handoff.py` PASS; candidate hash in the manifest equals the bytes; original hash equals `aa428157…8393`; if the runtime manifest is absent, say so and mark V3 `not_run` rather than shipping a static-only pass.
- Deadline: **2026-10-30 18:00**.

### M3 reporting rule
After each package: update your row in `docs/handoffs/BOARD.md` (status, artifact path, `SHA256SUMS` file hash, next action) and write one `docs/handoffs/38-m3-to-m5-<id>.md` file with the 9-line envelope from `docs/handoffs/35-ai-handoff-protocol.md`. Commit the metadata; never paste logs into chat.

## 4. M5 task card — contract, adapter, replay, Gate 4 record

DRI: **M5**. Gate: Gate 4 record + pipeline reaches `finished`.
Write scope: `app/services/attempt_writer.py`, `tools/routea_bundle_to_attempt.py`, `tools/p2_acceptance.py`, `routeb/` (kit only), `docs/handoffs/evidence/`, Gate 4 record, own handoff files. Do not edit `app/domain/acceptance.py`, M3's guest scripts, or M3's packages.

### T5.1 — Freeze the interface contract v1 (do this first; no M3 dependency)
- Publish `docs/handoffs/34` attachment or a short `docs/handoffs/INTERFACE-v1.md` that names: attempt bundle schema, evidence package schema (link `scripts/check_handoff.py`), file naming, hash rules (`SHA256SUMS` sorted, standard `sha256sum` format), and the adapter commands.
- Add a version bump rule: any change = v2 + one-line changelog entry + notify M3/M4/Lead in the same commit.
- DoD: `python scripts/check_handoff.py _scratch/handoff_demo/pass --expect-from M3 --expect-to M5` → PASS (self-test) and the document exists at the committed path.
- Deadline: **2026-10-30 12:00**.

### T5.2 — Adapter A → worker JSON + synthetic self-test (no M3 dependency)
- Make `app/services/attempt_writer.py` and `tools/routea_bundle_to_attempt.py` consume M3's shapes exactly: `result-bundle.json` with `gates.V0..V5` for Route A, and `routeb` bundle dir for Route B.
- Build a synthetic package that passes `check_handoff.py`, run the adapter, and drive the real worker + `tools/p2_acceptance.py` to a `finished` run. This proves the pipe before M3's real data arrives.
- DoD: `python -m pytest tests/integration/test_attempt_writer.py --basetemp=<pre-created> -p no:cacheprovider` → 4 passed; p2 exits 0 on the synthetic package and the record says `synthetic: true`; the real result is still `not_run`.
- Deadline: **2026-10-30 18:00**.

### T5.3 — Consume M3 packages, replay, and write the Gate 4 record
- For each incoming package: `check_handoff.py` first; if FAIL, reply with the exact failing lines and stop (do not "check by eye").
- Recompute candidate/manifest/`SHA256SUMS` hashes; map A → worker JSON; run the worker and `tools/p2_acceptance.py --job-id <id>`; fill the Gate 4 record with **observed** values only.
- Record every hash re-derivation and every missing item. If a package is missing or mismatched, the record row is `NOT VERIFIED`, not blank and not pass.
- DoD: p2 exit 0 with real (not synthetic) data; Gate 4 record has M5 signature row and observed values; every `not_run` stays visible; independent M4 verification and Lead approval rows remain blank until they act.
- Deadline: **2026-10-31 12:00**.

### M5 rejection criteria (fail closed)
Reject and report (do not accept) when: `check_handoff.py` FAIL; candidate hash ≠ manifest; original hash ≠ job record; six-case rows missing; isolation attestation missing; a `passed` appears without a command/evidence id. In each case write the verdict to `docs/handoffs/39-m5-to-m3-<id>.md`, with the exact missing list and a deadline.

## 5. Joint milestones (absolute dates)

| Time | Milestone | Owner | Acceptance command |
|---|---|---|---|
| 2026-10-30 12:00 | Interface v1 frozen; M3 access confirmed or blocked package | M5 / M3 | `check_handoff.py` self-test PASS |
| 2026-10-30 18:00 | P4 + P3A + P3B packages delivered | M3 | `check_handoff.py <pkg>` PASS |
| 2026-10-30 18:00 | Adapter + synthetic p2 exit 0 | M5 | `pytest tests/integration/test_attempt_writer.py` 4 passed; p2 exit 0 |
| 2026-10-31 12:00 | Real p2 exit 0; Gate 4 record draft | M5 | `tools/p2_acceptance.py --job-id <id>` exit 0 |
| 2026-10-31 18:00 | Independent verification + Lead approval | M4 / Lead | verifier rows signed; record hash pinned |
| 2026-11-01 | Fixture-freeze decision (only if gates 3–5 done) | Lead | — |

## 6. Escalation (no silent waiting)

- **24h without a BOARD update** → Lead moves the task to `OVERDUE`; the owner must publish a blocked package within 4h.
- **A blocked package** must name the exact external condition and the person who can unblock it. "Waiting for M5/M3" is not a valid blocking reason.
- **48h** → Lead narrows scope or reassigns; the gate stays `NOT RUN`, never "in progress" forever.
- No third-party relay: technical content goes through the repo; humans only copy large files and make decisions.

## 7. What this unblocks

When T3.1 + T5.3 close: Gate 4 becomes a real, signed record, and the worker receives real bundles for the first time. Route A/B runtime evidence then becomes attachable, and the fixture-freeze decision can finally be scheduled. Until then, Gate 4 stays `NOT RUN` and `p2` stays `2 BLOCKED` — that is the honest state.
