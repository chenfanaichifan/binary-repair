# Release evidence procedure (2026-11-15)

Status: phase 6. Companion to `docs/operations/release-gate-2026-11-14.md`.
Audience: release operator (Lead) and reviewers.

The release chain is only as strong as the links between its artefacts. This
document defines how the **local frozen-tree gate**, **GitHub Actions evidence**,
the **evidence branch**, and the **release tag** are hard-linked, what is
explicitly *not* evidence, and the exact commands to create and verify the
chain.

## 1. Invariants

A release claim `release-<date>` is valid only while all of the following hold:

1. `tag_sha` equals the current `origin/workbench-v3` mainline tip (no drift).
2. The gated SHA equals `tag_sha` in both `gate.json` and `freeze.json`.
3. The evidence branch tip contains
   `artifacts/release-gate-<date>/{gate.json,freeze.json,README.md,SHA256SUMS}`,
   and `SHA256SUMS` validates against that commit.
4. The gated SHA is an ancestor of the mainline ref.
5. The evidence branch changed only allowed paths relative to the gated commit:
   `artifacts/release-gate-*`, `docs/release-*`, `docs/acceptance/ci-*`, and
   `docs/status/claims.json`.
6. The local frozen-tree gate result cites the same frozen SHA, with
   `clean_tree=true` and `frozen_sha==release_sha`.
7. The hosted CI artifact (when cited) comes from an actual run of the
   `release-gate-hosted` job on that SHA; a skipped or absent run is not evidence.
8. Browser evidence (when cited) is the macOS/Chrome run (or a future supported
   runner); Linux browser skips are not evidence.
9. Self-hosted nightly evidence (when cited) comes from an actual enabled run on
   a Lima-provisioned runner; the job is inert by default and a skipped job is
   not evidence.

Any new commit, amend, rebase, or force-push on the release branch invalidates
items 1-6. Re-freeze a new SHA, re-run the gates, rebuild the evidence branch and
move the tag (section 6).

## 2. Evidence layers (kept separate on purpose)

| Layer | Produced by | Authority | What it is | What it is not |
|---|---|---|---|---|
| Local frozen-tree gate | `scripts/release_gate.py --release/--nightly --release-sha <sha> [--evidence-out ...]` on a clean frozen worktree | local operator | gate result and evidence file bound to the frozen SHA | not a CI run; does not prove GitHub Actions executed |
| Hosted CI gate | `.github/workflows/ci.yml` job `release-gate-hosted` (ubuntu-latest) via `scripts/release_freeze.py --offline` | GitHub Actions | genuine CI record; artifact `release-gate-hosted-evidence` contains `gate.json`, `freeze.json`, `README.md`, `SHA256SUMS`; `freeze.json` records the GitHub run id/workflow/job/sha | not the self-hosted Lima nightly; not a target-runtime proof by itself |
| Self-hosted nightly gate | job `release-nightly-gate` (`[self-hosted, lima]`, `BINARYREPAIR_RELEASE_GATE=true`) | operator-provisioned runner | nightly/real-Lima evidence when it actually runs | inert by default; a skipped job is not evidence and no run is claimed |
| Release-drift alarm | job `release-drift` (schedule/workflow_dispatch) | GitHub Actions | alarm comparing tag/mainline/evidence via `scripts/release_drift_check.py` | an alarm only; it never proves a release passed |
| Browser evidence | local macOS/Chrome run (e.g. `artifacts/browser-e2e-2026-11-14/`) or future supported runner | local/runner | browser suite behaviour and counts | Linux CI explicit skips are not passes and not release evidence |

## 3. Procedure (hard-linked)

### 3.1 Freeze

```bash
# Lead-only: create a clean, detached or release branch worktree at the target
# commit and record the full SHA (see release-gate doc section 2).
git worktree add <frozen-path> -b release/<date> <release-commit>   # Lead only
cd <frozen-path>
git status --porcelain        # must be empty
export FROZEN_SHA="$(git rev-parse HEAD)"
```

Nothing is edited in the frozen worktree after this point.

### 3.2 Local frozen-tree gate

```bash
python scripts/release_gate.py --release \
    --release-sha "$FROZEN_SHA" \
    --json --evidence-out artifacts/release-gate-<date>/evidence.json
# optional nightly layer when a Lima guest + browser are available:
python scripts/release_gate.py --nightly \
    --release-sha "$FROZEN_SHA" --json
```

Claim only when `ok=true`, `clean_tree=true`, `frozen_sha==release_sha` and
`release-tree-identity: passed` in `checks`.

### 3.3 Push and hosted CI evidence

Push the release commit to the mainline branch (`workbench-v3`) and let the
`release-gate-hosted` job run on that SHA (push or workflow_dispatch). Download
the `release-gate-hosted-evidence` artifact and confirm:

```bash
python - <<'PY'
import json
payload = json.load(open("gate.json"))
assert payload["ok"] is True
assert payload["frozen_sha"] == payload["release_sha"]
print("hosted gate frozen/release sha match")
PY
```

The artifact is genuine CI evidence only if the job actually ran and produced
it; an absent/skipped job remains "not run".

### 3.4 Evidence branch

Create `release/<date>-evidence` from the frozen commit, add the evidence bundle
(copy the local `gate.json`/`freeze.json`, write `README.md`, generate
`SHA256SUMS`) plus the release notes, and commit. Only these paths may change
relative to the gated commit:

- `artifacts/release-gate-*`
- `docs/release-*`
- `docs/acceptance/ci-*`
- `docs/status/claims.json`

