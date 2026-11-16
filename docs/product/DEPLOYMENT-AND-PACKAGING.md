# Deployment and packaging (prototype)

Status: prototype design for the M3 productization increment (2026-11-17).
Pricing and packaging are **prototypes that require real customer validation**;
no commercial commitment is made and no market data is invented here.

## 1. Three deployment forms

| Form | Where the binary lives | Network needed | Evidence location | Status |
|---|---|---|---|---|
| A. Local CLI / workbench | customer or operator machine | none for the deterministic path | local directory | **implemented** (this repository) |
| B. Private cloud (Docker / intranet) | customer network only | internal only | customer-controlled storage | **prototype** (no image built or tested: not_run) |
| C. Hosted SaaS | would leave the customer environment unless a hybrid split is used | external | vendor storage | **design only / not_run** |

### 1.1 Form A - local CLI / workbench (implemented)

- The deterministic demo needs no API key and no external network:
  `BT`tools/product/run-demo.sh <fixture> <outdir>`BT`;
- the existing FastAPI workbench and `BT`scripts/repair_binary.py`BT` remain the
  interactive/CLI entries; the workbench token is local;
- evidence stays on the operator machine; the customer decides retention;
- requirements: Python 3.11 environment, platform runtime oracle options
  (Lima/guest, Unicorn, native macOS for Mach-O).

### 1.2 Form B - private cloud / container (prototype, not built)

- Package the workbench and the deterministic engine into a container inside the
  customer network; optionally a dedicated guest runtime for the oracle;
- no outbound network is required for the deterministic path; AI paths would
  require an explicitly configured provider endpoint (never default);
- binaries do not leave the customer environment; evidence is written to
  customer-managed storage;
- **not_run**: no Dockerfile, no image build, no in-network deployment test, no
  resource-isolation hardening have been produced in this increment.

### 1.3 Form C - hosted SaaS (design only)

Two designs, with an explicit boundary:

1. **Upload model**: the customer uploads the binary to the vendor. This means
   the binary and its metadata leave the customer environment; it requires a
   data-processing agreement, encryption in transit and at rest, per-tenant
   isolation, retention limits and an audit log. **None of these are implemented
   in this delivery** (not_run). This model is not recommended for controlled
   supply-chain binaries without a security review.
2. **Hybrid split (recommended for regulated customers)**: the SaaS control plane
   only schedules and stores reports; the data plane (engine + oracle + binary)
   runs in the customer environment (Form B) and returns only evidence hashes and
   verdicts to the control plane. This keeps offline binaries local.

## 2. Packaging and pricing prototype (needs customer validation)

> Prices are intentionally **TBD**: no market survey or customer interview has
> been run (not_run). The table defines the value metric and packaging shape for
> validation, not a price list.

| Tier | Who it is for | Unit / value metric | Included | Excluded | Price status |
|---|---|---|---|---|---|
| Single repair | one known CVE / one binary, one-off | per engagement (one target function/sink + one PoC/regression set) | bounded repair attempt or explicit refusal, evidence package | multiple functions, sweep, production integration | TBD - prototype |
| Subscription | security team with recurring advisories | platform + N target-function engagements per period | workbench/CLI, evidence retention, periodic capability reports | hidden data, custom engine work | TBD - prototype |
| Enterprise / custom | supply-chain program, regulated industry | annual contract, on-prem (Form B) + integration | private deployment, integration with the customer ticketing/change process, review support | production-safety certification, whole-program proof | TBD - prototype |

Pricing decision inputs to validate with customers: cost per engagement (operator
time + oracle runtime), willingness to pay per CVE mitigation, procurement
constraints for on-prem, and the acceptable evidence retention period. Do not
publish a price before at least three real customer conversations.

## 3. Compliance and security boundaries

| Topic | Current position |
|---|---|
| Credentials | the deterministic path needs **no API key**; a session token protects the local workbench; never log or print keys |
| Customer data | binaries, PoCs and evidence are customer data; in Form A/B they stay on the customer side |
| Isolation | Form B needs per-customer isolation and a disposable guest for execution; **not implemented** (not_run) |
| Audit logs | the evidence index records what was produced; access audit logging is **not implemented** (not_run) |
| Retention/deletion | evidence retention is a customer policy in Form A/B; no automated deletion (not_run) |
| Authorization | modifying a third-party binary may violate its licence/EULA; the customer must hold written authorization; the report template requires an authorization reference |
| Claims | public benchmark 2/24 verified (8.3%), hidden 0/8; no production-safety claim (LIMITATIONS section 9) |
| Independent review | this delivery's verification and approval rows were signed by the same operator (LIMITATIONS section 4); a customer requiring independent approval must add its own reviewer |

## 4. 90-day product roadmap (aligned with the Lead review section 1.5)

Priority order is fixed by the Lead review: capability first, productization
second, autonomy facilities last.

| Window | Workstream | Exit criteria | Owner |
|---|---|---|---|
| Days 1-30 | Capability: Phase-10 CWE-121 behavior contract, CWE-134, non-loop 3/6 to 4/6+ | measured gains recorded with real fixtures + runtime oracle; no gate weakening | M1 |
| Days 1-30 | Minimal cross-function semantics needed by Phase-10 (Phase-9 subset) | only the cross-function cases required by Phase-10; experiments recorded | M2 |
| Days 15-45 | Product: demo/report/evidence hardening (this deliverable), trial onboarding | three external trial users complete the 5 trial tasks; feedback collected | M3 |
| Days 30-60 | Packaging validation: 3 tiers, pricing dimensions, Form B container prototype | >= 3 customer conversations; container prototype runs a fixture end-to-end in-network | M3 + Lead |
| Days 45-75 | Verification hardening: independent-verifier gaps that block Phase-10 cases | verifier decisions reproduce on all new cases; false_verified stays 0 | M1 + M4 |
| Days 60-90 | Release governance + backup/rotation closure (M4) | keys rotated, offsite backup verified, default branch switched, claims aligned | M4 |
| Not scheduled | Phase-8D/13/14 autonomy facilities | explicitly deprioritized by the Lead review | - |

Guardrails for the 90 days:

- every capability claim must come with a benchmark measurement; no claim from
  process artifacts;
- product materials must keep stating public 2/24 and hidden 0/8;
- no AI promotion of failed gate candidates; AI never owns acceptance;
- no production-safety or whole-program claims.

## 5. Known gaps (explicit)

- No container image, no multi-tenant isolation, no access audit log, no
  retention automation (all not_run);
- No pricing validation or customer interviews yet (not_run);
- Hosted SaaS upload model has unresolved data-boundary and compliance risk;
- Form C is a design, not a shipped service;
- Supporting an arbitrary customer binary depends on the deterministic matrix,
  not on deployment form.
