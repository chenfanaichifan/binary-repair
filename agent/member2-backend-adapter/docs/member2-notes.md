# Member 2 Notes · Graphical Interface (GUI)

> **Compiled from:** the 2026-10-15 project document set — `research-BinaryRepair.pdf`, `PRD-BinaryRepair-MVP.pdf` (v1.0), `TechDesign-BinaryRepair-MVP.pdf` (v1.0)
> **Scope:** only what the GUI role needs to know. This does not replace the source documents; each item cites its source, and the source documents win on conflict.
> **Version:** 2026-10-18 · Maintainer: Member 2
> **Suggested repository location:** `docs/member2-gui-notes.md`
> **Team division:** 2026-10-18 team decision — Member 1 controller/contract (focused on the proposal after handing off the integration tests), Member 2 three screens (you, independent), Member 3 sample + VM (blocked by the VM; provenance on paper first), Member 4 acceptance rules + three test suites (independent, feeds everyone), Member 5 DeepSeek adapter + schema (partly independent). This document follows that division.

---

## 0. The 30-second version

You are **Member 2 — Graphical interface**. You own three screens: **setup/review (create a job + review the contract) → progress/comparison (dual-route progress and comparison) → evidence/export (evidence and export)**. The stack is **FastAPI + Jinja2 server-side rendering + 2-second polling**, not a separated frontend/backend. Next week's deliverable is a **working local browser flow with truthful status labels**; it does not require a real successful repair this week. Total effort: 5 person-hours (1 h foundations + 3 h three screens + 1 h review); the proposal is due around 10-22.

**Your track is independent**: you do not wait for the VM (Member 3), DeepSeek (Member 5), or a real sample. You can start in parallel as soon as you have the contract API and fixture JSON. But the decision semantics (what counts as passed, how the six outcomes are decided) come from Member 4's acceptance rules and the PRD; do not invent your own.

---

## 1. Your role, time, and deliverables

| Item | Source |
|---|---|
| Role line: `2 — Graphical interface`; `1 h foundations; 3 h setup/comparison/evidence screens; 1 h review`; result: **Working local browser flow with truthful stage labels** | TechDesign §14, next-week 25 person-hour plan |
| 5 hours per person per week, 25 person-hours/week total (including learning, review, integration, demo preparation) | TechDesign §1 |
| This week's team goal is a "vertical slice": create a job → hash/screen the ELF → record the reviewed contract → show real analysis/candidate results → dual-route status → export an honestly labelled partial report | TechDesign §14 |
| **Route A actually applying a patch and Route B's semantics-preserving round trip are stretch goals this week; do not assume they will be done** | TechDesign §14 |
| Next week's demo (progress demo) definition: a runnable local GUI + a **partially complete** repair pipeline, with **unfinished stages visible**; exact date TBD | TechDesign §1 |
| If isolation/sample environment consumes the time: **keep the GUI and acceptance engine usable**, use clearly labelled synthetic development data, show the real blocker, and leave execution unavailable; **do not run binaries on the host**; historical results may only be shown as a replay with input hash/date | TechDesign §14 |
| Proposal deadline: one week from 2026-10-15, around **10-22** (exact time and format TBD) | PRD overview |

**One-sentence responsibility boundary:** you ensure that "everything the user sees in the browser is real, traceable, and has correct status semantics"; you are not responsible for making the patch actually succeed (that is the Member 1/3/4/5 chain).

### 1.1 Team division (2026-10-18 team decision, not source text)

| Member | Owns | Independence | What it means for you |
|---|---|---|---|
| Member 1 | Controller / contract | Independent; **focused on the proposal after handing off the integration tests** | The API contract is still your upstream; the integration tests are no longer covered by him, so confirm ownership face to face |
| **Member 2 (you)** | **Three screens** | Independent | Depends only on the contract interface and data shapes; does not wait for the VM / DeepSeek / real sample |
| Member 3 | Sample + VM | Blocked by the VM; **provenance on paper first** | Build the UI against the agreed fixture JSON first; connect provenance fields when his table is ready |
| Member 4 | Acceptance rules + three test suites | Independent; **feeds everyone** | Your status labels and outcome display must match his acceptance rules; negative cases and test data can be reused directly |
| Member 5 | DeepSeek adapter + schema | Partly independent | You display candidate status and AI usage; he must notify you in advance of schema changes |

