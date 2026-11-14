# Platform limits: contract literal vs measured capability (2026-11-15)

This page records the release-time gap between the **literal capability
contract** (what the repair matrix declares) and the **measured capability** (what
the runtime capability probe can actually deliver on the release host). The
measured side is authoritative: a declared tier is never turned into an
availability claim, and an unavailable capability is evidence of `not_run`, not
of a rejected or verified repair.

Measured with:

```text
python scripts/check_capability_contract.py --json
```

Release check output on the 2026-11-15 host (`darwin/arm64`):

```text
capability-contract: ok=True host=darwin/arm64 cells=8 negative_checks=5 violations=0
```

JSON fields consumed below (see `evaluate_contract` in
`scripts/check_capability_contract.py`): `ok`, `host`, `cell_count`,
`cells[].cell`, `cells[].declared_tier`, `cells[].declared_tiers`,
`cells[].measured_tier`, `cells[].available`, `cells[].poc_available`,
`cells[].emulated_available`, `cells[].reason`, `cells[].source`,
`cells[].ok`, `negative_checks[].id`, `negative_checks[].ok`,
`negative_checks[].detail`, `violations`.

## Contract literal vs measured (release host: darwin/arm64)

| contract target | contract literal (declared) | measured on darwin/arm64 (`--json` fields) | external PoC | release behaviour |
|---|---|---|---|---|
| macho/i386 (32-bit Mach-O native) | `declared_tier=unavailable`, `measured_tier=unavailable`, `available=false`, `source=macho_native`; reason: declared capability unavailable, no matrix cell declares a runtime tier and the host has no native or cross-arch path | unavailable: `available=false`, `emulated_available=false`, `poc_available=false` | `poc_available=false` | `unsupported`/`not_run`; no native claim, no candidate; negative check `macho/i386-unavailable` passes |
| macho/x86_64 on arm64 (Rosetta path) | `declared_tier=native_run`, `declared_tiers=[native_run]`; measured `emulated_run`, `available=true`, `emulated_available=true`, `poc_available=false`, `source=macho_native`; reason: declared native_run unavailable on this host, measured emulated_run is function-level evidence only (Rosetta cross-arch path) and the external PoC runner is unavailable | `emulated_run`, function-level only: `available=true`, `poc_available=false`, `emulated_available=true` | `poc_available=false` | external PoC `not_run`/inconclusive; only function-level evidence may be claimed; never `verified_patch` or download from a PoC claim; negative check `macho/x86_64-platform-semantics` passes |
| pe/x86_64 (external PoC) | `declared_tier=emulated_run`, `declared_tiers=[emulated_run]`, `available=true`, `emulated_available=true`, `poc_available=false`, `source=unicorn`; reason: Unicorn instruction-level execution evidence, external PoC runner unavailable | `emulated_run`, function-level Unicorn evidence only: `poc_available=false` | `poc_available=false` | PE external PoC `not_run`; never rejected and never verified; PoC manifests are not executed or faked; negative check `pe/x86_64-external-poc-unavailable` passes |
| pe/i386 (external PoC) | same contract shape as pe/x86_64 (`emulated_run`, `source=unicorn`) | `emulated_run`, `poc_available=false` | `poc_available=false` | PE external PoC `not_run`; same rule; negative check `pe/i386-external-poc-unavailable` passes |
| pe/arm64 (external PoC) | same contract shape as pe/x86_64 (`emulated_run`, `source=unicorn`) | `emulated_run`, `poc_available=false` | `poc_available=false` | PE external PoC `not_run`; same rule; negative check `pe/arm64-external-poc-unavailable` passes |
| elf/x86_64 | `declared_tier=native_run`, `declared_tiers=[native_run, emulated_run]`; measured on this host `emulated_run` via the Lima guest, `available=true`, `poc_available=true`, `source=guest_runner`; reason: declared native_run unavailable on this host, measured emulated_run is function-level evidence only and external PoC is available via the Lima guest runner | `emulated_run` (host-dependent): `available=true`, `poc_available=true` | `poc_available=true` on this host | native or emulated tier recorded by the probe; verified only with the declared evidence profile; no fabricated native tier |
| elf/i386 | `declared_tier=emulated_run`, `declared_tiers=[emulated_run]`, `source=guest_runner`, `poc_available=true` | `emulated_run`, `available=true`, `poc_available=true` | `poc_available=true` on this host | emulated tier recorded; verified only with the declared profile |
| elf/arm64 | `declared_tier=emulated_run`, `declared_tiers=[emulated_run]`, `source=guest_runner`, `poc_available=true` | `emulated_run`, `available=true`, `poc_available=true` | `poc_available=true` on this host | emulated tier recorded; verified only with the declared profile |
| macho/arm64 | `declared_tier=native_run`, `declared_tiers=[native_run]`, `source=macho_native`, `poc_available=true` | `native_run`, `available=true`, `poc_available=true`, `emulated_available=false` | `poc_available=true` on this host | native tier recorded; verified only with the declared profile |

Host dependence note: `elf/x86_64` is the only cell whose measured tier changes
with the host. The contract declares both `native_run` and `emulated_run`; the
release host measures `emulated_run` (Lima guest). A native Linux x86_64 host
projects `native_run` from the same probe (the host-projected value is
informational only; the release check is the real-host `--json` run).

## Negative platform checks (all required, all pass on the release host)

| negative check id | status | detail |
|---|---|---|
| `pe/i386-external-poc-unavailable` | ok | `poc_available=False reason=yes` |
| `pe/x86_64-external-poc-unavailable` | ok | `poc_available=False reason=yes` |
| `pe/arm64-external-poc-unavailable` | ok | `poc_available=False reason=yes` |
| `macho/i386-unavailable` | ok | 32-bit Mach-O native is declared `unavailable` with a reason |
| `macho/x86_64-platform-semantics` | ok | arm64 macOS host reports function-level `emulated_run` only: emulated evidence available, no external PoC |

## Rules

1. **Measured availability governs.** A contract literal may declare a tier; only
   `measured_tier` plus `available`/`poc_available` may be used to claim
   evidence. A declared tier is never rewritten into an availability claim.
2. **Unavailable means `not_run`, never rejected and never verified.** When a
   capability probe reports `available=false` (or `poc_available=false` for a
   PoC-requiring request), the gate records `not_run`/`inconclusive` and no
   success. It must not convert missing platform capability into a rejection of
   the candidate, and it must never fabricate a pass.
3. **No fabricated PoC.** PE external PoC, Mach-O x86_64 external PoC on arm64,
   and 32-bit Mach-O native execution are reported unavailable with the probe
   reason; PoC manifests are not executed and no PoC result is simulated.
4. **Consistency.** Every cell's `measured_tier` is in its declared tier list, or
   the contract carries a non-empty `reason` for the mismatch; an unavailable
   capability keeps `measured_tier=unavailable`, `available=false`, no
   PoC/emulated evidence and a non-empty reason.
5. **Release gate condition.** `scripts/check_capability_contract.py --json` must
   report `ok=true`, `violations=[]`, and all `negative_checks[].ok=true` on the
   release host. Any violation is a release blocker; this page cannot override
   the measured result.
6. **Evidence profile unchanged.** These platform limits do not create a new
   acceptance profile: repairs still verify only through the declared evidence
   profile, and a missing runtime/PoC tier stays `not_run`.
