# Release gate, release freeze and the full-coverage definition (2026-11-14)

Status: phase-3 gate implemented; **phase-4 release freeze added** (frozen SHA +
clean worktree enforcement, serialization/flake governance, browser-e2e CI job);
**phase-5 final-release evidence separation added** (frozen `github.sha` +
`--evidence-out` artifact upload in CI, repo-wide serial/language policy checks,
local macOS/Chrome browser evidence); **phase-6 hosted release gate and drift
chain added** (hosted `release-gate-hosted` job via `scripts/release_freeze.py`,
`release-drift` alarm via `scripts/release_drift_check.py`,
`scripts/verify_evidence_branch.py`, and the evidence procedure in
`docs/operations/release-evidence-procedure.md`).  Entry point:
`scripts/release_gate.py`.  Tests: `tests/test_release_gate.py`,
`tests/test_verify_test_serial.py`, `tests/test_release_drift_check.py`,
`tests/test_verify_evidence_branch.py` (no network; mock/tmp fixtures).  CI:
`.github/workflows/ci.yml` jobs `test`, `coverage-gate`, `release-gate-pr`,
`release-gate-hosted`, `release-drift`, `browser-e2e` and the inert-by-default
`release-nightly-gate`.

The gate exists so that "0 open gaps" is never used to hide a
`dynamic_unverified` cell, a non-goal, a missing runtime, a stale claims document
or an **unfrozen/dirty tree**.  It has three explicit cost layers, never fakes a
check, and exits non-zero on any violation.

## 1. What "full coverage" means (the release bar)

A release is only claimable when **all** of the following hold.  Every item below
is enforced by a named gate check; none is a human promise.

1. **Capability universe has no unknown cells.**
   `coverage-matrix.json` enumerates the universe
   (container/arch/bits/endian x strategy x sink class x destination kind x
   evidence profile x runtime tier x provider x proof scope).  Every cell is
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
   The measured audit has zero open gaps, no `GM-detector-error::*` rows, no
   unresolved `matrix_claim_mismatch` rows, and every measured non-goal is
   mapped; `claims.json` is structurally valid and declares no non-goal that is
   not measured.  A `mitigated` residual is accepted only when the audit records
   its rationale (`symptom` plus `next_step`/evidence) - for example the
   host-dependent `RG-runtime-evidence::elf/x86_64/64/little::native_run` row on
   macOS arm64, where x86_64 ELF cannot run natively and the emulated tier plus
   the capability-contract reason is the accepted residual.  Residual ids are
   always printed in the summary; an unexplained mitigated row is a violation.
9. **The acceptance invariant engine passes.**
   `app/services/acceptance_invariants.py` re-checks the committed acceptance
   capture (or raw packets) for the release invariants: verified => all required
   checks passed + evidence sha + profile required checks; rejected => reason;
   not_run/unavailable => no verified/no download; `patch.target_scope` present
   for target-scoped evidence and actions inside it; re-derived rewrite actions;
   manifest evidence uses the unified profile (never legacy check ids);
   inconclusive => no download.
10. **The coverage audit can detect its own defects.**
    `scripts/meta_audit.py` (via the local gate summary or standalone) requires
    recall >= 0.8, precision = 1.0 and >= 7 injected scenarios, so the "0 open"
    claim rests on detectors that were proven to catch known synthetic gaps.
11. **The whole suite is green.**
    `python -m pytest -q` exits 0 on the gated tree (serial; see section 6).
12. **The gated tree is the frozen release tree.**
    `--release` requires `--release-sha`; the read-only git identity of the tree
    (`HEAD`, branch, `git status --porcelain`) is recorded as `frozen_sha`,
    `branch`, `clean_tree`, and HEAD must equal the supplied SHA; the worktree
    must be clean.  Enforced by `release-tree-identity` (section 2).  Any commit after a
    green run invalidates that run.

The same bar is summarized by the gate in this JSON shape:

```json
{
  "schema_version": 1,
  "mode": "release",
  "ok": false,
  "exit_code": 1,
  "violations": ["provider-matrix: ..."],
  "notes": [],
  "release_sha": "725e7bb...",
  "frozen_sha": "725e7bb...",
  "branch": "release/2026-11-14",
  "clean_tree": true,
  "status_counts": {"passed": 8, "failed": 1, "unavailable": 1, "skipped": 0},
  "checks": [
    {"id": "release-tree-identity", "status": "passed", "required": true,
     "detail": "sha=... branch=release/2026-11-14 clean_tree=True release_sha=... MATCH",
     "violations": [], "elapsed_ms": 120},
    {"id": "local-coverage-gate", "status": "passed", "required": true,
     "detail": "open=[] dynamic_unverified=0 universe_unknown=0 cells=205",
     "violations": [], "elapsed_ms": 12345}
  ],
  "elapsed_ms": 60000
}
```

## 2. Release-freeze procedure (phase 4, P0)

A release claim is bound to one **frozen commit SHA**.  The gate proves the
identity of the tree it gated instead of trusting an operator's word.

### 2.1 Freeze

1. The Lead creates the frozen release worktree from the exact commit to be
   released: `git worktree add <path> -b release/<date> <release-commit>`
   (Lead-only git; agents never run state-changing git commands).
2. Nothing is edited in the frozen worktree after this point: the worktree must
   stay clean (`git status --porcelain` empty, including untracked files).
   Fixes go to the mainline worktree, then a **new** frozen SHA is prepared.
