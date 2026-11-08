# Member 2 notes — Graphical interface (GUI)

> **Sources**: project document set 2026-10-15 — `research-BinaryRepair.pdf`,
> `PRD-BinaryRepair-MVP.pdf` (v1.0), `TechDesign-BinaryRepair-MVP.pdf` (v1.0).
> This is a working index for the GUI slice, not a replacement for those documents.
> Version: 2026-10-18 · Maintainer: Member 2.

## 0. 30-second version

You own **Member 2 — Graphical interface**: three views — setup/review, progress/comparison,
evidence/export — built with FastAPI + Jinja2 server rendering and 2-second polling.
The weekly deliverable is a working local browser flow with truthful stage labels; real
repair success is not required this week. Five person-hours: 1 h foundations, 3 h for the
three screens, 1 h review. Proposal due around 22 October.

**The track is independent**: no need to wait for the VM (Member 3), DeepSeek (Member 5),
or a real sample. Work can start from the agreed API contract and fixture JSON. Accepted
semantics, however, come from Member 4's acceptance rules and the PRD; the GUI must not
invent its own.

## 1. Role, time and deliverables

- Role row: `2 — Graphical interface`; result: **working local browser flow with truthful
  stage labels** (Technical Design §14).
- Team capacity: five hours per member per week, 25 person-hours total including learning,
  review, integration and demo preparation (Technical Design §1).
- Weekly team target: a vertical slice — create a job, hash/screen the ELF, record a
  reviewed contract, show actual analysis or candidate-generation results, display both
  route states, export an honest partial report (Technical Design §14).
- Route A application and the Route B unchanged round trip are stretch goals this week and
  are not assumed complete (Technical Design §14).
- Progress demo definition: a working local GUI with a partially completed repair pipeline;
  unfinished stages stay visible; exact date TBD (Technical Design §1).
- If isolation or sample setup consumes the available time: keep the GUI and acceptance
  engine working with clearly labeled synthetic data, present the real blocker, leave
  execution unavailable; do not run binaries on the host; historical evidence may be shown
  only as a labeled replay with input hash and date (Technical Design §14).

**Responsibility boundary**: everything the operator sees in the browser must be real,
traceable, and semantically correct. Making a patch actually succeed is not on this track.

### 1.1 Team split (team decision, 2026-10-18)

| Member | Responsibility | Independence | Impact on Member 2 |
|---|---|---|---|
| Member 1 | Controller / contract | Independent; integration tests dropped to focus on the proposal | API contract remains the upstream dependency; integration-test ownership must be confirmed |
| **Member 2 (you)** | **Three screens** | Independent | Depends only on the contract interface and data shapes |
| Member 3 | Sample + VM | Blocked by VM; provenance can be drafted on paper first | Build against agreed fixture JSON; provenance fields come later |
| Member 4 | Acceptance rules + three test suites | Independent; feeds everyone | Status labels and outcome display must follow these rules |
| Member 5 | DeepSeek adapter + schema | Partly independent | Candidate status and AI-usage fields; schema changes must be announced early |

### 1.2 Collaboration contract: inputs and outputs

| Direction | With | Content | When |
|---|---|---|---|
| Receive | Member 1 | API paths and fields, state enums, error codes (409/422/413), idempotency, contract revision/hash semantics | 30-minute alignment before starting |
| Receive | Member 4 | Six outcome decision rules, obligations structure, `not_run` semantics, test-suite split and negative cases | Before the status/evidence screens |
| Receive | Member 3 | Fixture JSON, provenance fields, wrong-architecture error samples | While building the setup screen |
| Receive | Member 5 | Attempt status fields and whether model-call usage is available | While building the comparison screen |
| Provide | Member 4 | Stable DOM identifiers (`data-testid`), screen-state screenshots, GUI journey e2e cases | When he writes GUI/acceptance tests |
| Provide | Member 1 | Real API needs and missing-field reports | During integration |
| Provide | Team | Three-screen screenshots, seven-minute demo script, proposal GUI material | Before proposal/demo |

## 2. What each screen must contain

| Screen | Must display / support | Source |
|---|---|---|
| **Setup / Review** | Upload Linux x86-64 ELF, defect description, reproducer, valid-input tests, environment; show `original_sha256`; reject wrong architecture, malformed files and missing inputs before execution; show binary summary and recovered function/location; editable security contract (valid domain, forbidden behavior, invalid-input outcome, assumptions); reviewer confirmation; both routes reference the same original hash and reviewed contract; original source is not an input | PRD F1; Technical Design §7 |
| **Progress / Comparison** | One job with both routes side by side (including partial or unsuccessful outcomes); independent phase indicators; text + icon + color statuses; changed/added regions, test counts, verification and compatibility results, elapsed time, manual interventions, AI usage (or `unavailable`); cancel; refresh-safe; responsive during long analysis; unfinished stages visible | PRD F5, UI/UX direction; Technical Design §7 |
| **Evidence / Export** | Obligations and scope per attempt (bounds and assumptions beside the result); counterexamples and failure reasons; matching input/candidate hashes; HTML + JSON reports; artifact downloads (attachment, safe filenames); failed/inconclusive artifacts labeled **diagnostic candidate**; replay instructions; export is not production approval | PRD F4/F5; Technical Design §7, §13 |

