# Gate 4 — Route B unchanged round trip: PASS (supplementary); formal: NOT RUN (scripts ready)

**Date:** 2026-10-22
**Run:** GitHub Actions `gate4-routeb-roundtrip`, run `39752557610`
(`https://github.com/chenfanaichifan/binary-repair/actions/runs/39752557610`)
**Result (supplementary):** **6/6 behaviour-identical; gate4_pass = true.**
This is the unchanged round trip only — **not a repair**.

> **Formal acceptance status: NOT RUN** on the member3-provided disposable
> Ubuntu VM/snapshot with network disabled. The run below is a supplementary run
> on GitHub Actions `ubuntu-24.04`: disposable, but network is available during
> installation and it is not the team VM. Do not mark formal Gate 4 PASS until
> member3 provides the VM or explicitly accepts this runner profile.
> See [11-gate4-formal-checklist.md](11-gate4-formal-checklist.md).
>
> **Latest coordination (2026-10-22):** the scripts are now on `main` @ `3d6e703`
> and the `toolchain-v4-ready` snapshot is ready; the earlier “missing scripts”
> blocker is cleared. Formal Gate 4 is still **NOT RUN**: it must be executed on
> the snapshot with the v3 kit, and M4 must confirm image hash/version/smoke.
> The supplementary CI pass remains evidence, not a formal pass.
>
> | Script | SHA-256 |
> |---|---|
> | `routeb/gate4_runner.sh` | `515c4d609495dea723c6fe6ff9e55b34fca078a3bf450770ebb3c744f07bd357` |
> | `routeb/probe_patcherex2.py` | `35751f6ea8a53724721d06d7a16127aa3e87bc7e88cc0eae9b5b61067d82a379` |
> | `routeb/verify.py` | `851d3ff4c80f6cbbbc766d43d1d838dd991b0f802e0bb8de09f73132f44bd0df` |
> | `routeb/run_manifest_compare.py` | `c0bc45e39b0b74ca7815ac623c2784d4105caf0f5a44f2076b42b11854b8c427` |
>
> Kit: `dist/m5-routeb-kit-2026-10-22-v6.zip`,
> SHA-256 `499f510c9fda660826ea6b7f5b1969839334ba7cd63cc0c975a1e4ca951e4b1d`.
> Invocation: `jobwrap ... -- /path/to/repo/routeb/gate4_runner.sh /path/to/repo /var/tmp/gate4-work`
> (no `sudo -u runner jobwrap`).
>
> **Formal execution decision (2026-10-22): route A.**
> M5 does **not** enter the VM and gets no SSH/network. M3 executes the formal run
> in the isolation-ready snapshot with hardened jobwrap; M5 performs **independent
> judging only**; M4 independently verifies image hash, tool versions, and
> isolation. M5's GitHub Actions 6/6 remains supplementary.
>
> **Contract pin:** canonical contract is
> `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37` (six edits;
> CET/seccomp assumptions explicit). v6 embeds this contract; v5 is withdrawn.
> M4 signs `24bfe568…4e37`.
>
> Required raw artifacts (M3 pushes them to branch `member-3/gate4-evidence`,
> path `routeb/out/gate4/`; M5 reads, M4 verifies):
> `gate4-status.json`, `readelf.txt`, `manifest-compare.json`, `environment.txt`,
> `isolation-manifest.txt`, `ghidra.log`, `patcherex2.log`, `compare.log`.
> No formal pass until all are present and M4 signs the isolation/image check.

## 1. Identity

| Item | Value |
|---|---|
| Original | `fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf`, 26,792 B |
| Original SHA-256 | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| Round-trip SHA-256 | `decdcdb821bfe4c41a070b0a23a2f6497f46a92f439cb02a1e4139a82cde954b` |
| Round-trip size | 26,792 B (same as original) |
| Function | `CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink` @ `0x4012b0`, 104 B |

## 2. Environment (recorded for V5)

```text
Linux 7.0.0-1017-azure x86_64 (ubuntu-24.04 runner)
JDK 21.0.12.1 (Temurin)
Ghidra 12.2 PUBLIC (2026-10-16 build)
Patcherex2 0.2.14
gcc 13.3.0
Python 3.12.3
```

The workflow installs `clang-15` and `ld.lld-15` symlinks for Patcherex2's compiler
backend, makes the ELF executable, and runs on a disposable GitHub-hosted runner.

## 3. Procedure

