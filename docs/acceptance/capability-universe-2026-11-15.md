# Capability universe methodology (2026-11-15)

This document defines how the **capability universe** in
`artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json` is enumerated,
where every value comes from, when a cell may be `unknown`, and how the
methodology stays closed as the registry evolves.

Machine-readable companion/checker:
`scripts/check_universe_methodology.py`.
Canonical snapshot artifact:
`artifacts/capability-universe-2026-11-15/methodology.json` (+ `SHA256SUMS`).

## 1. Why a methodology artifact

A universe only means something if it is derived from declared sources and if
every declared capability actually appears in it.  The checker therefore builds
a **canonical registry snapshot** from the real modules (no host dependence, no
network, no GUI/main imports):

| snapshot block | real source |
|---|---|
| `repair_matrix.cells` | `app.services.repair_matrix.REPAIR_CELLS` (container, arch, bits, endian, strategies, runtime_tiers, sink_classes) |
| `repair_matrix.sink_classes` | `app.services.repair_matrix.SINK_CLASSES` |
| `repair_matrix.strategy_profiles` | `app.services.repair_matrix.STRATEGY_PROFILES` |
| `repair_matrix.evidence_profiles` | `app.services.repair_matrix.EVIDENCE_PROFILES` |
| `universe_taxonomy` | `app.services.coverage_audit.UNIVERSE_STATUSES / UNIVERSE_DESTINATION_KINDS / UNIVERSE_PROOF_SCOPES / UNIVERSE_PROVIDERS` + the documented sentinels below |

`registry_sha256 = sha256(canonical JSON snapshot)`; it changes only when a
registry changes, so a review can diff the artifact rather than the audit prose.

## 2. The 11 dimensions

Every universe cell carries exactly these dimensions.  Values are registry
values or the documented structural sentinels `(all)` / `(any)` / `(none)` /
`(legacy_whole_image)` / `(whole_image_legacy)`; sentinels are markers, never
capability claims.

| # | dimension | definition | registry source |
|---|---|---|---|
| 1 | `container` | thin container format of the cell (`elf`, `pe`, `macho`) | `REPAIR_CELLS.*.container`; sentinel `(all)` for the aggregate row |
| 2 | `arch` | target machine of the cell (`i386`, `x86_64`, `arm64`) | `REPAIR_CELLS.*.arch`; sentinel `(all)` |
| 3 | `bits` | address width as declared by the matrix (`32`, `64`) | `REPAIR_CELLS.*.bits`; sentinel `(all)` |
| 4 | `endian` | byte order declared by the matrix (`little`) | `REPAIR_CELLS.*.endian`; sentinel `(all)` |
| 5 | `strategy` | deterministic repair strategy (`strict-template`, `immediate`, `guard`, `capacity`) | cell `strategies` + `STRATEGY_PROFILES`; sentinel `(legacy_whole_image)` marks the strict-template pair, `(any)`/`(none)` structural rows |
| 6 | `sink_class` | sink taxonomy the analyzer emits (`unbounded_copy`, `memcpy_length`, `syscall_length`, `checked_copy`, `capacity_check_mismatch`) | cell `sink_classes` + `SINK_CLASSES`; sentinel `(legacy_whole_image)` for the strict-template pair |
| 7 | `destination_kind` | memory destination model (`stack`, `heap`, `global`); `global` is an explicit non-goal | `UNIVERSE_DESTINATION_KINDS`; sentinel `(any)` on the aggregate row |
| 8 | `evidence_profile` | unified evidence model of the cell (`strict_template`, `emulated_instruction`, `native_poc`, `native_poc_rewrite`) | `STRATEGY_PROFILES` values + `EVIDENCE_PROFILES`; sentinel `(any)` |
| 9 | `runtime_tier` | strongest declared evidence tier (`native_run`, `emulated_run`) | cell `runtime_tiers`; sentinel `(any)`; `unavailable` only in measured contracts, not claims |
| 10 | `provider` | who owns acceptance: `deterministic` (unified gate) or `ai` (candidate only) | `UNIVERSE_PROVIDERS`; sentinel `(all)` |
| 11 | `proof_scope` | what is proven: `target_scoped`, `whole_image`, `function_level`, `whole_program` | `UNIVERSE_PROOF_SCOPES`; sentinel `(all)` |

