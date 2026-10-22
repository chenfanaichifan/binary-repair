# 06 — M4 independent Gate 3 audit (retargeted to canonical main)

**Status:** implementation + tests on branch `member-4-routea-gate3` based on main
`ad1a1f8`; **not executed on the host** (ELF tests are guest/CI only). This is
review material for M5, not gate-3 evidence.

## What changed after the M5 review (`docs/route-b/20-m4-patch-review.md`)

| Finding | Fix |
|---|---|
| B1 old contract `ba33b4d0…` | removed `contract.route-a-v1.json`; the audit/bundle consume the canonical `fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json` (`24bfe568…`) |
| B2 old candidate `f3cb9cbb…`/fprintf | goldens and code shape retargeted to canonical `c4a159…` / `write(2)`+`exit_group`; no `fprintf`, no `sub rsp,8`, two syscalls |
| B3 pyelftools enum crash | `routea/facts.py` keeps header enums as pyelftools strings; no `int()` on `EI_CLASS`/`e_version` |
| B4 cave rejected at original memsz end | `cave_unused_audit` audits the **extended** RX segment (`inside_extended_rx_load`, `cave_within_extended_memsz`) and proves the cave was beyond the original `p_filesz`; adds `cave_inside_one_page` |
| B5 no-op diff test | explicit `candidate_differs_from_original` check; the unpatched binary now fails that check (and `redirect_bytes_written`), not the residue audit |
| B6 VM helper old identity | `scripts/routea_vm_check.sh` rewritten for `ad1a1f8`, `c4a159…`, `24bfe568…`, `routea.gate3` |

## Added files

- `routea/byteaudit.py` — dependency-free interval/residue audit (pure, no ELF).
- `routea/facts.py` — read-only ELF fact extraction (segments, sections, symbols,
  relocations, dynamic, CET property, tool versions).
- `routea/audit.py` — independent static audit: header invariants, section/dynamic
  byte identity, NX/GNU_STACK/RELRO/W^X, cave-unused proof, added-code rules,
  changed-byte/residue audit, optional independent `readelf -lW` cross-view.
- `routea/evidence.py` — static evidence bundle (candidate/original, manifest,
  audit, reproducibility, environment fingerprint, readelf/objdump views, record,
  `SHA256SUMS`; items 4-5 stay `not_run`).
- `routea/gate3.py` — CLI: `python -m routea.gate3 bundle|audit`.
- `tests/test_routea_byteaudit.py` — pure-byte tests.
- `tests/test_routea_audit.py` — canonical-candidate audit tests (golden
  `c4a159…`, contract `24bfe568…`, B4/B5 regressions).
- `scripts/routea_vm_check.sh` — guest static-half runner (stops before execution).

## Commands (guest/CI)

```bash
CASE=fixtures/public/CWE121_src_char_declare_cpy_51b
python -m pytest tests/test_routea_byteaudit.py tests/test_routea_manifest.py \
  tests/test_routea_cave.py tests/test_routea_audit.py -q -p no:cacheprovider
python -m routea.gate3 bundle --original $CASE/original.elf \
  --contract $CASE/contract.json --out-dir var/jobs/m4-gate3/<run>/static
```

Expected: tests green (actual count recorded, not asserted from prose); candidate
`c4a159…aa82`; contract `24bfe568…4e37`; bundle `SHA256SUMS` verifies; record
items 4-5 `not_run`.

## Not claimed

No candidate was executed; the runtime cave probe, six-case run, original V0 and
isolation evidence remain M3/VMer work (handoff 16/17). Gate 3 stays
`CONDITIONALLY FEASIBLE`; this branch is review material, not canonical code.