**The correct use of "independent":** you can start in parallel, but the decision semantics on the screen must come from Member 4's acceptance rules and the PRD. Do not invent a set of statuses that merely "looks right".

### 1.2 Collaboration contract: what you receive / what you deliver

| Direction | Counterpart | Content | When needed |
|---|---|---|---|
| Receive | Member 1 | API paths and fields, status enums, error codes (409/422/413), idempotency, contract revision/hash semantics | 30 minutes before starting |
| Receive | Member 4 | Six-outcome decision rules, obligations structure, `not_run` semantics, three test-suite split, negative-case data | Before the status / evidence screens |
| Receive | Member 3 | Fixture JSON, provenance fields (input hash/source/build info), wrong-architecture error samples | When building the setup screen |
| Receive | Member 5 | Attempt status fields, whether model-call usage is available (mark unavailable if not) | When building the comparison screen |
| Give | Member 4 | Stable DOM identifiers (prefer `data-testid`), three-screen screenshots, GUI journey e2e cases | When he writes GUI/acceptance tests |
| Give | Member 1 | Real frontend API needs and missing-field problems | During integration |
| Give | Whole team | Three-screen screenshots, 5-minute demo script, GUI chapter material for the proposal | Before the proposal/demo |

---

## 2. What each of the three screens must have

| Screen | Must display / must support | Source |
|---|---|---|
| **① Setup / Review** | Upload a Linux x86-64 ELF, defect description, reproduction input, valid-input tests, environment info; show `original_sha256`; give actionable errors for wrong architecture/corrupt file/missing required fields **before execution**; show binary summary, recovered function/location; **editable security contract** (valid input domain, forbidden behaviour, expected behaviour for invalid input, assumptions); reviewer confirmation; both routes reference the **same** original hash + reviewed contract; original source is not an input | PRD F1; TechDesign §7 |
| **② Progress / Comparison** | Side-by-side cards for the two routes of one job (including partial failure/non-success); independent stage indicator per route; status shown with text + icon + colour; show changed/added regions, test counts, verification results, compatibility results, elapsed time, human intervention, AI usage (mark unavailable if not available); cancel; state survives browser refresh; page stays responsive during long analysis; **unfinished stages visible** | PRD F5, UI/UX Direction; TechDesign §7 |
| **③ Evidence / Export** | Obligations and scope per attempt (including bounds/assumptions, next to the conclusion); counterexample/failure reason; input and candidate hashes match; HTML + JSON report; candidate and evidence downloads (attachment, safe filename); failed/inconclusive artifacts labelled **diagnostic candidate**; replay notes; export is not production approval | PRD F4, F5; TechDesign §7, §13 |

> **The three screens are not arbitrary**: the design document explicitly says "the operator uses three views: setup/review, repair comparison, evidence/export"; templates are server-rendered, and JS only fetches small status updates.

---

## 3. The status model (the easiest place to get it wrong)

### 3.1 phase and outcome must be two separate axes

**phase**, with one extra `roundtrip` for Route B:

`draft` → `screening` → `awaiting_review` → `queued` → `analyzing` → `generating` → `applying` → `validating` → `finished` (source: TechDesign §6)

**outcome**, matching the six PRD categories:

| Enum value (code) | Meaning | Display requirement |
|---|---|---|
| `success_within_scope` | All required checks within the stated scope passed | Bounds and assumptions must be shown alongside |
| `unsupported` | Capability/placement/interface outside the supported conditions | Explain the limitation; **must not be displayed as success** |
| `rejected` | Candidate failed a required check | Give the reason and keep diagnostic evidence |
| `inconclusive` | Evidence is insufficient to establish a required property | Show the unresolved obligation; **not acceptable** |
| `error` | Tool/service failure | Show the stage and reason; keep completed evidence |
| `cancelled` | Operator cancelled | Stop further work; label the retained evidence truthfully |

### 3.2 Three iron rules

1. **`not_run` ≠ `passed`**: a missing/unimplemented check is recorded as not_run and must never be displayed as passed.
2. **Display phase and outcome separately**: a completed phase does not mean a successful outcome, and vice versa.
3. **Do not fabricate progress percentages** (source wording: Never use fabricated progress percentages). Use stages + events + counts, not fake progress bars.

