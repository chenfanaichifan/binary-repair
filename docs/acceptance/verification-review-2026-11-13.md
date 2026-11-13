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
fixtures: 13 rows, sources: 156 rows -> PASS
bundle artifacts/binary-universal-v5-2026-11-13: 38 files -> PASS
bundle artifacts/ai-direct-binary-2026-11-13: 14 files -> PASS
bundle artifacts/ai-real-provider-2026-11-13: 2 files -> PASS
bundle artifacts/gate-blind-spots-2026-11-13: 2 files -> PASS
bundle artifacts/hard-case-benchmark-2026-11-13: 4 files -> PASS
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
| PoC differential is a gate predicate; full PoC replay is not | this review, `LIMITATIONS.md`; `poc.original_fails`/`poc.candidate_passes` are required, but native/guest PoC manifests are future work |

Stale statements in older LIMITATIONS sections (v4-era "714 tests" and "one
fixture family") were updated to the current v5/v6 state; historical V4 claims
that still apply are retained.

## 6. AI status: exactly two product paths, increment still not measured

The product's original two paths are now implemented and exposed:

1. **Path 1 `asm_roundtrip`** — ELF binary → Capstone disassembly of the target
   function → AI returns repaired **assembly** → clang assembles it back to
   machine code → injected executable block + function-entry redirect → patched
   ELF.  This is the "translate to assembly, repair, assemble back" path.
2. **Path 2 `binary_direct`** — binary → AI emits raw machine-code bytes or
   same-length byte edits → strict validator → existing writer patches directly
   → patched binary.  **No assembly text and no decompiled-C round trip.**

Both paths end in the same deterministic reparse/runtime/gate; AI cannot promote
a failed/incomplete gate.  The previous prototype names `ai_plan`/`ai_bytes` are
internal-only and are no longer in `AI_PATHS`, the API contract or the UI.

Scripted acceptance evidence (`artifacts/ai-direct-binary-2026-11-13/`) contains
11 positive records on macOS (9 on Linux where Mach-O native is skipped):
asm_roundtrip for ELF i386/x86_64/arm64, and binary_direct for PE x86-64/arm64,
ELF i386/x86_64/arm64, ELF i386 memcpy, plus **Mach-O x86-64/arm64 native
verified** on macOS.  The no-op injected guard is rejected by the gate.

**No AI increment is measured.**  The scripted model is a deterministic stand-in;
direct-path candidates coincide with the v5 deterministic baseline, and
assembly-path candidates differ in representation but do not prove extra
vulnerability coverage.  A real-provider, gate-blind/PoC increment experiment
remains future work.  Do not claim "AI repaired arbitrary binaries" or
"AI increment demonstrated."

## 7. Real-provider, PoC gate and gate blind spots (2026-11-13 follow-up)

- **PoC-style differential gate**: when the original runtime is available, the
  gate now requires `poc.original_fails` and `poc.candidate_passes` for the
  same capacity/input probe.  This is function-level runtime differential, not
  full guest PoC replay.  Reports include `verification.packet.poc`.
- **Gate blind-spot experiment**: 4/5 structurally valid but semantically
  deviant candidates are caught after hardening (destination fill, edit
  restriction); one residual blind spot remains (stdout/`puts` side effect).
  Evidence: `artifacts/gate-blind-spots-2026-11-13/`.
- **Real-provider experiment**: provider configured (DeepSeek model), six tasks:
  **3/6 AI verified vs 6/6 deterministic baseline; 0 coverage increments**.
  Failures recorded honestly (one assembly runtime rejection, two direct
  validator rejections).  Evidence: `artifacts/ai-real-provider-2026-11-13/`.
- This still does **not** answer "AI increment" on cases the deterministic
  baseline cannot repair; a gate-blind/PoC benchmark on those cases is the next
  concrete experiment.

## 8. Final local verification

- macOS 13.5 arm64: **1143 tests, 0 failed, 0 errors, 7 skipped** (307.4 s).
- Linux VM Ubuntu 24.04 arm64: **1143 tests, 0 failed, 0 errors, 10 skipped** (288.2 s).
- `scripts/verify_evidence.py`: 11 fixture rows + 110 source rows PASS;
  v5 bundle 38 files PASS; AI bundle 9 files PASS.
- CI: [43457857951](https://github.com/chenfanaichifan/binary-repair/actions/runs/43457857951)
  on `4ee5e5d` — **success** (hard-case AI benchmark, native PoC, static syntax
  and robustness gates; clang installed for path 1).  This record is a docs-only
  follow-up; the workflow re-runs the same suite.


## 9. Hard-case AI increment benchmark

Initial two-case benchmark (`artifacts/hard-case-benchmark-2026-11-13/`):
deterministic baseline 0/2; real-provider AI 1/2 (inline byte-loop case
verified by native PoC), CWE121 semantic case failed at the leaf-only assembly
validator.  This is the first measured hard-case increment, not a general claim;
expanding the benchmark and implementing paradigm A remain open.  Candidate and
PoC evidence are hashed in the bundle; raw provider response is not stored.
