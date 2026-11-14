# Release gate and the full-coverage definition (2026-11-14)

Status: implemented in phase 3 (full-coverage milestone).  Entry point:
`scripts/release_gate.py`.  Tests: `tests/test_release_gate.py` (no network,
mock artifacts).  CI: `.github/workflows/ci.yml` jobs `release-gate-pr` and the
inert-by-default `release-nightly-gate`.

The gate exists so that "0 open gaps" is never used to hide a
`dynamic_unverified` cell, a non-goal, a missing runtime or a stale claims
document.  It has three explicit cost layers, never fakes a check, and exits
non-zero on any violation.

## 1. What "full coverage" means (the release bar)

A release is only claimable when **all** of the following hold.  Every item below
is enforced by a named gate check; none is a human promise.

1. **Capability universe has no unknown cells.**
   `coverage-matrix.json` enumerates the universe
   (container/arch/bits/endian × strategy × sink class × destination kind ×
   evidence profile × runtime tier × provider × proof scope).  Every cell is
   `verified`, `supported`, `non_goal` or `unavailable`; `unknown == 0`, every
   non-goal/unavailable cell carries a reason, and unmapped non-goal ids are
   zero.  Enforced by `universe-unknown-zero` and the local coverage gate.
2. **`dynamic_unverified == 0` for release.**
   Static/PR mode intentionally runs no probes, so probe-dependent rows are
   reported as `dynamic_unverified` (not closed, not an open failure) and may be
   > 0.  The release layer runs the bounded local probes and requires the count to
   be zero; a remaining row is a release violation with its ids listed.
3. **All 11 non-goals are productized, not merely listed.**
   `docs/status/claims.json` `non_goals` and
   `docs/acceptance/non-goals-2026-11-14.md` carry `owner`, `review_by` (ISO
   date), `productization_criteria` and `fallback` for every entry, and every
   measured audit non-goal id is mapped to a declared entry with an enforcement
   that can never produce a success/disposition.  Enforced by
   `claims-measurement-diff` plus the coverage gate's mapping assertions.
4. **The manifest write path is unified.**
   Manifest-bearing repairs go through the unified evidence-profile gate;
   the legacy quick-repair gate fails closed on supplied PoC evidence
   (`manifest.legacy_gate_unsupported`) instead of verifying it.  Measured by the
   audit (`GM-legacy-gate-poc-manifest` closed) and the claims diff.
5. **Target policy is safe by default.**
   Without a caller-declared target and without the explicit
   `allow_whole_image=True` opt-in, a repair is `analysis_only`: no candidate,
   no success packet, no download.  With a target it is `target_scoped` and the
   gate requires `patch.target_scope` with every action site inside the declared
   function.  With the explicit opt-in the result is `whole_image` policy and is
   never presented as a target repair.  A PoC manifest alone never opts into
   whole-image repair.  Enforced by the T1 suites, the audit safe-default probe,
   and the acceptance capture controls.
6. **Real acceptance evidence exists and passed.**
   `artifacts/coverage-closure-2026-11-14/acceptance.json` must have
   `passed: true`, no failures, and the required roles: marcx review-API success
   with no failed/not-run checks and a native/emulated tier; capacity and heap
   `verified_patch` candidates with downloadable SHA-256-identified bytes;
   capacity/heap no-manifest controls held with no candidate; a target-scoped
   ownership case with `patch.target_scope=passed`; and a fail-closed
   wrong-target control with no candidate/download.
7. **Real measured matrix evidence exists.**
   `artifacts/provider-matrix-2026-11-14/` contains `README.md`,
   `summary.json`, `per-case/<case-id>.json` and `SHA256SUMS` with 12 case
   rows, aggregate `target_strict_pass_rate` / `target_in_scope_rate`
   (ratios in [0,1]), and target-strict fields on every case.  An honest
   provider-unavailable run is acceptable only with a typed
   `unavailable_reason` and no claimed AI success; fabricated success is not.
