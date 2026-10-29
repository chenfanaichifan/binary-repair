# Root-Cause Analysis: Why BinaryRepair Had No End-to-End Result After Two Weeks

> **Later status (HEAD `7b294ba`):** this diagnosis was written at the start of the
> consolidation window (12:34-12:55). Its tree totals (189 executed / 146 passed /
> 41 errored) are historical: after the member-4 acceptance merge, the controller
> evidence fix and the member-2 GUI merge the current measured totals are 238
> collected / 229 passed / 2 skipped / 7 environment errors / 5 uncollectable
> modules. See `docs/analysis/VERIFICATION.md` and `MEMORY.md`. The root-cause
> findings themselves remain the reference analysis.

| Field | Value |
|---|---|
| Date of analysis | 2026-10-29 (Asia/Hong_Kong) |
| Author role | process-analyst (Team task `task-3`) |
| Repository | `D:\BinaryRepair_Project` |
| Branch analysed | `integration/consolidation-2026-10-29`, created from `origin/main` `4107836` |
| Analysis window | 2026-10-29 12:34 - 12:55 (+08) |
| Host | Windows 11 AMD64, Python 3.14.6 |
| Deliverable | this document only; no product code, test, README, or `MEMORY.md` was modified by this analysis |
| Safety boundary | no uploaded or repaired binary was executed, loaded, or decompiled; exported/repaired artifacts were hashed as bytes only |

**How to read this document.** Section 1 is the answer in plain language. Section 2 is the
required root-cause table. Section 3 explains each cause. Section 4 holds the supporting
measurements. Section 5 records what this session actually fixed. Section 6 is the 3-day
recovery plan. Appendices A-E hold the exact commands, the full branch inventory, the
source index, the numbers from the brief that did not reproduce, and the teammate documents
this analysis used.

Every number below was reproduced on this host with a command in Appendix A. Git-object
citations are pinned by branch/commit (for example `origin/main:README.md` L11-18), so they
do not drift when teammates edit the working tree. Statements taken from teammate documents
or from evidence that cannot be reproduced from this host are labelled **[reported, not
reproduced here]** or **[unverified]**. The working tree is being edited by teammates while
this document is written; in-session artifacts are timestamped.

---

## 1. Executive Summary

**The one-sentence answer:** the project did not fail because a technology was missing. It
failed because it never defined a visible end-to-end milestone, never integrated the working
pieces into one branch, and let documentation/evidence ceremony and local environment
problems absorb the time that should have produced a demo. A genuine constraint (execution
belongs on a disposable guest VM) was allowed to freeze host-only work that never needed the
guest.

The user's complaint is factually correct, and it is measurable:

1. **There is no integrated product.** `origin/main` has 112 commits of working application
   code, but the strongest artifacts - the approved Gate 3 record, 34 handoff files, the
   status board, `MEMORY.md`, the screenshots - exist only on the stale branch
   `member-4-verification` (62 commits ahead, 103 behind `origin/main`), and `main` contains
   no `docs/route-a/` at all [C3, C7, C13, C14]. The last commit on any branch is
   `2026-10-22 19:56:33`; from 2026-10-23 to 2026-10-28 the repository received **zero
   commits** while two evidence deadlines passed [C12, C34].
2. **Every reader saw a different truth.** The `member-4-verification` README says the
   controller, fixture and routes are "not started"; the `origin/main` README says they are
   in `main`; the `AGENTS.md` on `member-4-verification` still says "No application code
   exists yet"; the test count is given as 83, 16 and 45 in the same README. The measured
   reality on this host is neither: 146 passed / 2 skipped / 41 environment-errored / 5
   uncollectable modules on the consolidated tree, and 187 passed / 2 skipped when the
   broken temp-directory fixture is replaced without touching any test [C15, C16, C18, C19].
