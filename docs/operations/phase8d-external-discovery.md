# Phase-8D D06/D07: external knowledge and real metamorphic discovery

Date: 2026-11-17 (Asia/Shanghai). This note covers only the D06 external
CWE-knowledge scanner and the D07 metamorphic/input-mutation mechanism. It does
not claim a new repair capability, capability promotion, hidden evidence, or
integration into the existing seven-mechanism gap-registry artifact.

## D06: external CWE 5.0 / schema 8.0 scanner

### Source acquisition

The official MITRE files were fetched for the committed snapshot:

- catalog: `https://cwe.mitre.org/data/xml/cwec_v5.0.xml.zip`
- schema: `https://cwe.mitre.org/data/xsd/cwe_schema_v8.0.xsd`
- previous baseline: `https://cwe.mitre.org/data/xml/cwec_v4.19.xml.zip`
- terms: `https://cwe.mitre.org/about/termsofuse.html`

Recorded hashes (full values in `data/external/cwe-5.0/provenance.json`):

- catalog zip `bcda44c9...` (2,119,263 bytes); extracted XML
  `47165a95...` (19,105,731 bytes)
- schema XSD `e68782e8...` (131,424 bytes)
- prior catalog zip `...` / extracted XML `952e31ad...` (18,838,899 bytes)

The raw XML/XSD are deliberately not committed. The committed projection is
241 KB: `snapshot.json`, `schema-drift.json`, `provenance.json`, `README.md`.
The scanner is offline by default; `--live` is an optional metadata/hash
comparison and is never used by tests.

### Measured external facts (not briefing approximations)

- CWE 5.0 XML, date 2026-10-28; **984 weakness entries**.
- Previous CWE 4.19 XML (2025-12-11): **969 weakness entries**.
- Measured new ids: **15** (`1461`-`1467`, `1469`-`1476`); removed: **0**.
- The briefing says approximately 956 weaknesses and 16 new. The committed
  measurement records 984 and 15; the repository does **not** assert 16.
- Schema breaking changes: namespace `http://cwe.mitre.org/cwe-7` (schema 7.3)
  becomes `http://cwe.mitre.org/cwe-8` (schema 8.0); the 5.0 weakness layout has
  **0 Categories** and **431 Groupings** (4.19: 420 Categories, 0 Groupings).
  62 Views are present.

### Mapping and guardrails

`app/services/external_knowledge.py` maps binary-relevant external entries to
bounded capability candidates using CWE-id and keyword rules. Every candidate:

- has `status="candidate"`, `discovery_source="knowledge_source_scan"`;
- has a deterministic proposed experiment and 2027-05-14 review date;
- carries `support_claimed=false` and mapped capability ids D01/D05-D19;
- reports public-corpus exposure counts separately, not support;
- validates through `app.services.gap_registry.validate_records`.

Scan result: **984 external entries, 232 mapped candidates, 752 unmapped**.
Candidate groups: memory_safety 37, arithmetic 9, control_flow 10, string 8,
initialization 18, resource 61, input_validation 21, file_handling 66,
logging 2. Version drift is reported as `current` only when the snapshot
matches configured catalog 5.0/schema 8.0; it is not a support claim.

## D07: actual metamorphic and input-mutation run

Implementation: `app/services/metamorphic_discovery.py`,
`scripts/run_metamorphic_discovery.py`. The script ran the real deterministic
engine (`benchmark_runner.execute_sample` -> `binary_pipeline.repair_any`) on
four committed Phase-8C compiler variants and the real Lima guest
(`guest_runner.run_path`) on family-specific input mutations. No hidden sample
was read; no network/AI was used.

Selected compiler relations:

- `compiler-variant-cwe122-heap-copy`: `variant-cwe122-O2`,
  `variant-cwe122-O2-stripped`
- `compiler-variant-cwe125-oob-read`: `variant-cwe125-O3-static`,
  `variant-cwe125-Os-static-stripped`

Measured engine results:

| variant | engine status | disposition | candidate |
|---|---|---|---|
| variant-cwe122-O2 | executed | analysis_only | no |
| variant-cwe122-O2-stripped | unsupported | none | no |
| variant-cwe125-O3-static | executed | analysis_only | no |
| variant-cwe125-Os-static-stripped | unsupported | none | no |

