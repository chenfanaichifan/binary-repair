# Documentation map

Working records, design documents, and evidence for the BinaryRepair MVP live in
this folder. Product requirements live in `docs_BinaryRepair/`; coding-agent
instructions live in `AGENTS.md` and `agent_docs/`.

## Layout

| Folder | Contents |
|---|---|
| `handoffs/` | Numbered handoff records 34-87 and the task board `BOARD.md`. Records 01-33 live in `docs_BinaryRepair/handoffs/` (that set is kept byte-identical to the member-4 branch). |
| `analysis/` | Root-cause analysis, runtime verification, controller fixes, M2 merge report, independent verification, and member-2 notes. |
| `guides/` | Controller integration and P0 checklist, GUI integration plan, worker runbook. |
| `interfaces/` | Frozen execution bridge v1 (`execution-bridge-v1.md`) and the Route A worker contract. |
| `proposal/` | GUI proposal section. |
| `prototype/` | Static agent-console prototype (mock data, no backend) referenced by handoff 86. |
| `route-a/` | Gate 3 record. |
| `route-b/` | Route B design, DB v2 decisions, and gate 4/6 evidence notes. |
| `screenshots/` | GUI screenshots captured in mock mode with labelled synthetic data. |

The loose documents that used to sit directly under `docs/` moved into `guides/`
and `analysis/` on 2026-11-04; the only file left at the `docs/` root is this
index.

## Handoff numbering

- 01-33 are in `docs_BinaryRepair/handoffs/`, with an index in its `README.md`.
- 34-87 are in `handoffs/` here.
- Two parallel streams produced two records for numbers 69, 70, 71, 72, 73, 76,
  and 80; both are kept. The M4 row for `1da22ff` is filed as 84 so it does not
  collide with the Gate 5 Route B approval that keeps number 80.

## Start here

- Current task board: `handoffs/BOARD.md`
- Live execution framework: `handoffs/85-lead-gui-vm-integration-framework-2026-11-03.md`
- Agent console redesign: `handoffs/86-lead-agent-gui-redesign-2026-11-03.md`
- Per-person assignment: `handoffs/87-lead-task-assignment-2026-11-03.md`
- Guest execution protocol: `interfaces/execution-bridge-v1.md`
