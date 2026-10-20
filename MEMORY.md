# Memory

Update this after major decisions, completed phases, or bugs that future agents need to know about. Keep it short. This shared project handoff is separate from a coding tool's private automatic memory.

## Current State

- Current task: member-4 verification slice — acceptance rules and 29 unit tests implemented on the member-4 branch. The AI-boundary skeleton was removed on 2026-10-20 because member 5's implementation and `main` tests supersede it. The identity/state suite is still a skeleton.
- Current phase: Foundation / environment and fixture feasibility.
- Next step: wait for the owner to finish reorganizing `main`, then rebase the acceptance engine (`app/domain/outcomes.py`, `app/domain/acceptance.py`, `tests/unit/test_acceptance.py`) onto the confirmed layout (or run it directly on `member-5-deepseek-schema` @ `ea29e56` for a combined acceptance + candidate/provider run). Do not merge into `main` while it is being deleted and reshaped. Member 1 still has to land `app.services.jobs` before the identity/state suite activates.
- Handoff [2026-10-18]: both interface confirmations are complete and recorded in `verification-design.md` (§4.1 member 1, §4.3 member 5). Member 5's implementation is on `member-5-deepseek-schema` @ `ea29e56`; it was merged to `main` once, but `main` is currently being reorganized/deleted by the owner, so that merge is not a stable reference.
- Handoff [2026-10-18]: member 3 fixture/VM handoff created at `docs_BinaryRepair/handoffs/03-member-3-fixture-vm.md` — §5 fixture profile, frozen test-manifest format with valid/invalid/oracle coverage, disposable VM requirements and version/image-hash recording, and the six-proof fixture selection gate with named owners. Awaiting reply; a recorded blocker is an acceptable delivery for this week.
- Remote [2026-10-20]: `main` was `024f887` (agent/ subtree archive + GUI + member 5's candidates/provider and 19 tests) but the owner has since been deleting and reshaping it; member 5 reports it was reduced to `agent/`, `run.bat`, and `start.ps1`. Treat the `main` layout as unconfirmed. Remote fetch/push from this sandbox currently fails with a TLS CA-bundle path error (`.../Git/ucrt64/etc/ssl/certs/ca-bundle.crt`), so the remote state cannot be verified from here without an approved escalation or an outside terminal. `origin/member-4-verification` is behind the local branch by 9 commits.
- Blocked by: none for the acceptance rules (implemented and passing). The identity/state suite still skips until `app.services.jobs` exists. Binary execution is blocked until the Ubuntu host, disposable guest, and isolation self-check exist.

## Decisions

- [2026-10-15] Both routes are mandatory for MVP acceptance: instruction repair (Route A) and recovered-C repair with compilation/reintegration (Route B). One accepted route does not satisfy the requirement, and the deterministic template baseline is an evaluation mode, not a substitute.
- [2026-10-15] Both routes repair the **same** public stack-buffer-overflow defect in the **same** original ELF. Input identity is bound by SHA-256, and each route writes a separate candidate copy; the original is never overwritten.
- [2026-10-15] Deterministic checks control acceptance; AI proposes candidates only. Confirmed Part 2 answers override earlier research recommendations for CLI-only operation and strictly in-place patches.
- [2026-10-15] Stack direction: Python, FastAPI, Jinja2 server-rendered HTML, local CSS with minimal JS polling, SQLite plus local immutable artifacts, separate workers inside a disposable Ubuntu x86-64 VM. Product AI via DeepSeek behind a replaceable adapter.
- [2026-10-15] Working method: mixed AI-assisted implementation; the team reads, reviews, and tests critical code rather than delegating it blindly. Human cross-review is required for contracts, edit placement, C normalization, verifier instrumentation, acceptance rules, and sandbox changes.
- [2026-10-15] Part 4 used **Codex** as the coding assistant with `AGENTS.md` as the shared instruction file. No separate client adapter was generated. The DeepSeek coding agent/gateway configuration is still TBD (open question 3 in the Tech Design).
- [2026-10-15] Product requirements live at `docs_BinaryRepair/PRD-BinaryRepair-MVP.md` and the design at `docs_BinaryRepair/TechDesign-BinaryRepair-MVP.md`; setup files link to those paths rather than the `docs/` paths proposed in the documents' own metadata. The folder was renamed from `ReadingList/` during setup; all references were updated in the same change.

- [2026-10-18] All repository artifacts are written in English: code, comments, docstrings, Markdown, commit messages, branch names, and test names. Conversation with the user stays in the user's language. Recorded in `AGENTS.md` so later agents do not switch languages.
- [2026-10-18] Branch naming on `origin` follows `member-<N>-<scope>` (`member-3-route-a`, `member-5-deepseek-schema`, `member2-gui`); the member-4 branch is `member-4-verification`. Commit messages start with the same tag, for example `[member-4-verification] feat: ...`. Milestone snapshots may be tagged `<memberN>-<scope>-<version>`. `main` is owned by member 1; other members open pull requests against it.
- [2026-10-18] §4.3 interface confirmed by member 5: `validate_candidate(payload, allowed_targets=None)`; Route A is 12 top-level fields and Route B adds `recovered_function_sha256` and `replacement_c` (14 total); the default target allowlist includes `copy_input` and `copy_name`; limits are 512 characters per free-text string, 32 entries per list, and 20,000 characters for `replacement_c`, with pydantic `extra="forbid"`; `may_leave_host` denies non-public content by default; hash-ownership and evidence-signing checks live in `validate_candidate_for_context` (signature still to be confirmed); provider failure is `app.services.provider.ProviderFailure(reason: FailureReason)` with `TIMEOUT`, `QUOTA`, `BUDGET`, `EMPTY`, `MALFORMED_JSON`, `SCHEMA`.
- [2026-10-18] §4.1 interface confirmed by member 1: accepted as-is. `Obligation`'s four fields are enough (gate id / evidence id / timestamps stay in the DB row or `detail`); the job controller calls the keyword-only function directly (a thin adapter may only map a record to arguments); the contract row holds `reviewed_scope_sha256` as the freeze-time source but **the run row is authoritative and the decision reads only it**; kind names follow V0–V5 (`identity`, `structure`, `interface`, `behaviour`, `symbolic`, `reproducibility`). The hash is opaque to the engine: presence is checked, correctness is owned by the contract/approval layer, and a wrong non-empty hash would not be detected.

- [2026-10-20] Duplicate AI-boundary test suite is deleted on purpose and will not be restored from git history. Single source of truth: `tests/test_ai_boundary_contract.py` (22 tests on `member-5-deepseek-schema` @ `ea29e56`) plus the generated JSON schema (`schemas/generated/candidate.v1.json`, checked by `python schemas/generate.py --check`). The four boundary assertions unique to the member-4 suite were migrated there (512/513 free text, 33-entry list, 20,001-char `replacement_c`, `allowed_targets` override). §4.3 is unchanged: `validate_candidate(payload, ...)` stays single-argument callable and `may_leave_host(classification, derived=False, *, authorized=False)` keeps working.

## AI / Tooling Decisions

- [2026-10-15] Product inference: DeepSeek via a provider interface; evaluate the documented `deepseek-flash` option first, then pin the exact model/version after a public-case smoke test. JSON output mode with strict local Pydantic validation; local checks are never removed in favour of a provider schema feature.
- [2026-10-15] Coding assistant: Codex connected to DeepSeek. Exact gateway, account, and settings remain unverified; keep the team's existing choice rather than substituting another tool for convenience.
- [2026-10-15] Retention/training terms, region, and any gateway forwarding are **unverified**. Do not describe the public privacy policy as an API-specific zero-retention guarantee. Verify before confidential material is involved.
- [2026-10-15] Proposed cost defaults (USD 2/job, USD 20 initial experiment allowance) are configurable engineering defaults, not committed purchases. Unknown usage is recorded as unavailable, never as zero.

## Known Issues

- No code, lockfile, or verified environment. Every command in `agent_docs/tech_stack.md` is unverified and must be tested and pinned before it is trusted or quoted.
- Execution commands must stay disabled until the isolation self-check passes; `BINARYREPAIR_EXECUTION_ENABLED` defaults to off.
- The development machine's host OS/architecture and virtualization support have not been recorded yet, and "Ubuntu" alone does not confirm an x86-64 CPU. Record the actual host facts before planning the guest.
- Public fixture, valid/invalid domain, destination capacity, contract, test manifest, and oracle are all unresolved (Tech Design open question 5). Route feasibility is not yet demonstrated.
- Host-environment notes for the current working copy (host scaffolding, not project deliverables):
  - The workspace folder was missing a write-owner permission for the signed-in user, which blocked every shell command in this session. A permission repair was applied to `D:\BinaryRepair_Project`, with a backup and an undo script under `var/acl-recovery/`. Keep that folder out of source control and delete it once the fix is confirmed stable.
  - Shell deletion of files created by the agent's file tools inside this workspace is denied by sandbox confinement (`Remove-Item` and `cmd /c del` both return access denied, reproducibly). The leftover `.write-probe.tmp` is now at the project root and could not be removed; it contains a one-line note saying it is safe to delete. Remove it from Explorer, or from an unconfined shell, when convenient.
  - The documents folder is `docs_BinaryRepair/` (renamed from `ReadingList/` during setup). All setup files were updated to the new path; `research-request-BinaryRepair.md` also moved with it and is not referenced by the instruction files.
- [2026-10-20] **Do not merge the `agent/` archive layout from the confined sandbox.** `main` now carries each member branch as a `git subtree` archive under `agent/<branch>/`. Merging that into a working branch makes git misdetect the root files (`AGENTS.md`, `app/domain/*`, `tests/*`, `docs_BinaryRepair/*`) as renames into `agent/member-1-interface-reply/`, and the sandbox then refuses to unlink several `docs_BinaryRepair` files, leaving the merge half-applied. Recovery that worked: `git read-tree --reset HEAD`, then delete `.git/MERGE_HEAD`/`MERGE_MSG`, then verify with `git status`. Integrate or merge on a normal terminal, or let member 1 merge the PR on GitHub.
- [2026-10-18] GitHub push completed for `member-4-verification` (commit `e000424`) plus tag `member4-verification-0.1.0`; the branch now tracks `origin/member-4-verification`. The push used a one-shot approved sandbox escalation, because a bare `git push` inside the DSH sandbox fails when the shell-based credential helper cannot create named pipes (`sh.exe: couldn't create signal pipe, Win32 error 5`). Future pushes from an agent need the same approval or an outside terminal. The earlier 403 was the missing collaborator permission (now resolved).

- [2026-10-18] Member 5's branch was initially pushed with the candidate/provider code under `route-b/`, which the root integration skeleton could not import. Commit `e175436` on `member-5-deepseek-schema` moved it to the shared root (`app/domain/candidates.py`, `app/services/provider.py`, `binaryrepair_ai/`, `schemas/`); the AI-boundary contract suite then passed 17/17 in an isolated worktree of that branch. Historical note; the current state is the 2026-10-20 entries above (`ea29e56`, 22 contract tests), and `main` is not a stable merge target yet.

- [2026-10-20] `main` is not stable: the owner has been deleting and reshaping it (member 5 reports only `agent/`, `run.bat`, `start.ps1` remained). Do not merge the acceptance engine or any other slice into `main` until the owner confirms the layout. Separately, `git fetch` / `git ls-remote` from the DSH sandbox now fail with `error adding trust anchors from file: .../Git/ucrt64/etc/ssl/certs/ca-bundle.crt` (schannel path fails with `SEC_E_NO_CREDENTIALS`), so remote operations need an approved escalation or an outside terminal.

## Completed

- [x] Source PRD and Tech Design read end to end; approved facts extracted.
- [x] Project instruction files created for this stage (AGENTS.md, MEMORY.md, REVIEW-CHECKLIST.md, agent_docs/).
- [x] Acceptance rules implemented in `app/domain/outcomes.py` and `app/domain/acceptance.py`; 29 negative-first unit tests passing.
- [x] Shared synthetic-ELF test fixtures in `tests/conftest.py` (no binary is executed).
- [x] Interface contracts and coverage matrix documented in `docs_BinaryRepair/verification-design.md`.
- [x] Contract suites for identity/state and AI-boundary; the identity/state suite still skips until `app.services.jobs` exists.
- [x] §4.1 and §4.3 interface contracts confirmed by the owning members (2026-10-18).
- [x] AI-boundary contract suite owned by member 5 (`tests/test_ai_boundary_contract.py`, 22 tests on `ea29e56`; full branch suite reported 107 passed). The member-4 duplicate was removed and its four unique boundary assertions were migrated.
- [ ] Public fixture selected, built, and provenance recorded — blocked on the fixture selection gate.
- [ ] GUI vertical slice: create job, hash + screen input, persist, display honestly.
- [ ] Reviewed security contract with a frozen revision and approval binding.
- [ ] Route A candidate produced and validated on the final ELF.
- [ ] Route B unchanged round trip passes, then the security edit.
- [ ] Shared acceptance engine enforces V0–V5 and the six outcome labels.
- [ ] Export bundle with HTML + JSON reports and matching hashes.
- [ ] Independent teammate replay of both route results.
