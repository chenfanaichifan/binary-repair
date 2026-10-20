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

## Decision 4: member 5's schema and `SecurityContract` are the single authority

**Decision: `app/db/migrations/001_init.sql` + `app/db/migrate.py` are the only
schema; `app/domain/contracts.py`'s `SecurityContract` is the only contract
model.**

Two competing schema sets were found:

- Member 5 (`member-5-deepseek-schema`): `app/domain/contracts.py`
  (`SecurityContract`), `app/db/migrate.py`, and
  `app/db/migrations/001_init.sql` with 8 tables (`jobs`, `contracts`, `runs`,
  `attempts`, `artifacts`, `obligations`, `events`, `model_calls`).
- Member 1 (`member1/jobs-minimal`): `app/db/schema.sql` with two tables
  (`jobs`, `artifacts`) plus `app/db/connection.py`.

They cannot coexist: job/contract/run fields and constraints would conflict.

**Ownership:**

- Member 5: schema, migrations, `SecurityContract` model.
- Member 1: job-controller behaviour, state transitions, HTTP API,
  idempotency/restart recovery. It consumes the schema and does not define a
  second one.
- Member 4: semantic review of the acceptance fields (`outcome`, `obligation`).

**Retirement:** member 1's `app/db/schema.sql` is retired. Do not add tables to
it; at integration delete it or leave a note that it migrated to member 5's
schema.

**Adaptation points for step ③:**

- `jobs` has no `filename` / `defect_description`: these are display fields, so
  keep them in a sidecar `var/jobs/<id>/meta.json` rather than expanding the
  schema. If the team insists on columns, member 5 issues `002_*.sql`.
- Approval is written to `contracts.body_json` (serialized `SecurityContract`)
  plus `sha256`; manifest/scope hashes go inside the body, not into new columns.
- `runs.idempotency_key` is globally `UNIQUE`: the controller uses a
  `job_id:key` prefix or the schema is adjusted.
- The `attempts` table backs the canonical evidence endpoint; implement it on
  member 5's schema.

The integration order is unchanged: ① member 5 → ② member 4 → ③ member 1
(controller-only, on member 5's schema) → ④ member 2.

---

## Decision 5: API paths follow Tech Design §7; member 2's paths become aliases

**Decision: Tech Design §7 paths are canonical; member 2's adapter paths are
kept as GUI-compatible aliases.**

Canonical (external contract):

- `POST /api/jobs/{id}/runs` — approved revision + idempotency key; `202` + run id
- `GET /api/attempts/{id}/evidence` — obligations / scope / counts / artifacts
- plus the §7 endpoints: `POST /api/jobs`, `GET /api/jobs/{id}`,
  `POST /api/jobs/{id}/approve`, and the rest.

Member 2's adapter paths (`/start`, `/obligations`, `/artifacts`) remain as GUI
aliases that call the same implementation; they must not duplicate decision
logic.

`/runs` requires an existing approval for that revision (looked up in
`contracts`) and returns `409` otherwise. The `/start` alias may auto-approve
from stored contract metadata during development, only for GUI integration, and
must be documented as such.

Migration cadence: step ③ adds the canonical routes and keeps the aliases; at
step ④, after the GUI is connected, the adapter gradually switches to the
canonical names.

---

## Action items

| # | Who | What | Done when |
|---|---|---|---|
| 1 | Member 1 | Prepare `member1/controller-only` on member 5's schema (no `app/db/schema.sql`) | Identity suite is 8 passed / 0 skipped |
| 2 | Member 1 | Add canonical `/runs` and `/attempts/{id}/evidence`; keep `/start` etc. as aliases | Both path sets hit the same logic; no duplicated decision |
| 3 | Member 5 | Confirm the `SecurityContract` serialization/fields satisfy the controller | Approval body can be written to `contracts.body_json` |
| 4 | Member 4 | Re-run identity/integration on `member1/controller-only` | Real pass/skip counts; a skip is not a pass |
| 5 | Member 1 | Fill member 1's evidence in proposal §5; other members fill their rows | Each entry has a path, command, and four-level label |

The earlier `agent/README.md` snapshot-table item is not in this list; treat it
as still open unless member 1 reports otherwise.

---

## Status note (2026-10-20, updated after member 1's delivery message)

- Member 1's full controller is on `member1/jobs-minimal`, not on `main`:
  `6e8ce4b` (minimal) → `f41558a` (approval binding, idempotent start,
  `cancel_job`, restart recovery) → `d7813d0` (controller HTTP API). A full-suite
  run on a temporary worktree at `d7813d0` gives **26 passed, 0 skipped**, which
  matches 8 identity + 7 controller-API + 11 GUI smoke/language tests.
- `main` is `453fe95`: it carries `app/`, `tests/`, and the `agent/` archive, but
  its `app/services/jobs.py` is the **old `6e8ce4b` minimal snapshot**, so a
  `main` checkout still shows the "deliberately not implemented yet" docstring.
  Member 1 described `main` as `29f2a6a` with only README + `agent/`; that is not
  the current `origin/main`.
- Action item 1 (the `controller-only` branch) is therefore the unlock: action
  item 4 (member 4 re-running the suites on it) is still pending. The `d7813d0`
  result above is evidence on the full branch, not on the controller-only slice,
  and does not replace that re-run.
