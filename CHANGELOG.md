# Changelog

All notable changes to this project are documented here. This project follows a
simple semantic-versioning policy for delivery snapshots.

## [1.1.1] — 2026-11-08

### Fixed

- Added the repaired-ELF upload/download entry (`operator_deliverable`; never
  executed and never acceptance evidence).
- Normalized artifact `SHA256SUMS` to LF; direct `shasum -c` now passes.
- Restored curated test paths (`artifacts/legacy-m5-evidence`, `artifacts/p1-routea-kit`)
  and the 124 candidate path.
- Full clean-clone suite: 717 passed / 2 Linux-only skipped / 0 failed.

## [1.1.0] — 2026-11-08

### Added

- Current accepted delivery state: T8.3 complete, P1 `success_within_scope`,
  P2 acceptance passed.
- Canonical evidence under `artifacts/`, including P1, Route A V4, 124 rerun,
  V5 original logs, M4 marker/revalidation and recorded test/e2e logs.
- Public repository organization: documentation map, contribution guide,
  security policy, issue/PR templates, changelog and citation metadata.

### Changed

- Moved canonical evidence from `delivery/` to `artifacts/`.
- Reorganized documentation into overview, architecture, acceptance, operations,
  reference, development and archive sections.
- Updated README, repository map and file guide for the curated snapshot.
- Preserved the original Review 9–12 provenance: the original text is still a
  canonical reconstruction, not a recovered verbatim document.

### Fixed

- Restored the byte-exact V5 replay logs and two test-mutated evidence files in
  the curated snapshot; all `artifacts/**/SHA256SUMS` verify.
- Removed development-only caches/temporary trees from the public release tree.

## [1.0.0] — 2026-10-31

Initial public MVP snapshot imported from the original development repository's
`mvp-2026-10-31` state. This tag is retained as history and is superseded by
1.1.0.

## Version policy

- `v1.0.0` is the historical initial snapshot; do not retag it.
- `v1.1.0` is the current organized delivery snapshot.
- Future changes that alter accepted behavior or evidence scope should use a new
  version and a new annotated tag rather than moving an existing tag.