3. The Lead records the full SHA.  A shorter SHA is accepted - the gate resolves
   it with `git rev-parse --verify <sha>^{commit}` - but the resolved full SHA is
   what is recorded and matched.

### 2.2 Run (from the frozen worktree root)

```bash
<main venv>/bin/python scripts/release_gate.py --release \
    --release-sha <frozen-sha> --json
```

The gate performs read-only git commands in the gated tree only:
`git -C <root> rev-parse HEAD`, `rev-parse --abbrev-ref HEAD`,
`rev-parse --verify <sha>^{commit}`, `status --porcelain`.  It never writes git
state.

### 2.3 Enforcement semantics

| Situation | Result |
|---|---|
| `--release` without `--release-sha` | **FAIL** (`release-tree-identity`): a clean tree alone cannot prove *which* frozen SHA was gated |
| `HEAD` != supplied SHA (after resolution) | **FAIL**: "the frozen tree moved or the wrong SHA was given" |
| supplied SHA unknown in the repository | **FAIL**: "not a commit in this repository" |
| dirty worktree (`--release`/`--nightly`) | **FAIL** with "worktree is dirty (N path(s)); commit or freeze before release" and the first dirty paths listed |
| git metadata unavailable (`--release`/`--nightly`) | **FAIL**: a frozen identity cannot be proven |
| clean frozen `HEAD` == SHA, clean tree | **PASS**; `release_sha`/`frozen_sha`/`branch`/`clean_tree` recorded in JSON |
| `--pr` without `--release-sha` | allowed (backward compatible); the identity check still reports `frozen_sha`/`clean_tree` |
| `--nightly` without `--release-sha` | allowed; clean tree is still required (the nightly must run on a frozen tree) |
| any `--release-sha` mismatch in any mode | **FAIL** |

Freeze failures **fail fast**: the remaining required checks are not run (the
summary contains only the failed `release-tree-identity` check and a note), so an
unfrozen tree does not burn a 10-minute suite.

### 2.4 Rebase/amendment invalidation

Any commit, amend, rebase, cherry-pick or reset that changes `HEAD` **invalidates
all previous gate evidence for that tree** - even if the content is identical:

- a green run is valid only for the `frozen_sha` recorded in its JSON summary;
- the release evidence must be regenerated on the new frozen SHA: re-freeze, then
  re-run `--release` (and `--nightly` if nightly evidence is claimed);
- never reuse acceptance/provider-matrix/screenshot evidence across SHAs without
  re-running the gate on the frozen tree; never edit the recorded `frozen_sha`;
- a short SHA is resolved at run time; the summary always shows the full
  `frozen_sha`, so a moved branch cannot silently reuse the old claim.

### 2.5 Rerun policy

- **Freeze/identity violations:** fix the freeze (commit or new frozen tree),
  never the check.  Re-run in full.
- **Non-freeze check failures:** fix on mainline, re-freeze a new SHA, re-run the
  full release layer.  Partial reruns, `--list-checks`-only "evidence" or
  hand-edited summaries are not evidence.
- **One classification rerun allowed** for an environmental failure on the *same*
  frozen SHA (to distinguish flake from defect, see section 6.3); two consecutive
  failures of the same check on the same SHA block the release.
- The release claim cites the JSON summary: `ok=true`, `clean_tree=true`,
  `frozen_sha == release_sha == <frozen SHA>`, and the gate's `checks` include
  `release-tree-identity: passed`.

## 3. Gate matrix (cost layers)

| Layer | Command | Checks | Relative cost | When |
|---|---|---|---|---|
| PR | `python scripts/release_gate.py --pr` | tree identity (record only) + static coverage gate (`--static-only`) + claims/measurement diff + targeted pytest subset | fast (~2-3 min locally: ~10 s static/claims + ~110 s targeted subset) | every PR / every edit batch |
| Nightly | `python scripts/release_gate.py --nightly` | frozen/clean tree + release checks + fresh real-Lima acceptance capture (temporary dir) when a guest runner is available | heavy (Lima guest + full suite) | `schedule` / manual on a Lima-capable self-hosted runner |
| Release | `python scripts/release_gate.py --release --release-sha <sha>` | frozen/clean tree + all PR checks + local coverage gate (`--local`: bounded probes, acceptance capture, meta-audit, invariants) + acceptance contract + provider matrix + full pytest | heavy (bounded probes + full suite; run on a Linux/Lima host) | before a release/tag and final acceptance |

Targeted PR subset (missing files tolerated while a workstream is mid-flight, at
least one must exist and pass): `test_release_gate.py`, `test_coverage_gate.py`,
`test_capability_audit.py`, `test_acceptance_invariants.py`,
`test_meta_audit.py`, `test_ci_evidence.py`, `test_repair_matrix.py`,
`test_runtime_capabilities.py`.  All pytest invocations in the gate pass
`-p no:xdist` (serial, see section 6).

`--nightly` behaviour when no guest runner exists: the capture check is
`unavailable` with the probe's explicit reason and is **not** a violation; the
other required release checks still apply.  An available runner with a failed or
non-passing capture **is** a violation.  A fresh capture is written to a
temporary directory and validated there; the gate never rewrites the committed
`artifacts/` evidence.

Both `--json` and human output are supported.  Exit codes: `0` all required
checks passed, `1` at least one violation, `2` usage error.  `--list-checks`
prints the mode/check matrix without running anything.

