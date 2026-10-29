# dist

- `m5-routeb-kit-2026-10-22-v6.zip` — Gate 4 kit for `toolchain-v4-ready`
  (jobwrap root -> setuid 1003, netns, no_new_privs, fixed argv). Embeds canonical
  contract `24bfe568…4e37`. Defaults: `PYTHON=/opt/angr-venv/bin/python`,
  `GHIDRA_HOME=/opt/ghidra_12.1.4_PUBLIC`, `CLANG=clang`, `LLD=ld.lld`; per-job
  symlinks cover Patcherex2's literal `clang-15`/`ld.lld-15` names. SHA-256 in
  `...v6.zip.sha256`. v5 is withdrawn (stale contract copy).
- `m5-routea-c4a159-2026-10-22.zip` — Route A candidate handoff: candidate ELF,
  original ELF, corrected six-entry contract, edit manifest, audit, 6/6 result,
  readelf audit, stdlib-only `regen_c4a159.py`. SHA-256 in
  `...c4a159...zip.sha256` (current `957d73d4…c108e`).
