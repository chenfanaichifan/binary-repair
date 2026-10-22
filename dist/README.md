# dist

`m5-routeb-kit-2026-10-22-v4.zip` — Gate 4 kit for the `toolchain-v4-ready` VM
(jobwrap root -> setuid 1003, netns, no_new_privs, fixed argv).

Use `PYTHON=/opt/angr-venv/bin/python`,
`GHIDRA_HOME=/opt/ghidra_12.1.4_PUBLIC`. The runner writes `gate4-status.json`
with `pass` / `fail` / `not_run`; formal Gate 4 remains NOT RUN until M3 executes
and M4 verifies image/tools/isolation.

SHA-256 is in `m5-routeb-kit-2026-10-22-v4.zip.sha256`.
