# 78 — M3/M5: Gate 5 Route A successor delivery (binary + source traceability + sanitized log)

**From:** M3+M5 (evidence owner)
**To:** M4 (verifier), Lead
**Date:** 2026-10-31 (Asia/Hong_Kong)
**Re:** M4's two blockers — successor binary not shipped, source commit `ac96e74` not reachable.

## 1. What changed this round

| M4 blocker | Disposition |
|---|---|
| successor binary not shipped; `90af91ef…ff20` was only a MESSAGE claim | **Shipped.** `docs/handoffs/evidence/Gate5/successor/jobwrap-gate5` (raw ELF) + its `sha256sum` line in the top-level `SHA256SUMS` (see §4). |
| `ac96e74` not reachable / not on main | **Pushed.** `ac96e74` and the successor chain are now on `origin/member-3-route-a` (this commit). Source `route-a/jobwrap-gate5/jobwrap_gate5.c` is traceable via `git show ac96e74`. |
| `gdb-probe.log` leaks `/home/lab/evaluator/src/` | **Sanitized.** The evaluator source prefix is replaced with `<REDACTED>/`; function name / line numbers unchanged. See §5. |

## 2. Successor binary — exact identity (raw sha256sum)

```
90af91ef6b238428d202f891e5829ed81733b76dd9e7f184acd91f4cd769ff20  successor/jobwrap-gate5
```

- File: `docs/handoffs/evidence/Gate5/successor/jobwrap-gate5`
- Source: `route-a/jobwrap-gate5/jobwrap_gate5.c` @ commit `ac96e74`, sha256 `09900e3ae11d8ad2f79faa7c67391a5b00f0f89b9a3f267535b9757ee3287340`
- Build: guest `gcc -O2 -Wall -Wextra -Werror -static` (recipe in `successor/build-recipe.md`)

## 3. Exact fixed argv

```
sudo /usr/local/sbin/jobwrap-gate5 probe m4-gate5 -- <repo-root> <work-dir>
```

After isolation, the successor `execv`s exactly (absolute paths, no shell, no PATH lookup):

```
/usr/bin/python3 <repo-root>/scripts/m4_gate5_probe.py <repo-root> <work-dir>
```

Observed values (from `invocation.txt`): `repo_root=/srv/gate5-build`,
`work_dir=/var/tmp/gate5-work`,
`probe=/srv/gate5-build/scripts/m4_gate5_probe.py`.

## 4. Wrapper / probe / subject hashes

| Object | SHA-256 |
|---|---|
| successor binary (wrapper) | `90af91ef6b238428d202f891e5829ed81733b76dd9e7f184acd91f4cd769ff20` |
| successor source `jobwrap_gate5.c` | `09900e3ae11d8ad2f79faa7c67391a5b00f0f89b9a3f267535b9757ee3287340` |
| probe `m4_gate5_probe.py` (compile-time pinned) | `f39a0302dd1aa42635da80fa4e9160d37a221f5ac383270add3eaedcffd146cb` |
| candidate `cave-probe.elf` | `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` |
| original `original.elf` | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |

## 5. Isolation controls (observed in `evidence/environment.txt`)

| Control | Observed value |
|---|---|
| Uid / Gid | `1003 1003 1003 1003` (all four) |
| CapEff | `0000000000000000` (0) |
| CapBnd | `000001ffffffffff` |
| NoNewPrivs | `1` |
| Seccomp | `2` (filter active) |
| default_route | `''` (rc=1, no egress) |
| netns | `net:[4026532222]` (isolated) |
| script_sha256 | `f39a0302…d146cb` (matches pin) |

Successor isolation order (from `jobwrap_gate5.c`): root-only → new netns + no-egress →
`setgroups` → `setgid(1003)` → `setuid(1003)` → `CapEff=0` → seccomp allow-list →
`NoNewPrivs=1` → rlimits → `clearenv` + minimal whitelist → fixed argv →
absolute paths → probe root-owned/non-writable → fail-closed (probe blob pinned at
compile time, does not read env).

## 6. Fail-closed negative test (raw, unchanged)

`fail-closed/`:
- `stderr.bin` = `jobwrap-gate5: probe blob mismatch: got 15ba41dcb2f3b9bd39a26347da75b7a483f77611c8957f78181c94b48e47d915, expected f39a0302dd1aa42635da80fa4e9160d37a221f5ac383270add3eaedcffd146cb`
- `exit-code.txt` = `1`
- `stdout.bin` = empty (0 bytes)
- `tampered-probe.sha256` = `15ba41dc…d915`

## 7. Sanitization note (hash change vs previous round)

Sanitizing `evidence/gdb-probe.log` changed two hashes from the previous (M4-received)
package. This is expected and is the point of the request:

| File | Before | After |
|---|---|---|
| `evidence/gdb-probe.log` | `261f4cce…26b8e` | `e4305d0f…86440` |
| `evidence/SHA256SUMS` (self-hash) | `05438764…73ec8` | `7aa79202…189e07c` |
| top-level `SHA256SUMS` (self-hash) | — | `02669336…4d1a71` |

The 29-line manifest self-hash M4 quoted earlier (`05438764…73ec8`) was the
pre-sanitize value. The sanitized manifest self-hash is `7aa79202…189e07c`.

> Note (LF fix): the first shipping of this package wrote the two `SHA256SUMS`
> with CRLF line endings, which breaks `sha256sum -c` (filenames gain a trailing
> `\r`). Both manifests were normalized to LF and the cross-reference line
> updated, so `sha256sum -c SHA256SUMS` now verifies 43/43 (top) and 29/29
> (inner) with zero FAILED. The two self-hashes above reflect the LF-normalized
> manifests.

## 8. Verification performed this round (self-verified, single agent)

- Top-level `SHA256SUMS`: 43 payload entries, re-hash **43/43 OK, 0 mismatch**.
- Inner `evidence/SHA256SUMS`: 29 entries, re-hash **29/29 OK**.
- Successor binary / source / probe / candidate / original: all five hashes match §4.
- Sanitization: `gdb-probe.log` now contains `0` occurrences of `evaluator` and `/home/lab`.

## 9. What is NOT claimed

- M4 has not yet independently re-hashed; `record 51` R1–R8 remains **UNSIGNED**.
- Gate 5 Route A stays **BLOCKED / NOT VERIFIED** until M4 signs.
- No `gate5_pass`, no final tag, fixture NOT FROZEN.

## 10. Signature

| Role | Name | Date | Statement |
|---|---|---|---|
| M3/M5 evidence owner | M3+M5 | 2026-10-31 | shipped binary + pushed `ac96e74` chain + sanitized log; self-verified 43/43 + 29/29 |
| M4 verifier | M4 | — | pending independent re-hash of record 51 R1–R8 |
| Lead | Lead | — | pending final tag decision |
