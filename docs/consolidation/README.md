# Consolidation documentation

The project consolidation report and the two focus-session analyses are written in
Chinese (the delivery language for the course/team) and are kept **outside** the
ASCII-only `docs/` tree so that the repository language gate stays green:

- `delivery/zh/consolidation/PROJECT-MASTER-REPORT-2026-11-16.md` - master report: goals, plan, status, remaining tasks, solutions
- `delivery/zh/consolidation/session-1-linux-vm-analysis.md` - Linux VM verification session analysis
- `delivery/zh/consolidation/session-2-all-types-analysis.md` - all-type binary repair session analysis
- `delivery/zh/consolidation/project-history.md` - early project history (2026-10-15 to 2026-11-13)
- `delivery/zh/consolidation/CONSOLIDATION-2026-11-16.md` - consolidation execution record (branch, deleted refs, backup, recovery)

ASCII summaries:

- `CONSOLIDATION.md` (repository root) - one-paragraph consolidation index
- `docs/handoff/README.md` - four-member handoff task package index

Policy note: new product documentation under `docs/` stays ASCII-English; Chinese
delivery documents live under `delivery/zh/` and are not scanned by
`scripts/check_markdown_language.py` (which only scans `docs/**/*.md`).
