# Artifact roles v1

Artifact `role` is a semantic label, not a security boundary. New evidence must
use one of these values; the ingest adapter rejects an unknown analysis role.

| role | meaning |
|---|---|
| `original` | immutable uploaded original ELF |
| `route_a_evidence` | Route A gate evidence |
| `route_b_evidence` | Route B gate evidence |
| `routeb_audit` | static Route B audit |
| `routeb_manifest_compare` | unchanged round-trip result (historical) |
| `routeb_manifest_repaired` | repaired-behaviour result (repair V3 credit) |
| `analysis_expected_effects` | candidate expected effects JSON |
| `analysis_assumptions` | candidate assumptions JSON |
| `analysis_uncertainties` | candidate uncertainties JSON |
| `analysis_v3` | legacy named analysis artifact |
| `behavior_comparison` | original-vs-candidate comparison JSON |
| `legacy_result_bundle` | optional INTERFACE-v1 result-bundle.json, hash-bound in SHA256SUMS |
| `agent_plan` | assistant plan (guidance only; never verdict) |
| `model_call` | model-call audit record (never acceptance evidence) |

## Analysis JSON

`analysis_expected_effects` / `analysis_assumptions` / `analysis_uncertainties`
must be JSON objects matching `app/domain/analysis.py::AnalysisArtifacts` (or a
document with the same three lists and `candidate_sha256`). Display only; they
must not be converted into a `passed` obligation.