3. **Process outran the product.** On `origin/main`, 81 commits touch Markdown versus 46
   that touch application code (1.76 : 1). On `member-4-verification`, 53 commits touch
   `docs_BinaryRepair/handoffs` versus 7 that touch `app/` or `tests/` (7.57 : 1; 85% of the
   branch's 62 unique commits are handoff edits). The 35 handoff files total 312,889 bytes,
   which is 4.4x the 70,470 bytes of application code on the same branch [C5, C6, C9]. The
   single Gate 3 record was re-pinned to at least six different hashes in one evening
   [C33].
4. **The environment was treated as a universal stop-work order.** Guest-only execution is
   a genuine design blocker for real binary checks. But the UI adapter, the controller, the
   demo, the integration and the README did not need a guest, and they still stalled. Most
   local blockers are also incidental: missing host toolchain (clang, Ghidra, JDK, LIEF,
   capstone, pyelftools), a PyPI mirror that returns no versions, 41 pytest errors caused by
   a broken sandbox temp directory, and 10 unreadable leftover temp directories in the
   workspace [C20-C22, C29]. One recorded blocker did **not** reproduce: `git worktree add`
   now succeeds [C24].
5. **There was no definition of done.** The README says "MVP in progress" and "No
   completed-MVP date is established" (m4 README L13, L219). The `MEMORY.md` "Completed"
   checklist still has eight unchecked product items. The only "entry points" on `main` are
   the GUI launcher and two provider/candidate scripts; no end-to-end repair path exists
   (C14-adjacent, see Section 4.6). The integration order put the GUI last, so the only
   user-visible surface was a demo banner.
6. **The good news.** This is recoverable, and much of the work is real: the FastAPI GUI
   boots and renders, the controller API persists jobs in SQLite, the acceptance engine
   returns honest `inconclusive` / `rejected` verdicts on synthetic data, a Gate 3 evidence
   bundle really exists locally with the recorded hash, and a synthetic end-to-end controller
   demo was measured for the first time in this session [C26, Section 5]. The missing step is
   assembly and an honest status board - not another research spike.

**If the team only remembers three things:**

1. One branch, one truth, one runnable demo by the end of Day 2 (Section 6).
2. Code and a demo before any new handoff; documentation follows a working artifact.
3. A missing guest makes checks `not_run` - it does not stop the rest of the product.

---

## 2. Root Causes (Table)

Severity scale: **Critical** = alone prevents the user-visible result; **High** = adds days
of rework and hides progress; **Medium** = makes every future week harder. "Cost" means time
or capability actually lost, not a feeling.

| # | Root cause | Key evidence (reproducible) | Severity | What it cost |
|---|---|---|---|---|
| **RC1** | **No end-to-end milestone / definition of done.** "MVP in progress" was an accepted status; no owner-level deliverable produced a runnable demo. | m4 README L13-15 and L219 ("No completed-MVP date is established"); `MEMORY.md` L105-119 has 8 unchecked product items; `origin/main` has no end-to-end script (`scripts/` = `smoke.py`, `demo_candidate.py`) [C14]; zero commits 2026-10-23..10-28 [C12]; only 4 active days total [C12]. | Critical | Two weeks without a user-showable result; the 10-23 deadlines passed silently; the client sees documentation, not a product. |
| **RC2** | **Integration by branch switch, not by merging.** Nobody owned a single integrated tree; work stayed on divergent branches until they became dangerous to merge. | 42 concrete branches (37 remote + 5 local) [C1]; 244 commits on all refs vs 112 on `origin/main`; **132 commits never reached main** [C2, C4]; 28 of the 36 non-main remote branches add **0** unique commits [C1b]; m4 is 62 ahead / 103 behind [C3]; m4's tree deletes **143** files of `main` (`app/controller_api.py`, `app/services/*`, `app/db/*`, `routea/*`, `routeb/*`) with -15,642 lines [C7]; `main` has no `docs/route-a/`, no handoffs, no `MEMORY.md` [C13, C14]. | Critical | The approved Gate 3 record and the whole status history are invisible from `main`; merging the "best" branch naively would destroy the application; every member rebuilt context from branches, and the session itself started on the stale m4 branch and showed "controller not started". |
| **RC3** | **Status truth divergence.** Different branches carried contradictory, stale status documents; test counts were quoted without re-running. | Three conflicting READMEs: m4 says controller/fixture/routes "not started" (L26-29) vs `main` says they are in main (L22-32); m4 `AGENTS.md` still says "No application code exists yet" (last changed 2026-10-18) while the branch has app code; m4 README carries **three different test numbers in one file** - "83 tests passing" (L31), "16 passed, 3 skipped" (L158), "expected total 45" (L159); `MEMORY.md` still says "Current phase: Foundation" (L38) and an obsolete "Next step" (L39) while newer entries above report Gate 3 approved. Measured: 146/2/41/5 and 187/2 vs 83/16/45 [C15, C16, C18, C19]. | High | Every teammate and agent acted on a different snapshot; repeated re-verification instead of progress; the user's "still nothing works" impression is a direct product of the repo telling three stories at once. |
| **RC4** | **Process-for-product substitution.** Handoffs, gate records and bundle re-pins became the main activity; each gate grew a producer/verifier/signature ceremony instead of ending in a demo. | `origin/main`: 81 commits touch `*.md` vs 46 touch `app/tests/routea/routeb/binaryrepair_ai` [C5]; `member-4-verification`: 53 handoff commits vs 7 app/test commits [C6]; 35 handoff files = 312,889 B vs 70,470 B of app code on the same branch (4.4x) [C9]; **26 handoff files mention Gate 3, all written on 2026-10-22** [C9b]; the Gate 3 record hash was re-pinned to >=6 values (`bddccbfe`, `3dcdc862`, `0b3b51e4`, `810bb893`, `62ed341b`, `94d7d314`) [C33]. | High | 2026-10-22 spent in evidence bookkeeping (133 of 244 commits in one day [C12]); integration postponed "until the record is canonical"; no integration milestone was ever scheduled. |
| **RC5** | **Environment treated as global stop-work instead of per-task status.** A real guest-only constraint was confused with accidental host setup problems, and both were allowed to block work that did not depend on either. | Genuine blocker: host may never execute uploaded binaries (AGENTS.md safety boundary; README architecture). Accidental local blockers measured: `clang`, `gcc`, `java`, `ghidra`, `lief`, `readelf`, `objdump` all MISSING; Python modules `capstone`, `elftools`, `lief`, `angr`, `z3` all MISSING [C22]; pip mirror returns "from versions: none" for both `capstone` and pure-Python `pyelftools` [C20, C21]; 41 pytest errors are one sandbox temp-directory defect, 5 modules are uncollectable [C16, C18]; 10 leftover workspace directories are unreadable [C29]; `var/` writes are denied [C23]. Recorded-but-not-reproduced: `git worktree add` now succeeds [C24]. | High | UI adapter, controller API, demo and integration were never attempted on the host although they need no guest; three days of "blocked" plus a 6-day silence. |
| **RC6** | **The visible product was scheduled last.** The agreed integration order put the GUI after M5/M4/M1 slices, so the only thing a non-author could see was a demo banner. | Order ① M5 -> ② M4 -> ③ M1 -> ④ GUI in `MEMORY.md` L56; `member2-backend-adapter` holds 50 unmerged commits of the real-controller GUI (backend adapter, honest verdict rendering, screenshots, e2e tests) and none of it is on `main` [C2; Appendix B]; `main`'s GUI is a demo-only app (`DEMO = True`, in-memory `app/demo.py`) and has no HTTP-controller adapter despite `README.md`/`docs/controller-integration.md` advertising it **[reported by runtime-verifier and confirmed by source search]**; `origin/main` has 3 screenshots only on m4, never merged. | High | After two weeks the deliverable was "a labelled fake"; the user cannot see progress even when code progress exists. |

---

## 3. Root Causes Explained

### RC1 - No end-to-end milestone (Critical)

**Plain language.** A milestone is something an outsider can run and see. The project only
had *gate*, *slice* and *handoff* units of work - internal terms - so "done" meant "my
document was signed", not "the product does something new". No date in the plan produced a
runnable artifact, and no owner was accountable for one.

**Evidence.**

- `origin/member-4-verification:README.md` L13-15: "Status: MVP in progress ... The repair
  controller, the public fixture, and the two real repair routes are not implemented yet."
  L219: "No completed-MVP date is established."
- `origin/member-4-verification:MEMORY.md` L105-119: the "Completed" list has 8 open `[ ]`
  items (fixture, GUI vertical slice, frozen contract, Route A candidate, Route B round
  trip, V0-V5 acceptance, export bundle, independent replay).
- `origin/main` has `scripts/smoke.py` and `scripts/demo_candidate.py` only; before this
  session there was no single end-to-end command. `run.bat`/`start.ps1` start the demo GUI
  only [C14].
- Commit dates show work on 4 days only: 10-15 (1), 10-18 (16), 10-20 (94), 10-22 (133);
  the last commit is `2026-10-22 19:56:33`, then nothing until this recovery session on
  10-29 [C12, C34]. Two "next-day" evidence deadlines (2026-10-23 12:00 and 18:00,
  `MEMORY.md` L10/L11, handoff 14 L66) left no commit.

**Cost.** The product could be "80% built" every day and still show nothing to the client.
The final week produced no commit at all, which is the clearest possible signal of a
missing definition of done.

**Prevention.** One owner-level demo per day with a runnable command, recorded output and a
screenshot. If the demo cannot grow that day, the day failed - regardless of how many
documents were signed.

### RC2 - Integration gap and branch sprawl (Critical)

**Plain language.** Branches are cheap; integration is expensive. The team treated `main` as
"someone else's merge target" and let each slice live on its own branch. Because the branches
diverged far enough to delete each other's files, merging became scary. Scary merges got
postponed, so the divergence grew - a classic feedback loop.

**Evidence.**

- `git branch -a` prints 43 refs because `origin/HEAD` is a symbolic ref; the real count is
  **37 remote + 5 local = 42 branches** [C1].
- **132 commits** are reachable from some ref but not from `origin/main` [C4]. Only 8 remote
  branches have any unique commit; **28 have zero** - they are stale leftovers, not parallel
  work [C1b].
- `origin/main...origin/member-4-verification` = **103 / 62** (main-only / m4-only) [C3].
- The m4 tree is an older, smaller layout: 87 files vs `main`'s 172 [C8]. Diffing
  `origin/main` -> m4: **218 files changed, +12,931 / -15,642**; **143 files deleted**,
  including `app/controller_api.py`, 7 `app/services/*` files, 6 `app/db/*` files, 10
  `routea/*` and 25 `routeb/*` files [C7]. The tree also predates the `docs/route-a/` folder.
- `origin/main` has no `docs_BinaryRepair/`, no `docs/route-a/`, no `MEMORY.md`, no
  `AGENTS.md` [C13, C14]. The approved Gate 3 record (signed 2026-10-22) exists only on
  `member-4-verification` and in `delivery/` [C26, C33].
- Session impact measured directly: the session started on `member-4-verification`, whose
  README says "controller ... not started" (L26), while `origin/main` actually contains
  `app/services/jobs.py`, `app/controller_api.py` and the acceptance engine (main README
  L22-32). Both statements were "true" on their own branch, and both were wrong as a view of
  the project.

**Cost.** The best-completed gate is not on the integration branch; the application has no
documentation/status history; the team cannot answer "what is the current product?" without
switching branches. Every new agent or teammate pays this cost again.

**Prevention.** `main` stays runnable and CI-tested; branches live <= 2 days and <= a few
commits; a merge that deletes another slice's files is blocked by a file-count check
(compare `app/ tests/ routea/ routeb/ binaryrepair_ai/ schemas/ fixtures/` against
`origin/main`); docs merge with the code they describe.

### RC3 - Status truth divergence (High)

**Plain language.** When the status page is wrong, everyone optimises the wrong thing. The
team had three READMEs, one `AGENTS.md`, one `MEMORY.md` and 35 handoffs - all partly stale.
Nobody could trust a document, so everyone re-checked or re-built, and progress could not be
seen even when it happened.

**Evidence.**

- m4 README L26-29: Job controller "**not started**", fixture "**not delivered**", Route
  A/B "**not started**". `origin/main` README L24-32: controller, GUI, acceptance engine,
  AI boundary, SQLite schema and fixture are "in `main`". Both were written on 2026-10-20 -
  and on 2026-10-22 Gate 3 was approved, so neither is current [C15].
- m4 `AGENTS.md` (last change 2026-10-18) still states "No application code exists yet";
  the same branch contains `app/domain/acceptance.py` and 41 tests. This analysis session
  loaded that file automatically - stale instructions actively mislead agents too.
- One README, three test numbers: "`main` currently runs **83 tests passing**" (L31),
  "Measured on `main` at `453fe95` (2026-10-20): **16 passed, 3 skipped**" (L158),
  "expected total after merge: **45**" (L159). Measured current trees: 146 passed on the
  integration tree, 117 on clean `origin/main`, 40 on clean m4, 187/2 with the measurement
  shim [C16, C17, C18, C19]. None of 83/16/45 is reproducible as a current statement.
- `MEMORY.md` L38 says "Current phase: Foundation / environment and fixture feasibility",
  and L39 still says the next step is to wait for `member1/controller-only` to be opened -
  while handoff README L7 already records that branch as existing (`f4c7fa9`) and re-run
  15/0, and `main` already includes controller work. Newer entries are prepended above the
  stale block; the file has 119 lines but no single current-state section that is updated in
  place [C10].
- `origin/main` README L105 claims "Expected on a clean checkout: all non-runtime tests
  pass"; on this host 5 modules cannot even be imported and a 41-test environment defect
  fires [C16].

**Cost.** The Lead, the members and every AI agent spent time reconciling documents instead
of building. The project's own history cannot be trusted, which is exactly the condition the
user is complaining about.

**Prevention.** One generated, measured status block (command + date + counts), regenerated
by a script; stale branch docs deleted or marked historical; `AGENTS.md` must include the
measurement date; no hand-written test counts.

### RC4 - Process-for-product substitution (High)

**Plain language.** The team built a very careful process for *proving* things - producer,
independent verifier, signature, bundle, hash, waiver, re-pin - but the process became the
output. Each gate loop is legitimate for a safety-critical acceptance system; the problem is
that no loop ended with a product increment, and each signature change forced new hashes,
which forced new messages and new files.

**Evidence.**

- Ratio on `origin/main`: **81** commits touch Markdown vs **46** touch the code paths
  (`app tests routea routeb binaryrepair_ai`) = 1.76 : 1 [C5].
- Ratio on `member-4-verification`: **53** commits touch `docs_BinaryRepair/handoffs` vs
  **7** touch `app`/`tests` = 7.57 : 1 [C6]. Since the branch has 62 unique commits, 85% of
  its work is handoff documentation.
- Volume: 35 handoff files = 312,889 bytes / 4,104 lines; application code on the same
  branch = 13 files, 70,470 bytes / 1,562 lines. Handoffs are **4.4x** the app bytes [C9].
  The whole `docs_BinaryRepair/` folder is 490,066 bytes, versus 177,030 bytes of app code
  on `main` [C8b, C9].
- **26 handoff files mention Gate 3, all dated 2026-10-22** [C9b]. `MEMORY.md` mentions
  2026-10-22 on 35 lines; 25 timestamped entries were added between 17:14 and 22:20 on that
  day alone [C10].
- The Gate 3 record (`docs/route-a/gate3-record.md`) was re-pinned to at least six different
  hashes in that evening: `bddccbfe`, `3dcdc862`, `0b3b51e4`, `810bb893`, `62ed341b`,
  `94d7d314`; the v1/v2 evidence bundles add `0ef65546`, reported-but-wrong `8256c850`, and
  the final `6151a806` [C33; m4 README/MEMORY cross-refs].
- Ceremony artifacts keep multiplying: 17 tags for 42 branches, 13 of them `archive/*`
  snapshot tags [C11]; the branch policy in main README L141-146 asks for short-lived
  branches - the opposite of what happened.

**Cost.** The single most productive day (2026-10-22, 133 commits) ended with an approved
gate - and still no integrated product; the gate work did not move `main` because the
evidence lived on the m4 branch. The cost is not "too much documentation" in the abstract;
it is that **the documentation was the deliverable**.

**Prevention.** Hard rule: no new handoff, gate record or bundle without a code/commit/demo
change in the same working day. Cap handoffs to 1 per decision. Generate record hashes with
one script instead of re-typing them into messages. Schedule the integration merge *before*
the evidence freeze, not after.

### RC5 - Environment treated as global stop-work (High)

**Plain language.** Some tasks genuinely need the guest VM: running the original and
repaired binaries, symbolic analysis, behavioural checks. But building the GUI adapter,
fixing the controller API, writing a demo and merging branches need only the host. The team
did not separate "this check is `not_run`" from "I am blocked", so host-only work also
stopped. On top of that, several *accidental* local problems (no toolchain, no PyPI, broken
temp ACL) were recorded as if the project itself were blocked.

**Evidence.** See the classification table in Section 4.5. Headline numbers: 46 pytest
problem items = 41 identical `PermissionError` temp-directory failures + 5 modules that
cannot import `capstone`/`elftools` (13 test functions) [C16, C18]; 10 unreadable leftover
directories in the workspace root, all pytest/pip temp artifacts [C29]; `var/` writes denied
[C23]; pip returns "from versions: none" for every package tried [C20, C21]; host toolchain
absent [C22]. The recorded "git worktree creation denied" did not reproduce: `git worktree
add --detach` and `git worktree remove` both succeeded [C24], so at least one recorded
blocker is stale and should not be quoted anymore.

**Cost.** Days of work that did not need a guest were treated as blocked (UI, controller,
demo, integration). The most visible of these - the GUI/controller adapter - was the one
thing the user could have seen.

**Prevention.** A blocker declares *which tasks* it blocks (`guest execution: V0/V3/V4`,
`host deps: routea/routeb unit tests`, ...). Anything not in that list stays queued and
continues. `not_run` is a status, not a stop sign.

### RC6 - Visible product scheduled last (High)

**Plain language.** The only part a client can see is the UI and the demo. The plan put the
GUI at step ④, after three invisible slices, so for two weeks the visible product stayed a
banner-labelled mock. The "honest demo" was a virtue, but it was also the only thing to
show.

**Evidence.**

- Integration order in `MEMORY.md` L56: "① member 5 -> ② member 4 -> ③ member 1 -> ④
  member 2 (GUI last)".
- `origin/member2-backend-adapter` holds **50 unmerged commits** (GUI backend adapter,
  verdict rendering, dry-run view, status page, e2e/CDP tests, screenshots, tools) [C2].
  None are in `main`.
- `origin/main`'s GUI is demo-only: runtime-verifier found `app/main.py` is `DEMO = True`
  backed by in-memory `app/demo.py`, with no `BINARYREPAIR_BACKEND` / `BINARYREPAIR_API_BASE`
  handling even though `README.md` and `docs/controller-integration.md` describe it
  **[measured in-session, docs/analysis/RUNTIME-VERIFICATION.md §8]**. That is a
  documentation-vs-code bug on `main`, not a guest blocker.
- m4 README L100-106 says the demo is "entirely on labelled demo data" and "the real
  controller replaces the demo data"; that replacement never happened on `main`.

**Cost.** Even when code progress existed, the user saw none of it. The complaint "no
working result" is a direct description of the only artifact the team exposed.

**Prevention.** Build the thinnest vertical slice first (screen -> real controller -> honest
verdict), even with synthetic attempts, and grow it daily. Put the visible artifact in the
definition of done.

---

## 4. Supporting Evidence

### 4.1 Timeline (facts only)

| Date | Commits (all refs) | What was produced | What a user could run |
|---|---|---|---|
| 2026-10-15 | 1 | decisions, PRD/design read, setup | nothing |
| 2026-10-18 | 16 | interface confirmations, handoffs 01-08, first branch push + tag | demo GUI skeleton at best |
| 2026-10-20 | 94 | `main` rebuilt at `453fe95`; integration decision; controller/acceptance branches; README status; `MEMORY.md` notes "main not green: 5 failed, 2 skipped" | demo GUI, tests partly failing |
| 2026-10-22 | 133 | tags/archives cleanup; Gate 3 evidence loop; 26 Gate 3 handoffs; Gate 3 approved 22:20; `main` tip `4107836`; m4 tip `9c6e1f7` | demo GUI only; no merged evidence |
| 2026-10-23 .. 10-28 | **0** | two evidence deadlines passed (12:00, 18:00 on 10-23); no commits | nothing changed |
| 2026-10-29 (this session) | 0 new commits at analysis time | consolidation branch, acceptance slice staged, measured runtime demo, this analysis, independent verification queued | synthetic end-to-end controller demo (first measured demo) |

Sources: C12 (per-day counts), C34 (last commit), `MEMORY.md` L10-11/L48-50 (deadlines),
`docs/analysis/RUNTIME-VERIFICATION.md` (in-session demo).

### 4.2 Branch drift detail - what each unmerged branch holds

Ahead/behind = "commits only on the branch / commits the branch is missing from main".
Of the 36 non-main remote branches, only 8 have unique commits; the other 28 add nothing and are stale
refs (full list in Appendix B).

| Branch | Ahead | Behind | What it actually holds | Verdict |
|---|---|---|---|---|
| `member-4-verification` | 62 | 103 | Approved Gate 3 record + `delivery/` copy; 34 numbered handoffs; `MEMORY.md`; `AGENTS.md`; screenshots; acceptance engine variant. Its app/ tree is a **subset** of main. | **Cherry-pick docs/gate evidence only; never merge the tree.** This is the single highest-value unmerged artifact. |
| `member2-backend-adapter` | 50 | 57 | Real-controller GUI adapter (`app/backend.py`, `app/status.py`, `app/visuals.py`), dry-run view, landing/setup templates, e2e/CDP tests, screenshots; also drags the `agent/` archive layout. | **Merge the GUI slice** (M2 work, missing user-visible product); discard `agent/` additions. |
| `member-5/gate3-m5-replay` | 48 | 103 | Gate 3 replay record; only 3 commits are not already in m4, and they record the stale `73b5e824` record that handoff 32 declared superseded. | **Superseded** by m4's approved record; archive and delete the branch. |
| `gate4-results` | 5 | 46 | CI-run evidence for the supplementary Route B round trip (run 39752557610: `routeb/out/gate4/*`, roundtrip ELF, Ghidra/Patcherex2 logs). Duplicates a one-off workflow run; formally Gate 4 still NOT RUN. | **Keep the evidence by hash in a doc**; branch can be archived. |
| `member-5/gate4-ci` | 4 | 46 | First 4 commits of `gate4-results`; **0 unique relative to it** [C30]. | **Duplicate**; delete. |
| `routea-probe-results` | 2 | 25 | CI cave-probe run output (`routea/out/runtime.log`, edit-manifest, readelf audit). Supplementary, not gate 3. | **Archive**; superseded as evidence by the v2 bundle. |
| `member-5/routea-probe2` | 1 | 25 | Same commit as in `routea-probe-results`; **0 unique relative to it** [C30]. | **Duplicate**; delete. |
| `member-4-routea-gate3` | 1 | 4 | Independent audit tooling (`routea/{byteaudit,facts,audit,evidence,gate3}.py`, two test files, `docs/route-a/06-m4-independent-audit.md`, VM check script) - additive, pending re-review, not required for gate 3. | **Optional**; useful verification helper, not MVP-critical. |

Local branches: `integration/consolidation-2026-10-29` (this branch, `4107836`),
`member-4-verification`, `member-4-routea-gate3` (also checked out in a now-missing temp
worktree), and two delivery helper branches `delivery-main`/`delivery-docs` used to move
evidence to the VM host [C24].

**Why merging m4 wholesale would be destructive** (measured, C7): 218 files changed,
+12,931 / -15,642; 143 deleted files, including the controller API, 7 service files, 6 db
files, 10 routea files and 25 routeb files. A naive `git merge` would look like "gate 3
approval" and silently remove the application. Keep the docs, refuse the tree.

### 4.3 Process-for-product numbers

| Metric | `origin/main` | `member-4-verification` | Interpretation |
|---|---|---|---|
| Commits touching Markdown | 81 of 112 (72%) | (35 handoff-related lines in MEMORY) | docs are the dominant activity |
| Commits touching code (`app tests routea routeb binaryrepair_ai`) | 46 of 112 (41%) | 7 of 62 (11%) | code is the minority activity |
| Doc:touch ratio | 1.76 : 1 | 7.57 : 1 | m4's unique work is 85% handoffs |
| Documentation bytes | `docs_BinaryRepair` 490,066 B total; handoffs 312,889 B | app code 70,470 B | handoffs alone are 4.4x app code on m4 |
| Tests added | 160 executable items collected (5 modules/13 functions uncollectable) | 41 tests on m4 | test volume is small relative to doc volume |
| Tags / branches | 17 tags (13 `archive/*`) / 42 branches | - | archiving substituted for integrating |
| CI test workflow | none; only 2 one-off evidence workflows (`gate4.yml`, `routea-probe.yml`) | - | nothing prevents divergence |

Caveat for fairness: the documentation is not worthless. It contains the gate definitions,
the acceptance semantics and the evidence chain that make this a *verifiable* project rather
than a demo. The defect is that it was not paired with integration increments. Evidence that
the method can work: the Gate 3 evidence bundle is real and its recorded hash verifies on
this host - `delivery/gate3-bundle-v2-2026-10-22.zip`, 18,318 B,
`6151a80633fdde0d9b1ce87c126b01994a730625557d17297828468799710a65`, and
`delivery/gate3-record-draft.md`, 14,082 B,
`0b3b51e49f24c5759ff5d37a0569d44149af989dd4e72af6e51b279f0901f2da` [C26]. The work was
real; it just never entered the product.

### 4.4 Status truth divergence - claim vs measurement

| Claim (source) | Claimed state | Measured on 2026-10-29 | Reproduced? |
|---|---|---|---|
| m4 README L26-29 | controller / fixture / routes "not started" | `origin/main` has controller, services, db, fixtures; Gate 3 approved 2026-10-22 | **No** - stale by 2 days on the branch that approved the gate |
| main README L11-18 | controller/GUI/acceptance in main; Gate 3 "IN PROGRESS"; Gate 4 NOT RUN; no binary repaired | Gate 3 approved 19:56, i.e. 1.5 h after the README's last edit (18:25); no binary repaired | **Partly** - code claims yes, gate status stale |
| m4 README L31 | "`main` currently runs 83 tests passing" | 117 passed on clean main; 146 on consolidated tree | **No** |
| m4 README L158 | "16 passed, 3 skipped" at `453fe95` | 16 does not reproduce on any current tree; only this historical README sentence contains it | **No (historical claim only)** |
| m4 README L159 | expected 45 after merge | 160 executable items on main + 29 acceptance = 189 | **No** |
| main README L105 | "all non-runtime tests pass" on clean checkout | 5 modules uncollectable, 41 temp-dir setup errors | **No** |
| m4 `AGENTS.md` | "No application code exists yet" | branch contains app code and 41 tests | **No** - instruction file stale since 2026-10-18 |
| `MEMORY.md` L38-39 | phase "Foundation"; next step = wait for controller-only branch | controller-only exists and main has controller work | **No** - stale block never updated |
| m4 README L219 | "No completed-MVP date is established" | zero product-level end-to-end path | **Yes** - and it is the honest sentence |

Test counts measured (exact commands in Appendix A):

| Tree | Executed test items | Passed | Skipped | Environment-errored | Uncollectable modules (test functions) | Failures |
|---|---|---|---|---|---|---|
| clean `origin/main` `4107836` | 160 | 117 | 2 | 41 | 5 (13) | 0 |
| clean `member-4-verification` `9c6e1f7` | 41 | 40 | 1 | 0 | 0 | 0 |
| consolidated worktree (main + m4 acceptance suite) | 189 | 146 | 2 | 41 | 5 (13) | 0 |
| consolidated worktree with measurement-only temp fixture (teammate run) | 189 | 187 | 2 | 0 | 5 (13) | 0 |

The 41 errors are all the same sandbox defect (`PermissionError` while pytest lists its
temporary-directory root), not assertion failures; replacing only the temp fixture turns all
41 into passes, which is why 187 is the honest upper bound on this host
[`docs/analysis/RUNTIME-VERIFICATION.md` §6]. The 5 uncollectable modules and the 13 test
functions are named in Section 8. The "16 passed" figure in the task brief is not
reproducible and should not be quoted further.

### 4.5 Environment - genuine blocker vs accidental blocker

| Blocker | Class | Measured / evidence | Does it truly block? |
|---|---|---|---|
| Host may not execute uploaded/repaired binaries; execution is guest-only | **Genuine design constraint** | `AGENTS.md` safety boundary; main README "The host never executes uploaded or repaired binaries" (L131) | Blocks V0/V3/V4/V5 real checks. Does **not** block UI, controller, acceptance unit tests, demo with synthetic bundles, docs.
| Guest VM / VMware not reachable from this host | **Genuine for host agents, not for the product** | `D:\VMs` absent, `D:\BinRepair` absent, `vmrun` not on PATH [C25]; guest `lab@192.168.30.128` recorded in `MEMORY.md` L15/L36 but not reachable here **[unverified from this host]** | Blocks host-side re-runs of guest evidence. M3's VM host already ran Gate 3 evidence on 2026-10-22 **[reported in gate3 record; not reproduced here]**.
| clang/gcc/Ghidra/JDK/LIEF/readelf/objdump absent on host | **Accidental local** | all MISSING [C22] | Blocks routea/routeb unit tests and local analysis; blocks nothing else on the host.
| No PyPI capability (mirror returns no versions) | **Accidental local** | `pip install --dry-run capstone` -> "from versions: none"; `pyelftools` (pure Python) -> same [C20, C21]; pip temp-cleanup warnings | Blocks installing test deps. Note: the claim "capstone has no cp314 wheel" is **[unverified]** - the mirror returned no versions for *any* package, so network/index reachability cannot be separated from wheel availability.
| pytest temp dirs become unreadable; 41 setup errors | **Accidental local (sandbox)** | `PermissionError: [WinError 5] ... pytest-of-Lenovo`; 41/46 problem items [C16, C18]; 10 unreadable leftover dirs [C29] | Blocks clean test summaries. Workaround exists (pre-created temp dir inside repo, or the measurement plugin) and does not weaken tests.
| `var/` writes denied | **Accidental local (sandbox)** | `Set-Content var\probe-...` -> access denied [C23] | Blocks default runtime data dir; controller already supports a data-dir override, so the demo runs under `_scratch/` **[measured in RUNTIME-VERIFICATION.md]**.
| `git worktree` creation denied | **Recorded, NOT reproduced** | `git worktree add --detach` + `remove` succeeded [C24] | Not a blocker now; delete the claim from project memory.
| Missing test deps on Python 3.14 | **Accidental local** | repo requires `pyelftools>=0.31`, `capstone>=5.0`, `lief>=0.15`; none installed; 5 modules import-fail [C22, C18] | Blocks 13 test functions; does not block the 187 that run.

**Work that did not need the guest and still stalled:** GUI/controller adapter (50 M2 commits
unmerged), controller API fixes (two run-start paths, static evidence endpoint - found by
runtime-verifier), a demo script, status-board consolidation, integration merges, test-harness
repair. All of these were possible on this host every day.

### 4.6 Missing definition of done and repeated "next actions"

`MEMORY.md` is the clearest trace. New entries are prepended at the top; the older
"Current phase / Next step / Blocked by" block (L38-43) was never updated, so the file
literally contains both "Gate 3 APPROVED" (L31) and "Current phase: Foundation" (L38).

| Open item | First recorded | Repeated in | Still open on 2026-10-22? | Evidence it was duplicated across dates |
|---|---|---|---|---|
| Wait for `member1/controller-only`, then re-run identity/integration | 2026-10-18 (`MEMORY.md` L39) | L7, L42, L43, L53, L99, L108-109 | Branch exists (`f4c7fa9`) and was re-run 15/0 per handoff README L7, yet the "Next step" text never changed | same action across 5 dated entries |
| "Re-run the full suite on current main and report the result" | 2026-10-20 (`MEMORY.md` L42/L99: main 5 failed, 2 skipped) | 2026-10-22 handoff 14 L44-45 (M1 action 2) | Yes - no green-suite record exists; measured 2026-10-29 | same action across 3 dates and 2 documents |
| Guest isolation evidence (deadline 2026-10-23 18:00) | 2026-10-22 17:20 (`MEMORY.md` L10-11, L36-37) | L10, L11, L13, L14, L48-50 | Deadline passed with zero commits; evidence survived only as a bundle | same blocker restated in >=8 entries on one day |
| M5 contract revision + manifest fix (target 2026-10-23 12:00) | 2026-10-22 (`MEMORY.md` L11, L18) | L13, L31, L48 | Contract hash `24bfe568` does appear in `main`'s requirements, but handoff 14 L89-92 shows the item still assigned | same target restated in 4+ entries |
| Fixture NOT FROZEN / freeze decision | 2026-10-15 (`MEMORY.md` L85) | L11, L16, L31, L49 | Yes - still not frozen | same status repeated in 4+ entries |
| Gate 4 formal NOT RUN | 2026-10-20 | L9, L11, L31, L32, L37, L48 | Yes - supplementary CI only | same status repeated in 6 entries |
| Gate 3 record canonical hash | 2026-10-22 | L21-L35 | Yes - 6 hash values in one night | record re-pinned 6 times |

Structural consequences of the missing definition of done:

- No entry point that ends in a product verdict: `origin/main` has the GUI launcher
  (`run.bat`, `start.ps1`) plus `scripts/smoke.py` (provider smoke) and
  `scripts/demo_candidate.py` (candidate validation), but nothing that drives
  job -> approve -> run -> evidence -> verdict end to end. The first such script
  (`scripts/demo_e2e.py`) was created in this session.
- No CI that runs tests: only 2 one-off evidence workflows exist (`gate4.yml`,
  `routea-probe.yml`) and both target one branch each.
- The integration order (GUI last) guaranteed that the visible surface could not show the
  other slices' progress.

---

## 5. What Was Actually Corrected in This Session (2026-10-29)

This section is deliberately conservative: it separates what was *measured* from what is
*planned or still uncommitted*. At the end of the analysis window the integration branch had
**no new commits** - `HEAD` was still `4107836`; the consolidation existed as staged and
working-tree changes.

| # | Corrective action | Owner/agent | Artifact / command | Status at 12:55 |
|---|---|---|---|---|
| 1 | Integration branch created from `origin/main` `4107836` | Lead | branch `integration/consolidation-2026-10-29`; `git branch --show-current` | Done (branch), no commits yet |
| 2 | Member-4 acceptance suite brought onto the integration tree | integrator | `tests/unit/test_acceptance.py` (304 lines, 10,431 B) staged; `app/domain/acceptance.py` / `outcomes.py` modified in the working tree (the m4 author's blobs differ from main's copy [C31]; byte equality of the working-tree files to the m4 blobs was not re-checked here) | In progress; staged, not committed |
| 3 | Layout consolidation | integrator | `AGENTS.md`, `MEMORY.md`, `REVIEW-CHECKLIST.md`, `agent_docs/`, `docs_BinaryRepair/` present in the worktree; `agent/` archive untouched | In progress; untracked |
| 4 | README rewritten to measured state | integrator | working-tree `README.md` (mtime 2026-10-29 12:42): "Measured test state on this host (2026-10-29)", no unverified 83/16 numbers | Done in working tree, not committed |
| 5 | Measured runtime demo | runtime-verifier | `scripts/demo_e2e.py` (26,090 B) + `docs/analysis/RUNTIME-VERIFICATION.md` (35,308 B): DB migration, GUI 3 screens 200, controller API HTTP+SQLite, full synthetic lifecycle; verdicts `inconclusive` / `rejected`; **no binary executed**; exit 0 | Measured and documented |
| 6 | Test-state measurement | runtime-verifier | `scripts/pytest_rt_report.py`; default run 146 passed / 2 skipped / 41 errored / 5 uncollectable; measurement-only temp fixture -> 187 passed / 2 skipped | Measured and documented |
| 7 | Independent verification | task-4 verifier | `docs/analysis/VERIFICATION.md` planned; must re-run tests + demo, check no lost `main` files, PASS/FAIL/NOT RUN per claim | **Not started** (waiting on tasks 1-3) |
| 8 | M2 GUI slice merge trial in isolation | m2-integrator | clone under `_scratch/m2-merge/`; report `docs/analysis/M2-MERGE-REPORT.md` planned | In progress; main worktree untouched |
| 9 | Controller honesty fix opened after the runtime audit | controller-fixer | task-6: `app/controller_api.py` modified in the worktree; `tests/test_evidence_endpoint.py` added; planned report `docs/analysis/CONTROLLER-FIXES.md` (persisted obligations served instead of the static `V0 passed` placeholder; honest mixed-result vocabulary) | In progress at 12:55; not finished |
| 10 | This root-cause analysis | process-analyst | this document | Done |

Corrective evidence generated by the demo that the team should keep: job creation from the
real fixture bytes (26,792 B, SHA-256 `aa428157...8393`, never executed on the host),
approval bound to the canonical contract hash
`24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37`, 409 before approval,
202 run start, idempotent restart, 409 on a conflicting idempotency key, 12 persisted
obligation rows, and verdicts produced by `app/domain/acceptance.py` only. See
`docs/analysis/RUNTIME-VERIFICATION.md` §5.

**Important gaps found while measuring the demo** (these are now the top engineering
priorities, not guest blockers; the controller-fixer task-6 was opened for item 2 during
this session and is in progress):

1. `app/main.py` has **no** HTTP-controller adapter despite README/docs advertising
   `BINARYREPAIR_BACKEND=http` (GUI was verified for rendering only).
2. `GET /api/attempts/{id}/evidence` returns a **static placeholder** (`V0 passed`,
   `V1-V5 not_run`) instead of the persisted obligation rows - it must not be cited as
   evidence until rewired.
3. Two run-start paths with two approval checks; the canonical `/runs` does not re-validate
   approval freshness.
4. `route.verification` becomes `"unknown"` for mixed `{passed, not_run}` sets - honest but
   imprecise UI vocabulary.
5. The test harness needs the measurement-only temp fixture or a POSIX host; this is an
   environment defect, not a product defect.

**Honest status of the session fix:** the *evidence* of a working slice now exists; the
*durable* integration does not, because nothing was committed and `main` was not touched.
The Lead must land the consolidation commit(s) before this can be called progress.

---

## 6. Recovery Plan - 3 Days

**Ground rules (they override habits):**

1. **One tree, one truth.** `integration/consolidation-2026-10-29` (then `main`) is the only
   tree anyone edits; status numbers come from one measured block, regenerated by a script.
2. **Every day ends with a visible artifact**: a commit, a runnable command with observed
   output, a screenshot, or a measured report - not a handoff.
3. **No new handoff or gate document without code/commit change** in the same day. Reuse the
   existing gate vocabulary; do not invent a new ceremony.
4. **Not_run is a status, not a stop.** A blocker names which tasks it blocks; all other
   tasks continue.
5. **Never fake a pass and never execute an uploaded/repaired binary on the host.** Missing
   guest = `not_run`, with owner and next date.
6. **Cut scope, not honesty.** It is acceptable for the demo to use labelled synthetic
   attempt bundles; it is not acceptable to call it a repair.

### 6.1 Owners (M1-M5 roles)

| Role | Owner responsibilities for the next 3 days |
|---|---|
| **M1** | Integration owner: land the consolidation commits, fix controller/API gaps (evidence endpoint, approval freshness, single run-start), own README/status board, run the daily merge gate. |
| **M2** | Product surface: land the GUI <-> real-controller adapter from `member2-backend-adapter`, render honest verdict labels, produce the three screenshots and the user-facing demo flow. |
| **M3** | Guest/VM/fixture: state guest availability explicitly (yes/no/date); if available, provide a 2-hour execution window and the isolation evidence; own the fixture-freeze proposal. |
| **M4** | Acceptance + independent verification: authoritative acceptance engine + tests on the integrated tree, verification report (PASS/FAIL/NOT RUN), enforce "no second success rule". |
| **M5** | Route tooling/evidence: Route A worker/contract revision on the integrated tree, Gate 4 static kit index, evidence bundle inventory with hashes; review M4 patches. |
| **Lead** | Decision owner: approve contract/merge/freeze, enforce one-tree rule, run the final demo end to end, delete stale branches/tags. |

Session helpers already in flight: `integrator` (M1 work), `runtime-verifier` (measured demo),
`m2-integrator` (M2 merge in isolation), `process-analyst` (this diagnosis), later the
independent verifier `task-4`.

### 6.2 Day-by-day plan

#### Day 1 (2026-10-30) - "One tree, one truth"

| Work | Owner | Deliverable / exit criterion |
|---|---|---|
| Commit the consolidation: M4 acceptance engine + `tests/unit/test_acceptance.py`, governance files, `docs_BinaryRepair/` (or its agreed new location), README with measured numbers, `.gitignore` | M1 + Lead | >=1 commit on `integration/consolidation-2026-10-29`; `git status` clean; `git diff --stat origin/main -- app tests routea routeb binaryrepair_ai schemas fixtures` shows no unexpected deletions |
| Run and record the acceptance suite: `python -m pytest tests/unit/test_acceptance.py -q` | M4 | observed count in the commit message and status block (29 passed per current report); no skips hiding failures |
| Re-run full suite with the measurement command and record counts + the 5 uncollectable modules | M4 | `docs/analysis/RUNTIME-VERIFICATION.md` numbers reproduced; README matches them |
| Merge the m2 GUI slice decision: apply the isolated-clone merge result or deliver conflict map + day-2 schedule | M2 + m2-integrator | branch/commit of the merge or `docs/analysis/M2-MERGE-REPORT.md`; main worktree never touched by the clone work |
| State guest availability for Day 3 (yes/no/date) and, if yes, book a window | M3 | one line in the status block: `guest: available 2026-10-31 10:00-12:00` or `guest: NOT AVAILABLE` |
| Publish Route A/M5 position: which tooling is required for MVP vs optional, contract revision file in the integrated tree | M5 | file exists on the integration tree; no new handoff |

Visible artifact for Day 1: **a commit that can be cloned and a measured status block**.

#### Day 2 (2026-10-31) - "One runnable product demo"

| Work | Owner | Deliverable / exit criterion |
|---|---|---|
| Implement the GUI HTTP-controller adapter (`BINARYREPAIR_BACKEND=http`, `BINARYREPAIR_API_BASE`) and render only controller verdicts | M2 + M1 | code search finds the env handling; GUI shows a real job from the controller API |
| Rewire `GET /api/attempts/{id}/evidence` to persisted rows; unify approval check across run-start paths | M1 | test or demo output shows persisted obligation values, not the static placeholder |
| Run `python scripts/demo_e2e.py` on the integrated tree and capture a transcript; add a GUI-driven variant if the adapter is in | M4 | exit 0; output shows fixture SHA-256, contract hash, `inconclusive`/`rejected`, "synthetic bundle" label, no binary execution |
| Produce and commit three screenshots (setup / comparison / evidence) with a real job id | M2 | `docs/analysis/screenshots/01-03` files committed with a caption each |
| Verify the demo independently (different shell/port), check no `passed` without evidence | M4 | `docs/analysis/VERIFICATION.md` draft with PASS/FAIL/NOT RUN |

Visible artifact for Day 2: **a runnable demo plus screenshots** - the first thing a
non-author can look at and understand.

#### Day 3 (2026-11-01) - "One honest evidence report and a freeze decision"

| Work | Owner | Deliverable / exit criterion |
|---|---|---|
| Guest window (only if M3 confirmed): run the original + candidate six-case checks under isolation; capture hashes/logs | M3 + M4 | `not_run` with blocker, or measured evidence with hashes; recorded in the status board |
| Independent verification of every claim in README, demo doc, this analysis, M2 report | task-4 verifier | `docs/analysis/VERIFICATION.md`: PASS/FAIL/NOT RUN table, no claim unverified |
| Single status board (README + `MEMORY.md` + status doc agree): Gate 3 PASS (record merged, hash verified), Gate 4 NOT RUN, Gate 5 partial/not_run, Gate 6 partial, fixture NOT FROZEN, real repair NOT RUN | M1 + Lead | no two documents disagree on any gate or number |
| Branch/tag cleanup: archive and delete the 28 zero-unique branches and the two duplicate CI branches (`gate4-ci`, `routea-probe2`, both among the 8 with unique commits); retire the stale local `delivery-*` refs; keep <=10 branches | Lead | `git branch -a` <= 10; every deleted tip has a tag or is merged |
| Freeze decision (freeze only if gates allow; otherwise record NOT FROZEN with the reason) | Lead + M3 | decision recorded in status board |
| Final demo run by the Lead on a fresh clone | Lead | transcript + tag `mvp-demo-2026-11-01` |

Visible artifact for Day 3: **an honest status report and a tagged, runnable demo**.

### 6.3 "Done means" checklist (MVP demo scope)

Must all be true before anyone says "the project works":

- [ ] `integration/consolidation-2026-10-29` has >=1 consolidation commit; `HEAD` is not
      `4107836`; a fresh clone starts the app.
- [ ] `git diff --stat origin/main -- app tests routea routeb binaryrepair_ai schemas
      fixtures` shows no unexplained deletion of `main` files (the m4 tree trap).
- [ ] `python -m pytest tests/unit/test_acceptance.py` passes; the observed count is in the
      status block.
- [ ] Full-suite measurement is recorded with its command: passed / skipped / errored /
      uncollectable counts, the 5 module names, and the reason (missing capstone/pyelftools
      or sandbox temp defect). No hand-typed counts.
- [ ] `python scripts/demo_e2e.py` exits 0 and prints: fixture SHA-256
      `aa428157...8393`, contract hash `24bfe568...4e37`, `inconclusive` for incomplete
      evidence, `rejected` for a failed required check, and an explicit
      "synthetic bundle / no binary executed" label.
- [ ] GUI renders the three real screens with a real job (HTTP 200) and the GUI ->
      controller adapter exists in code (search for `BINARYREPAIR_BACKEND`).
- [ ] `GET /api/attempts/{id}/evidence` returns persisted obligation rows (not the static
      placeholder) - shown by a test or a captured response.
- [ ] README, `MEMORY.md`, status board and evidence docs agree on Gate 3/4/5/6, fixture
      state and "no repaired binary"; gate 3 record hash
      `0b3b51e4...8f2da` verifies with `Get-FileHash`.
- [ ] Three screenshots committed with captions and real job ids.
- [ ] Branch count <= 10; 28 zero-unique branches (plus the two duplicate CI branches) are archived/deleted; a
      tag exists for every archived tip.
- [ ] Independent verifier report exists with PASS/FAIL/NOT RUN per claim and no unrun
      command presented as verified.
- [ ] Guest-dependent items are listed as `not_run` with a concrete blocker, owner and next
      date; no fake pass anywhere.
- [ ] Tag `mvp-demo-2026-11-01` on the integrated commit; the demo was run by the Lead from
      a fresh clone.

### 6.4 Risks and fallbacks

| Risk | Fallback |
|---|---|
| M2's 50-commit GUI merge is too conflicted | Ship `main`'s GUI for rendering + the controller-API demo, list the HTTP adapter as the first post-demo task; do not block tree consolidation on it. |
| Guest still unavailable on Day 3 | Keep Gate 4/5 runtime and real repair `not_run`; the demo remains synthetic-but-labelled. Do not fake. The integrated demo + honest board is still a real increment over two weeks of nothing. |
| `capstone`/`pyelftools` still missing | Keep the 13 tests uncollectable and named; do not weaken or delete them. Optionally vendor a pure-Python dependency offline as a separate, optional step. |
| Time pressure | Cut scope (fewer screenshots, one synthetic scenario), never cut the honesty rules or the acceptance single-source rule. |
| Teammates keep writing docs instead of code | Lead enforces "no handoff without code" and reviews the daily artifact, not the daily document. |

### 6.5 What stays `not_run` after these 3 days (honest ledger)

These are **not** failures of the 3-day plan; they are the boundary of what may be claimed:

| Item | State after 3 days | Why |
|---|---|---|
| Execution of the original/repaired ELF on the host | `not_run` (forbidden by design) | host safety boundary |
| Guest execution of the repaired candidate | `not_run` unless M3 provides a window | guest access is outside this host |
| Route A candidate generation (capstone/LIEF) | `not_run` on this host | dependencies absent; belongs to guest/host-2 |
| Route B candidate build (Patcherex2/angr/z3) | `not_run` on this host | same |
| V4 symbolic security check | `not_run` | no symbolic engine installed |
| V5 independent replay | `not_run` | needs a real candidate |
| Formal Gate 4 walk-through | `not_run` | needs the guest environment |
| Fixture freeze | decided, possibly still `NOT FROZEN` | depends on gates 3-5 |
| Real DeepSeek provider call | `not_run` in the measured demo | no API key used; provider boundary unchanged |
| "The CWE-121 fixture was repaired and accepted" | **not claimed** | no end-to-end repair evidence exists |

---

## 7. Lessons for a First-Year Team (short)

1. **A branch is not a deliverable.** If it is not on `main`, the product does not have it.
2. **Define done as something a stranger can run.** "Gate signed" is not done.
3. **Documents describe; they do not deliver.** One handoff per decision is enough.
4. **One status page, generated from a command.** Never hand-write test counts or gate status.
5. **A blocker must name what it blocks.** "No guest" blocks binary execution, not the UI.
6. **Merge early, merge small.** A 62-commit branch that deletes 143 files is not a merge,
   it is a rewrite.
7. **The visible slice is not "last".** Build the thinnest visible path first and grow it.
8. **If the repo has no commit for a week, the project is stopped - whatever the
   documents say.** Commit count is the most honest progress metric there is.

---

## Appendix A - Exact Commands and Observed Output

All commands were run from `D:\BinaryRepair_Project` on 2026-10-29 between 12:34 and 12:55
(+08) unless marked otherwise. `python` is 3.14.6. The worktree was being edited by
teammates; `git` counts are pinned to refs, not to the working tree.

| ID | Purpose | Command | Observed |
|---|---|---|---|
| C1 | Branch count | `git for-each-ref --format='%(refname)' refs/remotes \| Where-Object { $_ -notmatch '/HEAD$' }` + `git for-each-ref refs/heads` | 37 remote + 5 local = **42**; `git branch -a` prints 43 lines because `origin/HEAD` is a symbolic ref |
| C1b | Branches with unique commits | loop `git rev-list --count origin/main..<branch>` over the 36 non-main remote branches (excluding the symbolic `origin/HEAD`) | 8 branches ahead > 0; **28 branches ahead = 0**; 37 remote branches total incl. `main`; ahead sum 173 (with duplicates) |
| C2 | Commit totals | `git rev-list --count --all`; `git rev-list --count origin/main` | **244** / **112** |
| C3 | Divergence m4 vs main | `git rev-list --left-right --count origin/main...origin/member-4-verification` | `103  62` (main-only / m4-only) |
| C4 | Commits never in main | `git rev-list --count --all --not origin/main` | **132** |
| C5 | Doc vs code commits on main | `git log origin/main --oneline -- '*.md' \| Measure-Object -Line` and `-- app tests routea routeb binaryrepair_ai` | **81** vs **46** |
| C6 | Handoff vs code commits on m4 | `git log origin/member-4-verification --oneline -- docs_BinaryRepair/handoffs` and `-- app tests` | **53** vs **7** (of 62 unique commits) |
| C7 | m4 tree vs main | `git diff --stat origin/main origin/member-4-verification`; `--diff-filter=D --name-only`; `--numstat ... -- tests`; `--numstat ... -- app` | 218 files, +12,931/-15,642; **143 deleted files**; tests 22 files +480/-**2,609**; app 21 files +4/-**3,225**; deleted app files include `controller_api.py`, 7 services, 6 db, 10 routea, 25 routeb |
| C8 | Tree sizes | `git ls-tree -r --name-only origin/main \| wc -l` vs m4 | **172** vs **87** files |
| C8b | Code volume | line/byte sum over extracted `origin/main` tree: `app/**/*.{py,html,css,js}`, `tests/**/*.py` | app 27 files / 4,253 lines / 177,030 B; tests 23 files / 2,427 lines |
| C9 | Handoff volume | `Get-ChildItem docs_BinaryRepair\handoffs -File \| Measure Length -Sum`; same from m4 tree | **35 files** (34 numbered + README), **312,889 B**, 4,104 lines; m4 app code 13 files / 70,470 B -> 4.4x |
| C9b | Gate-3 handoffs | filter handoff files whose text matches `Gate 3\|gate-3\|gate3` | **26 files**, all with mtime 2026-10-22 |
| C10 | MEMORY.md | `git cat-file -s origin/member-4-verification:MEMORY.md`; line scan | **55,640 B** (git blob), 119 lines; 35 lines mention 2026-10-22; 25 timestamped entries on that day (17:14-22:20); L38-39 stale phase/next-step |
| C11 | Tags | `git tag \| Measure -Line`; archive subset | **17** tags, **13** `archive/*` |
| C12 | Commits per day | `git log --all --format='%ad' --date=short \| Group-Object` | 10-15:1, 10-18:16, 10-20:94, 10-22:133; nothing after 10-22 |
| C13 | m4 files absent from main | `git diff --diff-filter=A --name-only origin/main origin/member-4-verification` (non-`agent/`) | adds `docs/route-a/gate3-record.md`, `docs/route-a/SHA256SUMS`, 34 handoffs, `AGENTS.md`, `MEMORY.md`, `REVIEW-CHECKLIST.md`, screenshots - none on main |
| C14 | main docs/scripts/workflows | `git ls-tree -r --name-only origin/main -- docs scripts .github` | docs: only `docs/route-b/*` + 2 files; scripts: `demo_candidate.py`, `smoke.py`; workflows: `gate4.yml`, `routea-probe.yml`; **no `docs/route-a/`, no handoffs** |
| C15 | README texts | `git show origin/main:README.md`; `git show origin/member-4-verification:README.md`; `git log -1 --format='%h %ad %s' -- README.md` per branch | main README last edit 2026-10-22 18:25; m4 README last edit **2026-10-20 10:39** (2 days before its tip, 2026-10-22 19:56); quotes as cited in Section 4.4 |
| C16 | pytest on clean main tree | extract `git archive origin/main` to temp, then `python -m pytest tests/ -q -p no:cacheprovider --continue-on-collection-errors --junitxml=...` | junit `tests=165 errors=46 skipped=2 failures=0`; errors = 5 collection + 41 `PermissionError`; passed = 160-41-2 = **117** |
| C17 | pytest on clean m4 tree | extract `git archive origin/member-4-verification` to temp, run same command | `tests=41 errors=0 skipped=1 failures=0` -> **40 passed, 1 skipped** |
| C18 | pytest on consolidated worktree | same command in `D:\BinaryRepair_Project` | `tests=194 errors=46 skipped=2` -> **146 passed, 2 skipped, 41 env-errored, 5 uncollectable** |
| C19 | Measurement-only run | teammate command with `scripts/pytest_rt_report.py` (see `docs/analysis/RUNTIME-VERIFICATION.md` §6.3) | **187 passed, 2 skipped, 5 collection errors (13 uncollected test functions)**, pytest exit 1 only from collection errors. Run by runtime-verifier, not by this analysis; command recorded there. |
| C20 | pip mirror, compiled pkg | `python -m pip install --dry-run --no-input --timeout 15 capstone` | `Looking in indexes: https://pypi.tuna.tsinghua.edu.cn/simple`; `ERROR: Could not find a version that satisfies the requirement capstone (from versions: none)`; temp-cleanup warnings |
| C21 | pip mirror, pure-Python pkg | same with `pyelftools` | identical `from versions: none` -> outage/blocked index, not a wheel-availability issue |
| C22 | Host toolchain | `Get-Command` for clang/gcc/java/ghidra/lief/readelf/objdump; `python -c "import <m>"` for capstone/elftools/lief/angr/z3 | all MISSING |
| C23 | `var/` write probe | `Set-Content var\probe-<guid>.tmp` in try/catch | access denied (`Exception.Message`), no file created |
| C24 | git worktree probe | `git worktree add --detach <temp>\wt-probe HEAD`; `git worktree remove --force`; `git worktree list` | add **succeeded** (exit 0), remove **succeeded**; the recorded "worktree denied" did not reproduce; an old prunable worktree from 10-22 still listed at a missing temp path |
| C25 | Guest/VM presence | `Test-Path D:\VMs`; `Test-Path D:\BinRepair`; `Get-Command vmrun` | False / False / missing |
| C26 | Delivered gate evidence hashes | `Get-FileHash delivery\gate3-bundle-v2-2026-10-22.zip`, `delivery\gate3-record-draft.md`, `delivery\gate3-item6-support-2026-10-22.zip` | 18,318 B `6151a806...0a65`; 14,082 B `0b3b51e4...8f2da`; 4,004 B `3d49625c...f72b0` - all match recorded values |
| C27 | App importability | `python -c "import app.main"` | import ok (GUI app importable on Python 3.14.6) |
| C28 | Python version | `python --version` | 3.14.6 |
| C29 | Unreadable leftovers | `Get-ChildItem -Directory -Force` + `Get-ChildItem <dir> -Force` try/catch | 10 pytest/pip temp dirs unreadable: `.pytest-tmp`, 3x `pytest-cache-files-*`, `pytest_tmp`, `pytest_tmp_full1`, `pytest_tmp_int`, `pytest_tmp_lead3`, `pytest_tmp_lead5`, `pytest_tmp_rt` |
| C30 | Duplicate branches | `git rev-list --count origin/member-5/gate4-ci --not origin/gate4-results`; same probe2 vs routea-probe-results; m5 replay vs m4 | 0; 0; **3** commits not in m4 (replay doc, declared stale/superseded by handoff 32) |
| C31 | Duplicate acceptance engines | `git rev-parse origin/main:app/domain/acceptance.py` vs `origin/member-4-verification:...` | different blobs (`bc472f6d...` vs `01200eb5...`) - main has a copy, not the authoritative m4 version |
| C32 | Session git state | `git rev-parse --short HEAD`; `git status --short` | HEAD **4107836**; staged/modified: `tests/unit/test_acceptance.py` (A), `.gitignore`, `README.md`, `app/domain/acceptance.py`, `app/domain/outcomes.py` (M); untracked: `AGENTS.md`, `MEMORY.md`, `REVIEW-CHECKLIST.md`, `agent_docs/`, `docs_BinaryRepair/`, `docs/analysis/`, `scripts/demo_e2e.py`, `scripts/pytest_rt_report.py` |
| C33 | Gate 3 approvals and hash churn | `git show origin/member-4-verification:docs/route-a/gate3-record.md`; grep status lines; `MEMORY.md` hash mentions | record status "SIGNED - GATE 3 APPROVED (2026-10-22)"; six distinct record-hash values in `MEMORY.md` (`bddccbfe`, `3dcdc862`, `0b3b51e4`, `810bb893`, `62ed341b`, `94d7d314`) |
| C34 | Last commit on any ref | `git log --all -1 --format='%h %ad %s' --date=iso` | `9c6e1f7 2026-10-22 19:56:33 +0800 [member-4-verification] gate3: approve Gate 3 ...` |

Safety: no command above executed, loaded or decompiled an uploaded or repaired binary. The
fixture and delivered artifacts were read/hashed as bytes only. The guest was never contacted
from this host.

---

## Appendix B - Branch Inventory (all 37 remote branches)

Unique = commits reachable from the branch but not from `origin/main`
(`git rev-list --count origin/main..<branch>`). Branches with 0 unique are fully merged or
stale refs and can be tagged/deleted after a final check.

**Branches with unique commits (8):**

| Branch | Unique | Behind | Disposition |
|---|---|---|---|
| `member-4-verification` | 62 | 103 | Keep: cherry-pick gate-3 docs/record/MEMORY; never merge tree |
| `member2-backend-adapter` | 50 | 57 | Keep: merge GUI adapter slice; drop `agent/` additions |
| `member-5/gate3-m5-replay` | 48 | 103 | Archive tag then delete (superseded by m4 approval) |
| `gate4-results` | 5 | 46 | Archive tag (supplementary CI evidence) then delete |
| `member-5/gate4-ci` | 4 | 46 | Delete (fully contained in `gate4-results`) |
| `routea-probe-results` | 2 | 25 | Archive tag then delete (supplementary probe evidence) |
| `member-5/routea-probe2` | 1 | 25 | Delete (fully contained in `routea-probe-results`) |
| `member-4-routea-gate3` | 1 | 4 | Optional: independent audit tooling, pending review |

**Branches with 0 unique commits (28, i.e. 36 non-main remote branches minus the 8 with unique work) - merge/archive candidates:**
`gate4-results` neighbours and member-5 evidence branches:
`member-5/routea-c4a159-handoff`, `member-5/routea-cave`, `member-5/routea-probe`,
`member-5/routea-evidence`, `member-5/routea-final`, `member-5/routea-plan`,
`member-5/routeb-bundle`, `member-5/runner-hash`, `member-5/routeb-attempt`,
`member-5/routea-review`, `member-5/routea-syscall`, `member-5/routea-worker`,
`member-5/readme-status`, `member-5/docs-final`, `member-5/gate3-six-matrix`,
`member-5/gate4-clang18`, `member-5/contract-0x401309`, `member-5/candidate-quality`,
`member-5/canonical-contract`, `member-5/gate4-coverage`, `member-5/gate4-v6`,
`member-5/latest`, `member-5/m4-patch-review`, `member-5/gate4-runner`,
`member-5/gate4-evidence`, `member-5/gate4-fix`, `member-5/gate4-formal`,
`member-3-route-a` (28 names; re-verify with C1 before deleting anything).

**Local branches (5):** `integration/consolidation-2026-10-29` (current, `4107836`),
`member-4-verification`, `member-4-routea-gate3`, `delivery-main`, `delivery-docs`.
The two `delivery-*` branches were transport helpers for the VM evidence transfer and should
be retired after the evidence is on the integrated tree.

---

## Appendix C - Source Index (pinned references)

Git blobs (immutable, cite by branch + path + line):

- `origin/main:README.md` - L11-18 status block; L22-32 "what is in main"; L34-46 "not yet
  done"; L99-108 tests; L131 host-execution boundary; L141-146 branch policy.
- `origin/member-4-verification:README.md` - L13-15 "MVP in progress" status; L19-31 status
  table incl. "not started" rows and "83 tests passing"; L100-106 demo data; L150-164 tests
  (L158 "16 passed, 3 skipped"; L159 "expected total 45"); L219 "No completed-MVP date".
- `origin/member-4-verification:AGENTS.md` - "Current state: No application code exists yet"
  (last changed 2026-10-18).
- `origin/member-4-verification:MEMORY.md` - L7 current-task entry; L10-11 evidence
  ownership/deadlines; L13 "Next actions"; L21-35 gate-3 record hash history; L38-43 stale
  "Current phase / Next step / Blocked by"; L48-50 decisions; L56 integration order; L81
  known Route A gap; L86-89 host environment notes; L90 `agent/` merge warning; L97 gate 6
  partial; L99 main not green; L105-119 completed checklist.
- `origin/member-4-verification:docs_BinaryRepair/handoffs/README.md` - L7 controller-only
  fact; L9-10 stale "To send" handoffs; L15-39 handoff 09-33 status history.
- `origin/member-4-verification:docs_BinaryRepair/handoffs/14-next-actions-by-owner.md` -
  L31-36 critical path; L66 and L89 the 2026-10-23 deadlines; L38-105 per-owner next actions.
- `origin/member-4-verification:docs/route-a/gate3-record.md` - L13 signed/approved status;
  L78-87 six-item pass table; verdict "Gate 3: PASS - APPROVED 2026-10-22".
- `origin/main:docs/controller-integration.md` - adapter modes `mock`/`local`/`http` that
  the GUI is documented to use.
- `origin/main:docs/route-b/09-gate4-evidence.md` - supplementary Gate 4 CI PASS vs formal
  "NOT RUN".

Working-tree artifacts created in this session (uncommitted at analysis time):

- `docs/analysis/RUNTIME-VERIFICATION.md` - measured runtime demo and test-state report
  (runtime-verifier).
- `scripts/demo_e2e.py` - the synthetic end-to-end controller demo (runtime-verifier).
- `scripts/pytest_rt_report.py` - measurement-only pytest plugin (runtime-verifier).
- `README.md` (working tree) - measured status block (integrator).
- `AGENTS.md` (working tree) - measured current state (integrator).
- `tests/unit/test_acceptance.py` staged - M4 acceptance suite (integrator).
- `_scratch/m2-merge/` - isolated M2 merge clone (m2-integrator, not part of the tree).
- this document.

---

## Appendix D - Numbers Stated in the Brief That Did Not Reproduce

| Stated by the Lead | Measured | Note |
|---|---|---|
| "42 branches" | **42** = 37 remote + 5 local; `git branch -a` prints 43 lines because of `origin/HEAD` | Reproduced with an exact definition; quoting "43" without that definition would be wrong. |
| "244 commits all refs; 112 on origin/main" | 244 / 112 | Reproduced exactly. |
| "origin/main..member-4-verification = 62, reverse = 103" | 62 / 103 | Reproduced exactly. |
| "33 handoff files (~300 KB)" | **35 files** (34 numbered + README), **312,889 B** | ~300 KB reproduces; the file count is 35, not 33. |
| "MEMORY.md 55 KB append-only" | 55,640 B; newest-first insertions, not strictly append-only; 119 lines | Size reproduces. |
| "81 commits touch .md vs 46 touch code" | 81 / 46 | Reproduced exactly. |
| "53 handoffs vs 7 app/tests on m4" | 53 / 7 | Reproduced exactly. |
| "20+ handoffs for Gate 3 on 2026-10-22" | **26** handoff files mention Gate 3, all 2026-10-22 | Reproduced and improved. |
| "m4 tree deletes 28 files, ~3,178 deletions in tests alone" | 143 files deleted total; **17 app files / -3,225 app lines**; **20 test files / -2,609 test lines**; 218 files changed, +12,931/-15,642 | **Not reproduced as stated.** The deletion risk is larger than stated in file count, smaller in test lines. |
| "16 passed ... 5 test files cannot even collect" | 5 uncollectable modules (13 test functions) reproduced; **"16 passed" not reproducible** on any tree tested (117 main / 40 m4 / 146 consolidated / 187 with temp shim) | The only "16 passed" is a historical README sentence about commit `453fe95`. Should not be quoted. |
| "pip fails under the sandbox; capstone has no cp314 wheel; the tsinghua mirror returns nothing" | Mirror returns "from versions: none" for capstone **and** pure-Python pyelftools | Mirror/PyPI outage reproduced; "capstone has no cp314 wheel" is **[unverified]** because no package could be fetched at all. |
| "`var/` writes denied" | Denied (access denied), no file created | Reproduced. |
| "pytest temp dirs become unreadable" | 41 identical `PermissionError` setup errors; 10 unreadable leftover dirs | Reproduced. |
| "git worktree creation denied" | `git worktree add --detach` and `remove` succeeded | **Not reproduced**; treat the recorded denial as an earlier-session artifact and stop citing it. |
| "guest VM/VMware access" | `D:\VMs`, `D:\BinRepair`, `vmrun` all absent on this host | Reproduced as absence; the guest's existence/history is recorded in handoffs but is **[unverified from this host]**. |
| "no single runnable entry point" | `main` has a GUI launcher and two provider scripts; no end-to-end repair path | True for "end-to-end product"; the GUI launcher does exist, so the statement needs that qualification. |

---

## Appendix E - Teammate Documents Used

- `docs/analysis/RUNTIME-VERIFICATION.md` (runtime-verifier, measured 2026-10-29):
  boot/test/demo evidence, environment facts, defects list, test counts, `not_run` ledger.
  This analysis independently reproduced its 146/2/41/5 test numbers and its environment
  findings (C16-C18, C20-C29), and relies on it for the 187-pass measurement run (C19) and
  for the GUI-adapter/evidence-endpoint defects.
- `AGENTS.md` / `README.md` (working tree, integrator, 2026-10-29): measured status and
  acceptance-suite count used as the "in-session corrective action" evidence in Section 5.
- `_scratch/m2-merge/` (m2-integrator): isolated M2 merge work; its `docs/analysis/M2-MERGE-REPORT.md`
  was not present at the analysis time, so the M2 status is recorded as in progress.
- Gate 3 evidence and handoff documents are cited by their pinned git blobs above; the
  delivered bundle/record hashes were independently re-verified as bytes (C26).