1. Ghidra headless export of `badSink`:
   `routeb/ghidra/export.sh ... <badSink> routeb/out/gate4`.
2. Normalize types/names into
   `routeb/experiment/samples/juliet_badSink.normalized.c`; the raw Ghidra output
   and `.meta.txt` are kept as evidence.
3. Patcherex2 `ModifyFunctionPatch` replaces the function with the **unchanged**
   normalized C; no behaviour edit.
4. `routeb/run_manifest_compare.py` runs the frozen 6-case manifest on the original
   and the round-trip binary and compares exit code, stdout and stderr byte-for-byte.

## 4. Result

| Case | Kind | Input | Original | Round trip | Same |
|---|---|---|---:|---|---|
| valid-empty | valid | 0 B | exit 0, `\n` | exit 0, `\n` | yes |
| valid-smallest | valid | 1 B | exit 0, `A\n` | exit 0, `A\n` | yes |
| valid-typical | valid | 10 B | exit 0, `A…\n` | exit 0, `A…\n` | yes |
| valid-maximum | valid | 49 B | exit 0, `A…\n` | exit 0, `A…\n` | yes |
| invalid-first | invalid | 50 B | exit 0, silent overflow | exit 0, silent overflow | yes |
| invalid-longer | invalid | 100 B | SIGSEGV (-11) | SIGSEGV (-11) | yes |

The original is **4/6** on the repaired oracle (the two invalid cases fail); the
round trip reproduces exactly that 4/6. That is the gate 4 criterion.

## 5. What this proves / does not prove

Proves:

- Ghidra export → normalization → Patcherex2 function replacement works on this
  real Juliet ELF;
- the round trip preserves exit code/stdout/stderr on all six frozen cases;
- the toolchain versions and runner profile are recorded for V5.

Does not prove:

- that an **edited** candidate repairs the defect (V3 repair is separate);
- Route A feasibility (gate 3 still needs a scope ruling);
- symbolic security (V4);
- behaviour outside the six frozen cases.

## 6. Evidence files

| File | Purpose |
|---|---|
| `routeb/out/gate4/manifest-compare.json` | machine-readable 6/6 result |
| `routeb/out/gate4/CWE121…badSink.c` | raw Ghidra output (evidence, never edited) |
| `routeb/out/gate4/CWE121…badSink.c.meta.txt` | entry/size/signature/callees |
| `routeb/out/gate4/roundtrip.elf` | patched ELF, SHA-256 `decdcd…` |
| `routeb/out/gate4/environment.txt` | OS/JDK/Ghidra/Patcherex2 versions |
| `routeb/out/gate4/ghidra.log`, `patcherex2.log`, `compare.log` | commands and diagnostics |
| `.github/workflows/gate4.yml` | reproducible run |

## 7. Reproduce

Push to `member-5/gate4-ci` (workflow trigger) or run the steps manually on a
disposable Ubuntu 24.04 VM with JDK21 + Ghidra 12.2 + Patcherex2. The workflow
force-pushes `gate4-results` with the evidence.

## 8. G0–G9 coverage (as of 2026-10-22)

| Gate | Status | Evidence / blocker |
|---|---|---|
| G0 identity | PASS | original SHA-256, size 26,792, ELF x86-64; recorded in `manifest-compare.json` |
| G1 contract + frozen manifest | PASS | `tests/test_fixture_v3_manifest.py`; contract v2 50/49; manifest-set hash `a564f039…` |
| G2 Ghidra export | PASS | Ghidra 12.2 raw C + `.meta.txt` in `routeb/out/gate4/` |
| G3 Route A | **BLOCKED** | needs scope ruling for new R--/R-X segments; plan in `07-route-a-trampoline-plan.md` |
| G4 Route B unchanged round trip | **formal NOT RUN (supplementary PASS)** | decision A: M3 executes, M5 judges, M4 verifies; v6 kit + raw artifacts pending on `member-3/gate4-evidence` |
| G5 placement | PARTIAL | Route B replaced a same-size function; Route A layout audit not run |
| G6 concrete crash | PASS (partial) | `06-gate6-evidence.md`; 100 B → SIGSEGV at `ret 0x401317` |
| G6 symbolic (V4) | **BLOCKED** | angr/Z3/V4 toolchain absent |
| G7 fixed repair | NOT RUN | depends on G3/G4 fixed candidate |
| G8 acceptance | NOT RUN | depends on G7 |
| G9 report | this document | — |

Gate 4 is therefore a real round-trip pass, not a full G0–G9 repair claim.
