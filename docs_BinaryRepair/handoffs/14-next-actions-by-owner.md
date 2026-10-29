# 14 — Next actions by owner (2026-10-22 18:00)

**Purpose:** one page that says, for every member, what is still missing, what the deliverable
is, and what it unblocks. Status rules stay: missing evidence is `not_run`/`NOT VERIFIED`, never
pass; no oracle, manifest, or frozen hash change without a full-team re-freeze.

## Status snapshot

| Gate | Status | Owner |
|---|---|---|
| 3 — Route A patch feasibility | **CONDITIONALLY FEASIBLE** (work status, not pass) | M4 (evidence package) + M3 (guest) |
| 4 — Route B unchanged round trip | **NOT RUN** (guest access + M5 `routeb/` scripts) | M5 + M3 |
| 5 — safe placement | pending (Route A: M4; Route B: M5; guest: M3) | M4/M5/M3 |
| 6 — verifier detects the original violation | **partial** (concrete crash accepted; symbolic half pending V4) | M4 |
| Fixture | **NOT FROZEN** | team |

**Ready but not evidence:** M5's CI cave-probe (`origin/main` `33235f5`, candidate
`f3cb9cbb…`, CI 6/6) and M4's design branch `member-4-routea-gate3` @ `7977bac` (manifest
schema 2, audit, `verify`, `bundle`, VM helper, tests). Neither can close gate 3: both ran
without the team guest/isolation, and only `py_compile`/pure-bytes helpers ran on the host.

**Contract proposal (checked by the Lead):**
`fixtures/public/CWE121_src_char_declare_cpy_51b/contract.route-a-v1.json` on
`member-4-routea-gate3`; its canonical `reviewed_scope_sha256` reproduces as
`ba33b4d070b8799b778a9ca1a257190079627bda72b5c42933edfebb0f5d8fc4`; the six
`authorized_edits` match handoff 09 §4.1, `allowed_calls = ("fprintf","printLine","strcpy")`,
and the oracle constants are unchanged. It is a **proposal**, pending M5 confirmation and Lead
approval; the `environment_assumptions` wording was refined (precise CET note + guest seccomp
requirement) and must be approved explicitly, not silently.

## Critical path

`M3 isolation evidence + guest access` -> `M4 guest run of handoff 12` -> `gate-3 record` ->
`M5 confirms contract revision + manifest` -> `Lead approval` -> `fixture-freeze decision after
gates 3-5`. M5's gate 4 runs in parallel once the guest is reachable and the `routeb/` scripts
exist.

## Member 1 — main, status page, persistence

1. Update `main` README/status: gate 3 = `IN PROGRESS — CONDITIONALLY FEASIBLE` (owner M4;
   runtime cave probe + six-case run pending), gate 4 = `NOT RUN` (guest access + M5 `routeb/`
   scripts), fixture `NOT FROZEN`, contract revision pending. No "not pass", no pre-labelled
   `unsupported`.
2. Re-run the full suite on current `main` and report the result; known historical failures must
   be fixed or recorded (`contracts.body_json` db-v2, V3 manifest line endings).
3. Controller/persistence: confirm the approval layer can persist the revised
   `SecurityContract` (free-text `authorized_edits`/`allowed_calls`, no schema change) and bind
   the approval to the new `reviewed_scope_sha256`; confirm canonical
   `POST /api/jobs/{id}/runs` / `GET /api/attempts/{id}/evidence` are ready for M2.
4. Keep main merges in the agreed order; do not merge the gate-3 evidence branch before Lead
   approval.

## Member 2 — GUI

1. Finish the vertical slice on the canonical API: create job, hash + screen input, persist,
   display both route states honestly.
2. Render outcomes only from the acceptance engine; no success label may originate in a
   template or route handler.
3. Display `CONDITIONALLY FEASIBLE` / `NOT RUN` / `not verified` / `inconclusive` distinctly; a
   pending gate must never look green.
4. Comparison view + export presence; migrate off the old adapter paths to canonical routes
   (keep aliases).

## Member 3 — guest, isolation, fixture

1. By **2026-10-23 18:00**: install evidence (versions, `pip freeze`, smoke raw output, image
   chain manifest + guest fingerprint + `df`), snapshot revert test (take a `pre-reset-test`
   protection snapshot first), `jobwrap` verification (fixed validated `execv` argv, netns
   before the drop, setuid 1003, no egress, `uid=1003`/`CapEff=0`/`NoNewPrivs=1`, evaluator
   unreadable, raw logs).
2. Provide guest access for **M4** (and M5 for gate 4): record the method, account, and limits.
3. Confirm the canonical `original.elf` source (`origin/main` blob vs the claimed `d1e0741`);
   retract the uncommitted "SHA256SUMS 24/24" claim until it exists on `origin`.
4. Prepare the fixture freeze record only after gates 3-5 evidence; never change the oracle.

## Member 4 — gate 3 evidence, Route A half of gate 5, gate 6 support

1. Rebase/merge `member-4-routea-gate3` @ `7977bac` on the current `main`; run
   `scripts/routea_vm_check.sh` static half in the guest, then the runtime cave probe, liveness
   traces, and six-case run under isolation (handoff 12); produce `gate3-record.md` +
   `SHA256SUMS`; report every item as `PASS` / `FAIL` / `NOT VERIFIED`.
2. Do not approve your own evidence: hand the record to M5 for replay and the Lead for approval.
3. V4: run calibration on the original now that the toolchain exists; report `inconclusive`
   unless the bounded exploration completes. Gate 6 stays partial until then.
4. Treat `contract.route-a-v1.json` (`ba33b4d0…`) as a proposal for M5; do not freeze it.

## Member 5 — contract revision, gate 4, routea review

1. By **2026-10-23 12:00**: confirm or amend M4's proposed contract revision (`ba33b4d0…`),
   including the refined `environment_assumptions`; make it the canonical persisted contract
   value; complete the edit manifest (schema 2) or approve M4's supplementary manifest; hand
   over the build recipe + tool versions; confirm no competing gate-3 evidence will be pushed.
2. Gate 4: deliver the `routeb/` scripts and run the unchanged round trip once guest access
   exists; if access is missing, report that blocker explicitly.
3. Review any `routea/` change (M5 owns code review; M4 may propose patches).

## Lead

1. Approve the contract revision after M5 confirmation and M4 review (`ba33b4d0…`; oracle
   constants unchanged).
2. Review the gate-3 record and evidence bundle; resolve the "SHA256SUMS 24/24" and `d1e0741`
   discrepancies with M3/M5.
3. Decide the fixture freeze when gates 3-5 evidence exists; protect the oracle; keep the status
   board honest.
4. Coordinate guest access and the merge order.

## Contingency

- Isolation evidence missing by 2026-10-23 18:00 -> gate 3 stays `CONDITIONALLY FEASIBLE`,
  gate 4 `NOT RUN`; demo shows the partial state honestly; no oracle change.
- Gate 3 fails on placement/encoding -> `unsupported` with the concrete fact; the team decides
  once between an alternate placement inside the same authorization and a different public
  fixture with a full re-freeze.

## Evidence for this list

- Lead verified M4's contract proposal with the canonical `SecurityContract` rule (hash match,
  six edits, oracle constants unchanged).
- Lead verified the `origin/main` `33235f5` Route A artifacts by struct-only parsing (identity,
  13 program headers, one changed `PT_LOAD` `0x8e9->0x1000`, redirect target `0x4018e9`, cave
  head + 42-byte message, diff intervals); recorded in handoff 13 §10 as inputs, not evidence.