## 4. Checks, evidence and thresholds

| Check id | What it proves | Threshold / evidence |
|---|---|---|
| `release-tree-identity` | the gated tree is the frozen release tree: HEAD SHA, branch, clean worktree; `--release` requires `--release-sha` | release/nightly: clean tree and (release) `--release-sha` resolving exactly to HEAD; any supplied SHA must match; identity recorded in JSON (`frozen_sha`/`branch`/`clean_tree`/`release_sha`). PR: record only. |
| `static-coverage-gate` | audit is healthy and no open/high/detector-error gap exists in static census; claims mapping valid | `violations == []`, `ok is not False`, exit 0; `dynamic_unverified>0` is expected here and printed, not failed |
| `claims-measurement-diff` | measured audit matches declared claims | 0 open; no detector errors; no open/mitigated `MM-*`; non-goals mapped; claims structurally valid; measured non-goals not stale; `mitigated` residuals accepted only with a recorded rationale (ids printed as `mitigated_residual`) |
| `targeted-pytest` | PR-relevant gate/audit/release contracts are tested | rc 0; >=1 listed file present; missing files reported `not_present`; serial (`-p no:xdist`) |
| `acceptance-contract` | committed real-guest capture covers the end-to-end classes | `passed is true`, no failures, required roles/controls as in section 1 item 6 |
| `local-coverage-gate` | bounded dynamic probes + committed acceptance + meta-audit + invariants at the gate level | exit 0; `violations == []`; `open_gap_ids == []`; `dynamic_unverified_count == 0`; `universe.unknown == 0`, no unmapped cells/reason gaps; `acceptance.ok`, `meta_audit.ok`, `invariants.ok` |
| `meta-audit` | the audit detects injected defects without inventing gaps | `ok/passed is true`, `violations == []`; script thresholds recall >= 0.8, precision = 1.0, scenarios >= 7 |
| `acceptance-invariants` | release invariants hold on the accepted packets/capture | `ok is true`, `violations == []` (packets_checked reported) |
| `universe-unknown-zero` | capability universe is closed (three-state matrix) | `universe.unknown == 0`, no unmapped non-goals, no missing reasons |
| `provider-matrix` | real 12-case provider matrix with target-strict measurement | 12 case rows; `summary.json` schema/kind 1; per-case target-strict fields; honest provider status; SHA256SUMS cover README/summary/per-case and digests match; rates in [0,1] |
| `full-pytest` | no regression anywhere in the suite | `pytest -q -p no:xdist` rc 0; serial |
| `nightly-real-lima-acceptance` | fresh real-Lima capture when a runner exists | runner available => fresh capture `passed`; runner unavailable => explicit `unavailable` (non-blocking, reported in notes) |

## 5. CI wiring (no run is claimed here)

`.github/workflows/ci.yml` keeps pytest serial in every job (`-p no:xdist`,
enforced repo-wide by `scripts/verify_test_serial.py`) and defines:

| Job | Runner | Command | State |
|---|---|---|---|
| `test` | `ubuntu-latest` | syntax gate + offline CI claims + language policy + serialization policy + Markdown language policy (`--json`) + flake policy (`--json`) + universe methodology (`--check`) + serial non-browser pytest | active for every push/PR; governance checks are CI policy (see section 8 for the current observed state); the serialization checker is dependency-light (PyYAML when present, built-in `run:` scanner otherwise) |
| `coverage-gate` | `ubuntu-latest` | the same governance steps + `verify_coverage_gate.py --static-only` + serial gate/audit pytest | active; `dynamic_unverified>0` is expected at this static layer |
| `release-gate-pr` | `ubuntu-latest` | `python scripts/release_gate.py --pr --json` | active for every PR; records tree identity but does not require a frozen SHA |
| `release-gate-hosted` | `ubuntu-latest` | `python scripts/release_freeze.py --mode release --sha ${{ github.sha }} --offline --expected-mainline ignore --evidence-dir artifacts/release-gate-ci --json`, then uploads `release-gate-hosted-evidence` with `actions/upload-artifact@v4` (`if: always()`) | runs on push to `main`/`workbench-v3` and on manual dispatch (not on PRs); a genuine hosted CI execution record when it actually ran (`freeze.json` records the runner/workflow/run id/sha); it is not the self-hosted nightly |
| `release-drift` | `ubuntu-latest` (`fetch-depth: 0`) | `python scripts/release_drift_check.py --tag "$RELEASE_TAG" --json`, where `RELEASE_TAG` is the workflow_dispatch `tag` input (default `release-2026-11-15`), then uploads `release-drift-report` | daily schedule/manual; **alarm only, never release evidence**; a red run means the tag no longer matches mainline or the evidence branch, so the release window has closed and a new tag/evidence review is due |
| `browser-e2e` | `ubuntu-latest` | best-effort Chromium install, then `pytest -q -p no:xdist tests/e2e -rs` | runs serially; the repository CDP helper probes macOS/Windows browser paths only, so on Linux CI the suite records **explicit pytest skips** (visible with `-rs`).  **Linux skips are not release evidence**; the release browser evidence is the local macOS/Chrome run in `artifacts/browser-e2e-2026-11-14/` (section 15). |
| `release-nightly-gate` | `[self-hosted, lima]` | `python scripts/release_gate.py --release --release-sha ${{ github.sha }} --evidence-out artifacts/release-gate-ci/evidence.json` on push/PR/manual, the `--nightly` equivalent on schedule | **inert by default**: job-level guard `if: ${{ vars.BINARYREPAIR_RELEASE_GATE == 'true' }}`; requires an operator-provisioned self-hosted Lima runner and the repository variable. Evidence is uploaded as `release-gate-evidence` with `if: always()`; no such run is claimed here. |