The stripped variants fail target resolution (`cwe122_bad`/`cwe125_bad` cannot
be resolved to a unique function with a determinable end); the non-stripped
variants execute but produce no candidate. Two engine-level capability
differences are recorded, not hidden.

Input mutation: 11 mutation rows (6 CWE-122 length boundaries, 5 CWE-125 index
boundaries). **11/11 rows executed on both variants; 11/11 relations held** for
this measured window. The crash/no-crash boundary differs by family: CWE-122
crashes at lengths 64 and 256 but not at 0/15/16/17; CWE-125 mutations produced
no crash in this window. These are observations, not semantic-equivalence
proofs or a complete input-space claim.

No candidate was produced by the deterministic engine, so the mechanism does
not add a verified repair or change any capability denominator. It does turn
the prior "metamorphic NOT RUN" state into a measured mechanism with explicit
`not_run`/unsupported records and differences.

## Evidence

- snapshot: `data/external/cwe-5.0/snapshot.json`
  sha256 `c0841f25480436097fabd18a03953009fa4435adb90b979355c3d3a88adabf04`
- schema drift: `data/external/cwe-5.0/schema-drift.json`
  sha256 `faf1e7c5f50abef57cda5c0aa9c8d4431570bb8e8dadb69bd7596e0a132c7cf0`
- provenance: `data/external/cwe-5.0/provenance.json`
  sha256 `1206a713684685f7d0aa89960a6d3578e5c6d3b08d556dff16325682938597bd`
- knowledge scan: `artifacts/phase8d-external-knowledge-2026-11-17/external-knowledge.json`
  sha256 `98d27be7c449fb57b9c7013a1ae534819b859aa57a90dc5732b4e0322e5d9786`
- metamorphic discovery: `artifacts/phase8d-discovery-2026-11-17/discovery.json`
  sha256 `f1aa6037ddd0a4e9c477ef9341b8d3b552965d29103a47b7f9ee17589424ba62`

## Commands and results

```bash
PY=.venv/bin/python
$PY scripts/scan_external_knowledge.py --write
# external-knowledge: wrote ... files=3
$PY scripts/scan_external_knowledge.py --check
# external-knowledge: check OK
$PY scripts/run_metamorphic_discovery.py --write
# metamorphic: wrote ... files=3
$PY scripts/run_metamorphic_discovery.py --check
# metamorphic: check OK
$PY -m pytest -q tests/test_phase8d_external_knowledge.py \
  tests/test_phase8d_metamorphic_discovery.py
# 15 passed
```

## Integration note for the Lead

The existing `scripts/discover_capability_gaps.py` still declares four of seven
mechanisms `not_run`; this work did not edit that file or its frozen artifact
because it is outside this angle. To integrate, the Lead can add adapters:

- `knowledge_source_scan`: consume `scan()` and mark status `run` with 232
  candidate records (still `status="candidate"`).
- `metamorphic`: consume `discover()` and mark status `run` with the explicit
  engine differences and 11 mutation rows. Do not mark the separate `mutation`
  adapter run unless the Lead decides this mechanism qualifies; otherwise keep
  its existing not_run reason.
- `sample_based` remains absent; do not fabricate a sampled corpus.

After integration the committed seven-mechanism artifact must be regenerated
and tested. This note does not claim that regeneration happened.

## Honest limitations

- External knowledge is a candidate source only; no support claim.
- Mapping rules are heuristic (id + keyword), so 752 entries were not mapped;
  no effort was made to force every external entry into a candidate.
- The normalized snapshot stores description hashes, not CWE prose; raw files
  are available from MITRE.
- The 15-vs-16 new-id discrepancy is left explicit; the briefing number is not
  asserted.
- Metamorphic equality is observational; it is not a proof of semantic
  equivalence. Input mutation is bounded (11 rows) and host-dependent.
- The stripped variants' target-resolution failure is a real capability
  difference, not a transformation-equivalence result.
- No candidate, hidden result, coverage, or capability promotion is claimed.