`SHA256SUMS` must cover `gate.json`, `freeze.json` and `README.md`:

```bash
cd artifacts/release-gate-<date>
sha256sum gate.json freeze.json README.md > SHA256SUMS
```

### 3.5 Verify the evidence branch

```bash
python scripts/verify_evidence_branch.py \
    --gated-sha "$FROZEN_SHA" \
    --evidence-ref "release/<date>-evidence" \
    --mainline-ref origin/workbench-v3 --json
```

Exit 0 requires every check `passed`: gated SHA resolves, gated is an ancestor
of mainline, evidence tip resolves, required files exist, `gate.json` and
`freeze.json` pin the gated SHA, `SHA256SUMS` validates, and the changed-path
allowlist holds.

### 3.6 Tag

```bash
# Lead-only, after 3.2-3.5 are green and the evidence branch is pushed.
git tag -a "release-<date>" -m "release <date>: frozen evidence <FROZEN_SHA>" "$FROZEN_SHA"
git push origin "release-<date>"
```

Annotated tag only; no force-push/amend after this point. The tag, mainline and
evidence branch must agree (hash `tag_sha == FROZEN_SHA`).

### 3.7 Monitor drift (daily alarm)

```bash
python scripts/release_drift_check.py --tag release-<date> --json
```

`ok=true` only when `tag_sha == mainline_sha`, `drift == 0`, and
`evidence_gated_sha == tag_sha`. Exit 1 means the release window is over: the
tag no longer describes mainline (or the evidence is missing/mismatched), so a
new release review is due. The CI `release-drift` job runs this on a daily
schedule and uploads `release-drift-report`; it is an alarm, not evidence.

## 4. Not-run and skip semantics (explicit wording)

Use these exact meanings in release notes and claims:

| Situation | Correct wording | Never write |
|---|---|---|
| `release-nightly-gate` skipped (inert guard unset) | "self-hosted nightly not run (job inert by default)" | "nightly passed" |
| Hosted job skipped/absent | "hosted release gate not run" | "CI gate passed" |
| Drift job red | "drift alarm raised; release window closed" | "release failed validation" (it is an alarm) |
| Browser suite on Linux CI | "explicit skips in CI; browser evidence recorded on macOS/Chrome" | "browser suite passed in CI" |
| Non-required `unavailable` check | "unavailable: <reason> (not counted as green)" | "expected", "covered elsewhere" |
| Required check `unavailable` | "release blocked: <reason>" | "pass by omission" |

A skipped job, an omitted artifact, and a non-required `unavailable` check are
never passes. Only an actual run's `gate.json`/`freeze.json` (or the browser
`summary.json` with `result.status == "passed"`) can be cited.

## 5. Release window

- **Open:** when the frozen SHA is chosen and the local frozen-tree gate plus
  hosted CI artifact are green.
- **Close:** any commit/rebase/amend on the release branch, a red drift alarm,
  or a decision to withdraw; the window then requires a new freeze and a new tag.
- The evidence branch and tag are cut from the same frozen SHA and must not
  change while the window is open.
- Re-tagging is a new release: new freeze, new gates, new evidence bundle, new
  tag name; never reuse old evidence for a moved tag.
- The drift alarm is the mechanical window-closer: `drift > 0` means mainline
  moved on and the release needs a fresh review.

## 6. Rollback / re-release

1. Do not move or delete the published tag to hide drift; publish a new release.
2. Freeze a new SHA from the intended mainline commit.
3. Re-run 3.2-3.5 and cut a new evidence branch/tag.
4. If the old evidence is now invalid, mark it superseded in the release notes
   and keep it for audit history (never edit its recorded SHAs).

## 7. Reviewer checklist (copy into the release note)

- [ ] `FROZEN_SHA` recorded; frozen worktree clean.
- [ ] local `--release`/`--nightly` JSON: `ok=true`, `clean_tree=true`,
      `frozen_sha==release_sha`.
- [ ] hosted artifact `release-gate-hosted-evidence` exists for `github.sha`
      (or explicitly "hosted gate not run").
- [ ] evidence branch: `verify_evidence_branch.py --json` exit 0.
- [ ] tag `release-<date>` at `FROZEN_SHA`; `release_drift_check.py --json`
      exit 0 at publication time.
- [ ] browser evidence path/counts cited (or explicitly "not run").
- [ ] self-hosted nightly: cited only if it actually ran; otherwise "not run
      (inert job)".
- [ ] no CI run or gate result claimed that is not backed by an artifact.

## 8. Verification command summary

```bash
# local frozen-tree gates
python scripts/release_gate.py --release --release-sha "$FROZEN_SHA" --json
python scripts/release_gate.py --nightly --release-sha "$FROZEN_SHA" --json

# hosted CI artifact check (downloaded from the release-gate-hosted job)
python -c 'import json; d=json.load(open("artifacts/release-gate-ci/gate.json")); print(d["ok"], d["frozen_sha"], d["release_sha"])'

# evidence branch and drift
python scripts/verify_evidence_branch.py --gated-sha "$FROZEN_SHA" \
    --evidence-ref "release/<date>-evidence" --mainline-ref origin/workbench-v3 --json
python scripts/release_drift_check.py --tag "release-<date>" --json

# policy checks used by CI and reviewers
python scripts/verify_test_serial.py --json
python scripts/check_language_policy.py
python scripts/check_markdown_language.py
python scripts/check_flake_policy.py
```

`check_markdown_language.py` and `check_flake_policy.py` are part of the phase-6
CI governance; when a checkout predates them, record that they were not
available rather than claiming the checks passed.