To enable the self-hosted nightly job: provision a runner labelled `lima` with
the `binaryrepair` Lima VM and the real fixtures, then set the repository
variable `BINARYREPAIR_RELEASE_GATE=true`.  A skipped job is not evidence; only
the gate's own JSON output counts.

**Hosted vs self-hosted vs browser vs drift:** `release-gate-hosted` is CI
evidence only when the job actually ran and produced
`artifacts/release-gate-ci/{gate.json,freeze.json,README.md,SHA256SUMS}`.
`release-nightly-gate` skipped means "not run", never "passed".
`release-drift` is an alarm, not evidence.  `browser-e2e` Linux skips are not
passes.  The full hard-link procedure (tag == mainline == evidence gate SHA) is
in `docs/operations/release-evidence-procedure.md`; the release window is
defined in section 17.

## 6. Flake governance and contract serialization (P2-3)

### 6.1 Serial execution (single Lima guest)

The Lima VM, the real PoC differential and the guest-runner staging area are
**single-instance resources**.  Parallel test execution against them produces
nondeterministic failures, so:

- every pytest invocation in the gate is serial:
  `python -m pytest -q -p no:xdist` (explicit even when xdist is not installed,
  so an environment with a parallel plugin cannot silently parallelize);
- CI jobs that run tests (`test`, `coverage-gate`, `browser-e2e`, and
  `release-gate-pr` via the gate) are serial; the self-hosted nightly job runs
  one gate process at a time;
- never run two guest-touching suites concurrently on one host (the gate's full
  suite and the acceptance capture are sequential inside one release run);
- the browser e2e suite runs serially as well (`tests/e2e` uses one browser
  target per test and the CI job passes `-p no:xdist`).

### 6.2 Quarantine policy

- A failing test on the frozen tree **blocks release**; "green by quarantining"
  is not allowed for release evidence.
- A test may be quarantined only with: (a) proof the failure is environmental
  (reproduced on the same SHA and shown to be resource/browser/guest related, or
  passing twice on an identical frozen SHA), (b) an owner, a reason and a
  tracking note in the PR, (c) an explicit skip/marker with that reason, and
  (d) no quarantine of any test that validates acceptance, gate evidence,
  release-freeze or provider-matrix claims.
- Quarantined tests are reported (never counted as passing) and must be revisited
  before the next release.  The gate itself is not modified to tolerate them.

### 6.3 Thresholds and rerun policy

| Layer | Failure threshold | Rerun policy |
|---|---|---|
| PR | 0 test failures; coverage-gate violations 0; serial | re-run freely while iterating; PR is not release evidence |
| Nightly | 0 test failures; 0 gate violations; guest capture unavailable is explicit `unavailable` (not a pass) | one environment-classification rerun per frozen SHA; two consecutive failures block |
| Release | 0 test failures; 0 gate violations; `release-tree-identity` passed; `dynamic_unverified=0`; meta-audit recall >= 0.8 / precision = 1.0; invariants violations 0; provider matrix 12/12 cases validated | one environment-classification rerun on the same frozen SHA; any commit/re-freeze requires a full rerun (section 2.5) |
| Browser e2e | 0 failures when a supported browser is present (macOS Chrome/CDP); explicit skips on hosts without one, never silently green | evidence comes from a macOS Chrome run or the Lead's acceptance capture; CI Linux skips are documented, not claimed |

No `--reruns` style plugin is used by the gate; flakiness is handled by explicit
rerun classification, not by automatic retries.

## 7. P0 acceptance metrics (frozen release)

Measured on the integrated/frozen tree with the phase-3/phase-4 gates; the
`--release` JSON summary is the canonical evidence (`frozen_sha` binds it).

