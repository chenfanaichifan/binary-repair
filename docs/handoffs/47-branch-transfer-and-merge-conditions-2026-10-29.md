# 47 — M1 branch transfer and 2026-10-31 merge conditions

**From:** Lead (decision) + M4 (verification-row definition)
**To:** M1 (main owner / release), cc M2/M3/M4/M5
**Date:** 2026-10-29 (Asia/Hong_Kong)
**Status:** decision + transfer instructions. No gate status changes: Gate 3 closed, **Gate 4
`NOT RUN`**, Gate 5 pending, Gate 6 partial, fixture `NOT FROZEN`.
**Basis:** M1's report (remote lacks the integration branch; remote `main` is `d969e6d`); this
checkout's measured git state (below); `docs/handoffs/41` §1/§6, `docs/analysis/VERIFICATION.md`.

## 1. Answer 1 — the branch is local-only; here is the commit and the transfer bundle

Measured in `D:\BinaryRepair_Project`:

| Fact | Observed value |
|---|---|
| branch | `integration/consolidation-2026-10-29` |
| tip commit | **as named in `delivery/TRANSFER-integration-2026-10-29.md`** (the tip at transfer time; the pre-`47` tip was `86f78af`) |
| upstream / remote ref | **none** — the branch has no upstream and was never pushed; `git branch -r` has no `origin/integration/…` |
| last-fetched `origin/main` here | `4107836` (the branch is ~60 commits ahead of it; exact count at the transfer tip is in the transfer note) |
| M1's `main` `d969e6d` | **not an object in this checkout** (`git cat-file -t d969e6d` fails); the remote is not reachable from this host (`git ls-remote` fails with a CA trust-anchor error), so I cannot confirm its ancestry |
| verified code state | `986a49f`; `git diff --stat 986a49f..HEAD -- app tests routea routeb binaryrepair_ai schemas fixtures` = **empty** (later commits are docs/scripts only) |

**Transfer bundle (preferred path):**

```text
delivery/integration-consolidation-2026-10-29-<tip>.bundle
```

The bundle is created with `git bundle create <file> integration/consolidation-2026-10-29`,
`git bundle verify` prints `The bundle records a complete history` / `is okay`, and a fetch into
a fresh scratch repository resolves the branch tip exactly. Size ≈ 18.4 MiB; the exact tip,
size and SHA-256 are published in the transfer note
(`delivery/TRANSFER-integration-2026-10-29.md`) next to the bundle and in the BOARD update log.
**Transfer is the human copy step** — I do not push; pushing needs an approved credential path
and is M1's action.

M1's import commands (run in the target clone):

```bash
git bundle verify /path/to/integration-consolidation-2026-10-29-<tip>.bundle
git fetch /path/to/integration-consolidation-2026-10-29-<tip>.bundle \
  refs/heads/integration/consolidation-2026-10-29:refs/heads/integration/consolidation-2026-10-29
git rev-parse integration/consolidation-2026-10-29   # must equal the tip named in the transfer note
git log --oneline -1 integration/consolidation-2026-10-29
```

The bundle contains the full ancestry back through `origin/main` `4107836`, so it also works in
a clone that does not have `4107836`. If M1's `main` is `d969e6d`, confirm the relationship
before the PR (report both lines, do not guess):

```bash
git merge-base --is-ancestor 4107836 d969e6d; echo "ancestor_rc=$?"
git merge-base 4107836 d969e6d
git cat-file -e d969e6d:tests/test_evidence_endpoint.py; echo "evidence_test_rc=$?"
git rev-parse d969e6d:app/controller_api.py
```

Expected controller-evidence form (the verified branch has it; `4107836` and the member branches
do not):

```text
app/controller_api.py              ab9ff06b07c08077db3f9b54459eed72871d0964   (blob)
tests/test_evidence_endpoint.py    present
```

### 1.1 If the tip moves

Any further commit on the branch changes the bundle. The transfer note's tip/SHA-256 must match
the bundle M1 actually receives; if they differ, ask for a regenerated bundle and do not merge
the mismatch. The content of that delta will be listed commit-by-commit in the M4 row (§3).

## 2. Answer 2 — do NOT rebuild from `main` + member branches as an equivalent branch

