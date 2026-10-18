# Memory

Update this after major decisions, completed phases, or bugs that future agents need to know about. Keep it short. This shared project handoff is separate from a coding tool's private automatic memory.

## Current State

- Current task: member-4 verification slice — acceptance rules and tests implemented; integration/AI-boundary suites are contract skeletons.
- Current phase: Foundation / environment and fixture feasibility.
- Next step: member 1 lands `app.services.jobs` and member 5 lands `app.domain.candidates`; the two skeleton suites then activate. Until then the verification slice is complete on its own scope.
- Handoff [2026-10-18]: two send-ready interface-confirmation files are in `docs_BinaryRepair/handoffs/` — member 1 (§4.1 Obligation/Verdict + `reviewed_scope_sha256` ownership), member 5 (§4.3 candidate schema / data boundary / provider failure type). Awaiting replies; confirmation unblocks writing the modules, but the skeletons only activate when those modules exist (skip is not passing).
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
- [2026-10-18] Branch convention is `<memberN>/<scope>`: `member1/controller`, `member2/gui`, `member3/sample`, `member4/verification`, `member5/ai-route-b`. Commit messages start with the same tag, for example `[member4/verification] feat: ...`. Milestone snapshots may be tagged `<memberN>-<scope>-<version>`. `main` is owned by member 1; other members open pull requests against it.

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
- [2026-10-18] GitHub push: the collaborator permission issue was resolved by the repository owner, but `git push` still fails **inside the DSH sandbox** with `sh.exe: couldn't create signal pipe, Win32 error 5` and `failed to execute prompt script (exit code 66)`. The sandbox forbids named pipes, so the shell-based credential helper cannot run. This is an environment boundary, not a repository or permission problem. Push from a normal terminal outside the sandbox: `git push -u origin member4/verification` and `git push origin member4-verification-0.1.0`. Earlier symptom, before the permission fix, was `remote: Permission to chenfanaichifan/binary-repair.git denied to leesirleesirlee-star` / `403`. The local branch tracks `origin/main`, so use the explicit `git push -u origin member4/verification` form, not a bare `git push`.

## Completed

- [x] Source PRD and Tech Design read end to end; approved facts extracted.
- [x] Project instruction files created for this stage (AGENTS.md, MEMORY.md, REVIEW-CHECKLIST.md, agent_docs/).
- [x] Acceptance rules implemented in `app/domain/outcomes.py` and `app/domain/acceptance.py`; 29 negative-first unit tests passing.
- [x] Shared synthetic-ELF test fixtures in `tests/conftest.py` (no binary is executed).
- [x] Interface contracts and coverage matrix documented in `docs_BinaryRepair/verification-design.md`.
- [x] Contract skeletons for identity/state and AI-boundary suites; they skip until the owning modules exist.
- [ ] Public fixture selected, built, and provenance recorded — blocked on the fixture selection gate.
- [ ] GUI vertical slice: create job, hash + screen input, persist, display honestly.
- [ ] Reviewed security contract with a frozen revision and approval binding.
- [ ] Route A candidate produced and validated on the final ELF.
- [ ] Route B unchanged round trip passes, then the security edit.
- [ ] Shared acceptance engine enforces V0–V5 and the six outcome labels.
- [ ] Export bundle with HTML + JSON reports and matching hashes.
- [ ] Independent teammate replay of both route results.
