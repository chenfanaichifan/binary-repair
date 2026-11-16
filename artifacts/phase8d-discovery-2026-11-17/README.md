# Phase-8D metamorphic and input-mutation discovery (2026-11-17)

Real deterministic-engine and guest-oracle runs over the committed
Phase-8C compiler variants. No candidates or capabilities are invented.

- manifest: `benchmark/phase8c/manifest.json` sha `d46f06bfef59ae7116d888ea2b5810fcf518a9d5c5a178a5cef73996fac72b78`
- variants run: 4
- engine executed: 2; not_run/unsupported: 2
- input mutations: 11; executed: 11
- relations held: 11; differences: 0
- engine-level differences: 2

## Relations

| relation | variants |
|---|---|
| compiler-variant-cwe122-heap-copy | variant-cwe122-O2, variant-cwe122-O2-stripped |
| compiler-variant-cwe125-oob-read | variant-cwe125-O3-static, variant-cwe125-Os-static-stripped |

## Measured differences

- `compiler_variant_engine_capability_difference` / `compiler-variant-cwe122-heap-copy`: same-source variants did not yield the same target-resolution/repair disposition; this is a measured capability difference, not proof of semantic change
- `compiler_variant_engine_capability_difference` / `compiler-variant-cwe125-oob-read`: same-source variants did not yield the same target-resolution/repair disposition; this is a measured capability difference, not proof of semantic change

## Not run

- `variant-cwe122-O2-stripped`: variant-cwe122-O2-stripped: deterministic engine disposition unsupported: target 'cwe122_bad' could not be resolved to a unique function with a determinable end address
- `variant-cwe125-Os-static-stripped`: variant-cwe125-Os-static-stripped: deterministic engine disposition unsupported: target 'cwe125_bad' could not be resolved to a unique function with a determinable end address

## Limitations

- metamorphic relations are observational; equal outcomes are not a semantic-equivalence proof
- input mutations are family-specific and bounded; they do not exhaust the input space
- unsupported/stripped target resolution and guest failures are recorded as differences/not_run, not hidden
- no candidate, capability, or support claim is promoted from this artifact
- guest outcomes are host-dependent; this artifact records one measured reference-host pass

## Reproduce

```bash
python scripts/run_metamorphic_discovery.py --write
python scripts/run_metamorphic_discovery.py --check
python -m pytest -q tests/test_phase8d_metamorphic_discovery.py
```