A branch-merge rebuild **would silently lose verified product content**, so it is not authorized
as a substitute for the bundle. Measured reasons:

| Integration content | Where it exists | On M1's remote? |
|---|---|---|
| controller evidence fix: `app/controller_api.py` blob `ab9ff06b…` + `tests/test_evidence_endpoint.py` | only local consolidation commit `cc29158` | **no** — `git branch -a --contains cc29158` lists only this integration branch; `4107836`, `036328d`, `9c6e1f7`, `a29d217`, `222f7e3` do not contain the file/tests |
| acceptance slice `app/domain/acceptance.py` / `outcomes.py` / `tests/unit/test_acceptance.py` | content-equivalent on `member-4-verification` @ `9c6e1f7`, merged as content by `cc29158` | yes, as content, but `9c6e1f7` is **not** an ancestor of the integration branch (`merge-base` = `02ce2b9`); merging it reintroduces an old layout |
| M2 GUI slice | merge commit `381e4ef` = parents `036328d` + `4107836` | `member2-backend-adapter` @ `036328d` exists |
| Route B/member-5 and member-3 content | already in the `4107836` ancestry | `member-5/latest` @ `a29d217` and `member-3-route-a` @ `222f7e3` are **ancestors** — nothing to merge |

A rebuild from `main` + branches would therefore ship the **known static-placeholder controller
evidence defect** and/or a different acceptance/test tree, and would not be the independently
verified tree. That is a product regression, not a packaging choice.

**Fallback authorization (only if the bundle genuinely cannot cross the host boundary).** The
Lead authorizes exactly this input list and nothing else; the result is a **new tree** and needs
the full §3 M4 re-verification (new measured numbers, no reuse of the old row):

1. `main` @ `d969e6d` — base, **only if** `git merge-base --is-ancestor 4107836 d969e6d` exits
   0 **and** `d969e6d` already contains the controller-evidence blob/tests named in §1 plus the
   acceptance-slice file hashes below. If either check fails: **stop, publish a blocked note,
   do not construct a replacement controller fix for this merge.**
2. `origin/member2-backend-adapter` @ `036328d` — merge it (it is the M2 slice parent of
   `381e4ef`).
3. `origin/member-4-verification` @ `9c6e1f7` — **do not merge the branch**; if the three
   acceptance files are missing from `main`, take exactly these three blobs from it and verify
   the bytes equal the verified values:
   `app/domain/acceptance.py` `732c43f0c827da745a37731158a93cd13822edb7367a110ce0ccf1904970aba4`,
   `app/domain/outcomes.py` `e4723dd94c2a9239f32fc1f1626de7693457198e3677202dd3fa9fc644f4826b`,
   `tests/unit/test_acceptance.py` `141b815ff60041029cd6a580cacdb356cfdad3708c946bea8fe872a1b8bdd1d0`.
4. `origin/member-5/latest` @ `a29d217` — already an ancestor; **do not merge**.
5. `origin/member-3-route-a` @ `222f7e3` — already an ancestor; **do not merge**.

Any other branch (`member-5/*`, `member-4-routea-gate3`, `gate4-results`, `routea-probe-results`)
is **not** an input. If the fallback is used, M1 must report the new head SHA and measured
commands before asking for M4/M5/Lead action, and the deadline risk is M1's to record.

## 3. Answer 3 — the 10-31 merge needs M4's integration row, not the Gate 4 row

Two different rows, and they must not be conflated:

| Row | Artifact | Gates what | State now |
|---|---|---|---|
| **M4 integration / PR-head verification row** | written record, e.g. `docs/handoffs/48-m4-merge-verification-<head8>.md` (kept next to the PR head) | **the merge of the integration branch into `main`** | not started — PR head does not exist yet |
| M4 verifier row in the **Gate 4 record** | `docs/handoffs/evidence/P4-…/` Gate 4 record | **Gate 4 closure only** (JOIN-1) | blank/`NOT VERIFIED`; Gate 4 stays `NOT RUN`; **not** a merge condition |

The M4 merge-verification row must contain, for the exact PR head `H`:

1. `git rev-parse H` (full SHA) and `git log --oneline H -1`.
2. `git diff --stat 986a49f..H -- app tests routea routeb binaryrepair_ai schemas fixtures` —
   must be **empty** (no product/test change since the independently verified state).