### 3.3 Approval binding and invalidation

An approval binds: original hash, contract revision, test-manifest hash, patch policy, environment profile, verification scope. **If any one is edited, the approval is immediately invalid and a new run must be started**; the old run is retained.

GUI impact: after saving the contract, show the new revision/hash; `approve` carries the exact expected hashes; **a stale value returns 409**, and the UI must prompt "the contract has changed, please review again" — never silently retry.

### 3.4 Implementation coverage ≠ repair conclusion

Next week's demo may have no passing candidate, but it must show "which stages are actually implemented". These two things must be displayed separately in the UI (TechDesign §9 last paragraph, §14).

---

## 4. The API the GUI consumes (only these)

Source: TechDesign §7 Planned API surface.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/jobs` | multipart upload of ELF + structured test manifest + defect info; returns job ID and original hash |
| POST | `/api/jobs/{id}/analysis` | queue screening and binary analysis; 202 + run/task id |
| GET | `/api/jobs/{id}` | summary, current contract, phases, capabilities, outcomes |
| PUT | `/api/jobs/{id}/contract` | submit the validated contract body + expected revision; returns the new revision/hash |
| POST | `/api/jobs/{id}/approve` | with exact input/contract/manifest/scope hashes; stale → 409 |
| POST | `/api/jobs/{id}/runs` | approved revision + idempotency key; both routes queued; 202 |
| GET | `/api/runs/{id}/events?after=sequence` | bounded incremental events + current summary (for polling) |
| POST | `/api/runs/{id}/cancel` | idempotent cancel request |
| GET | `/api/attempts/{id}/evidence` | obligations, scope, counts, changed regions, artifact IDs |
| GET | `/api/artifacts/{id}/download` | only registered regular files; attachment + safe filename |
| POST | `/api/runs/{id}/exports` | generate a deterministic report bundle; returns artifact ID |

**Error-code semantics** (show the corresponding message; do not pop a generic "something went wrong"):

- `422` invalid structured input · `413` size limit exceeded · `401/403` session or Origin failure · `404` object unavailable · `409` stale approval / illegal state transition
- Every response/error carries a **correlation ID**; **never echo a traceback or a provider response containing secrets to the browser**
- "Capability unsupported" for a queued job must be expressed in the job evidence; **do not imply a successful repair through HTTP 200**

**Test manifest constraints**: only parameter arrays, stdin artifact IDs, expected return/stdout/stderr, and optional allowed output files; **no** arbitrary host commands, shell scripts, or unrestricted file paths. The GUI upload form must not expose a "free command" entry point.

**Polling**: fetch persisted events/status every 2 seconds; long analysis must run outside the request thread (worker process), and the page must not block.

---

## 5. Local service security (hard requirement, not a bonus)

Source: TechDesign §11, §12. It must be in place at the skeleton stage next week; adding it later is expensive.

- Bind only to `127.0.0.1`.
- Bootstrap a **random one-time session token** from launcher → browser; then use an `HttpOnly; SameSite=Strict` session cookie; **remove the token from the address bar, do not log it, and reject reuse**.
- Validate Host and Origin; state-changing requests require a CSRF token.
- **Disable permissive CORS**; local HTTP only, **do not claim transport encryption**, and do not expose it remotely.
- Auto-escape templates + handle untrusted output with `DOM textContent`; use a restrictive CSP for static assets; `nosniff` + frame restrictions.
- Binaries/raw artifacts **must be forced downloads** (attachment).
- Generated evidence HTML must go through trusted templates; **never display worker-provided HTML as active content**.
- Session/auth tokens and API keys must not appear in reports, browser bundles, guest environments, or logs.
- Exports package only **registered safe relative paths** + an independently generated hash manifest, not the whole job directory.
- Mark failed/inconclusive artifacts as diagnostic candidates; **export is not production approval**.

> Note: localhost also needs protection — a malicious web page can try to reach the local service. The document explicitly requires testing this.

---

## 6. UI/UX hard requirements (each is acceptance-checkable)

Source: PRD UI/UX Direction, TechDesign §7.

1. Put important limitations **next to the corresponding result**, not collected at the bottom of the page.
2. Show status with **text + icon + colour** (do not rely on colour alone).
3. Technical details can be expandable, but the main conclusion must be immediately understandable.
4. The two routes should be easy to compare, but **do not imply "smaller patch = safer"**.
5. When a stage fails, **retain the evidence of completed stages**.
6. Keep browser navigation responsive during long analysis.
7. Show both routes (including partial success/failure), each with an independent stage indicator and accessible status labels.
8. AI usage/cost: show it when available; mark `unavailable` when not (**do not write 0, and do not invent**).
9. The UI must not contain claims such as "the whole program is proven safe", "globally minimal patch", or "production-ready".

---

### 6.1 Language policy (2026-10-18 team decision)

- **UI**: Chinese is allowed — titles, buttons, status badges, explanatory text.
- **Uploaded / API / export data**: English ASCII only — defect description, reproduction input, environment, the four contract fields, job fields, obligations, outcome reasons, changed regions, artifact roles, export JSON.
- Server-side validation: non-ASCII form content returns `422`; the frontend blocks it before submission.
- Uploaded filenames are converted to ASCII-safe names so Chinese filenames never enter export data.
- Test guard: `/api/jobs/{id}` and export JSON are scanned for CJK characters; UI pages remain Chinese (`tests/test_language_policy.py`).
- Benefit: evidence/reports can go directly to English-speaking clients, teammates, and proposals without a second translation.

---

## 7. Development mode and data truthfulness (the demo red line)

- Add an **explicit GUI-only development mode**: drive the UI with stored/synthetic results, and **label it clearly** (e.g. "development fixture — execution disabled"); this mode **must never produce accepted-patch evidence** (TechDesign §12).
- API execution is **off by default** until the isolation self-check passes; the GUI must be able to show the truthful state "execution not enabled".
- A hash is an **identity**, not proof of correctness or authenticity — do not write "verified" in UI copy.
- Next week may have no successful candidate, but **must not** present fixture results as a real repair, and must not run binaries on the host to "make the demo look good".

---

## 8. Testing and acceptance (verify it yourself)

Source: TechDesign §13 GUI row, §11 boundary row; PRD success metrics.

GUI scenarios you must walk through manually:

| Scenario | Expectation |
|---|---|
| Setup → review → start → compare → export | Complete the full flow **without a terminal** |
| During work execution | Page responsive, status updates, no freeze |
| Cancel | Idempotent; state becomes cancelled (or error/termination_unconfirmed); evidence retained |
| Browser refresh | State is not lost; no duplicate job is created |
| Unfinished stage | Visible and truthfully labelled |
| Negative cases | Wrong architecture / missing inputs / stale approval / 409 / 422 / 413 all have readable messages |
| Local boundary | Missing session, cross-origin POST, export path traversal/symlink rejected |

Tooling: once the app exists, use **Playwright Python** for the key browser journeys (TechDesign §13); render the three screens before committing, check status and error-state readability, then merge.

Two PRD success metrics directly relevant to you:
- **GUI journey**: one complete setup → review → repair → compare → export without a terminal (environment preparation may require technical operations).
- **Rejection accuracy**: every defined unsupported/error/inconclusive scenario gets the correct label.

Demo script (5-minute suggestion): create a job (show the hash) → review the contract (change it and save, show revision/hash change) → start → dual-route status → one failure/one unfinished → evidence page (obligations/scope/hashes) → export (HTML+JSON) → explicitly say "export is not production approval".

---

## 9. How to plan 5 hours

Source: TechDesign §14 your allocation row, plus the team vertical-slice goal.

| Slot | What to do | Output |
|---|---|---|
| 0–1 h (foundations) | Agree the API contract and status enums with Member 1; get `app/main.py`, `app/templates/`, `app/static/` skeleton running/built; understand the three screens and six outcomes | Skeleton starts, can create a job, can poll |
| 1–2 h | Setup/Review screen: upload, hash, pre-run validation, contract editing, approve (including 409 handling) | F1 works (no terminal) |
| 2–3 h | Progress/Comparison screen: dual-route cards, stage indicators, status labels, cancel, refresh recovery, unfinished visible | Truthful comparison of the two routes |
| 3–4 h | Evidence/Export screen: obligations/scope, bounds, changed regions, downloads, HTML+JSON, diagnostic labels | F5 works |
| 4–5 h (review) | Manual regression per section 8 + three-screen screenshots + a one-page GUI note for the proposal owner | Runnable demo + proposal material |

> Priority when time is short: skeleton → setup → progress → evidence (minimum usable). Evidence can be summary + download only, without fancy layout.

---

## 10. Dependencies and integration

| Dependency | Whom to ask | What you need |
|---|---|---|
| API contract, job lifecycle, cross-screen fields | Member 1 (integration/proposal) | Field names, status enums, 409/422 semantics, idempotency |
| Upload/hash/architecture screening errors | Member 3 (binary/sample) | Real fixture or a usable screening interface and error codes |
| Evidence data structure | Member 4 (acceptance rules + three test suites) | Obligations, scope, counts, changed regions, V0–V5 summary, six-outcome decision rules |
| Test boundaries | Member 4 (lead) + you (GUI e2e) | Acceptance-rule tests and negative/security tests are led by him; GUI journey e2e is written by you; integration-test ownership is confirmed face to face (Member 1 has handed it off) |
| Dual-route stages/outcomes, AI usage | Member 5 (AI/Route B) | Attempt status, whether usage is available |

**The biggest dependency is the API contract** — spend 30 minutes aligning with Member 1 first, otherwise the three-screen fields will keep changing.

### 10.1 The "three test suites" and your relationship to them

In the team division, Member 4 owns "acceptance rules + three test suites" and feeds everyone. According to TechDesign §13's test grouping, the most relevant to you are:

- **Acceptance-rule tests** (acceptance / identity-state): decide how outcome is judged → directly determine your labels and colours; **read the rules before building the status UI**.
- **Negative/security tests** (wrong architecture, stale approval, provider failure, budget exhaustion, ...): exactly the material for setup-screen error messages; ask him for the list.
- **GUI/replay tests** (Setup→review→start→compare→export, cancel, refresh, unfinished stage visible): your e2e; write Playwright using the `data-testid` convention.

On day one, settle "who writes `tests/e2e/test_gui_journey.py`": **you write it, Member 4 reviews it**. This satisfies "the acceptor is independent of the implementer" without duplicating work. The exact "three suites" are whatever you agreed orally; the above is the reasonable mapping from §13.

---

## 11. Scope guardrails (explicitly out of scope)

Source: PRD out-of-scope, TechDesign option comparison.

- No React/separated frontend-backend, no SSE/WebSocket (2-second polling is enough).
- No multi-user/login/OAuth/remote access/enterprise authorization.
- No mobile optimization.
- Do not fabricate progress percentages, do not treat fixture data as real results, do not run binaries on the host.
- Do not weaken acceptance rules for implementation convenience (source: agents/implementers must not weaken tests or remove verification gates to make tests green).
- Do not claim overall correctness, a globally minimal patch, or production readiness.

---

## 12. GitHub delivery conventions (team convention, for reference)

> Your output goes into GitHub. Below is how to land it according to the document structure; the team repository is the final authority.

### 12.1 Suggested repository layout (document §12 layout, with your files marked)

```text
binaryrepair-mvp/
├─ app/
│  ├─ main.py                  ← you
│  ├─ api/                     ← you (existing route shell)
│  ├─ templates/
│  │  ├─ setup.html            ← you
│  │  ├─ comparison.html       ← you
│  │  └─ evidence.html         ← you
│  ├─ static/
│  │  ├─ css/app.css           ← you
│  │  └─ js/poll.js            ← you
│  ├─ domain/                  ← Member 1 (contract/schema/status enums)
│  ├─ services/                ← Member 1 (job controller/export)
│  └─ db/                      ← Member 1
├─ workers/                    ← Member 3/4/5
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  └─ e2e/test_gui_journey.py  ← you (Playwright)
├─ fixtures/public/            ← Member 3 (public samples)
├─ docs/
│  ├─ member2-gui-notes.md     ← this file
│  └─ gui-screens/             ← screenshots
├─ var/jobs/                   ← runtime artifacts, **not committed**
├─ pyproject.toml
├─ .gitignore
└─ README.md
```

Test ownership: `tests/unit`, `tests/evals` belong to Member 4; `tests/integration` **TBD** (Member 1 has handed it off; suggest Member 4 takes it); `tests/e2e` belongs to you. Neither side may change tests or remove verification gates to make tests green.

### 12.2 What may be committed

**May commit**: source code, templates, CSS/JS, tests, documentation, public sample fixtures, screenshots (watch the size), notes under `docs/`.

**Must never commit**:
- Any API key / `.env` (only `.env.example`).
- Client binaries or confidential derived content (PRD data boundary: client material stays local by default; external transfer needs explicit authorization; earlier material also says do not upload to GitHub).
- VM images, large artifacts, `var/jobs/` runtime directory, logs containing secrets.
- The three PDFs are internal team documents: if they must be committed, put them in `docs/reference/` and confirm the team agrees; otherwise link their version in the README and track them by hash (`SHA256SUMS.txt`).

### 12.3 Starting `.gitignore` fragment

```gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.mypy_cache/
.env
var/jobs/
*.log
node_modules/
.DS_Store
```

### 12.4 Branch / PR / commit

- One PR per screen: `feat(gui): setup+review view`, `feat(gui): comparison view`, `feat(gui): evidence+export view`.
- In the PR description include: acceptance items (mapping to sections 2, 6, 8 of this file), three-screen screenshots, manual regression notes.
- Commit examples: `feat(gui): add status polling and truthful phase labels`, `docs(gui): add member2 must-know`.
- Self-check before commit: `pytest` (the levels that can run), `ruff check .`, manual three-screen check.

### 12.5 What the README must state

1. How to start locally (a real command such as `uvicorn app.main:app --host 127.0.0.1 --port 8000`).
2. How to enable GUI-only development mode and what label it displays.
3. Evidence boundary: what counts as passed, what is only diagnostic, export is not approval.
4. Three-screen screenshots and a one-sentence description.

---

## 13. Glossary

| Term | What it means for you |
|---|---|
| **Contract (security contract)** | A set of assumptions and requirements confirmed by the reviewer: valid input domain, forbidden behaviour, expected behaviour for invalid input, environment assumptions; editable in the GUI, with revision and hash |
| **Obligation** | One required check (required/not required) with a result such as passed/not_run/inconclusive; the core data of the evidence page |
| **V0–V5** | Verification ladder: identity/preconditions → structure/placement → interface/compatibility → concrete behaviour → bounded symbolic → reproducibility; the evidence page shows a summary per layer |
| **Route A / Route B** | A = direct machine-instruction repair; B = recover C → compile → reintegrate; both must succeed for MVP success |
| **diagnostic candidate** | A failed/inconclusive artifact, downloadable but explicitly labelled for diagnosis |
| **bounded verification** | Checks a property within the declared domain/model; **not** a proof that the whole program is safe; the UI must show bounds/assumptions |
| **roundtrip** | Route B's "semantics-preserving round trip" precondition gate; it is a phase, not optional decoration |
| **not_run** | Not executed/not implemented; must not count as passed |
| **idempotency key** | Prevents duplicate starts/duplicate charges; double-clicking in the GUI must not create two runs |

---

## 14. Source index (when you need the original text)

| Topic | Document | Location |
|---|---|---|
| Three views, planned API, error codes | TechDesign | §7 (approx. p.7–8) |
| phase/outcome, approval binding, idempotency, cancel | TechDesign | §6 (approx. p.6–7) |
| Verification ladder V0–V5, acceptance rules, symbolic-verification boundary | TechDesign | §9 (approx. p.10–11) |
| Local service security, artifact handling | TechDesign | §11 (approx. p.13–14) |
| Directory layout, development commands, config names, dev mode | TechDesign | §12 (approx. p.14–15) |
| Test scenarios, export bundle contents, replay | TechDesign | §13 (approx. p.15–16) |
| Your role row, vertical slice, fallback when time is short | TechDesign | §14 (approx. p.16–17) |
| F1/F5 acceptance criteria, six outcomes, UI/UX direction, success metrics | PRD | MVP Features / UI/UX Direction / Success Metrics (approx. p.2–6) |
| Data and confidentiality boundary | PRD | AI / Automation Scope, Constraints (approx. p.7–8) |
| Why "proven safe" cannot be claimed, three key findings | research | §1 Executive feasibility assessment |

---

*This file is a working index for the GUI role. The documents themselves are design drafts: commands have not been executed, code has not been implemented, and numbers are planned values; keep the "proposed / default / not measured" qualifiers when citing them.*
