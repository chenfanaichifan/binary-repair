# Memory

Update this after major decisions, completed phases, or bugs that future agents need to know about. Keep it short. This shared project handoff is separate from a coding tool's private automatic memory.

## Current State

- Current task: member-4 verification slice — acceptance rules, 29 unit tests, and the AI-boundary contract suite (17 tests) implemented; the identity/state suite is still a skeleton.
- Current phase: Foundation / environment and fixture feasibility.
- Next step: merge member 5's `member-5-deepseek-schema` branch into `main` (it already has the root `app/domain/candidates.py` and `app/services/provider.py`), so the AI-boundary suite runs in the shared tree; member 1 still has to land `app.services.jobs` before the identity/state suite activates.
- Handoff [2026-10-18]: both interface confirmations are complete and recorded in `verification-design.md` (§4.1 member 1, §4.3 member 5). Member 5's branch `member-5-deepseek-schema` (commit `e175436`) moved the code to the shared root; the contract suite passes **17/17** in an isolated worktree of that branch. The member-4 branch still skips until that branch is merged, and a skip is never reported as a pass.
- Blocked by: none for the acceptance rules (implemented and passing). Integration and AI-boundary tests skip by design until their owning modules exist. Binary execution is blocked until the Ubuntu host, disposable guest, and isolation self-check exist.

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
- [2026-10-18] GitHub push: the collaborator permission issue was resolved by the repository owner, but `git push` still fails **inside the DSH sandbox** with `sh.exe: couldn't create signal pipe, Win32 error 5` and `failed to execute prompt script (exit code 66)`. The sandbox forbids named pipes, so the shell-based credential helper cannot run. This is an environment boundary, not a repository or permission problem. Push from a normal terminal outside the sandbox: `git push -u origin member-4-verification` and `git push origin member-4-verification-0.1.0`. Earlier symptom, before the permission fix, was `remote: Permission to chenfanaichifan/binary-repair.git denied to leesirleesirlee-star` / `403`. The local branch tracks `origin/main`, so use the explicit `git push -u origin member-4-verification` form, not a bare `git push`.

- [2026-10-18] Member 5's branch was initially pushed with the candidate/provider code under `route-b/`, which the root integration skeleton could not import. Commit `e175436` on `member-5-deepseek-schema` moved it to the shared root (`app/domain/candidates.py`, `app/services/provider.py`, `binaryrepair_ai/`, `schemas/`); the AI-boundary contract suite then passed 17/17 in an isolated worktree of that branch. The member-4 branch still lacks these files, so its own run keeps skipping until the branch is merged into `main`.

## Completed

- [x] Source PRD and Tech Design read end to end; approved facts extracted.
- [x] Project instruction files created for this stage (AGENTS.md, MEMORY.md, REVIEW-CHECKLIST.md, agent_docs/).
- [x] Acceptance rules implemented in `app/domain/outcomes.py` and `app/domain/acceptance.py`; 29 negative-first unit tests passing.
- [x] Shared synthetic-ELF test fixtures in `tests/conftest.py` (no binary is executed).
- [x] Interface contracts and coverage matrix documented in `docs_BinaryRepair/verification-design.md`.
- [x] Contract suites for identity/state and AI-boundary; the identity/state suite still skips until `app.services.jobs` exists.
- [x] §4.1 and §4.3 interface contracts confirmed by the owning members (2026-10-18).
- [x] AI-boundary contract suite verified against member 5's branch `e175436`: 17 passed, 0 skipped, 0 failed (isolated worktree; not yet merged into `main`).
- [ ] Public fixture selected, built, and provenance recorded — blocked on the fixture selection gate.
- [ ] GUI vertical slice: create job, hash + screen input, persist, display honestly.
- [ ] Reviewed security contract with a frozen revision and approval binding.
- [ ] Route A candidate produced and validated on the final ELF.
- [ ] Route B unchanged round trip passes, then the security edit.
- [ ] Shared acceptance engine enforces V0–V5 and the six outcome labels.
- [ ] Export bundle with HTML + JSON reports and matching hashes.
- [ ] Independent teammate replay of both route results.
