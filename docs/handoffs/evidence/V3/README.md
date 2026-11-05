# V3 — Route A behaviour verification (2026-11-05)

**Result: the vulnerability is real on the original, and the Route A candidate
repairs it — byte-exact.**

This is the "last step" that earlier rounds left `not_run`. It answers the only
question that actually matters for a repair claim: *does the binary behave
differently, and does it behave exactly as the reviewed contract says?*

## 1. Method

Two binaries, one frozen test matrix, one guest session:

| Binary | sha256 | Role |
|---|---|---|
| `original.elf` | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` | pre-repair control |
| `route_a/candidate.elf` | `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` | Route A repair candidate |

The guest observer (`workers/broker/guest_behaviour.py`) executed each manifest
case with the binary placed under the exact basename the manifest expects
(`./original`), captured **raw bytes** for stdout/stderr, and recorded a signal
death as the shell convention `128+N`. It judged nothing.

The host then evaluated those observations with the frozen oracle
(`tests/v3_oracle.py`), which is a pure function: observations in, verdict out.
The guest never decides.

## 2. Measured results

### Original — `failed`, 4 / 6

| Case | Kind | Expected | Measured |
|---|---|---|---|
| `valid-empty` | valid | rc 0, `"\n"` | as expected |
| `valid-smallest` | valid | rc 0, `"A\n"` | as expected |
| `valid-typical` | valid | rc 0, 10×A | as expected |
| `valid-maximum` | valid | rc 0, 49×A | as expected |
| **`invalid-first`** | invalid | rc 1, empty stdout, exact stderr | **rc 0**, stdout = 51 bytes (`50×A + "\n"`), stderr empty |
| **`invalid-longer`** | invalid | rc 1, exact stderr | **rc 139** (= 128 + SIGSEGV), stderr empty |

The 50-byte case is the important negative: the program **exits successfully**
while writing one byte past a 50-byte object. A crash is not the only violation
— the absence of a defined rejection is the other half. The 100-byte case dies
with SIGSEGV, matching the fixture provenance.

### Candidate — `passed`, 6 / 6

All four valid cases reproduce the original's output byte for byte, and both
invalid cases now return rc 1 with stdout empty and stderr exactly
`ERROR: input exceeds destination capacity\n` (42 bytes, trailing newline
included).

## 3. Why this is not a rubber stamp

The oracle's own suite (24 tests, all passing) includes the negative controls
that would catch a permissive verifier:

- `test_wrong_return_code_fails`
- `test_missing_trailing_newline_in_stderr_fails` — one missing `\n` is a failure
- `test_extra_stdout_on_the_invalid_path_fails` — one stray byte is a failure
- `test_missing_observation_is_not_run_never_passed` — absent evidence degrades, never blesses
- `test_vulnerable_original_scores_four_of_six` — and the original **did** score 4/6 here

## 4. Files

| File | Content |
|---|---|
| `original-observations.json` | Raw guest observations for `original.elf` (rc, stdout/stderr as hex) |
| `candidate-observations.json` | Raw guest observations for the candidate |
| `verdict.json` | Oracle output for both, plus the conclusion |
| `environment.txt` | Build/session provenance |
| `SHA256SUMS` | Hashes of the above |

Re-judge from the observations alone:

```bash
python - <<'PY'
import json, sys
sys.path.insert(0, 'fixtures/public/CWE121_src_char_declare_cpy_51b/tests')
import v3_oracle as O
T='fixtures/public/CWE121_src_char_declare_cpy_51b/tests'
d=json.load(open('docs/handoffs/evidence/V3/candidate-observations.json'))
obs={c['case_id']: O.Observation(c['return_code'], bytes.fromhex(c['stdout_hex']),
                                 bytes.fromhex(c['stderr_hex'])) for c in d['cases']}
print(O.evaluate_files([f'{T}/valid.json', f'{T}/invalid.json'], obs).result)
PY
```

## 5. What this does and does not establish

**Does:** within the frozen test domain, the candidate changes behaviour exactly
as the contract requires, and the original demonstrably violates it. Both halves
are measured on the same machine in the same session, so the comparison is
like-for-like.

**Does not:** prove the absence of other defects outside the six frozen cases
(no V4 symbolic check was run here), and does not constitute Gate 6. The public
fixture is a NIST Juliet case, so a model may have recognised the pattern from
training data — that limitation travels with any result on this fixture
(provenance §11).