## 3. State model

### 3.1 Two independent axes

**phase**: `draft` → `screening` → `awaiting_review` → `queued` → `analyzing` →
`generating` → `applying` → `validating` → `finished` (Route B adds `roundtrip`).

**outcome** (six values):

| Value | Meaning | Display requirement |
|---|---|---|
| `success_within_scope` | All required checks passed within the stated scope | Show bounds and assumptions |
| `unsupported` | Capability/placement/interface outside supported conditions | Explain the limitation; never display as success |
| `rejected` | Candidate failed a required check | Show the reason; retain diagnostic evidence |
| `inconclusive` | Evidence cannot establish a required property | Show the unresolved obligation; never accept |
| `error` | Tool/service failure | Show stage and reason; keep completed evidence |
| `cancelled` | Operator cancelled | Stop work; label retained evidence honestly |

### 3.2 Three rules

1. `not_run` is not `passed`; never render missing checks as passed.
2. Display phase and outcome separately.
3. No fabricated progress percentages; use phases, events, and counts.

### 3.3 Approval binding and invalidation

Approval binds the original hash, contract revision, test-manifest hash, patch policy,
environment profile, and verification scope. Editing any bound input invalidates approval
and requires a new run; earlier runs are preserved. The GUI shows the new revision/hash and
must surface `409 stale approval` as "contract changed, review again" instead of retrying.

## 4. API consumed by the GUI

