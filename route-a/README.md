# Route A — Binary analysis

Branch: `member-3-route-a`
Owner: **He-Xinwei** — Member 3 (binary / sample)
Lab item: **3 — Binary analysis and Route A**
Status: **skeleton only — work not started** (2026-10-15)

> This branch records the Route A feasibility work (binary inspection, sample
> analysis, instruction-repair investigation). It does not contain any repair
> result yet. Empty tables and unchecked boxes are intentional.

## My division of work

Allocation from `TechDesign-BinaryRepair-MVP.md` §14 (five hours, explanation
and review time included). Member 3 owns the binary and the sample.

| Allocation | Hours | Output |
|---|---|---|
| Common foundations (walk the shared pipeline once) | 1 h | short pipeline notes |
| Public-fixture and VM feasibility | 2 h | a working isolated VM plus a candidate sample, **or** a recorded blocker |
| ELF inspection | 1 h | architecture and instruction notes for the sample |
| Review with the team | 1 h | corrections folded back into this branch |

**Reviewable result:** provenance and real input metadata for the shared sample,
or an explicit setup blocker. The sample identity, build provenance, and hashes
are the hand-off to the verification slice (Member 4); validation evidence is
worthless if the sample is not pinned.

Lab assignment from the team plan:

- *Objectives* — set up the isolated Ubuntu execution environment first; check
  the basic binary-inspection tools; learn how to identify architecture and
  inspect instructions.
- *Deliverable* — select the shared public sample, analyse its vulnerable
  function, and investigate instruction repair.

Mapping of that work onto this branch:

| Work item | Where it is recorded |
|---|---|
| Isolated execution environment | `docs/01-isolated-ubuntu-env.md` |
| Binary-inspection tool check | `docs/02-tool-inventory.md` |
| Architecture identification | `docs/03-architecture.md` |
| Instruction inspection | `docs/04-instruction-inspection.md` |
| Shared sample + vulnerable function | `docs/05-sample-analysis.md` |
| Instruction-repair investigation | `docs/06-instruction-repair.md` |

Not in my slice — do not fill these in here: GUI screens (Member 2), acceptance
and verification rules (Member 4), Route B / AI adapter (Member 5), job
controller and proposal (Member 1).

If setup consumes the hours, record the blocker with the command and the error
that produced it, hand back whatever exists, and leave execution unavailable. Do
not run the sample on the host to make the picture look complete.

## What this lab has to deliver

| # | Work item | Deliverable | Status |
|---|-----------|-------------|--------|
| 1 | Isolated Ubuntu execution environment | reproducible setup notes + evidence | ☐ not started |
| 2 | Basic binary-inspection tools checked | tool inventory with versions | ☐ not started |
| 3 | Architecture identified | `file` / `readelf` findings for the sample | ☐ not started |
| 4 | Instructions inspected | annotated disassembly of the vulnerable function | ☐ not started |
| 5 | Shared public sample selected | sample ID, SHA-256, build provenance | ☐ not started |
| 6 | Vulnerable function analysed | root cause + valid/invalid input contract | ☐ not started |
| 7 | Instruction repair investigated | candidate strategies + feasibility notes | ☐ not started |

## Layout

```
route-a/
├── README.md                     this file
├── docs/
│   ├── 01-isolated-ubuntu-env.md      work item 1
│   ├── 02-tool-inventory.md           work item 2
│   ├── 03-architecture.md             work item 3
│   ├── 04-instruction-inspection.md   work item 4
│   ├── 05-sample-analysis.md          work items 5–6
│   └── 06-instruction-repair.md       work item 7
├── scripts/
│   ├── check-tools.sh            lists installed inspection tools + versions
│   └── inspect-binary.sh         stub: one-shot ELF inspection report
└── reports/                      command output, hashes, screenshots
```

## Ground rules

Taken from `PRD-BinaryRepair-MVP.md` and `TechDesign-BinaryRepair-MVP.md`:

- Target profile: ELF64, x86-64, little-endian, ideally non-PIE, symbols kept
  for localisation; defect class is a public CWE-121 stack buffer overflow.
- Never run the sample on the host. All execution happens inside the isolated
  Ubuntu environment.
- The original binary is never modified. Work on copies, and record hashes of
  every artifact.
- No fabricated evidence: every claim in these docs must point to a command and
  to its captured output under `reports/`. A missing result is written as
  "not run", not as a plausible number.
- This is a learning and feasibility record, not a repair result and not a
  correctness proof.

## Filling this in

1. Do the work items in order; each `docs/` page ends with a record checklist.
2. Save every command's output in `reports/` using the naming convention in
   `reports/README.md`.
3. Update the status column in the table above as items complete.
4. Keep the honest label on the sample: use the shared public sample once the
   team freezes it; anything else is a labelled rehearsal.
