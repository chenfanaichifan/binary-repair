# Verification review — v5 claims, readelf, hashes and AI status (2026-11-13)

This note answers an independent review of the v5 acceptance record.  It is a
verification record, not a new feature claim.  Final machine counts and CI
conclusion are recorded at the end after the final tree was re-run.

## 1. Verdict and corrected wording

The v5 evidence chain is internally consistent: commits, CI runs, branches and
fixtures match the claims.  The wording "100%" needs a scope qualifier:

- **Correct:** "the approved plan G1–G5 (dynamic ELF32, PE32 `FF15`, i386
  memcpy-immediate, ELF32 extend-rx, fat Mach-O input) is complete, and the
  deterministic repair matrix is implemented with 0 failing tests."
- **Incorrect:** "arbitrary binary repair is 100% complete" or "AI can repair
  arbitrary vulnerabilities."  v5 is a deterministic matrix extension, not
  universal vulnerability repair, and v5 AI is review-only.

The canonical scope statement is `LIMITATIONS.md` section 9 (now section 9 +
AI section).  The matrix is ELF/PE/Mach-O x86-64/arm64 plus ELF32/PE32 i386;
heap/global, `sprintf`, UAF/integer/loop, arm32, big-endian and fat-Mach-O
rewrite remain outside the matrix.

## 2. CI evidence re-checked

| run | commit | conclusion |
|---|---|---|
| [43411767923](https://github.com/chenfanaichifan/binary-repair/actions/runs/43411767923) | `47465e0` v5 feature | success |
| [43412399232](https://github.com/chenfanaichifan/binary-repair/actions/runs/43412399232) | `f65c2dc` CI record | success |
| [43412905037](https://github.com/chenfanaichifan/binary-repair/actions/runs/43412905037) | `72db891` v5 docs | success |
| [43418024120](https://github.com/chenfanaichifan/binary-repair/actions/runs/43418024120) | `abeab27` AI paths feature | success |
| [43418615884](https://github.com/chenfanaichifan/binary-repair/actions/runs/43418615884) | `6d525ca` AI docs | success |

`main` remains `8869b07…`; `handoff-v4-local` remains `3d5d0f0…`.  The v5
acceptance record's "no CI record" sentence was stale and is corrected.

## 3. macOS readelf / Route B failure: what changed

The earlier failure was:

```text
tests/test_routeb_executor.py::test_static_routeb_bundle
assert len(views) in (0, 5)   # observed: 1 independent view
```

Cause: GNU `readelf` was absent, so only the `objdump` view was captured.  The
test has always tolerated either **all five** independent views or **none**
(supplying `objdump` alone yields one view and fails); that logic is unchanged
since commit `5932df3`.

Resolution on this host: **Homebrew GNU readelf 2.47 was installed**, not a
backend replacement:

```text
$ which readelf
/opt/homebrew/bin/readelf
$ readelf --version | head -1
GNU readelf (GNU Binutils) 2.47.20260726
```

CI Ubuntu installs `binutils`, so it takes the five-view path.  A stock macOS
host without GNU readelf can still reproduce the one-view failure; this is an
environment prerequisite, not a code fix.  The historical failing junit is
preserved in `artifacts/binary-universal-2026-11-13/junit.xml`; the v5 acceptance
run has 0 failures under the documented environment.  The method suggestion's
alternative (LIEF/llvm-readelf backend) remains future work.

## 4. SHA-256 content hashes (reproducible)

Git blob object ids are SHA-1; they are not comparable to the content SHA-256 in
`PROVENANCE.json`.  Use the committed verifier:

```bash
cd binary-repair-gui
.venv/bin/python scripts/verify_evidence.py --json
```

Observed on the final tree:

```text
fixtures: 11 rows, sources: 110 rows -> PASS
bundle artifacts/binary-universal-v5-2026-11-13: 38 files -> PASS
bundle artifacts/ai-direct-binary-2026-11-13: 9 files -> PASS
overall: PASS
```

The verifier recomputes `fixtures/PROVENANCE.json` path/size/SHA-256 and every
`SHA256SUMS` entry.  It is covered by
`tests/test_verify_evidence.py`.

## 5. LIMITATIONS cross-check

| declaration | verified against |
|---|---|
| deterministic matrix only; matrix-outside = no rewrite | `repair_matrix.py`, v5 acceptance matrix, tests |
| one function per deterministic candidate | `binary_pipeline._primary_repair_function`, tests |
| static-only never success | `finish_candidate`, API/UI download gating tests |
| Unicorn instruction-level, not host kernel | `runtime/emulated.py`, acceptance wording |
| no whole-program/production safety claim | LIMITATIONS sections 1–9 |
| `ai_plan` only selects deterministic actions | `ai_binary_repair.py`, AI tests |
| `ai_bytes` is structurally validated only; gate owns semantics | `ai_patch_validation.py`, no-op guard gate test |
| Mach-O AI injection not in scripted positive matrix | AI acceptance §5 |
| PoC-failure is not yet a gate predicate | this review, `LIMITATIONS.md`; runtime gate is canary/output/buffer-match, not a separate PoC replay |

Stale statements in older LIMITATIONS sections (v4-era "714 tests" and "one
fixture family") were updated to the current v5/v6 state; historical V4 claims
that still apply are retained.

## 6. AI status: two B+AI paths implemented, increment not yet measured

The review's recommendation was "B + AI": keep deterministic instruction-level
rewriting (B), but let AI enter the generation loop and keep the gate as the
acceptance authority.  That is now implemented on
`feature/ai-binary-repair` (fast-forwarded to `workbench-v3`):

1. `ai_plan`: AI selects/instantiates one deterministic writer action
   (`sink_index`, `strategy`) from a metadata-only packet.
2. `ai_bytes`: AI emits raw machine-code guard bytes or same-length in-place
   edits; a fail-closed Capstone/allowlist/injection validator constrains them,
   then the same deterministic runtime/gate decides.

Neither path emits assembly text or decompiled C.  AI still cannot promote a
failed/incomplete gate; `static_only` is explicit opt-in.

Scripted acceptance evidence (`artifacts/ai-direct-binary-2026-11-13/`) shows
six positive `verified_patch` candidates (PE x86-64, ELF arm64, ELF i386; both
paths) and one rejected structurally-valid no-op injected guard.  Importantly,
**no AI increment is measured on these fixtures**: the scripted model
instantiates the same deterministic actions, so each AI candidate equals the v5
deterministic baseline candidate (`same_candidate_as_deterministic` in
`summary.json`).  This proves protocol/validator/writeback/gate integration, not
LLM repair quality or incremental capability.

The next milestone remains: PoC-failure as a gate predicate, plus a gate-blind
case suite that can distinguish AI-generated repairs from the deterministic
baseline.  Until then, do not claim "AI repaired arbitrary binaries" or
"AI increment demonstrated."

## 7. Final local verification

- macOS 13.5 arm64: **1119 tests, 0 failed, 0 errors, 4 skipped** (233.8 s).
- Linux VM Ubuntu 24.04 arm64: **1119 tests, 0 failed, 0 errors, 7 skipped** (249.5 s).
- `scripts/verify_evidence.py`: 11 fixture rows + 110 source rows PASS;
  v5 bundle 38 files PASS; AI bundle 9 files PASS.
- CI: recorded after the final push (next section/final answer).