8. **Claims/measurement diff is clean.**
   The measured audit has zero open and zero mitigated gaps, no
   `GM-detector-error::*` rows, no unresolved `matrix_claim_mismatch` rows, and
   every measured non-goal is mapped; `claims.json` is structurally valid and
   declares no non-goal that is not measured.
9. **The acceptance invariant engine passes.**
   `app/services/acceptance_invariants.py` re-checks the committed acceptance
   capture (or raw packets) for the release invariants: verified ⇒ all required
   checks passed + evidence sha + profile required checks; rejected ⇒ reason;
   not_run/unavailable ⇒ no verified/no download; `patch.target_scope` present
   for target-scoped evidence and actions inside it; re-derived rewrite actions;
   manifest evidence uses the unified profile (never legacy check ids);
   inconclusive ⇒ no download.
10. **The coverage audit can detect its own defects.**
    `scripts/meta_audit.py` (via the local gate summary or standalone) requires
    recall ≥ 0.8, precision = 1.0 and ≥ 7 injected scenarios, so the "0 open"
    claim rests on detectors that were proven to catch known synthetic gaps.
11. **The whole suite is green.**
    `python -m pytest -q` exits 0 on the gated tree.

The same bar is summarized by the gate in this JSON shape:

```json
{
  "schema_version": 1,
  "mode": "release",
  "ok": false,
  "exit_code": 1,
  "violations": ["provider-matrix: ..."],
  "notes": [],
  "status_counts": {"passed": 7, "failed": 1, "unavailable": 1, "skipped": 0},
  "checks": [
    {"id": "local-coverage-gate", "status": "passed", "required": true,
     "detail": "open=[] dynamic_unverified=0 universe_unknown=0 cells=8",
     "violations": [], "elapsed_ms": 12345}
  ],
  "elapsed_ms": 60000
}
```

## 2. Gate matrix (cost layers)

| Layer | Command | Checks | Relative cost | When |
|---|---|---|---|---|
| PR | `python scripts/release_gate.py --pr` | static coverage gate (`--static-only`) + claims/measurement diff + targeted pytest subset | fast (~2–3 min locally on the reference tree: ~10 s static/claims + ~110 s targeted subset) | every PR / every edit batch |
| Nightly | `python scripts/release_gate.py --nightly` | release checks + fresh real-Lima acceptance capture (temporary dir) when a guest runner is available | heavy (Lima guest + full suite) | `schedule` / manual on a Lima-capable self-hosted runner |
| Release | `python scripts/release_gate.py --release` | all PR checks + local coverage gate (`--local`: bounded probes, acceptance capture, meta-audit, invariants) + acceptance contract + provider matrix + full pytest | heavy (bounded probes + full suite; run on Linux/Lima host) | before a release/tag and final acceptance |

Targeted PR subset (missing files tolerated while a workstream is mid-flight, at
least one must exist and pass): `test_release_gate.py`, `test_coverage_gate.py`,
`test_capability_audit.py`, `test_acceptance_invariants.py`,
`test_meta_audit.py`, `test_ci_evidence.py`, `test_repair_matrix.py`,
`test_runtime_capabilities.py`.

`--nightly` behaviour when no guest runner exists: the capture check is
`unavailable` with the probe's explicit reason and is **not** a violation; the
other required release checks still apply.  An available runner with a failed or
non-passing capture **is** a violation.  A fresh capture is written to a
temporary directory and validated there; the gate never rewrites the committed
`artifacts/` evidence.

Both `--json` and human output are supported.  Exit codes: `0` all required
checks passed, `1` at least one violation, `2` usage error.  `--list-checks`
prints the mode/check matrix without running anything.

## 3. Checks, evidence and thresholds