| Item | Metric | Target | Measured (reference tree) | Evidence |
|---|---|---|---|---|
| P0-1 full-coverage release bar | release gate checks passed | all required checks | 9/9 phase-3 release checks passed (655 s); phase-4 adds `release-tree-identity` => 10/10 on a frozen tree | `scripts/release_gate.py --release --json` |
| P0-1 capability universe | `universe.unknown` | 0 | 0 (205 cells: verified 36, supported 51, non_goal 115, unavailable 3) | local coverage gate / `coverage-matrix.json` |
| P0-1 dynamic coverage | `dynamic_unverified_count` at release | 0 | 0 (static/PR layer reports 6, correctly allowed there) | local coverage gate JSON |
| P0-1 honest non-goals | measured non-goal rows mapped with owner/review_by/productization/fallback | 11/11 | 11/11 | `docs/status/claims.json` + `docs/acceptance/non-goals-2026-11-14.md` |
| P0-1 acceptance | required roles/controls pass | all | capacity 21/21 checks, heap 19/19, target-scoped 20/20, no-manifest/wrong-target controls fail closed | `artifacts/coverage-closure-2026-11-14/acceptance.json` |
| P0-1 audit health | open / high open / detector errors | 0 / 0 / 0 | 0 / 0 / 0 (61 static rows: 45 closed, 10 non_goal, 6 dynamic_unverified) | static coverage gate |
| P1-2 provider matrix | 12-case target-strict measurement | 12 cases, target-strict fields on every case, honest provider status | 12 cases; `target_strict_pass_rate=1.0`, `target_in_scope_rate=0.0`; AI target verified 6/12; references 6/6 (+6 source_only); provider served `deepseek-flash` for requested `deepseek-chat`, recorded `identity_ok=false` | `artifacts/provider-matrix-2026-11-14/` (SHA256SUMS verified) |
| P2-3 cost layering | PR / release gate wall time | staged, PR fast | PR ~97 s (3+1 checks); release ~655 s (9 checks), serial | gate `--json` elapsed_ms |
| P2-3 freeze enforcement | frozen SHA + clean tree recorded/enforced | `--release` requires SHA; dirty tree fails | enforced by `release-tree-identity`; dirty/unfrozen tree fails fast with named reason (unit + CLI tested) | `tests/test_release_gate.py`, JSON summary |
| P3-1 worktree safety | protocol documented and adopted | documented | `docs/operations/worktree-safety.md` (two reset incidents, isolation/stash/restore/tests) | doc |
| P3-1 CI/governance | serial tests, browser-e2e job, inert nightly | CI updated, no run claimed | `coverage-gate`/`release-gate-pr` serial; `browser-e2e` documents Linux explicit skips; `release-nightly-gate` inert with vars guard | `.github/workflows/ci.yml` (PyYAML-validated) |

## 8. Current state (2026-11-14, phase 4 freeze / phase 5 final release / phase 6 hosted chain)

- Frozen release worktree: `worktree-release-2026-11-14`, branch
  `release/2026-11-14`, created by the Lead at the mainline release commit
  (`725e7bb`); it contains the committed phase-3 gate including the 9/9 release
  run and the acceptance/provider-matrix evidence.
- Phase-4 changes in this worktree: `--release-sha` + clean-worktree
  enforcement, `release-tree-identity` check and
  `frozen_sha`/`clean_tree`/`branch`/`release_sha` in the JSON summary;
  freeze/rerun procedure and flake governance in this document; serialized CI
  plus the `browser-e2e` job.
- Unit verification: `python -m pytest -q tests/test_release_gate.py` -> 55
  passed (release-sha match/mismatch/unknown/short-form, dirty-tree fail-fast,
  PR backward compatibility, git-unavailable, symmetric SHA fields).
  `.github/workflows/ci.yml` is PyYAML-valid (5 jobs, serial `-p no:xdist`,
  `browser-e2e`, inert nightly guard).
- Local `--nightly` on the pristine frozen tree (phase-3 gate content, clean
  worktree, 777.6 s) exercised the real environment: **8/10 checks passed**,
  including `nightly-real-lima-acceptance: passed` (fresh capture in a temporary
  directory, `runner=lima:limactl tier=emulated_run`, 41.3 s) and the local probe
  gate (`100.7 s`, `dynamic_unverified=0`, `universe.unknown=0`, 240 cells on
  this frozen content).  The two failures were **frozen-tree findings**, reported
  to the owners instead of hidden:
  (a) `claims-measurement-diff` rejected the measured `mitigated`
  host-dependent runtime residual although the audit records its rationale - the
  gate now accepts reasoned `mitigated` residuals and prints them (section 1 item 8);
  (b) `full-pytest` failed 4 tests: a deterministic stale committed artifact
  (`provider-coverage-2026-11-14` cites an old SHA of
  `docs/acceptance/LIMITATIONS.md`) plus three T2 audit/coverage tests that pass
  individually but fail only in whole-suite order (order-dependence/flake,
  T2 scope).  A frozen tree must be green; these require fixes on mainline and a
  **new frozen SHA**.
  The phase-4 tree is expected to fail closed on `release-tree-identity` until
  the Lead commits these changes and re-freezes; `--release` on the re-frozen
  tree must then be run with the new `--release-sha` and is not claimed here.
- Browser e2e: not run in CI (Linux explicit skips by design).  The local
  macOS/Chrome run for this phase passed 12/12 (zero skips) and is recorded in
  `artifacts/browser-e2e-2026-11-14/` (summary.json + README.md + SHA256SUMS,
  Chrome 157.0.8103.51); see section 15.  A skip is never counted as a pass.
- Phase-5 final-release wiring (task-19): `release-nightly-gate` now calls
  `--release/--nightly --release-sha ${{ github.sha }}
  --evidence-out artifacts/release-gate-ci/evidence.json` and uploads the
  `release-gate-evidence` artifact with `if: always()`, keeping the inert
  `vars.BINARYREPAIR_RELEASE_GATE == 'true'` guard and the not-run comments.
  `test`/`coverage-gate` run `scripts/check_language_policy.py` and the new
  `scripts/verify_test_serial.py`; `ubuntu-verify.yml` now passes
  `-p no:xdist` too.  Repo-wide snapshot: `verify_test_serial.py` passes
  (5 pytest commands across 2 workflows) and `check_language_policy.py` passes
  (0 non-ASCII comments/docstrings; the 26 pre-existing fixtures seen earlier
  were fixed by their owners before this snapshot - CI fails on any regression).
  `--evidence-out` is now on disk in `scripts/release_gate.py` and was
  smoke-tested with the exact CI step shape: it writes the evidence JSON
  (keys include `frozen_sha`, `release_sha`, `tree_sha`/`tree_hash`,
  `clean_tree`, `branch`, `checks`, `artifacts`, `environment`, `lima`,
  `not_run`, `mitigated_residual`), creates missing parent directories, and
  returns exit 2 with a clear message if the evidence file cannot be written.

