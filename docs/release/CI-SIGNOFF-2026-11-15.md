# CI signoff record (2026-11-15)

This is a **release-owner signoff record**, not CI evidence. It records the
release decision for the frozen tree and the reason the self-hosted nightly CI
was not run. It must never be quoted as a successful CI run.

## Signoff

```text
signoff_owner: release owner
signoff_date: 2026-11-15
signoff_scope: final release SHA fd6ca41 (workbench-v3)
signoff_reason: no self-hosted Lima runner provisioned; local frozen-tree gate passed; hosted GitHub release-gate job provides separate CI evidence; nightly Lima CI not run
is_ci_run: false
impersonates_ci: false
```

| field | value |
|---|---|
| owner | release owner |
| date | 2026-11-15 |
| scope | final release SHA `fd6ca41` (workbench-v3) |
| reason | `no self-hosted Lima runner provisioned; local frozen-tree gate passed; hosted GitHub release-gate job provides separate CI evidence; nightly Lima CI not run` |

## Evidence separation

The three evidence slots are distinct and must not be merged in release notes,
the report, or claims:

| evidence slot | status for this signoff | provider | notes |
|---|---|---|---|
| local frozen-tree gate | passed (release-owner record) | local macOS/arm64 host, frozen tree | Recorded separately by the release gate evidence; a local run is not hosted CI evidence and is not a substitute for it. |
| hosted GitHub release-gate job | separate CI evidence | GitHub Actions, hosted runner (release CI workstream; job `release-gate-hosted` in `.github/workflows/ci.yml`) | Quoted only from its own CI run/artifact (run URL or uploaded `release-gate-hosted-evidence` artifact). This signoff does not and cannot stand in for that run. |
| nightly Lima CI | not run | self-hosted runner `[self-hosted, lima]` (job `release-nightly-gate`) | No self-hosted Lima runner was provisioned for this release window; the job stays inert/skipped and must not be reported as a pass. |

Related: `docs/operations/release-gate-2026-11-14.md` defines the local/CI
evidence split and not-run semantics; `.github/workflows/ci.yml` holds the job
definitions and the self-hosted guard.

## Explicit non-claims

This signoff does not claim, and must not be read as claiming:

1. that hosted CI (any job) ran or passed for this SHA;
2. that the nightly self-hosted Lima gate ran or passed;
3. that the local frozen-tree gate is hosted CI evidence;
4. that any test result was produced by CI rather than a local run;
5. that a real-Lima acceptance capture was produced inside CI for this release;
6. that the release may describe "CI green" or "nightly verified" anywhere.

The hosted GitHub release-gate job provides its own separate CI evidence; the
nightly Lima CI is explicitly not run and stays "not run" in the release
record. Any later CI run supersedes this record only through its own run URL and
artifact, never by editing this signoff.

## Release decision

The release owner signs off the frozen tree for this release window on the basis
of the local frozen-tree gate plus the separate hosted release-gate evidence
slot, while explicitly recording that the self-hosted Lima nightly CI did not
run. If the hosted release-gate evidence is unavailable or failing, this signoff
does not authorize a release claim.