| Check id | What it proves | Threshold / evidence |
|---|---|---|
| `static-coverage-gate` | audit is healthy and no open/high/detector-error gap exists in static census; claims mapping valid | `violations == []`, `ok is not False`, exit 0; `dynamic_unverified>0` is expected here and printed, not failed |
| `claims-measurement-diff` | measured audit matches declared claims | 0 open, 0 mitigated, no detector errors, no open/mitigated `MM-*`, non-goals mapped, claims structurally valid, measured non-goals not stale |
| `targeted-pytest` | PR-relevant gate/audit/release contracts are tested | rc 0; ≥1 listed file present; missing files reported `not_present` |
| `acceptance-contract` | committed real-guest capture covers the end-to-end classes | `passed is true`, no failures, required roles/controls as in §1 item 6 |
| `local-coverage-gate` | bounded dynamic probes + committed acceptance + meta-audit + invariants at the gate level | exit 0; `violations == []`; `open_gap_ids == []`; `dynamic_unverified_count == 0`; `universe.unknown == 0`, no unmapped cells/reason gaps; `acceptance.ok`, `meta_audit.ok`, `invariants.ok` |
| `meta-audit` | the audit detects injected defects without inventing gaps | `ok/passed is true`, `violations == []`; script thresholds recall ≥ 0.8, precision = 1.0, scenarios ≥ 7 |
| `acceptance-invariants` | release invariants hold on the accepted packets/capture | `ok is true`, `violations == []` (packets_checked reported) |
| `universe-unknown-zero` | capability universe is closed (three-state matrix) | `universe.unknown == 0`, no unmapped non-goals, no missing reasons |
| `provider-matrix` | real 12-case provider matrix with target-strict measurement | 12 case rows; `summary.json` schema/kind 1; per-case target-strict fields; honest provider status; SHA256SUMS cover README/summary/per-case and digests match; rates in [0,1] |
| `full-pytest` | no regression anywhere in the suite | `python -m pytest -q` rc 0 |
| `nightly-real-lima-acceptance` | fresh real-Lima capture when a runner exists | runner available ⇒ fresh capture `passed`; runner unavailable ⇒ explicit `unavailable` (non-blocking, reported in notes) |

## 4. CI wiring (no run is claimed here)

`.github/workflows/ci.yml` keeps the existing `test` and `coverage-gate` jobs
unchanged (the static gate in `coverage-gate` may legitimately report
`dynamic_unverified>0`), and adds:

| Job | Runner | Command | State |
|---|---|---|---|
| `release-gate-pr` | `ubuntu-latest` | `python scripts/release_gate.py --pr --json` | active for every PR |
| `release-nightly-gate` | `[self-hosted, lima]` | `--release` on push/PR/manual, `--nightly` on schedule | **inert by default**: job-level guard `if: ${{ vars.BINARYREPAIR_RELEASE_GATE == 'true' }}`; requires an operator-provisioned self-hosted Lima runner and the repository variable. No such run is claimed. |

To enable the nightly/release job: provision a self-hosted runner labelled
`lima` with the `binaryrepair` Lima VM and the real fixtures, then set the
repository variable `BINARYREPAIR_RELEASE_GATE=true`.  A skipped job is not
evidence; only the gate's own JSON output counts.

## 5. Current state (2026-11-14, phase 3)

Measured on the integrated tree after the T1/T2/T4 workstreams settled; the same
commands are re-run by the Lead on the frozen tree before the release claim.

**PR layer: PASS.** `python scripts/release_gate.py --pr --json` exits 0
(~97 s): `static-coverage-gate` passed (open=[], 10 non_goal rows, 6
`dynamic_unverified` — allowed in static mode and printed),
`claims-measurement-diff` passed (61 static rows: 45 closed, 10 non_goal, 6
dynamic_unverified, 0 open; 11 claims non-goals; no unresolved `MM-*`),
`targeted-pytest` passed (8 gate/audit/release files, ~110 s).

**Release layer: PASS (9/9 required checks, exit 0).**
`python scripts/release_gate.py --release --json` on the settled tree:
elapsed ~655 s; `violations: []`, `status_counts: {passed: 9, failed: 0,
unavailable: 0, skipped: 0}`.

