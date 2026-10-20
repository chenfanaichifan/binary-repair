# BinaryRepair

AI-driven binary vulnerability repair and correctness verification (MVP prototype).

The project repairs one known vulnerability in a Linux x86-64 ELF **without source**,
through two independent AI-assisted routes, and decides the result with one shared
deterministic acceptance engine. A candidate is never "fixed because the model says
so": it counts only when every required check passes on the final bytes.

## Status (as of 2026-10-18)

This repository currently contains the **verification slice**: the shared acceptance
rules and their contract tests. Other workstreams are developed on separate branches
and are not merged here yet.

Implemented and verified:

- `app/domain/outcomes.py` and `app/domain/acceptance.py`: the six terminal outcomes,
  the five check results, and the single `decide_attempt_outcome` /
  `decide_run_outcome` decision path. **29 unit tests pass.**
- `tests/integration/test_ai_boundary.py`: candidate-schema, data-boundary, and
  typed-provider-failure contract tests. **17 tests pass against the
  `member-5-deepseek-schema` branch** (checked in an isolated worktree; the tests
  skip here until that branch is merged).

Not verified yet — do not present these as working:

- No public fixture, no disposable VM/guest, and no symbolic tool, so gates V1–V4
  cannot run in this repository yet.
- `tests/integration/test_identity_state.py` is a contract skeleton; it skips until
  `app.services.jobs` lands.
- No repair candidate exists, and no result label is evidence of a real repair.
- No uploaded or repaired binary is executed, and no model-generated C is compiled,
  on the host.

## Repository layout

```text
app/domain/            outcome labels and acceptance rules (pure functions, no I/O)
tests/unit/            acceptance unit tests (negative-first)
tests/integration/     contract suites; they skip until the owning modules exist
docs_BinaryRepair/     verification design and teammate interface handoffs
var/                   local runtime artifacts (gitignored)
```

## Running the tests

From the repository root (no install step; `tests/conftest.py` puts the project root
on `sys.path`):

```bash
python -m pytest tests/unit -q -p no:cacheprovider
python -m pytest tests/integration -q -p no:cacheprovider
```

- `-p no:cacheprovider` avoids a cache-permission problem in the development sandbox.
- The AI-boundary suite additionally needs `pydantic` and `httpx`; it never calls the
  real provider, needs no API key, and spends no money.
- A skip means the test did not run. **A skip is not a pass.**
- The target platform is Python 3.12 on Ubuntu x86-64. The local development copy is
  Python 3.14 on Windows and has not run on the target interpreter.
- There is no packaging or build step yet, and that is intentional.

## Acceptance contract

Exactly six terminal outcomes exist: `success_within_scope`, `unsupported`,
`rejected`, `inconclusive`, `error`, and `cancelled`. Only
`success_within_scope` can satisfy the MVP, and it requires every required
obligation to pass with matching final hashes and a non-empty reviewed scope.

The UI renders outcomes; it never derives them. Any second place that computes a
success label is a defect.

The full design, decision precedence, test coverage matrix, and confirmed
interfaces are in [`docs_BinaryRepair/verification-design.md`](docs_BinaryRepair/verification-design.md).
The interface confirmation records for the other slices are in
[`docs_BinaryRepair/handoffs/`](docs_BinaryRepair/handoffs/).

## Branch and review workflow

- `main` is the integration branch and is owned by member 1.
- Work happens on `member-<N>-<scope>` branches (for example
  `member-5-deepseek-schema`) and is merged into `main` through pull requests.
- Commit messages start with the branch tag, for example
  `[member-4-verification] test: ...`.
- The current verification branch is `member-4-verification`.

## Safety rules

- Never execute an uploaded or repaired binary, or compile model-generated C, on the
  host. Parsing, compilation, execution, and symbolic analysis belong to the
  disposable guest under the broker; when the guest is unavailable, those checks are
  unavailable.
- Missing evidence is `not_run`, never `passed`.
- Never weaken a test, oracle, or verification gate to get a green result.
- Client binaries and confidential derived content stay local. The provider key is
  used only by the trusted provider process and never reaches the guest, browser
  bundle, logs, or reports.

## Product documents

The PRD and technical design are maintained in `docs_BinaryRepair/`. Only the
verification design and the interface handoffs are tracked in this repository so
far; the remaining documents are still local-only.