- Phase-6 hosted/drift chain (task-23): `release-gate-hosted` runs
  `scripts/release_freeze.py --mode release --sha ${{ github.sha }} --offline
  --expected-mainline ignore --evidence-dir artifacts/release-gate-ci --json`
  on push/dispatch and uploads `release-gate-hosted-evidence`; `release-drift`
  runs `scripts/release_drift_check.py` on schedule/manual and uploads
  `release-drift-report` (alarm only); both are PyYAML-validated.  New
  `scripts/verify_evidence_branch.py` + `scripts/release_drift_check.py` have
  their own tests (`tests/test_verify_evidence_branch.py` uses real temporary
  git repositories; `tests/test_release_drift_check.py` uses a mock runner).
  `release_gate.py` now also requires `provenance-complete` (release/nightly
  check count 12 -> 13); hosted CI is expected to surface any Linux-only
  `unavailable` guest check as an explicit failure rather than skipping it.
  Observed local governance status: `check_universe_methodology.py --check`
  passes, `check_flake_policy.py --json` passes (`ok=true`), and
  `check_markdown_language.py --json` currently reports pre-existing non-ASCII
  legacy documents (for example `whitepaper-2026-11-14.md`) so the new CI step
  is red until those documents are converted/allowlisted by their owners; this
  document does not claim it is green.

## 9. Operating the gate

```bash
# fast, host-portable (no probes, no network); dirty trees are fine here
.venv/bin/python scripts/release_gate.py --pr

# full release bar on the FROZEN tree (clean worktree, supplied frozen SHA)
.venv/bin/python scripts/release_gate.py --release \
    --release-sha <frozen-sha> --json

# nightly: frozen/clean tree + fresh real-Lima capture when a runner exists
.venv/bin/python scripts/release_gate.py --nightly --json
```

Triage: only a `failed`/`unavailable` **required** check produces a violation;
`skipped` and non-required `unavailable` checks are reported but do not pass a
claim.  Each violation names the failing check and the upstream evidence, so the
fix belongs in that owner's scope (audit -> T2, acceptance -> Lead,
provider matrix -> T4, pipeline/gate -> T1, release wiring/freeze -> T5).  Never
weaken a check to make the gate green: fix the evidence, freeze a new SHA, or
mark the cell an explicit non-goal with an owner and review date.

## 10. Limits

- PR mode proves only the static census, claims mapping and targeted tests; it
  never claims dynamic verification or a frozen identity (it records the tree
  identity, it does not require one).
- Release mode requires the real guest infrastructure and a frozen, clean tree;
  a host without a Lima guest cannot produce a release claim, and a dirty tree is
  rejected by design.
- The gate proves identity of the tree it gated (`frozen_sha` match + clean
  worktree tracked by git).  It cannot prove binary provenance beyond that git
  snapshot, nor that ignored (`.gitignore`d) files are absent; freeze from a
  fresh worktree checkout.
- The acceptance capture covers the documented end-to-end fixtures
  (capacity-check, heap guard, target-scoped ownership), not every universe cell;
  it is real-guest evidence, not a whole-program proof.
- The provider matrix is 12 declared cases at repeat 1 by default: it is
  measurement evidence, not a statistical confidence interval claim.
- "0 open" is necessary but not sufficient: `dynamic_unverified`, non-goals and
  unavailable capability cells are reported separately and must be zero/reasoned
  for a release.
- The self-hosted CI nightly job is inert by default and `browser-e2e` records
  explicit Linux skips; neither is a release claim, and this document does not
  claim a CI run happened.


## 11. Evidence layers and provenance

Three evidence layers are kept separate on purpose; none is allowed to stand in
for another.

| Layer | Where it lives | Authority | Proves | Does not prove |
|---|---|---|---|---|
| Local frozen-tree gate | lead-run `--release`/`--nightly` JSON on the frozen worktree | `local-frozen-tree` | the bar in section 1 on the frozen, clean, SHA-pinned tree, including the real Lima guest capture | that CI ran, or that a different SHA/branch was tested |
| GitHub Actions run | `release-gate-evidence` artifact from the self-hosted run, plus run/job metadata | `github-actions-run` | the same gate ran inside Actions on `${{ github.sha }}` with the uploaded evidence file | anything about runs that did not happen; a skipped job is not evidence |
| Browser evidence | `artifacts/browser-e2e-2026-11-14/` (local macOS/Chrome) or a future supported-runner capture | `local-browser` | the browser e2e suite behavior on a supported browser/OS | CI execution, Linux browser behavior, or gate results |

Provenance fields that must stay attached to a release claim:

- **Frozen git identity:** `frozen_sha`, `release_sha`, `branch`,
  `clean_tree` from the gate summary.  `frozen_sha == release_sha` and
  `clean_tree == true` for a release claim.
- **Check evidence:** the full `checks` list (ids/status/detail/violations) from
  the gate JSON, not a prose summary.  `--evidence-out PATH` writes this JSON
  next to stdout (optional; IO failure is a usage error) and the CI uploads it
  as `release-gate-evidence`.
