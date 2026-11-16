# Handoff task package (2026-11-16)

Four self-contained member handoff packages (Chinese text, kept outside the
ASCII-only `docs/` tree so the repository language gate stays green):

| Member | Task | File |
|---|---|---|
| M1 | Non-loop / CWE-121 / CWE-134 capability work (top priority) | `delivery/zh/handoff/M1-task.md` |
| M2 | Cross-function semantic minimal prototype (Phase-9 start, read-only analysis) | `delivery/zh/handoff/M2-task.md` |
| M3 | Productization and end-to-end delivery (SaaS product view) | `delivery/zh/handoff/M3-task.md` |
| M4 | Security / backup / release governance / consistency review | `delivery/zh/handoff/M4-task.md` |

Workspace copies are kept at the workspace root with the requested Chinese names
(`M1任务.md`, `M2任务.md`, `M3任务.md`, `M4任务.md`).

Shared prerequisites (done by the Lead):

- Lead-review corrections applied to the master report (section 1.5): API-key rotation P0, non-loop 3/6 correction, strategy re-prioritization (capability/product before Phase-8D/13/14), backup/default-branch actions.
- Tool area: `tools/handoff/` (check-env / run-scope-tests / member-report / scan-secrets / offsite-backup).
- Self-cognition library: `review/STATE.md`.
- Team task board: shared tasks with disjoint write scopes; members do not run git writes; the Lead integrates.

Repository: `binary-repair-gui/` (branch `final/consolidated-2026-11-16`)
