# M5 Route B / Gate 4 kit (v6)

**Formal Gate 4: NOT RUN.** GitHub Actions 6/6 is supplementary only. M3 runs
this kit in the isolation-ready snapshot; M5 judges; M4 verifies image/tools.

## Canonical inputs

- `contract.json` canonical `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37`
- `original.elf` SHA-256 `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`
- runner SHA-256 `e49a88799e4daaff22832f59ca82d2fa3d41dd7bce1910db3312cade813adfb3`

## Environment

```bash
export PYTHON=/opt/angr-venv/bin/python
export GHIDRA_HOME=/opt/ghidra_12.1.4_PUBLIC
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export CLANG=clang
export LLD=ld.lld
```

Patcherex2 0.2.14 calls literal `clang-15`/`ld.lld-15`; the runner creates
per-job symlinks to `$CLANG`/`$LLD`, prepends PATH, records actual versions.
Clang 18.1.3 is supported.

## Run

```bash
jobwrap ... -- /path/to/repo/routeb/gate4_runner.sh \
  /path/to/repo /var/tmp/gate4-work
```

Never `sudo -u runner jobwrap`; never `unshare` inside the runner. The runner
checks uid 1003, ELF SHA-256, tools, then Ghidra export → Patcherex2 unchanged
round trip → six-case compare. It writes `gate4-status.json` = `pass` / `fail` /
`not_run`.

## Six cases

| id | argv[1] | expected |
|---|---|---|
| valid-empty | `""` | rc 0, stdout `0a`, stderr empty |
| valid-smallest | `"A"` | rc 0, stdout `410a` |
| valid-typical | `"AAAAAAAAAA"` | rc 0, stdout 10×`41` + `0a` |
| valid-maximum | 49×`A` | rc 0, stdout 49×`41` + `0a` |
| invalid-first | 50×`A` | rc 1, stdout empty, exact 42 B stderr |
| invalid-longer | 100×`A` | rc 1, stdout empty, exact 42 B stderr |

`manifest-compare.json` must contain `same_count=6,total=6,gate4_pass=true`.
`gate4-status.json` contains `gate4`, `reason`, `uid`, `expected_uid`,
`elf_sha256`, `patched_sha256`, `manifest_compare`, `environment`.