Source: Technical Design §7 planned API surface.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/jobs` | Multipart upload plus typed test manifest and defect details; returns job ID and original hash |
| GET | `/api/jobs/{id}` | Summary, current contract, phases, capabilities, outcomes |
| POST | `/api/jobs/{id}/start` | Start (controller-specific in the real implementation) |
| POST | `/api/jobs/{id}/cancel` | Idempotent cancellation |
| GET | `/api/jobs/{id}/obligations` | Per-route obligations, scope, reasons |
| GET | `/api/jobs/{id}/artifacts` | Registered artifacts and hashes |

Error codes: `422` invalid structured input, `413` size limit, `401/403` session or origin
failure, `404` unavailable object, `409` stale approval or invalid transition. Every error
carries a correlation ID; never return shell tracebacks or secret-bearing provider bodies.

**Language policy**: UI Chinese; uploaded/API/export data English ASCII. Non-ASCII form
content returns `422`; uploaded filenames are sanitized; API and export payloads are scanned
for CJK characters (language rule, 2026-10-18).

## 5. Local-service security

- Bind to `127.0.0.1` only.
- Random one-time session token bootstrap; then `HttpOnly; SameSite=Strict` session cookie;
  remove the token from the address bar, do not log it, reject reuse.
- Validate Host and Origin; require a CSRF token for state-changing requests.
- No permissive CORS; local HTTP only; do not claim transport encryption.
- Template escaping and `textContent` for untrusted values; restrictive CSP; `nosniff` and
  frame restrictions.
- Force downloads for binaries/raw artifacts; render evidence HTML only through trusted
  templates.
- Session tokens and API keys must not appear in reports, browser bundles, guest
  environments, or logs.
- Export only registered safe relative paths with an independently generated hash manifest.

## 6. UI/UX requirements

1. Put important limitations next to the relevant result.
2. Use text + icons + color for statuses.
3. Keep technical details expandable while the main result stays readable.
4. Compare both routes without implying that smaller means safer.
5. Preserve completed evidence when a later stage fails.
6. Keep browser navigation responsive during long analysis.
7. Show both routes, including partial or failed outcomes, with independent phase
   indicators and accessible labels.
8. Display AI usage/cost when available; label it `unavailable` otherwise (never `0`).
9. Never claim whole-program correctness, global minimality, or production readiness.

## 7. Dev mode and data truthfulness

- Provide an explicit GUI-only development mode driven by stored/synthetic results; the
  page must label it clearly and must never emit accepted-patch evidence (Technical
  Design §12).
- Execution stays disabled until the isolation self-check passes; the GUI must be able to
  show "execution not enabled".
- Hashes establish identity, not correctness; do not label anything "verified".
- The demo may have no successful candidate, but fixture data must never be presented as a
  real repair, and binaries must not be executed on the host to make a demo look complete.

## 8. Testing and acceptance

GUI scenarios that must be exercised: full setup → review → start → compare → export
without a terminal; responsive during work; cancellation is idempotent and evidence is
retained; refresh does not lose state or duplicate jobs; unfinished stages visible; negative
cases (wrong architecture, missing inputs, stale approval, 409, 422, 413) have readable
messages; local boundary cases (missing session, cross-origin POST, export traversal) are
rejected.

Use Playwright Python for the critical browser journey once the application exists
(Technical Design §13). Render the three screens before merging and inspect status and error
states.

PRD success metrics relevant to this role: one complete GUI journey without terminal use;
correct labels for every defined unsupported/error/inconclusive scenario.

## 9. Five-hour plan

| Slot | Work | Output |
|---|---|---|
| 0–1 h | Align API contract with Member 1; build `app/main.py`, templates, static skeleton; understand the screens and six outcomes | Skeleton runs, job creation, polling |
| 1–2 h | Setup/Review: upload, hash, pre-execution validation, contract editing, approval (with 409 handling) | F1 journey works |
| 2–3 h | Progress/Comparison: dual route cards, phase indicators, status labels, cancel, refresh recovery, unfinished stages | Truthful comparison |
| 3–4 h | Evidence/Export: obligations/scope, bounds, changed regions, downloads, HTML+JSON, diagnostic labels | F5 journey works |
| 4–5 h | Manual regression per §8, screenshots, one-page GUI summary for the proposal | Demo + proposal material |

Priority if time runs short: skeleton → setup → progress → evidence (minimal).

## 10. Dependencies

| Dependency | Owner | Needed |
|---|---|---|
| API contract, job lifecycle, cross-screen fields | Member 1 | Field names, state enums, 409/422 semantics, idempotency |
| Real data interface (`http` mode) | Member 1 (controller) | Six endpoints plus JSON; adapter is already in place (`app/backend.py`); switch with `BINARYREPAIR_BACKEND=http` |
| Upload/hash/architecture screening | Member 3 | Real fixture or screening interface and error codes |
| Evidence data structure | Member 4 | Obligations, scope, counts, changed regions, V0–V5 summary, six-outcome rules |
| Route phases/outcomes and AI usage | Member 5 | Attempt status and usage availability |

The API contract is the critical dependency; align it with Member 1 first.

## 11. Scope guardrails

- No React or frontend/backend split; no SSE/WebSocket (2-second polling is enough).
- No multi-user, login, OAuth, remote access, or enterprise authorization.
- No mobile optimization.
- No fabricated progress percentages, no fixture data presented as real, no binaries
  executed on the host.
- Do not weaken acceptance rules or delete verification gates to make tests green.
- Do not claim whole-program correctness, global minimality, or production readiness.

## 12. GitHub workflow (team decision, 2026-10-18: branches only, no merge into main)

- Cut `member2-*` branches from the latest `main`; commit and push the branch; do not merge
  into `main` on your own (the team integrates when needed).
- Branch names: `member2-backend-adapter`, `member2-e2e`, `member2-proposal`.
- Commit examples: `feat(gui): add status polling and truthful phase labels`,
  `feat(backend): add mock/http data adapter`.
- Self-check before pushing: run the available tests and inspect the three screens.
- Documentation in the repository is English; the GUI display stays Chinese.

## 13. Glossary

| Term | Meaning |
|---|---|
| Contract | Reviewed assumptions and required outcomes: valid domain, forbidden behavior, invalid-input outcome, environment assumptions; versioned and hashed |
| Obligation | One required check with a result (passed/failed/not_run/inconclusive); the core evidence data |
| V0–V5 | Verification ladder: identity/preconditions, structure/placement, interface/compatibility, concrete behavior, bounded symbolic, reproducibility |
| Route A / Route B | A = direct instruction repair; B = recovered C, compiled and reintegrated; both must succeed for full acceptance |
| diagnostic candidate | Failed or inconclusive artifact, downloadable but labeled diagnostic |
| bounded verification | A property checked within a stated domain/model, not a whole-program proof; bounds and assumptions must be shown |
| roundtrip | Route B's unchanged semantic round-trip gate |
| not_run | Not executed / not implemented; never counts as passed |
| idempotency key | Prevents duplicate runs or duplicate charged attempts |

## 14. Sources

| Topic | Document | Location |
|---|---|---|
| Three views, planned API, error codes | Technical Design | §7 |
| phase/outcome, approval binding, idempotency, cancellation | Technical Design | §6 |
| Verification ladder, acceptance rules, symbolic limits | Technical Design | §9 |
| Local-service security, artifact handling | Technical Design | §11 |
| Layout, dev commands, configuration, dev mode | Technical Design | §12 |
| Test scenarios, export bundle, replay | Technical Design | §13 |
| Role allocation, vertical slice, fallback | Technical Design | §14 |
| F1/F5 acceptance, six outcomes, UI/UX direction, success metrics | PRD | MVP Features / UI/UX Direction / Success Metrics |
| Data and confidentiality boundaries | PRD | AI / Automation Scope, Constraints |
| Why no "proved safe" claim; key findings | research | Section 1, Executive feasibility assessment |