## 3. Enumeration method

1. The audit builds cells from the registry: for every matrix cell, every
   declared `(strategy, sink_class)` pair, the meaningful destination kinds
   (stack always; heap only where the analyzer recovers heap capacity; global as
   an explicit non-goal), the derived evidence profile, every declared runtime
   tier, both providers, and the applicable proof scopes.
2. A cell status is assigned from measured/census evidence only
   (`verified|supported|non_goal|unavailable|unknown`); non-goal and unavailable
   cells carry an explicit reason (and a claims non-goal id where one exists).
3. The checklist turns that document into a **closure check**:
   - every dimension value must be a registry value or a documented sentinel;
   - every registry entry (cell, sink class, strategy, runtime tier, evidence
     profile) must appear at least once (reverse coverage);
   - `unknown`/status counts are recomputed from cells, never trusted from the
     summary;
   - every unexplained cell is listed explicitly in `unexplained_cells`.
4. `--write-artifact` stores the canonical snapshot + check result and a
   `SHA256SUMS`; the artifact sha is committed next to the release evidence.

## 4. Unknown rules

The `unknown_rules` block emitted by the checker is authoritative:

1. **`unknown.status_semantics`** - a cell is `unknown` only when the registry
   has no mapping for it.  Release requires `unknown == 0`; the universe
   summary and the coverage gate fail otherwise.  Unexplained (unregistered)
   cells are a separate failure and are never silently treated as covered.
2. **`unknown.registry_authority`** - the registry is the only allowed value
   source; synthetic sentinels are structural markers, not capabilities.
3. **`unknown.denominator`** - `cell_count`, `unknown` and status counts are
   recomputed from the cells; a document whose own summary disagrees fails.
4. **`unknown.reverse_coverage`** - every registry entry must appear at least
   once, otherwise a declared capability would be invisible.

## 5. Current measured state (static audit, 2026-11-15)

- cells: **240**, statuses: supported 87 / non_goal 129 / unavailable 24 /
  verified 0 (static; full audit reports verified cells separately),
  `unknown = 0`;
- registry reverse coverage: all 8 matrix cells, 5 sink classes, 4 strategies,
  runtime tiers and 4 evidence profiles appear; `missing_registry_entries = []`;
- `unexplained_cells = []`, `registry_sha256` recorded in the artifact.

## 6. Limitations

- The registry snapshot is code-derived; a stale checkout produces a different
  `registry_sha256` (the gate compares the committed methodology artifact with a
  live registry build in release/local mode).
- Sentinels are structural, so a sentinel-only capability can look "covered";
  the documented allow-list above is the guard against inventing capabilities.
- Host-dependent runtime evidence is represented in `runtime_tier`/status and by
  the capability contract (`scripts/check_capability_contract.py`); the universe
  itself is host-independent.
- The universe is a closure check over declared capabilities, not a proof that
  every cell has a shipped fixture or a passing end-to-end path; those are
  separate audit gaps.

## 7. Quarterly review

- **Cadence:** quarterly (next review **2027-02-14**, aligned with the claims
  non-goal review date).  Each review re-runs
  `python scripts/check_universe_methodology.py --check --write-artifact`,
  diffs `registry_sha256`, reviews `unexplained_cells`/missing entries, and
  records any new sentinel/registry change in this document and the claims
  `non_goals` review dates.
- **Owner:** audit owner (`audit-tools`), with the capability-contract owner for
  runtime-tier rows and the claims owner for non-goal ids.
- **Exit criteria for a new capability:** registry declaration + matrix cell +
  fixture + runtime oracle + evidence profile + gate check + claims entry; the
  universe cell flips from `unavailable`/`non_goal` to `supported`/`verified`
  only after those are measured.
