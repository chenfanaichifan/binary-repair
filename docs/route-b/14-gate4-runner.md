# Gate 4 formal run — M3 executes, M5 judges, M4 verifies

**Formal status: NOT RUN.** The GitHub Actions 6/6 run is supplementary only.

Gate 4 has its own pass rule (`gate4-status.json=pass` + M4 environment
confirmation). Do **not** use the Gate 3 six-item matrix for Gate 4; that matrix
is only for Gate 3.

## Roles

| Role | Action |
|---|---|
| M3 | restore `toolchain-v4-ready` snapshot, root-start hardened jobwrap (setuid 1003, netns, no_new_privs, clear caps, fixed argv), execute this kit |
| M5 | judge the raw `gate4-status.json` / `manifest-compare.json` and report **pass / fail / NOT RUN** |
| M4 | independently verify tool versions, image hash/manifest, isolation evidence |

M5 does not enter the VM and never runs `sudo -u runner jobwrap`; jobwrap is
root-started and drops to uid 1003 itself.

## Interpreter and Ghidra

```bash
export PYTHON=/opt/angr-venv/bin/python          # default
export GHIDRA_HOME=/opt/ghidra_12.1.4_PUBLIC
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export CLANG=clang                               # default; snapshot has 18.1.3
export LLD=ld.lld                                # default
```

Expected versions: JDK 21.0.12.1, Ghidra 12.1.4, Patcherex2 0.2.14,
angr 10.0.4, z3 5.1.0, LIEF 1.0.0, clang 18.1.3, ld.lld 18.

Patcherex2 0.2.14 invokes the literal names `clang-15` and `ld.lld-15`. The
runner does **not** require those packages: it creates per-job symlinks
`$WORK/toolchain-shims/clang-15 -> $(command -v "$CLANG")` and
`ld.lld-15 -> $(command -v "$LLD")`, prepends that directory to `PATH`, and
records the real versions in `environment.txt`. No sudo/system install.

The previous GitHub Actions Gate 4 run used the same shim approach (Ubuntu
24.04 `clang` 18.1.3 symlinked as `clang-15`) and Patcherex2 0.2.14 completed
the unchanged round trip; the formal VM run records the exact versions.

## Entry point

```bash
jobwrap ... -- /path/to/repo/routeb/gate4_runner.sh /path/to/repo /var/tmp/gate4-work
```

The runner only calls `$PYTHON`, Ghidra, `python3`-free; it never calls
`sudo`/`unshare`, and exits `not_run` on uid/tool/ELF mismatch.

## Six cases

| id | argv[1] | expected |
|---|---|---|
| valid-empty | `""` | rc 0, stdout `0a`, stderr empty |
| valid-smallest | `"A"` | rc 0, stdout `410a`, stderr empty |
| valid-typical | `"AAAAAAAAAA"` | rc 0, stdout `41…0a`, stderr empty |
| valid-maximum | 49 × `A` | rc 0, stdout 49 × `41` + `0a`, stderr empty |
| invalid-first | 50 × `A` | rc **1**, stdout empty, stderr `4552524f…0a` (42 B) |
| invalid-longer | 100 × `A` | rc **1**, stdout empty, stderr same 42 B |

All six at once:

```bash
"$PYTHON" routeb/run_manifest_compare.py \
  --original "$WORK/original.elf" --patched "$WORK/roundtrip.elf" \
  --tests fixtures/public/CWE121_src_char_declare_cpy_51b/tests \
  --out "$WORK/manifest-compare.json"
```

`manifest-compare.json` shape:

```json
{"original_sha256":"...","patched_sha256":"...","cases":[...],
 "same_count":6,"total":6,"gate4_pass":true}
```

`gate4-status.json` shape:

```json
{"gate4":"pass|fail|not_run","reason":"...","uid":1003,
 "expected_uid":1003,"elf_sha256":"...","patched_sha256":"...",
 "manifest_compare":"/path/manifest-compare.json",
 "environment":"/path/environment.txt"}
```

Gate 4 is pass only when `gate4_pass=true` (same_count 6/6) **and** M4 accepts
the image/tool/isolation evidence. Otherwise the formal label is `fail` or
`NOT RUN`; never "should pass".
