# Ubuntu verification evidence (final)

Pinned commit:

```text
bb21913c39a04d9e5777a2aed269b5a038398112
```

GitHub Actions run:

```text
https://github.com/chenfanaichifan/binary-repair/actions/runs/43246391510
```

Result:

```text
conclusion: success
runner: ubuntu-24.04
python: 3.11
command: pytest -q --ignore=tests/e2e
```

All test and evidence steps passed:

```text
Install system tools
Install Python dependencies
Run fixture staging regression
Run non-browser test suite
Capture environment
Checksums
Upload verification evidence
```

The workflow installs `binutils` and runs a native Linux x86-64 fixture test in
addition to the Unicorn and structural checks. It also includes a fixture
staging regression step.

The Actions artifact `ubuntu-verification` contains `junit.xml`, `pytest.log`,
`environment.txt`, `environment.json`, `pip-freeze.txt`, and `SHA256SUMS`.
Downloading it requires GitHub authentication.

## macOS failure resolution

The previous macOS-only failure was:

```text
tests/test_routeb_executor.py::test_static_routeb_bundle
assert len(independent-views) in (0, 5)
actual: 1 (objdump only)
```

The host lacked `readelf`. Ubuntu installs `binutils`, producing all five
independent views, and the suite passed.

A separate real issue was also fixed: ELF fixtures were committed without
executable permission. Ubuntu raised:

```text
PermissionError: .../fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf
```

The executable bits were committed, and the next run passed.

## Scope

This verifies the non-browser suite and native Linux x86-64 fixture execution
on Ubuntu. It does not prove PE/Mach-O semantic repair, GOT/PLT repair, binary
`sprintf`, UAF/integer/loop repair, or isolated guest execution.
