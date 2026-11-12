# Ubuntu verification evidence (a971ffd)

```text
commit: a971ffd
run:    https://github.com/chenfanaichifan/binary-repair/actions/runs/43248090960
result: success
runner: ubuntu-24.04
```

All steps passed, including the fixture staging regression, the full non-browser
suite, native Linux x86-64 fixtures, checksums and artifact upload.

This run includes the PE strcat/memcpy, Mach-O `__brfix` cave, ELF relocation
audit and `/api/binary/scan` + `/api/binary/repair` routes.

The Actions artifact `ubuntu-verification` contains `junit.xml`, `pytest.log`,
`fixture-regression.log`, `environment.*`, `pip-freeze.txt` and `SHA256SUMS`.
Download requires GitHub authentication.

Scope: non-browser suite and native Linux x86-64 fixture execution. PE/Mach-O
runtime, binary `sprintf`, UAF/integer/loop and isolated guest remain separate.
