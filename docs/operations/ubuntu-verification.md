# Ubuntu verification baseline

The canonical non-browser baseline is the Ubuntu 24.04 GitHub Actions run, not
the macOS host. The macOS host can miss GNU `readelf`, which makes the Route B
independent-view count differ; Ubuntu installs `binutils` and is the acceptance
environment for this baseline.

## CI history (corrected)

The direct-ELF review feature was first verified at `df82b6c`:

```text
commit:   df82b6c40d78b5eb643a16e0123e10a76b44475a
run:      https://github.com/chenfanaichifan/binary-repair/actions/runs/43248205593
result:   success
```

A later documentation-only commit was **not** green, despite an earlier draft of
this page saying it was:

| Commit | Run | Claimed then | Actual |
|---|---|---|---|
| `df82b6c` | [43248205593](https://github.com/chenfanaichifan/binary-repair/actions/runs/43248205593) | success | **success** |
| `5d8d006` | [43248395728](https://github.com/chenfanaichifan/binary-repair/actions/runs/43248395728) | success | **success** |
| `a436b64` | [43248544193](https://github.com/chenfanaichifan/binary-repair/actions/runs/43248544193) | success | **failure** |
| `9a451fd` | [43249875815](https://github.com/chenfanaichifan/binary-repair/actions/runs/43249875815) | success | **success (docs-only; flake did not reproduce)** |
| `774c584` | [43256190605](https://github.com/chenfanaichifan/binary-repair/actions/runs/43256190605) | — | **success (compiler-timeout fix)** |
| `aa580bb` | [43256481655](https://github.com/chenfanaichifan/binary-repair/actions/runs/43256481655) | — | **success (counts published)** |
| `0fe9241` | [43256887551](https://github.com/chenfanaichifan/binary-repair/actions/runs/43256887551) | — | **success: 889 passed / 1 skipped / 0 failed** |

### What failed at `a436b64`

The failing step was **Run non-browser test suite**; the targeted fixture
staging regression passed. The failure was:

```text
tests/test_c_overflow_patterns.py::test_five_c_buffer_overflow_shapes_are_detected_and_patched
AssertionError: assert '<same source>' != '<same source>'
```

Root cause: `_finalize_patch` runs `clang -fsyntax-only` on the rule-generated
C patch. On that runner the compiler call hit its timeout / an OS-level
infrastructure failure. `validate_c_patch` treated that as a rejected patch, so
`_finalize_patch` reverted the off-by-one patch to the original source. The test
then saw `patched_code == original` even though the rule had detected the
off-by-one. The failure was therefore a **transient compiler-infrastructure
failure presented as a functional test failure**, not a regression caused by
the documentation commit.

This also explains green -> red -> green between docs-only commits: the
compiler timeout is load-dependent and not deterministic.

### Fix

- `validate_c_patch` now treats an installed-compiler timeout/OS error as
  **unavailable**, not as proof that the patch is invalid; static checks still
  apply. A real non-zero compiler exit still rejects.
- The compiler timeout was raised from 8 s to 20 s.
- `_finalize_patch` records `patch_validation="compiler_unavailable"` and an
  explicit note instead of silently reverting.
- Regression tests simulate the timeout and a real compiler error without
  invoking the host compiler.

The post-fix Ubuntu runs are green:

```text
fix:     774c584
run:     https://github.com/chenfanaichifan/binary-repair/actions/runs/43256190605
result:  success

counts:  aa580bb
run:     https://github.com/chenfanaichifan/binary-repair/actions/runs/43256481655
job:     https://github.com/chenfanaichifan/binary-repair/actions/runs/43256481655/job/131315970646
result:  success

final:   0fe9241
run:     https://github.com/chenfanaichifan/binary-repair/actions/runs/43256887551
job:     https://github.com/chenfanaichifan/binary-repair/actions/runs/43256887551/job/131317401154
counts:  889 passed / 1 skipped / 0 failed / 890 total
result:  success
```

From `774c584` onward the workflow also publishes a public
`Ubuntu test counts` check annotation and job-summary counts for the fixture
regression and the full suite, including skip reasons; `aa580bb` adds the
explicit notice and corrected history. Earlier green runs,
including the `df82b6c` feature run, remain valid for what they covered, but
`a436b64` is **not** evidence of a green full suite.

The earlier pinned baseline (before the review feature) remains:

```text
commit:   bb21913c39a04d9e5777a2aed269b5a038398112
run:      https://github.com/chenfanaichifan/binary-repair/actions/runs/43246391510
result:   success (all non-browser tests passed)
```

Recorded baseline evidence:
[`docs/acceptance/evidence/ubuntu-bb21913/`](../acceptance/evidence/ubuntu-bb21913/README.md).

## Commands

Targeted fixture permission regression:

```bash
python -m pytest -q -vv \
  tests/test_fixture_v3_manifest.py::test_original_is_v0_on_invalid_inputs_if_binary_present
```

Full non-browser suite (never `-x`; the rest of the suite must run even if one
case fails):

```bash
python -m pytest -q --ignore=tests/e2e \
  --junitxml=artifacts/ubuntu-verification/junit.xml
```

The workflow runs the targeted step first and the full suite with
`if: always()`, so a targeted failure still produces a complete-suite result.
Both logs are uploaded with the `ubuntu-verification` artifact.

## Skip reasons

The four macOS skips are:

```text
tests/test_fixture_v3_manifest.py::test_original_is_v0_on_invalid_inputs_if_binary_present
  Linux ELF execution; runs on Ubuntu
tests/test_fixture_v3_manifest.py::test_repaired_candidate_matches_v3_if_provided
  requires BINARYREPAIR_CANDIDATE_ELF; remains skipped on Ubuntu
tests/test_native_linux_runtime.py::test_vulnerable_fixture_native_linux
  Linux ELF execution; runs on Ubuntu
tests/test_native_linux_runtime.py::test_strict_fixture_native_linux_blocks_long_input
  Linux ELF execution; runs on Ubuntu
```

On Ubuntu the fixture V0 test and the two native runtime tests run; only the
optional candidate-env test stays skipped. The job summary and JUnit artifact
report the exact pass/skip/fail counts.

## Fixture staging rule

The checked-in CWE121 `original.elf` is evidence, not a test executable. Git may
track it as `100644` or `100755` depending on history, and an Ubuntu checkout
then raises `PermissionError` if a test launches it in place.

`tests/test_fixture_v3_manifest.py` therefore writes a **0644** copy into
`tmp_path`, stages another copy with `chmod 0755`, verifies the bytes and hash,
and executes only the staged copy. The regression starts from 0644 even if the
repository currently marks the fixture executable. No test mutates the checked-in
fixture or depends on its Git mode.

## Artifacts

The Actions artifact `ubuntu-verification` contains:

```text
junit.xml
pytest.log
fixture-regression.log
environment.txt
environment.json
pip-freeze.txt
SHA256SUMS
```

Downloading the artifact requires GitHub authentication. The committed evidence
records the run URL, head SHA, command and step outcomes.

## Scope

This verifies the non-browser suite on Ubuntu. It does not prove PE/Mach-O
semantic repair, isolated guest execution, or broad ELF coverage. Those remain
separate claims.