- **Artifact digests:** acceptance capture sha, provider-matrix `SHA256SUMS`,
  browser-e2e `SHA256SUMS`.  A cited artifact must be the one hashed by its
  recorded digest.
- **Runner/guest identity:** the Lima runner probe (`runner`, `tier`, reason)
  recorded by `nightly-real-lima-acceptance`; an `unavailable` probe is an
  explicit non-pass.
- **Binary/guest provenance:** committed fixture binary sha256 -> the evidence
  record that cites it -> the guest tier that executed it.  The gate validates
  the record; it does not rebuild the binary.  A claim may only cite the chain it
  actually has.

## 12. Not-run semantics and claims fields

Rules (enforced by the gate structure and reviewed in release notes):

- A **skipped CI job** is not evidence.  An **`unavailable` required check** is a
  violation; an **`unavailable` non-required check** (e.g. nightly capture with
  no guest runner) is reported and never counted as green.
- PR mode never claims dynamic verification or a frozen identity; it records the
  tree identity but does not require a frozen SHA.
- A release claim requires all of: `ok == true`, `violations == []`,
  `frozen_sha == release_sha`, `clean_tree == true`, and
  `release-tree-identity: passed` in `checks`.
- "Not run" must be written as "not run" with the reason; never as a pass,
  "green by omission", "expected", or "covered elsewhere".

Canonical JSON fields (gate summary and `--evidence-out`):

| Field | Meaning |
|---|---|
| `mode` | `pr` / `release` / `nightly` |
| `ok`, `exit_code`, `violations`, `notes` | result and named failures/warnings |
| `frozen_sha`, `release_sha`, `branch`, `clean_tree` | frozen tree identity (section 2) |
| `tree_sha` / `tree_hash` | evidence-time tree digest recorded by `--evidence-out` |
| `frozen_matches_release` | convenience boolean (`frozen_sha == release_sha`) |
| `status_counts` | passed/failed/unavailable/skipped counts |
| `checks[].id/status/required/detail/violations/elapsed_ms` | per-check evidence |
| `artifacts` | artifact digests cited by the run |
| `environment`, `lima`, `not_run`, `mitigated_residual` | runner/guest provenance, explicit non-runs, accepted residuals |
| `elapsed_ms`, `schema_version`, `generated_at`, `kind`, `evidence_scope` | run metadata |

`--evidence-out PATH` is optional (release/nightly/pr), writes the JSON next to
stdout, creates parent directories, and exits 2 if the path cannot be written;
the CI uploads it as the `release-gate-evidence` artifact with `if: always()`.
A skipped job produces no evidence file and remains "not run".

Claims documents (`docs/status/claims.json`, release notes) must state: what was
run, where (local frozen tree vs Actions), the frozen SHA, the evidence file/
artifact, and every residual (`dynamic_unverified`, non-goals, `mitigated`
residuals, `unavailable` checks).  Do not cite a run that did not happen.

## 13. Evidence branch/tag procedure

1. **Freeze:** Lead creates `release/<date>` from the intended commit, keeps it
   clean and records the full SHA (phase-4 procedure, section 2).
2. **Gate:** run `--release --release-sha <frozen-sha>` (and `--nightly` when a
   guest is available); keep the JSON/evidence file.  The local evidence is
   valid only for that `frozen_sha`.
3. **CI evidence (optional):** enable the self-hosted runner variable
   `BINARYREPAIR_RELEASE_GATE=true` and dispatch the workflow on the frozen
   commit; the run uploads `release-gate-evidence`, whose `frozen_sha` must
   equal `github.sha`.  A skipped/inert job stays "not run".
4. **Evidence branch:** commit the evidence bundle (gate JSON, browser-e2e
   directory, acceptance/provider-matrix digests) to `evidence/<date>` (or keep
   the Actions artifact and its digest in the release note); Lead-only git.
5. **Tag:** create the annotated release tag only after the frozen tree is green
   and the evidence is stored.  Do not amend, force-push, or rebase after the
   tag; any new commit invalidates the evidence -> new freeze, new gate run, new
   tag.
6. **Revert/retag:** if the tag must move, treat it as a new release: fresh
   freeze + gate + evidence; never present the old evidence for the new SHA.

The executable version of this procedure (commands, verification, rollback and
reviewer checklist) is `docs/operations/release-evidence-procedure.md`.

## 14. Flake governance: quarantine ownership and no rerun-as-pass

Serial execution (section 6.1) stays mandatory: single Lima guest, single PoC
differential, `-p no:xdist` everywhere (now enforced repo-wide by
`scripts/verify_test_serial.py`).

Quarantine records must carry: test id, owner, reason, evidence link,
`opened` date and `expiry` date (max 14 days), and re-review note.  A quarantine
is a tracking device, **not a pass**: quarantined tests are reported and cannot
be counted as green, and no acceptance/gate/release-freeze/provider-matrix test
may be quarantined.  Expired quarantines fail the review.

No rerun-as-pass: on a frozen SHA, one environment-classification rerun is
allowed to distinguish flake from defect, but a failure is never converted into
a pass by retrying and only the first clean frozen-SHA run counts as evidence.
Any rerun must be reported with its reason; two consecutive failures of the same
check block the release (section 6.3).

## 15. Browser evidence: macOS/Chrome pass vs Linux CI skips

`artifacts/browser-e2e-2026-11-14/` records the local browser run:

- command: `.venv/bin/python -m pytest -q -p no:xdist tests/e2e -rs
  --junitxml=artifacts/browser-e2e-2026-11-14/junit.xml`
