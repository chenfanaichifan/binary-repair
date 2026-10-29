# 35 — Two-person AI handoff protocol (M3 and M5, each with their own AI)

**From:** Lead
**Date:** 2026-10-29
**Applies to:** any two owners who exchange technical work through separate AI sessions (today: M3 ↔ M5; also usable for M4 verification handoffs).

Each person runs their own AI. The AIs do not share context, and they never will. The only shared context is **this repository**. Therefore: *the repo is the message bus; chat is notification only.* A handoff that exists only in a chat message does not exist.

## 1. Five rules that remove the ping-pong

1. **Artifact first, message second.** Before you write to the other person, commit or publish the artifact and run the validator. A message without an artifact is only legal as a *blocked package* with an exact external cause.
2. **One ball at a time.** Every message ends with exactly one line: `NEXT: <owner> must <action> by <time>`. The sender is done; the receiver owns the next action. No "let's discuss".
3. **Machine-checkable delivery.** A handoff package must pass
   `python scripts/check_handoff.py <package> --expect-from M3 --expect-to M5`.
   The printed `PASS`/`FAIL` lines are the truth; opinions do not count.
4. **Fail closed.** Missing file, missing row, hash mismatch, or a `passed` without a command = `NOT VERIFIED`. Never "looks fine". Never infer.
5. **24-hour escalation.** No BOARD update in 24h → Lead marks `OVERDUE`; owner publishes a blocked package within 4h. No silent waiting, no third round of "please check".

## 2. The handoff envelope (copy this shape)

Every handoff message is a file `docs/handoffs/<NN>-<from>-to-<to>-<id>.md` with this fixed content:

```text
FROM: M3
TO: M5
TASK: T3.1 / P4
STATUS: delivered | verified | failed | blocked
ARTIFACT: docs/handoffs/evidence/P4/  (SHA256SUMS sha256: <64 hex>)
VALIDATOR: PASS handoff 'P4' task='T3.1' from='M3' to='M5' artifacts=12 sums=13 interface=1
COMMAND(S): routeb/gate4_runner.sh <repo-root> <work-dir>
EXPECTED: gate4_pass=true; six cases 6/6; uid=1003; CapEff=0; no-egress
OBSERVED: gate4_pass=true; 6/6; uid=1003; CapEff=0; egress blocked (log line 42)
REQUESTED: run adapter + p2, reply PASS/FAIL with the observed p2 line
DEADLINE: 2026-10-31 12:00
NEXT: M5 must verify P4 and record Gate 4 result by 2026-10-31 12:00
```

Rules for the envelope:
- `ARTIFACT` is a path + the hash of `SHA256SUMS` (not a screenshot, not a WeChat filename).
- `COMMAND(S)` must be exactly reproducible on the receiving host; if the command needs a guest, say which host and snapshot.
- `EXPECTED` and `OBSERVED` must be comparable line by line.
- `STATUS: blocked` requires `NOTES:` with the exact external condition and who can clear it.
- No attachments in chat beyond a one-line notification ("P4 published, validator PASS, see file X").

## 3. Workflow

```
producer AI                      repository                        consumer AI
-----------                      ----------                        -----------
run task ──► build package ──►  evidence/<id>/  ──►  check_handoff.py
                  │                handoff.json                 │
                  │                SHA256SUMS                   ▼
                  │                logs/                  PASS? ──no──► reply FAIL list (exact lines)
                  ▼                                            │
           check_handoff.py PASS                                yes
                  │                                            ▼
                  └──► BOARD row + envelope file ──►  consume → adapter → p2 → verdict file
                                                              │
                                                      BOARD row + envelope file
```

Status vocabulary (only these): `not_started`, `in_progress`, `delivered`, `verified`, `failed`, `blocked`, `overdue`, `closed`. Use `delivered` when the producer hands off, `verified` only after the consumer reproduces, `closed` only after the Lead approves.

## 4. How each AI session should be run

**Session start ritual (paste into your AI, every session):**
1. Read `docs/handoffs/34-m3-m5-task-split.md`, `docs/handoffs/35-ai-handoff-protocol.md`, your role card (`36` or `37`), and `docs/handoffs/BOARD.md`.
2. Run `git log --oneline -1` and `git status --short`; quote both.
3. State: task id, what artifact you will produce today, and the exact validator command you will run.
4. Do not ask the other AI anything directly; the other AI is not in this session. Publish or reply through the package.

**During work:**
- Run commands; paste the *observed* output line, not a summary.
- Write evidence to files under `docs/handoffs/evidence/<id>/`; do not paste large logs into chat.
- When blocked: create a blocked package and stop. The AI must not "try to make it pass" or edit the other side's files.
- Keep one fresh session per task. Do not carry yesterday's chat as state; the repo is the state.

