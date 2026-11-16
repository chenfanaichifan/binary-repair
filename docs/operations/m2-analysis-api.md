# M2 analysis -> RepairSpec input draft (NOT gate-validated)

Status: DRAFT, 2026-11-16, produced by M2. This document is an interface
proposal for M1 (Phase-10 repair work). It is **not consumed by any gate, the
planner or repair_any**, it has no acceptance status, and it must not be cited
as a capability. M1 may use it only as an input hypothesis; the deterministic
gate and independent verification remain the only promotion path.

Source of the analysis: app/services/analysis/** and
scripts/analyze_crossfn.py (read-only, deterministic, no model/provider).
Committed example outputs: artifacts/m2-analysis-2026-11-16/.

## 1. Input contract (analysis result)

The analysis result is the JSON emitted by scripts/analyze_crossfn.py --json.
The fields relevant to repair planning are:

    {
      "tool": "m2-analysis-dataflow",
      "schema_version": 1,
      "input": {"path": "...", "sha256": "...", "size": 7800},
      "sinks": [
        {
          "site_va": 16783016,
          "callee": "strcpy",
          "copy_token": "strcpy",
          "function": {"va": 16782992, "name": "copy_payload",
                       "source": "symtab"},
          "destination": {
            "origin": "parameter",        // stack_local | global_object |
                                          // global_address | heap_allocation |
                                          // parameter | immediate | unknown
            "capacity": null,             // integer only when every path agrees
            "capacity_source": null,      // frame_geometry_upper_bound |
                                          // object_symbol_size |
                                          // allocation_immediate_size | null
            "agreement": "conflict",      // all_paths | conflict | no_capacity
            "resolution": "partially_resolved",
            "paths": [
              {"caller": {"va": ..., "name": "wrapper"},
               "call_site_va": ...,
               "origin": "stack_local",
               "capacity": 32,
               "capacity_source": "frame_geometry_upper_bound",
               "alias": {"relation": "must_alias_at_callsite",
                         "argument_locations": [...]},
               "steps": [...]},
              {"caller": {"va": ..., "name": "wrapper2"},
               "origin": "global_object",
               "capacity": 16,
               "capacity_source": "object_symbol_size",
               "steps": [...]}
            ]
          },
          "source_argument": {...},
          "alias": {"destination_locations": [...],
                    "destination_may_alias_anything": true},
          "confidence": "low"
        }
      ]
    }

## 2. Mapping to RepairSpec v1 fields (proposal)

| RepairSpec field | Proposed value from the analysis | Notes |
|---|---|---|
| affected_function | sink.function.name | must resolve to a unique symbol; unresolved -> do not plan |
| affected_addresses | ["0x%x" % sink.site_va] | the call site, not the whole function |
| root_cause | "unbounded copy into destination with capacity < required" | wording is M1's decision; the analysis does not decide root cause semantics |
| required_invariant | "length + 1 <= capacity" | only when capacity_usable is true (see section 3) |
| repair_strategy | "guard" / "bounded copy" | M1's strategy registry decides; analysis is strategy-agnostic |
| verification_conditions | [] -> M1 fills | analysis cannot verify behavior |
| failure_behavior | not provided | needs the PoC/failure contract, out of M2 scope |
| confidence | map sink.confidence (high/medium/low/unknown) | high only for exact object_symbol_size |

Affected addresses are call-site-relative. Do not put the callee (e.g. strcpy)
in affected_registers/affected_memory without M1-side evidence.

## 3. Fail-closed rules for consuming this analysis

1. **Upper-bound capacities are not repair capacities.** capacity_source
   frame_geometry_upper_bound can exceed the real object (wrapper's char
   buf[16] is reported as 32). A guard built on an upper bound still overflows.
   Use it only as a limitation/diagnostic bound, never as the invariant
   capacity. Safe capacity sources today: object_symbol_size (exact ELF
   STT_OBJECT size). allocation_immediate_size is the allocation size, not a
   member size, so it is at most an upper bound too (heap_canary: 24 vs 16).
2. **agreement=conflict means no single RepairSpec.** The sink in
   copy_payload has caller-specific capacities (32 upper bound / 16 exact).
   Emit one RepairSpec per resolved call path, or reject the sink, or extend
   the spec with a call-site constraint. Never average or pick silently.
3. **resolution != resolved means analysis_only.** unknown origins must not
   become candidates.
4. **resolve=unsupported_arch** (non-x86-64 in this increment), stripped-image
   misses and indirect-call unknowns stay analysis_only.
5. The analysis never authorizes a patch. A RepairSpec derived from it still
   needs the normal plan validation + unified gate + independent verification.

## 4. Proposed extension fields (draft, not implemented in the gate)

These are analysis-side suggestions for a future RepairSpec schema; they do
not exist in the current gate contracts:

    "analysis_evidence": {
      "tool": "m2-analysis-dataflow",
      "schema_version": 1,
      "artifact": "artifacts/m2-analysis-2026-11-16/crossfn-param.analysis.json",
      "artifact_sha256": "...",
      "json_pointer": "/sinks/0",
      "call_site_va": 16783016,
      "capacity_source": "frame_geometry_upper_bound",
      "capacity_usable": false,
      "caller_path": ["wrapper", "copy_payload"]
    }

RepairSpec v2 already has evidence_refs; prefer putting the artifact path and
JSON pointer there, and keep capacity usability a gate-side re-derivation
(never trust a model/analysis field as authorization).

## 5. Example: exact global capacity (safe to plan on)

From fixtures/crossfn/crossfn_global.elf (artifact
crossfn-global.analysis.json, sink index 0):

    affected_function: "store_out"
    affected_addresses: ["0x10015c7"]
    capacity: 16, capacity_source: "object_symbol_size", agreement: "all_paths"
    sink.function.va: 0x10015b0, site_va: 0x10015c7, callee: strcpy
    destination symbol: g_out (ELF STT_OBJECT, st_size=16)

Still required from M1 before any candidate: an invariant/strategy that
actually rejects over-long input, a failure_behavior contract, and independent
verification. The analysis only says where the sink and its capacity are.

## 6. Example: conflicting cross-function capacity (needs a per-call-site decision)

From fixtures/crossfn/crossfn_param.elf (artifact crossfn-param.analysis.json):

    sink site_va: 0x10016a8, callee strcpy, function copy_payload (0x1001690)
    path A caller wrapper (0x1001620): stack_local capacity 32 upper bound
    path B caller wrapper2 (0x1001650): global_object capacity 16 exact
                                     (s_ret through ret_buffer() return value)
    sink-level: agreement=conflict, capacity=null, resolution=partially_resolved

M1 options (all gate-validated afterwards): plan per call path; restrict the
repair target to wrapper2 (exact 16); or reject until DWARF object sizes make
path A exact.

## 7. Boundaries

* M2 does not change repair_any behavior, gate checks or RepairSpec code.
* M2 does not produce candidates or downloads; no candidate exists to hand to
  M1 as a patch.
* M2 evidence is regenerated deterministically by
  artifacts/m2-analysis-2026-11-16/generate_evidence.py.
* Any M1 adoption must go through the existing contracts and gates; this draft
  grants no authorization.
