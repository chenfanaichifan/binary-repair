# Phase-8C CI signoff

- Hosted portable CI is the CI workflow on `workbench-v3`; its recorded run is
  bound in `docs/status/claims.json`.
- The self-hosted Lima nightly is **not_run**: no self-hosted runner is
  provisioned for this repository. The local frozen-tree nightly gate on the
  reference host is separate evidence recorded under
  `artifacts/release-gate-2026-11-16-phase8c/` and the Phase-8C evidence branch.
- CI does not execute hidden-corpus material or claim a hidden benchmark pass;
  hidden evidence is reference-host, aggregate-only evidence.
