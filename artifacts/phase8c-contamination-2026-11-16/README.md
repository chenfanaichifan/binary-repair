# Phase-8C contamination audit (2026-11-16)

Mode: `public_only`; status: `ok`; verdict: **clean**

| count | value |
|---|---|
| public_samples | 32 |
| public_dev | 18 |
| public_validation | 14 |
| public_core | 28 |
| public_runtime | 20 |
| public_analysis_only | 8 |
| hidden_samples | 0 |

## Findings

| kind | severity | resolution | samples | similarity |
|---|---|---|---|---|
| binary | note | same_binary_different_target_allowed | hard-multicall, hard-nonconst, hard-sprintf | - |
| binary | note | same_binary_different_target_allowed | hard-loop64, hard-loop8 | - |
| binary | note | same_binary_different_target_allowed | hard-loop16, hard-loop32, hard-reverse | - |
| reference | note | shared_declared_family_allowed | repair-cwe122, variant-cwe122-O2, variant-cwe122-O2-stripped | - |
| reference | note | shared_declared_family_allowed | repair-cwe125, variant-cwe125-O3-static, variant-cwe125-Os-static-stripped | - |
| reference | note | shared_declared_family_allowed | hard-loop16, hard-reverse | - |
| source | note | shared_declared_family_allowed | hard-multicall, hard-nonconst, hard-sprintf | - |
| source | note | shared_declared_family_allowed | repair-cwe122, variant-cwe122-O2, variant-cwe122-O2-stripped | - |
| source | note | shared_declared_family_allowed | repair-cwe125, variant-cwe125-O3-static, variant-cwe125-Os-static-stripped | - |
| source | note | shared_declared_family_allowed | hard-loop16, hard-reverse | - |
| source | note | shared_declared_family_allowed | repair-cwe122, variant-cwe122-O2, variant-cwe122-O2-stripped | - |
| source | note | shared_declared_family_allowed | hard-loop64, hard-loop8 | - |
| source | note | shared_declared_family_allowed | hard-loop16, hard-loop32, hard-loop64, hard-loop8, hard-reverse | - |
| source | note | shared_declared_family_allowed | stack-memcpy-x86, stack-strcpy-x86, stack-strcpy-x86_64 | - |
| source | note | shared_declared_family_allowed | repair-cwe125, variant-cwe125-O3-static, variant-cwe125-Os-static-stripped | - |
| source_text | note | declared_family_near_duplicate | hard-loop16, hard-loop64 | 0.968 |
| source_text | note | declared_family_near_duplicate | hard-loop16, hard-loop8 | 0.968 |
| source_text | note | declared_family_near_duplicate | hard-loop32, hard-loop64 | 0.968 |
| source_text | note | declared_family_near_duplicate | hard-loop32, hard-loop8 | 0.968 |
| source_text | note | declared_family_near_duplicate | hard-loop64, hard-reverse | 0.968 |
| source_text | note | declared_family_near_duplicate | hard-loop8, hard-reverse | 0.968 |

Hidden mode is explicit and never fakes availability: a missing hidden root/manifest is `not_run`, not `clean`.

## Reproduce

```
python scripts/audit_phase8c_contamination.py --write
python scripts/audit_phase8c_contamination.py --check
python scripts/audit_phase8c_contamination.py --hidden-root PATH --write
```
