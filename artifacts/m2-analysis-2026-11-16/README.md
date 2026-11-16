# M2 cross-function analysis evidence (2026-11-16)

Read-only analysis evidence for the M2 task (Phase-9 E-01/E-02/E-03 minimal
prototype). **This is not repair capability**: nothing here is wired into
repair_any, the unified gate or any planner; no repair candidate is produced,
no model/provider is called and no target binary is executed.

Regenerate everything deterministically (no timestamps, no randomness):

    cd binary-repair-gui
    .venv/bin/python artifacts/m2-analysis-2026-11-16/generate_evidence.py

Then verify the committed digests:

    cd artifacts/m2-analysis-2026-11-16
    sha256sum -c SHA256SUMS        # GNU coreutils
    shasum -a 256 -c SHA256SUMS    # macOS

## Files

| File | Content |
|---|---|
| envelope.json | host/packages/build flags, fixture digests, explicit not_run list, design boundaries |
| cfg-elf-strcpy-x86_64.json | E-01: real-fixture CFG + direct call graph (1256 functions indexed, main/vuln_copy blocks+instructions, edges from them, statistics, first 40 limitations) |
| crossfn-param.analysis.json | E-02: cross-function dataflow on fixtures/crossfn/crossfn_param.elf (sink in copy_payload, two caller paths) |
| crossfn-global.analysis.json | E-02: cross-function dataflow on fixtures/crossfn/crossfn_global.elf (global destination g_out[16]) |
| heap-canary.analysis.json | E-02/E-04 cross-check on the existing hard case (heap malloc(24) for char data[16]) |
| capacity-param.crosscheck.json | P2: why the same-function capacity class is a different gap; stripped-image limitation observation |
| engine-probe.json | current deterministic engine results on the fixtures (read-only repair_any probe; candidate bytes discarded, never written) |
| comparison.json | per-fixture engine-failure vs prototype-location comparison |
| SHA256SUMS | digests of every committed file except itself |

## Headline results (all reproducible from the JSON above)

1. Required real fixture (E-01): fixtures/elf/vuln-strcpy-x86_64.elf decodes
   into 1256 functions / 21417 blocks / 120834 reachable instructions; 3605
   call/tail-jump edges of which 834 are indirect and explicitly
   resolved=false with a reason. vuln_copy has a direct, resolved call edge to
   the strcpy symbol; main has a direct call edge to vuln_copy.
2. Current engine on the same required fixture, target vuln_copy: disposition
   verified_patch (same-function sink class works). The probe discards the
   candidate bytes; nothing is written.
3. New cross-function fixture 1: sink strcpy inside copy_payload. Current
   engine target copy_payload/wrapper -> analysis_only (no patchable sink).
   Prototype locates the sink and resolves two caller-specific origins:
   wrapper -> stack_local capacity 32 (frame_geometry_upper_bound, an explicit
   over-estimate; real char buf[16]) and wrapper2 -> global_object capacity 16
   through the ret_buffer() return value (object_symbol_size, exact). Because
   the two paths disagree, the sink-level capacity is reported as conflict and
   is NOT reduced to one number.
4. New cross-function fixture 2: sink strcpy inside store_out, destination
   static g_out[16]. Current engine -> analysis_only. Prototype resolves the
   destination to the ELF STT_OBJECT symbol g_out and reports exact capacity 16
   (object_symbol_size); the source is caller argv[1] (unbounded input), which
   is reported, not repaired.
5. Existing hard case cross-check: prototype recovers heap capacity 24 for
   heap_bad (immediate malloc size) and flags the documented over-estimate
   against the real char data[16] member (LIMITATIONS section 21). The engine's
   target-strict baseline for this case is analysis_only, matching the probe.

## Honest gaps (not_run / limitations)

* Runtime PoC/regression on the new fixtures is not_run: the fixtures are
  x86-64 Linux ELF and this host is macOS arm64. The PoC manifests carry
  evidence_level=declared_not_run.
* DWARF object sizes are not analyzed: stack capacities remain frame-geometry
  upper bounds. A frame-geometry upper bound is NOT a safe repair capacity
  (a guard built on 32 for a 16-byte buffer would still overflow); see the M1
  interface draft docs/operations/m2-analysis-api.md.
* Indirect calls are explicit unresolved edges (834 on the required fixture);
  no target is guessed.
* Stripped images: function discovery is symbol-anchored, so
  vuln-capacity-param-x86_64.elf (built with -s) yields only the entry point
  and direct-call-target functions; no sink is found there. Documented in
  capacity-param.crosscheck.json.
* Path sensitivity, concurrency, struct member layout, whole-program claims:
  out of scope, not_run.
