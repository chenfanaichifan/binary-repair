# Integration decision — member 1 (2026-10-20)

| Field | Value |
|---|---|
| Decided by | Member 1 (integration lead / controller) |
| Date | 2026-10-20 |
| Scope | `main`, `agent/`, and the merge order of member branches |
| Status | Decided; the action items below are pending unless marked done |

*Source: translated from member 1's `08_集成决策_成员1.md` (2026-10-20). This
repository copy is the reference for other slices and later agents.*

---

## Decision 1: `agent/` is a read-only archive

**Decision: read-only; no development there.**

- Do not edit code or documents under `agent/`; every change goes through a
  `member-*` branch.
- `agent/` is for history, comparison, and handover only. Do not run tests there
  and do not use it as a runtime entry point.
- `agent/README.md` records each subdirectory's source branch, snapshot commit,
  and date. Adding or replacing an archive needs a separate review.
- Root integration code and the `agent/` archive are two different things:
  integrate from root, read history from `agent/`.

**Rationale:** each subtree comes from a different branch with independent
history, so editing it would create two sources of truth; running tests from a
subdirectory hides root import/path/dependency problems; read-only keeps the
archive traceable and unmodified.

---

## Decision 2: root integration order is ① member 5 → ② member 4 → ③ member 1 → ④ member 2

**Decision: merge in this order, keeping `main` runnable and testable after
every step.**

| Step | Merge | Why it sits here |
|---|---|---|
| ① Member 5 | `app/domain/candidates.py`, `app/services/provider.py`, `binaryrepair_ai/`, `db/`, `schemas/`, base tests | Establishes the package layout, schema, provider, and dependencies; everything after depends on it |
| ② Member 4 | `app/domain/acceptance.py`, `outcomes.py`, verification design, unit/integration tests | Depends only on the domain layer; lands the single decision point and the test baseline |
| ③ Member 1 | **Controller slice only:** `app/services/jobs.py` + `app/db/`, no GUI | Depends on member 5's db/schema; the API is adapted afterwards |
| ④ Member 2 | `app/main.py`, `demo.py`, `i18n.py`, `templates/`, `static/`, GUI tests | Connects the real API/GUI last; `app/main.py` stays exactly as member 2 wrote it and remains the only entry point |

**Execution rules:**

- Run the relevant tests (unit / integration / GUI) after each step. Do not carry
  a conflict into the next step.
- Do not merge the whole `member1/jobs-minimal` branch at step ③: that branch
  restored the GUI so its tests could run. Integrate only `app/services/jobs.py`
  and `app/db/`, or open a separate `member1/controller-only` branch.
- Keep member 2's `app/main.py` unchanged at step ④; controller and acceptance
  are reached only through interfaces and never duplicate the decision logic.
- If any step produces "two success-decision paths" or "a skip reported as a
  pass", roll that step back immediately.

**Why not GUI first:** the GUI can run its demo without a real backend, but it
brings `app/main.py`, templates, and tests in one shot and pushes all later
domain/controller conflicts onto the GUI. Build the foundation with 5 and 4, add
the controller with 1, and connect the UI with 2 last — conflicts stay smallest.

---

## Decision 3: archives are frozen history snapshots; no periodic `git subtree pull`

**Decision: frozen; re-archive only at milestones.**

- `agent/member-4-verification` keeps its current snapshot (source branch
  `3a8aa4c`); no automatic `subtree pull`.
- Re-archive only at milestones (root integration complete, proposal submitted,
  release): replace that prefix with a new `git subtree add`, or add a new
  snapshot directory; record the source branch commit, date, and archiver in
  `agent/README.md`.
- For current code use the source branch, not the archive.
- Do not run tests on the archive; run them on the root integration tree or the
  source branch.

**Rationale:** `subtree pull` keeps producing merge commits and conflicts and
maintains two copies; the archive's value is a traceable history snapshot, not
being always current; freezing keeps `agent/` from becoming a second development
tree, consistent with Decision 1.

`agent/member-4-verification` being stale is expected. Mark it
"snapshot @ 3a8aa4c · 2026-10-18" in `agent/README.md`; there is no need to catch
it up.

---

## Action items

| # | Who | What | Done when |
|---|---|---|---|
| 1 | Member 1 | Split `member1/controller-only` (only `app/services/jobs.py` + `app/db/`) | It can merge alone at step ③ |
| 2 | Member 1 | Add the snapshot table (source branch / commit / date / read-only statement) to `agent/README.md` | Archive status is visible at a glance |
| 3 | Member 4 | Re-run `pytest tests/integration/test_identity_state.py -rs` on `member1/jobs-minimal` | Real pass/skip counts; a skip is not a pass |
| 4 | Member 2 | Keep `app/main.py` as-is until step ④ | The controller leaves the GUI entry point alone |
| 5 | Members 3/5 | Fill the evidence per proposal skeleton §5 | Each entry has a path, command, and four-level label |

---

## Status note (2026-10-20)

- **Action item 3 is done.** `tests/integration/test_identity_state.py` on
  `member1/jobs-minimal` (`6e8ce4b`) gives **5 passed, 3 skipped**; the skips
  name the missing `approve_contract` and `start_run` entry points. `main`'s
  `app/services/jobs.py` is byte-identical to that commit.
- `main` at `453fe95` already contains the GUI and the minimal job controller but
  not member 5's or member 4's `app/domain/` code. That is not yet the order in
  Decision 2; confirm with member 1 before starting the official merge.
