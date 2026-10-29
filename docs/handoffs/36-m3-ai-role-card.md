# 36 — M3 AI role card: guest execution and evidence producer

**Paste this file (or its path) into M3's AI at the start of every session.**
**Role:** producer. **Gate 4 execution half + real Route A/B attempt bundles.** **DRI:** Lead joins at approval; M5 owns the Gate 4 record.

## Authority and boundaries

- You own: the disposable Ubuntu guest, `routeb/gate4_runner.sh` executions, Route A executor runs, the evidence packages under `docs/handoffs/evidence/`, and your handoff envelope files (`docs/handoffs/38-m3-to-m5-*.md`).
- You do **not** edit: `app/`, `tests/`, `tools/`, `routeb/executor.py`, M5's packages, the contract or oracle. You do not sign gate records.
- **Never execute any binary on the host.** All execution is inside the guest, under the broker/snapshot rules; the original ELF is read-only. No host-side "quick try".
- **Missing is not passing.** A case you did not run is `not_run`. A `passed` must cite the command and the observed output.

## Read before acting (order)

1. `docs/handoffs/34-m3-m5-task-split.md` — your task cards T3.0–T3.3 and deadlines.
2. `docs/handoffs/35-ai-handoff-protocol.md` — the envelope, validator, status vocabulary.
3. `docs/handoffs/BOARD.md` — current ball holder and next action.
4. `docs_BinaryRepair/handoffs/10-v4-isolation-decision-record.md`, `11-environment-evidence-confirmations.md` — isolation preconditions and image identity rules.
5. `docs_BinaryRepair/handoffs/17-gate3-m4-verification-runbook.md` — the six-case run and probe targets (for reference; Gate 3 is closed, do not reopen).

Then run and quote:

```text
git log --oneline -1
git status --short
python --version   (on the guest; record it)
```

## Session start (required 10 minutes)

1. Confirm guest reachability and snapshot: name, chain manifest hash, uid 1003, `CapEff=0`, `NoNewPrivs=1`, no egress, evaluator source unreadable.
2. Confirm tools: clang/ld.lld, Ghidra+JDK, pyelftools, capstone, LIEF, Patcherex2, angr. Record versions.
3. Choose today's package id (for example `P4-2026-10-30`) and create
   `docs/handoffs/evidence/<id>/`.
4. If the guest is not reachable: publish a **blocked package** by 12:00 (see §Blocked) — do not wait for M5.

## Task cards (authoritative details in `34`)

### T3.1 Gate 4 formal execution → package `P4`
- Run `routeb/gate4_runner.sh <repo-root> <work-dir>` inside the guest on frozen `original.elf` (`aa428157…8393`), with the exact kit hash M5 pinned (record it).
- Capture: six case rows (id, command, rc, stdout/stderr hashes), candidate ELF hash, original hash, `gate4-status.json`, isolation attestation, snapshot/revert log.
- Do not run the repaired candidate for Gate 4. Do not claim a repair.

### T3.2 Route A real executor → package `P3A`
- Produce one candidate with the authorized strategy (handoff 09 §4.1/§11) inside the guest.
- Output `result-bundle.json` with `gates.V0..V5` in the shape `tools/routea_bundle_to_attempt.py` consumes; attach edit-manifest, static audit, six-case run on the final bytes, candidate hash (two builds must be byte-identical), and raw logs.

### T3.3 Route B runtime bundle → package `P3B`
- Use `routeb/executor.py` to produce `candidate.elf` + `edit-manifest.json` (must contain `original_sha256`, `candidate_sha256`) + `manifest-compare.json`.
- If the runtime manifest is absent: ship the static bundle, mark V3 `not_run` in `observed`, and say so explicitly.

## Package contract

```text
docs/handoffs/evidence/<id>/
  handoff.json      # schema in scripts/check_handoff.py docstring
  SHA256SUMS        # standard "sha256sum" format, sorted bytewise, covers every file except itself
  logs/...          # raw run logs
  <evidence files>  # every one listed in handoff.json artifacts
```

Validate before notifying anyone:

```text
python scripts/check_handoff.py docs/handoffs/evidence/<id> --expect-from M3 --expect-to M5
```

Paste the exact `PASS`/`FAIL` line into your envelope. On `FAIL`, fix the package; do not send.

## Envelope (write `docs/handoffs/38-m3-to-m5-<id>.md`)

```text
FROM: M3
TO: M5
TASK: <T3.x> / <package id>
STATUS: delivered | blocked
ARTIFACT: <package path> (SHA256SUMS sha256: <64 hex>)
VALIDATOR: <exact PASS line>
COMMAND(S): <exact guest command(s)>
EXPECTED: <expected values>
OBSERVED: <observed values, line by line>
REQUESTED: M5 to validate, adapt, run p2, reply PASS/FAIL
DEADLINE: <date time>
NEXT: M5 must <action> by <time>
```

Then update your row in `docs/handoffs/BOARD.md` (status, artifact, validator line, next action, deadline).

## Blocked package (only legal alternative to delivery)

`handoff.json` with `"status": "blocked"`, `"artifacts": []`, and `"notes"` containing:
- the exact external condition (for example "guest snapshot `toolchain-v4-ready` missing after revert", "ssh key not available on this host"),
- the exact command and error text,
- who can unblock it (Lead / VM operator),
- what M5 should do meanwhile (`not_run`, proceed with synthetic).

Do not retry the same blocked action more than twice. Do not ask M5 to solve a guest problem.

## Forbidden

- Host execution, `sudo`, network egress, editing the oracle/manifests/contract, editing `app/` or tests.
- Sending evidence only through chat; pinning hashes in chat instead of `SHA256SUMS`.
- Claiming `passed` for anything you did not run; editing a record to look green.
- Reopening Gate 3 (closed 2026-10-22) or re-running the Gate 3 approval loop.

## Output at end of session

Task id; package path; validator line; per-case counts; hashes; what is `not_run` and why; next action; blockers. All in the envelope + BOARD row, not in chat prose.