3. The list of commits `986a49f..H` (docs/tooling only, each named; a product/test change in the
   delta makes the row `FAIL` and sends the branch back to M1).
4. M1's branch-tip measured block (§4) pasted verbatim with the command that produced it; M4 also
   re-measures what this host supports (`tests/unit/test_acceptance.py`, `scripts/demo_e2e.py`,
   and the full-suite helper/plain-run state) and records **its own** observed lines.
5. Secret/binary scan result (`git ls-files` no `.env`/key; no client binary), and the branch tip
   is the bundle tip (no local uncommitted changes).
6. Verdict `PASS` / `FAIL` / `NOT VERIFIED`; `NOT VERIFIED` blocks the merge.

**Merge sequence:**

1. M1 freezes PR head `H` (includes the latest `main` merged in or the branch as-is) and runs
   the measured block on `H`.
2. M1 publishes/asks for the M4 row; M4 fills it for `H`.
3. Lead writes the approval record (below) citing `H`, the M4 row file hash, and the planned
   merge commit + tag.
4. M1 merges as a **merge commit**, tags `mvp-integration-2026-10-31`, updates `main` README with
   measured-only facts.

**Lead approval form — written confirmation is binding; a GitHub PR `Approve` is not enough.**
The repo is the message bus (`docs/handoffs/35`), so the durable approval is a written record in
the repo (an approval row in the merge-verification record or a separate Lead approval file)
that cites: PR head `H`, M4 row path + SHA-256, merge commit/tag target, and the scope boundary
(Gate 4 NOT RUN unless separately closed). A GitHub PR review `Approve` may accompany it as the
mechanical platform action, but chat or PR comments without the written record do not count.
If `H` changes after the M4 row or after approval, **both are void** and must be redone.

## 4. Answer 4 — PR wording before the re-run: "reported" is allowed only as labelled history

- **Allowed now:** a section titled **"Reported (not re-measured on this PR head)"** quoting the
  numbers from `docs/analysis/VERIFICATION.md` §1/§7 at verified code state `986a49f` (measured
  on Windows 11, Python 3.14.6, pytest 9.1.1 by M4), with the source and commit named. These are
  provenance, **not** merge evidence.
- **Required before merge:** a separate section **"Measured on this PR head"** with M1's own
  commands and the exact observed lines, run on the PR-head tree. The merge evidence is only this
  block.
- **Never:** paste a number from this workspace as if it were measured on `H`; use the reported
  numbers as acceptance evidence; drop the command/provenance. `docs/handoffs/41` §7 and
  `AGENTS.md` require "measured numbers only, with the command that produced it".
- Environment note: on this Windows host plain `pytest` hits the sandbox `tmp_path` defect
  (`--basetemp` run stops at 5 collection errors, or 238 markers with 167 pass / 69 environment
  errors / 2 skip / **0 failures** and a session-finish crash). Use `scripts/pytest_rt_report.py`
  with `PYTHONPATH=scripts`, `RT_REPORT_PATH`, `RT_TMP_ROOT`, or run on Ubuntu; quote the helper
  summary line, not a recollection.

Suggested PR body shape:

```text
## Reported (not re-measured on this PR head)
Source: docs/analysis/VERIFICATION.md §1/§7, verified code state 986a49f (Windows 11, Python 3.14.6).
<line(s)>

## Measured on this PR head (<full SHA>)
$ <command>
<observed line(s)>
Host: <OS> / Python <version> / pytest <version>

## Gates
Gate 4 NOT RUN (separate record); no repair claim; fixture NOT FROZEN.
```

## 5. What M1 should send back (one message, artifact-first)

1. `git rev-parse integration/consolidation-2026-10-29` after the bundle fetch, or the transfer
   blocked with the exact host error and who can move the file.
2. The four ancestry/presence lines from §1 for `d969e6d`.
3. The PR head `H` and the measured block from §4.
4. Whether the §2 fallback is needed; if yes, stop after step 1 of §2's fallback and report the
   precondition results.

No gate status changes with this document: **Gate 4 remains `NOT RUN`**, Gate 5 pending, Gate 6
partial, fixture `NOT FROZEN`; the merge row is about the integration branch, not about Gate 4.
