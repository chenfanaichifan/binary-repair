# Acceptance: two AI direct-binary repair paths (2026-11-13)

Branch: `feature/ai-binary-repair` (post-v5, base `72db891`).
Scope: two AI-assisted repair paths that operate directly on binary bytes,
without creating an assembly-text or decompiled-C round trip.

## 1. What was added

- `app/services/ai_binary_repair.py` — protocol, packets, plan validation, AI
  metadata and the shared finish/gate path.
- `app/services/ai_patch_validation.py` — fail-closed static validator for the
  raw `ai_bytes` patch (Capstone decode + allowlist + injection/redirect/edits
  checks).
- `app/services/binary_pipeline.py` — shared `finish_candidate()` tail extracted
  so deterministic and AI candidates use exactly the same reparse/runtime/gate.
- `app/services/runtime/emulated.py` + `runtime/evidence.py` — `buffer_match`
  evidence for bounded copies, closing the "structurally valid no-op guard"
  gate gap.
- `GET /api/binary/ai-paths`, `POST /api/binary/ai-repair`;
  `scripts/repair_binary.py --ai-path`;
  `/binary` UI section with two path cards (product-owned template/JS/CSS/i18n).
- Tests: `tests/test_ai_binary_repair.py`,
  `tests/test_ai_patch_validation.py`, `tests/test_binary_ai_ui.py`,
  `tests/test_ai_evidence_script.py`.
- Scripted evidence: `scripts/capture_ai_binary_repair.py` and
  `artifacts/ai-direct-binary-2026-11-13/` (no network/provider used).

## 2. The two paths

| Path | AI output | Binary write | Deterministic gate |
|---|---|---|---|
| `ai_plan` | `{sink_index, strategy}` only | v5 writer action (guard/immediate) | same runtime/gate as v5 |
| `ai_bytes` | raw `code_hex` (guard) or same-length `edits` | validator + writer inject/redirect or in-place edit | same runtime/gate as v5 |

No assembly text and no decompiled C are produced, reassembled or recompiled.
The model may not promote a failed or incomplete gate; `static_only` remains
explicit opt-in and never success.

## 3. Scripted evidence (both paths, no real provider)

Command: `python scripts/capture_ai_binary_repair.py --out artifacts/ai-direct-binary-2026-11-13`

| fixture | format/arch | `ai_plan` | `ai_bytes` | candidate SHA-256 |
|---|---|---|---|---|
| `fixtures/pe/vuln-strcpy-x64.exe` | PE x86-64 guard | `verified_patch` | `verified_patch` | `179724b99dacd799a8640a4e451b6e06fe6e271882de32b5afc6fd106e0dd350` |
| `fixtures/elf/vuln-strcpy-arm64.elf` | ELF arm64 guard | `verified_patch` | `verified_patch` | `ce1e3e190c09d7e12dfde50dfb696e8d2e168e632f623e1f32e719d38ca6610d` |
| `fixtures/elf/vuln-memcpy-x86.elf` | ELF i386 memcpy immediate | `verified_patch` | `verified_patch` | `e5670ebc9643533607604554a19447e2b2a3cab43479a4485628a4245c3cac88` |

Negative control: an `ai_bytes` guard of `c3` (`ret`) is structurally valid but
semantically empty; the deterministic gate rejects it: `verified=false`,
`disposition=rejected` (`negative-bytes-noop-guard.json`).

The scripted model is a deterministic stand-in.  It proves the protocol, the
validator, the direct binary writeback and the gate integration; it does not
measure LLM repair quality and makes no network call.

## 4. Tests

| Environment | Result |
|---|---|
| macOS 13.5 arm64 / Python 3.11.8 | **1118 tests, 0 failed, 0 errors, 4 skipped** (217.2 s) |
| Linux VM Ubuntu 24.04 arm64 / Python 3.12.3 | **1118 tests, 0 failed, 0 errors, 7 skipped** (209.2 s) |

The 4/7 skips are the same platform-gated Mach-O/Linux-execution cases as v5.
Targeted coverage includes:

- plan path: valid guard/immediate selection -> `verified_patch`; out-of-range/
  wrong-strategy/schema/unknown-field/invalid-JSON/provider-error/no-provider
  -> no candidate + typed AI status;
- bytes path: valid PE x86-64 guard injection, ELF i386 immediate edit ->
  `verified_patch`; syscall/undecodable code, missing sink, before mismatch,
  unrelated edit, no-op guard -> fail closed; no-op guard specifically rejected
  by the deterministic `buffer_match` gate rather than the AI;
- API: `503` no provider, `422` invalid/blocked, `200` verified candidate,
  `ai-paths` contract is ASCII; CLI success and by-path failure cases;
- UI: 13 tests for the two path cards, endpoint contract with a fake client,
  download gating, textContent rendering and no regression of the original
  single-path `/binary` flow.

## 5. CI

- Workflow: `Ubuntu verification` (`.github/workflows/ubuntu-verify.yml`,
  `ubuntu-24.04`, Python 3.11, full non-browser suite).
- Run: [43418024120](https://github.com/chenfanaichifan/binary-repair/actions/runs/43418024120)
  on `abeab27` (`workbench-v3`) — **success**.
- `feature/ai-binary-repair` and the CI-trigger branch `workbench-v3` are both
  pushed to `chenfanaichifan/binary-repair` at the same commit; `main` and
  `handoff-v4-local` are untouched.
- This acceptance record is a docs-only commit after that run; the workflow
  re-runs the same suite and its branch history records the final conclusion.

## 5. Boundaries

- One sink per AI candidate; multi-function selection remains a limitation.
- `ai_plan` cannot exceed the v5 action matrix.
- `ai_bytes` structural validation is not a semantic proof; the runtime gate
  decides.  Guard injection positive evidence covers PE x86-64/arm64 and ELF
  i386/arm64; Mach-O injection is not in the scripted positive matrix.
- Scripted evidence is not real-LLM evidence; provider quality is out of scope.
- AI never owns acceptance; `verified_patch` requires the deterministic gate.
