# Handoff board — M3 / M5 (Gate 4 and real execution)

**Last updated:** 2026-10-29 (Lead)
**Rules:** the repository is the message bus; chat only notifies. Every change to a row carries a timestamp and an artifact hash. Only the row owner edits the owner column content; the Lead edits status, deadlines, and reassignments. A question without an artifact is not accepted; a missing item is `NOT VERIFIED`, never pass.

## Ball holder today

- **M3** holds the ball for **T3.0 access confirmation** (must be an artifact or a blocked package by **2026-10-30 12:00**).
- **M5** holds the ball for **T5.1 interface v1** and **T5.2 adapter + synthetic end-to-end** (no dependency on M3; deadline **2026-10-30 18:00**).
- **M4** preparation is ready but JOIN-1 is **not started**: checklist `docs/handoffs/42` and Gate 5/6 plan `docs/handoffs/43` are published; JOIN-1 begins only when M5's record + real p2 and M3's packages exist (2026-10-31 12:00).
- The two tracks run **in parallel**. Neither may start by waiting for the other.

## Tasks

| ID | Task | Owner | Status | Next action (who) | Artifact / validator | Deadline |
|---|---|---|---|---|---|---|
| T3.0 | Guest access + snapshot confirmation | M3 | not_started | Record snapshot/uid/tools, or publish blocked package (M3) | `docs/handoffs/evidence/T3.0-access/` | 2026-10-30 12:00 |
| T3.1 | Gate 4 formal guest execution → `P4` | M3 | not_started | Run `routeb/gate4_runner.sh` in guest, build package (M3) | `evidence/P4/`, `check_handoff.py` PASS | 2026-10-30 18:00 |
| T3.2 | Route A real executor bundle → `P3A` | M3 | not_started | Run authorized Route A executor in guest, build package (M3) | `evidence/P3A/`, `check_handoff.py` PASS | 2026-10-30 18:00 |
| T3.3 | Route B runtime bundle → `P3B` | M3 | not_started | Run `routeb/executor.py`, include `edit-manifest.json` (M3) | `evidence/P3B/`, `check_handoff.py` PASS | 2026-10-30 18:00 |
| T5.1 | Freeze interface v1 | M5 | not_started | Publish `docs/handoffs/INTERFACE-v1.md` + self-test (M5) | `check_handoff.py _scratch/handoff_demo/pass` PASS | 2026-10-30 12:00 |
| T5.2 | Adapter A→worker + synthetic p2 | M5 | not_started | Implement adapter, drive p2 to exit 0 on synthetic data (M5) | `pytest tests/integration/test_attempt_writer.py` 4 passed; p2 exit 0 | 2026-10-30 18:00 |
| T5.3 | Consume packages, replay, Gate 4 record | M5 | blocked_by T3.1–T3.3 | Validate packages first, then adapter/p2/record (M5) | Gate 4 record + p2 observed line | 2026-10-31 12:00 |
| JOIN-1 | Independent verification of Gate 4 record | M4 | pending | M4 checklist ready (`docs/handoffs/42`); execute when P4/P3A/P3B + M5 record + real p2 exist; request guest window for Gate 5 after P4 (M4/M3) | verifier row in record; `scripts/m4_verify_gate4.py` | 2026-10-31 18:00 |
| JOIN-2 | Lead approval row | Lead | pending | Approve or reject with recorded reason (Lead) | approval row + record hash | 2026-10-31 18:00 |

## Gate status (unchanged by this board)

| Gate | Status | Evidence |
|---|---|---|
| Gate 3 (Route A) | **CLOSED / APPROVED** 2026-10-22 | record `0b3b51e4…f2da`; do not reopen |
| Gate 4 (Route B formal) | **NOT RUN** | no guest run + no signed record yet; this board is the path to close it |
| Gate 5 (placement) | pending Route A runtime (M4/M3) | Gate 3 design closed; runtime proof still `not_run` |
| Gate 6 (violation detection) | partial | concrete crash accepted; symbolic half pending V4 |
| Fixture | **NOT FROZEN** | freeze decision only after gates 3–5 |
| Real pipeline (`tools/p2_acceptance.py`) | **BLOCKED (exit 2)** | measured 2026-10-29; no real result bundle reached the worker |

## Status vocabulary

`not_started` → `in_progress` → `delivered` → `verified` → `closed`; plus `failed`, `blocked`, `overdue`.

## Update log

| Date | Change | By |
|---|---|---|
| 2026-10-29 | Board created; M3/M5 split and protocol published (`34`–`37`) | Lead |
| 2026-10-29 | M4 published Gate 4 independent-verification checklist (`42`) + Gate 5/6 plan (`43`); host-side helper `scripts/m4_verify_gate4.py` self-tested only on synthetic packages; evidence store still has no P4/P3A/P3B, no record, no real p2 job; **no gate status changed (Gate 4 NOT RUN, Gate 5 pending, Gate 6 partial)** | M4 |
