# Two AI direct-binary repair paths

Status: implemented on `feature/ai-binary-repair` (post-v5).  See the
acceptance record [`docs/acceptance/ai-binary-repair-2026-11-13.md`](../acceptance/ai-binary-repair-2026-11-13.md).

## Rule kept from the workbench

The AI may plan, propose, generate bytes, accept, reject and stop.  It may
**never** turn a failed, incomplete or missing deterministic gate into
`verified_patch`.  Both paths therefore end in the same deterministic
reparse/runtime/gate code (`app/services/binary_pipeline.py::finish_candidate`)
and the same report schema v4 disposition vocabulary.

Neither path converts the file to assembly text and reassembles it, and neither
decompiles to C and recompiles it.  The model's output is either a bounded
choice over already-reviewed actions (path 1) or raw bytes that a static
validator constrains before the writer touches the image (path 2).

## Path 1 — `ai_plan`: plan then deterministic byte writeback

```text
original bytes
  -> deterministic container/import/stack analysis
  -> bounded JSON packet (metadata only: format/arch/matrix, findings, limits)
  -> model returns {schema_version:1, sink_index, strategy: guard|immediate}
  -> strict plan validation (index, patchability, sink-kind/strategy match)
  -> existing deterministic writer emits the bytes
  -> reparse + runtime + deterministic gate
```

- The packet contains **no raw binary bytes**; it carries the binary SHA-256,
  format/architecture, repair-matrix cell, patchable findings (kind, callee,
  capacity, length, call address/function address) and analysis limitations.
- `guard` is accepted only for an `unbounded_copy` sink; `immediate` only for an
  immediate-length sink whose length exceeds capacity.  The model cannot invent
  offsets, capacities, instruction bytes or hashes.
- The output action vocabulary is the v5 engine's own: `guard` injection with
  the deterministic guard template, or immediate clamping.  No new machine code
  is authored by the model on this path.
- Invalid/unknown/unsupported plans fail closed: no candidate, `ai.status =
  invalid`, report disposition `unsupported`.  A provider exception is
  `ai.status = error`; no provider is `ai.status = unavailable` (HTTP 503).

## Path 2 — `ai_bytes`: raw machine code / same-length byte edits

```text
original bytes
  -> bounded packet (metadata + executable section ranges + sink call/length offsets + limits)
  -> model returns raw binary patch
       guard sink:    {schema_version:1, sink_index, inject:{code_hex}}
       immediate sink:{schema_version:1, sink_index, edits:[{offset,before_hex,after_hex}]}
  -> static validator (untrusted bytes)
  -> existing writer injects + call-redirects, or rewrites same-length bytes
  -> reparse + runtime + deterministic gate
```

The model emits bytes, never assembly or C.  The validator
(`app/services/ai_patch_validation.py`) enforces:

- `schema_version == 1`, a valid patchable `sink_index`, sink/container
  architecture match;
- guard sink: exactly one injected machine-code block, no edits; the block must
  decode **completely** with Capstone for the container architecture, may only
  contain whitelisted mnemonics, may not contain calls, syscalls, privileged
  instructions, indirect jumps or parameterised returns, must end in a
  terminating instruction, and every direct branch must stay inside the block;
- the original call site must be the writer-redirectable form (`E8`, `FF15`,
  `FF25`, or arm64 `BL`) with the expected size/architecture; the block is
  injected with the existing writer adapter and the call is redirected only if
  the displacement is encodable;
- immediate sink: only same-length in-place edits, each `before_hex` must match
  the original file byte-for-byte, offsets must lie inside an executable
  section, at most 16 edits / 256 bytes, no overlaps or no-ops; at least one
  edit must hit the selected sink's `length_offset` (unrelated executable edits
  are not a repair);
- the resulting candidate must reparse as the same container format and
  architecture;
- PE guard injection marks the Authenticode signature invalidated; Mach-O guard
  injection marks the code signature invalidated.

The validator proves structural safety only.  Semantic correctness is decided
by the deterministic runtime gate, which includes destination-buffer matching
for bounded copies (`buffer_match`): a structurally valid but semantically
empty guard (for example a lone `ret`) is rejected instead of sampled as a
success.

## Shared surface

| Surface | Value |
|---|---|
| API | `GET /api/binary/ai-paths` (English ASCII contract), `POST /api/binary/ai-repair` (multipart: `binary`, `csrf`, `path=ai_plan|ai_bytes`, optional `allow_static_only=1`) |
| CLI | `scripts/repair_binary.py <input> <output> --ai-path ai_plan|ai_bytes` (single-file; provider from the existing environment/key-store client) |
| UI | `/binary` page section "AI 直接修复（两条路径）": independent file selector, shared best-effort opt-in, one result card per path, AI metadata, disposition/verified, report JSON, download only when `delivery.download_allowed` is true |
| Report | existing report schema v4 plus `ai` metadata (`path`, `called`, `mode`, `provider`, `model`, `status`, `plan_sha256`, `latency_ms`, `validation`, `authority`) |
| Provider | existing `app/services/assistant_llm.py` client (`client.chat_json(messages, max_tokens=..., thinking=False)`); tests and scripted evidence inject a fake/scripted client and perform no network call |

HTTP semantics: `503` when no provider is configured; `422` when the AI payload
is invalid, no candidate is produced, or the deterministic gate refuses the
candidate; `200` only with a downloadable candidate (which can be
`verified=false` only when static-only was explicitly requested).

## Boundaries

- One sink per AI candidate; multi-function/multi-sink selection remains a
  limitation.  The deterministic v5 one-function-per-candidate policy still
  applies to the surrounding report.
- `ai_plan` cannot exceed the v5 engine's supported action matrix.
- `ai_bytes` guard injection currently has positive coverage for PE x86-64/
  arm64 and ELF i386/arm64; Mach-O injection is structurally routed through the
  existing writer adapter but is not part of the scripted acceptance matrix.
- The model can be adversarial or wrong; all model bytes are untrusted and the
  gate, not the model, owns the verdict.  Scripted evidence measures protocol/
  validator/gate integration, not real-LLM repair quality.
