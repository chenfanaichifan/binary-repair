# Ubuntu verification evidence

Pinned commit:

```text
3400a13f26836e809ca3cff67929ee6f5189dc9a
```

GitHub Actions run:

```text
https://github.com/chenfanaichifan/binary-repair/actions/runs/43244713385
```

Result:

```text
conclusion: success
runner: ubuntu-24.04
python: 3.11
command: pytest -q --ignore=tests/e2e
```

All recorded workflow steps passed, including:

```text
Install system tools
Install Python dependencies
Run non-browser test suite
Capture environment
Checksums
Upload verification evidence
```

The Actions artifact `ubuntu-verification` contains `junit.xml`, `pytest.log`,
`environment.txt`, `environment.json`, `pip-freeze.txt`, and `SHA256SUMS`.
Downloading that artifact requires GitHub authentication.

## Why the macOS failure disappeared

The local macOS failure was:

```text
tests/test_routeb_executor.py::test_static_routeb_bundle
assert len(independent-views) in (0, 5)
actual: 1 (objdump only)
```

The host had `objdump` but no `readelf`, so only one independent view was
generated. The Ubuntu workflow installs `binutils`, which provides both
`readelf` and `objdump`; the full suite then passed.

This was a host-tooling failure, but it was **not** dismissed as “known
environmental” without a real Ubuntu run. The Ubuntu run is the evidence.

## Scope

This verifies the non-browser suite on Ubuntu. It does **not** prove:

- PE/Mach-O semantic repair;
- GOT/PLT relocation correctness;
- binary `sprintf`;
- UAF/integer/loop repair;
- real guest execution.

Guest status remains `not_verified`.