**Session end (5 minutes):**
1. Run the validator and save its output in the package.
2. Update your row in `docs/handoffs/BOARD.md` (status, artifact, validator line, next action, deadline).
3. Write the envelope file for the other owner.
4. Commit the metadata (`handoff.json`, `SHA256SUMS`, logs, envelope, BOARD row). Never commit secrets or client binaries.

## 5. Copy-paste prompts

### 5.1 Producer prompt (M3's AI)

```text
You are the producer for BinaryRepair task T3.1 (Gate 4 guest execution).
Read these first, in this order:
1. docs/handoffs/34-m3-m5-task-split.md
2. docs/handoffs/36-m3-ai-role-card.md
3. docs/handoffs/35-ai-handoff-protocol.md
4. docs/handoffs/BOARD.md
Then run: git log --oneline -1; git status --short; report both.

Rules:
- Execute only inside the disposable guest; never execute a binary on the host.
- Produce the package at docs/handoffs/evidence/<handoff-id>/ with handoff.json, SHA256SUMS, logs.
- Run: python scripts/check_handoff.py <package> --expect-from M3 --expect-to M5
  and paste the exact PASS/FAIL output.
- Do not ask M5 for anything. When you are done, update your BOARD row and write
  docs/handoffs/38-m3-to-m5-<id>.md with the 10-line envelope.
- If the guest is unavailable, publish a blocked package by 12:00 with the exact
  error and who can unblock it; do not wait.
- Never report a check as passed unless you ran it and quote the observed line.
Output at the end: task id, package path, validator line, evidence counts, next action, blockers.
```

### 5.2 Consumer / verifier prompt (M5's AI)

```text
You are the consumer and record owner for BinaryRepair task T5.3 (Gate 4 record).
Read these first:
1. docs/handoffs/34-m3-m5-task-split.md
2. docs/handoffs/37-m5-ai-role-card.md
3. docs/handoffs/35-ai-handoff-protocol.md
4. docs/handoffs/BOARD.md
Then run: git log --oneline -1; git status --short; report both.

Rules:
- Accept only packages where python scripts/check_handoff.py <package> --expect-from M3
  --expect-to M5 prints PASS. Paste the exact output.
- Recompute candidate/manifest/SHA256SUMS hashes yourself; do not trust the sender's
  values. Map the bundle with app/services/attempt_writer.py or
  tools/routea_bundle_to_attempt.py, run the worker, then
  python tools/p2_acceptance.py --job-id <id>.
- Reject with docs/handoffs/39-m5-to-m3-<id>.md listing the exact missing/mismatched
  items. Do not edit M3's package. Do not weaken tests or acceptance rules.
- Fill the Gate 4 record with observed values only; missing = NOT VERIFIED.
- Try to falsify: list at least what you could NOT verify.
Output at the end: verdict PASS/FAIL/NOT VERIFIED per requirement, commands +
observed lines, record path, next action.
```

### 5.3 Blocked-message prompt

```text
Publish a blocked handoff package. Include: exact external condition, the command
you ran, the exact error text, who can unblock it, and the deadline. Do not ask the
other owner to "check" anything; do not retry the same blocked action more than twice.
```

## 6. Anti-patterns that caused the two-week stall (checklist)

| Anti-pattern | Replace with |
|---|---|
| "Can you check?" with no artifact | publish a package + validator PASS + one requested action |
| "I sent it on WeChat" | commit `handoff.json` + `SHA256SUMS`; chat only notifies the path |
| "It looks fine" | run `check_handoff.py` and p2; paste observed output |
| Waiting for the other person's step before starting yours | each side has an independent first step (M5: contract + synthetic; M3: access + packages) |
| Re-discussing scope every exchange | scope frozen in `34`; changes need a version bump + Lead approval |
| The same AI produces and signs off | producer and verifier sessions are separate; verifier prompt says "try to falsify" |
| A gate changing owners mid-flight | one DRI per gate; Gate 4 DRI = M5 |
| Long chat essays | 10-line envelope + one artifact |
| Pinning hashes in chat | hashes live in `SHA256SUMS` and the record; chat cites the file hash |
| Silently skipping a case | `not_run`/`NOT VERIFIED` row, visible in the record |

## 7. Cadence

- **Daily (async, 10 min per person):** update your BOARD row and publish one envelope if you delivered or are blocked. No meeting needed.
- **Decision sync (15 min)** only when the Lead escalates: one decision per sync, written into `34` or a ruling file; otherwise skip.
- **End of gate:** Lead updates the board to `closed` or `overdue` and records the outcome in `MEMORY.md`.
