# Proposal section — Member 2: Graphical interface

Project 11: AI-driven automated binary vulnerability repair and correctness verification.
Team: five first-year students, 25 person-hours per week. Proposal due approximately
2026-10-22.

This section describes the graphical-interface slice: what the demo shows, what is
implemented, what is deliberately not claimed, and how to present it in five minutes.

## 1. Scope of the GUI slice

The operator works in a local browser in three screens:

1. **Setup / Review** — upload a Linux x86-64 ELF, record its SHA-256, enter the defect
   description, reproducer and valid-input tests, review and edit the security contract.
2. **Progress / Comparison** — watch both repair routes (direct instruction repair and
   recovered-C reintegration) side by side, with independent phase indicators.
3. **Evidence / Export** — inspect obligations V0–V5, scope and assumptions, artifact
   hashes, and export a JSON evidence bundle.

The GUI never executes an uploaded or repaired binary on the host. Execution belongs to
the disposable Ubuntu VM owned by the other members.

## 2. What the demo shows

| Screen | PRD requirement | Demonstration value |
|---|---|---|
| Setup / Review | F1 | The operator defines identity (hash), defect, tests, and a reviewed contract before anything runs |
| Progress / Comparison | F5 | Both routes are visible with truthful phases and six outcome labels; a failed route cannot silently become "success" |
| Evidence / Export | F4, F5 | Obligations, scope, assumptions and diagnostic-candidate labelling are shown next to the result; export states it is not production approval |

State model: `phase` and `outcome` are two independent axes. Phases are
draft/screening/analyzing/roundtrip/generating/applying/validating/finished; outcomes are
success_within_scope/unsupported/rejected/inconclusive/error/cancelled. `not_run` is never
rendered as passed. There are no fabricated progress percentages; the page polls every two
seconds.

## 3. Implementation status

| Item | Status |
|---|---|
| Three screens, Chinese UI labels | Done |
| SHA-256 identity, ASCII filename sanitization, 20 MiB upload limit | Done |
| Phase/outcome badges, stage indicators, changed-region table, AI-usage field | Done |
| Evidence page with V0–V5 obligations, scope, replay notes | Done |
| JSON evidence export | Done |
| Data-source adapter with `mock`, `http`, `local` modes | Done |
| Local mode wired to the Member 1 SQLite job store | Done; job identity and original bytes are real, repair execution is not implemented |
| Controller HTTP contract (`/api/jobs`, `/api/jobs/{id}`, start, cancel, obligations, artifacts) | Adapter and stub implemented; waiting for the real controller endpoint |
| Contract revision and `409 stale approval` handling | Not yet |
| Session token, CSRF/Origin checks | Not yet (host validation is in place) |
| Playwright-style browser acceptance | Done, using Edge over the DevTools protocol (no extra dependency) |

## 4. Data-source modes and honesty

The GUI reads through one adapter (`app/backend.py`), so the pages and polling logic do not
change when the data source changes:

- `mock` (default) — synthetic fixture data. A banner states that no real repair was
  executed. Used for the demo and covered by contract tests.
- `http` — calls the controller API described in Technical Design section 7. A local stub
  (`tools/stub_backend.py`) allows integration before the real controller exists.
- `local` — calls the Member 1 controller directly: the job id, original bytes and SHA-256
  are persisted in SQLite. Repair execution is not implemented, so the start action is
  hidden and obligations remain `not_run`. This is the honest "real data, no fake result"
  state.

The language policy is enforced in tests: the UI is Chinese, but every uploaded, API and
exported field is English ASCII. Non-ASCII form content returns `422`.

## 5. Acceptance evidence

Command: `.\.venv\Scripts\python.exe -m pytest -q tests`

- 28 passed, 3 skipped (the skips belong to another member's integration suite).
- Unit/contract: screens, host validation, upload limits, export, HTTP adapter mapping,
  404/network/non-English error handling, stub JSON shape, local-mode persistence and
  honest obligations.
- Language policy: API and export payloads contain no CJK characters while UI pages stay
  Chinese.
- Browser end-to-end (Edge + DevTools protocol, no download): full journey
  setup → start → comparison → evidence → export, refresh during a run, cancellation with
  retained evidence, and local-mode honesty.

## 6. Limitations and risks (stated explicitly)

- The demo data is synthetic; it is not evidence that a patch is verified.
- Local mode has a real job store but no repair execution; start/cancel return `409`.
- Route A/B results are not yet connected to the real verifier; the GUI is ready to consume
  them through the contract.
- Approval binding and `409 stale approval` are designed but not implemented.
- The host sees untrusted bytes only; no hardening beyond host validation and download
  handling is implemented yet.

## 7. Five-minute demo script

| Time | Action | What to say |
|---|---|---|
| 0:00–0:30 | Open `http://127.0.0.1:8123/jobs/new` | "The analyst starts from a local browser; the vulnerable binary never leaves the host for analysis." |
| 0:30–1:30 | Upload the sample, fill defect/tests, review the contract | "Identity is a SHA-256; the contract fixes the valid domain, forbidden behaviour and the required invalid-input outcome." |
| 1:30–2:30 | Submit, start, watch both routes | "Both routes run from the same hash and contract. Phase and outcome are separate axes; unfinished stages stay visible." |
| 2:30–3:30 | Show Route A rejected, Route B inconclusive | "A failed regression must not look like success. The labels are text plus colour, not colour alone." |
| 3:30–4:15 | Open Evidence | "V0–V5, scope and assumptions sit next to the result; failed or inconclusive artifacts are labelled diagnostic candidates." |
| 4:15–4:45 | Export JSON | "The export records hashes and outcomes and states it is not production approval." |
| 4:45–5:00 | Switch to local mode (optional) | "With the real job store the task identity is real, but execution is not implemented, so the start action is hidden instead of faking a run." |

## 8. Next milestones

1. Align the controller HTTP API with the adapter contract and switch to `http` mode.
2. Add contract revision and `409 stale approval`, plus session token and CSRF.
3. Connect Route A/B phases and verifier obligations to the real pipeline.
4. Add a Playwright-compatible e2e run to CI when the environment allows browser installs.

## 9. Screenshots

- `docs/screenshots/01-setup.png` — setup/review screen
- `docs/screenshots/02-comparison.png` — comparison screen after a run
- `docs/screenshots/03-evidence.png` — evidence/export screen
- `docs/screenshots/04-local-mode.png` — local controller mode: real job, execution not
  available (honest state)