- browser: Google Chrome 157.0.8103.51 at
  `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- result: **12 passed / 0 failed / 0 errors / 0 skipped**, 35.742 s, JUnit
  counts, deterministic rerun agreement; every file hashed in `SHA256SUMS`.
- skip semantics: this run had zero skips because a supported browser exists.
  Linux CI (`browser-e2e` job) auto-skips when the repo CDP helper (which probes
  macOS/Windows browser paths) finds no supported browser; **those skips are not
  release evidence and not passes**.  Release browser evidence requires a local
  macOS/Chrome run like the one above (or a future supported-runner capture).

## 16. Final release commands

Run from the frozen, clean worktree (`release/<date>`), with the frozen SHA
recorded by the Lead:

```bash
# 0) repo governance (CI also runs these; they are cheap)
.venv/bin/python scripts/verify_test_serial.py --json
.venv/bin/python scripts/check_language_policy.py

# 1) PR smoke layer (not a release claim)
.venv/bin/python scripts/release_gate.py --pr --json

# 2) release layer on the frozen tree, writing the evidence file
.venv/bin/python scripts/release_gate.py --release \
    --release-sha <frozen-sha> \
    --json --evidence-out artifacts/release-gate-ci/evidence.json

# 3) nightly layer when a guest runner/browser is available
.venv/bin/python scripts/release_gate.py --nightly \
    --release-sha <frozen-sha> \
    --json --evidence-out artifacts/release-gate-ci/evidence.json

# 4) browser e2e evidence (macOS/Chrome; Linux CI skips are not evidence)
.venv/bin/python -m pytest -q -p no:xdist tests/e2e -rs \
    --junitxml=artifacts/browser-e2e-<date>/junit.xml

# 5) CI evidence (operator action, only after the self-hosted runner is enabled)
#    set BINARYREPAIR_RELEASE_GATE=true, dispatch the workflow on the frozen
#    commit, download the release-gate-evidence artifact, compare frozen_sha to
#    the commit; a skipped job is not evidence.
```

Additional hosted/evidence commands (full procedure in
`docs/operations/release-evidence-procedure.md`):

```bash
# hosted CI artifact (downloaded from the release-gate-hosted run)
python -c 'import json; d=json.load(open("artifacts/release-gate-ci/gate.json")); print(d["ok"], d["frozen_sha"], d["release_sha"])'

# evidence branch and drift
python scripts/verify_evidence_branch.py --gated-sha <frozen-sha> \
    --evidence-ref release/<date>-evidence --mainline-ref origin/workbench-v3 --json
python scripts/release_drift_check.py --tag release-<date> --json
```

Claims may only cite commands actually run; this phase's recorded local evidence
is the browser run in section 15 plus the `--release`/`--nightly` results in the phase
handoff.  No GitHub Actions run is claimed.

## 17. Hosted CI gate, self-hosted nightly and the release window

The release evidence chain is defined in
`docs/operations/release-evidence-procedure.md`; this section records the
CI-specific semantics.

Layers:

| Layer | Job | Meaning of a green run | Meaning of a skipped/absent run |
|---|---|---|---|
| Hosted CI gate | `release-gate-hosted` | the frozen-tree release gate ran in GitHub Actions on `github.sha` and produced the `release-gate-hosted-evidence` bundle | "hosted gate not run"; never evidence |
| Self-hosted nightly | `release-nightly-gate` | a Lima-capable runner actually executed the nightly layer (real guest capture) | "nightly not run (inert job)"; never evidence |
| Drift alarm | `release-drift` | the release tag still matches mainline and the evidence gate SHA | alarm disabled/not run; not evidence either way |
| Browser e2e | `browser-e2e` (Linux) | browser tests ran with a supported browser | explicit skips; not evidence (see section 15) |

Release window:

1. **Open:** a clean frozen tree exists, the local `--release` gate is green
   (including `provenance-complete` and `release-tree-identity`), and the hosted
   `release-gate-hosted` run on the same `github.sha` produced its artifact.
2. **Evidence:** the evidence branch verifies with
   `scripts/verify_evidence_branch.py` (gated SHA is an ancestor of mainline,
   gate/freeze pin the gated SHA, `SHA256SUMS` validates, changed paths are
   allowed).
3. **Tag:** the annotated `release-<date>` tag points at the frozen SHA.
4. **Monitor:** `release-drift` runs daily; `ok=true` means
   `tag_sha == mainline_sha`, `drift == 0`, `evidence_gated_sha == tag_sha`.
5. **Close:** any new mainline commit after the tag (drift > 0), a red drift
   alarm, or a rebase/amend invalidates the window.  Re-freeze a new SHA, re-run
   the local gate and hosted job, rebuild the evidence branch and cut a new tag;
   never move or reuse the old evidence.
6. **Hosted fallback policy (Lead decision, not claimed here):** if a
   GitHub-hosted runner cannot produce a genuine release-mode pass because the
   real-Lima/guest checks are `unavailable` there, the fallback is to keep
   `release-gate-hosted` on a CI-appropriate mode (for example `--pr`) and treat
   the Ubuntu full pytest run as separate CI evidence - never to report a
   skipped/unavailable check as a pass.  The current file runs the release mode
   as specified and will fail explicitly if a required Linux check is
   unavailable; the Lead verifies with a real CI run before changing the mode.

