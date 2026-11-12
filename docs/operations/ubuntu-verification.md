# Ubuntu verification baseline

The canonical non-browser baseline is the Ubuntu 24.04 GitHub Actions run, not
the macOS host. The macOS host can miss GNU `readelf`, which makes the Route B
independent-view count differ; Ubuntu installs `binutils` and is the acceptance
environment for this baseline.

## Current recorded run

```text
commit:   bb21913c39a04d9e5777a2aed269b5a038398112
run:      https://github.com/chenfanaichifan/binary-repair/actions/runs/43246391510
runner:   ubuntu-24.04
python:   3.11
command:  python -m pytest -q --ignore=tests/e2e
result:   success (all non-browser tests passed)
```

The recorded evidence is in
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
