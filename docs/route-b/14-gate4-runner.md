# Gate 4 runner for jobwrap (uid 1003, no sudo, no unshare)

`routeb/gate4_runner.sh <repo-root> <writable-work-dir>` is the job command.
It assumes **jobwrap already ran as root, applied setuid 1003 and the no-egress
netns**. It never calls `sudo` or `unshare`; the broker must not use
`sudo -u runner jobwrap`.

It verifies:

- uid == 1003 (override with `EXPECTED_UID`);
- ELF SHA-256 `aa428157…8393`;
- Ghidra `analyzeHeadless`, `clang-15`, `ld.lld-15`;
- Patcherex2/angr/z3/LIEF versions (recorded, not enforced);
- Ghidra export → Patcherex2 unchanged round trip → 6-case manifest compare;
- writes `gate4-status.json` with `gate4` = `pass` / `fail` / `not_run`.

No network is used. If the checkout lacks the fixture or toolchain, it exits
`not_run`, not a fake pass. The `routeb/` scripts are in the repository and in
`dist/m5-routeb-kit-2026-10-22-v3.zip`.