| Check | Result |
|---|---|
| static-coverage-gate | PASSED (open=[], dynamic_unverified=6 allowed at this layer) |
| claims-measurement-diff | PASSED (61 static rows, 0 open, 0 unresolved MM-*) |
| acceptance-contract | PASSED (roles: capacity=1, heap=1, target-scoped=1, controls=2) |
| local-coverage-gate | PASSED (82 s: open=[], dynamic_unverified=0, universe.unknown=0, 205 cells; meta-audit + invariants + acceptance inside the gate) |
| meta-audit | PASSED (recall=1.0, precision=1.0, scenarios=9) |
| acceptance-invariants | PASSED (packets_checked=9, limitations recorded) |
| universe-unknown-zero | PASSED (205 cells; unknown=0, verified=36, supported=51, non_goal=115, unavailable=3) |
| provider-matrix | PASSED (12 cases, provider_status=ok, target_strict_pass_rate=1.0, target_in_scope_rate=0.0, SHA256SUMS verified) |
| full-pytest | PASSED (full `python -m pytest -q`, ~566 s) |

The release layer originally failed closed while the workstreams were landing
(an older invariant engine rejected the newly regenerated safe-default
acceptance records; the provider matrix was checked before its artifact existed;
and the full suite was transiently red on other lanes' files).  Those failures
were reported with named checks rather than skipped — the intended staged-gate
behaviour — and disappeared once the tree settled.

**Acceptance capture** was regenerated for the new safe-default policy: it keeps
the capacity/heap/target-scoped positives and controls and adds
`marcx_safe_default` / `heap_safe_default` `analysis_only` records (no candidate,
no download).  The T5 contract validates these roles.

**Provider matrix (T4)** is a real provider run: `provider_status=ok`, 12 cases,
target-strict expectation 12/12, AI target verified 6/12, reference 6/6 verified
+ 6 `source_only`, cost `null` with an explicit basis; the model-identity caveat
(configured `deepseek-chat`, served `deepseek-flash`, `identity_ok=false`) is
recorded in the summary rather than hidden.

**Not yet run/claimed:** `--nightly` (it repeats the release checks plus a fresh
real-Lima capture; ~TBD, to be run on the self-hosted Lima runner once the
inert CI job is enabled) and any CI run of the new jobs.  A skipped job or a
check that did not run is never counted as green.

## 6. Operating the gate

```bash
# fast, host-portable (no probes, no network)
.venv/bin/python scripts/release_gate.py --pr

# full release bar; run on a Linux/Lima-capable host
.venv/bin/python scripts/release_gate.py --release --json

# nightly: release checks + fresh real-Lima capture when a runner exists
.venv/bin/python scripts/release_gate.py --nightly --json
```

Triage: only a `failed`/`unavailable` **required** check produces a violation;
`skipped` and non-required `unavailable` checks are reported but do not pass a
claim.  Each violation names the failing check and the upstream evidence, so the
fix belongs in that owner's scope (audit → T2, acceptance → Lead,
provider matrix → T4, pipeline/gate → T1, release wiring → T5).  Never weaken a
check to make the gate green: fix the evidence or mark the cell an explicit
non-goal with an owner and review date.

## 7. Limits

- PR mode proves only the static census, claims mapping and targeted tests; it
  never claims dynamic verification.
- Release mode requires the real guest infrastructure; a host without a Lima
  guest cannot produce a release claim.
- The acceptance capture covers the documented end-to-end fixtures
  (capacity-check, heap guard, target-scoped ownership), not every universe cell;
  it is real-guest evidence, not a whole-program proof.
- The provider matrix is 12 declared cases at repeat 1 by default: it is
  measurement evidence, not a statistical confidence interval claim.
- "0 open" is necessary but not sufficient: `dynamic_unverified`, non-goals and
  unavailable capability cells are reported separately and must be zero/reasoned
  for a release.
- The self-hosted CI job is inert by default; this document and the repository
  do not claim it has run.
