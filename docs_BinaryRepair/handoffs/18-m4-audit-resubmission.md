# 18 — Resubmission: M4 independent audit retargeted to canonical main (B1–B6)

**Recipients:** Member 5 (reviewer), cc Member 4, Member 3, Lead
**From:** Member 4 (verification)
**Date:** 2026-10-22
**Status:** **re-submitted for review; not canonical, not gate-3 evidence.** No candidate has
been executed and no gate status changes (Gate 3 `CONDITIONALLY FEASIBLE`, Gate 4 `NOT RUN`,
fixture `NOT FROZEN`).
**Answers:** `docs/route-b/20-m4-patch-review.md` (M5, main `766499e`), findings B1–B6.

---

## 1. Resubmission identity

| Item | Value |
|---|---|
| Base commit (declared) | `ad1a1f8a482ed122b4bb14f9cead671fb9d2ffdf` (`origin/main` at review time) |
| Branch | `origin/member-4-routea-gate3` @ `2ac0f6662415346d9d5a4cb73d6dfe7898bea962` |
| Patch file | `docs/route-a/m4-patches/0002-member-4-routea-gate3-canonical-audit.patch` (79,800 B) |
| Patch SHA-256 | `b68aabcd57675e7814b65379ba79ee806d7ecb89f6d56db7e1f380ce9ee1cab8` |
| Apply check | `git apply --check` expected clean on `ad1a1f8` (same content as the branch diff) |

This supersedes the patch reviewed in `20-m4-patch-review.md`
(`4c2d480e…f142`, base `33235f5`). It is **additive tooling only**: it does not replace main's
canonical `routea/cave.py`, `routea/worker.py`, tests, contract, candidate, or `routea/out/`.

## 2. B1–B6 disposition

| # | Finding | Fix in this submission |
|---|---|---|
| B1 | old contract `ba33b4d0…` | no contract file is copied; everything consumes `fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json` (canonical `24bfe568…4e37`); the old `contract.route-a-v1.json` is gone |
| B2 | old candidate `f3cb9cbb…`/fprintf | goldens and code-shape checks retargeted to `c4a159…aa82` and the canonical `write(2)` + `exit_group(1)` code: `two_syscalls`, `write_syscall_setup`, `exit_group_status_1_setup`, `no_plt_call`, `no_stack_write`; the audit builds with the canonical `routea.cave` plan |
| B3 | pyelftools enum `int()` crash | `routea/facts.py` keeps `EI_CLASS`/`EI_DATA`/`e_type`/`e_machine`/`e_version` as the strings pyelftools returns; offsets/counts stay ints |
| B4 | cave rejected at original `p_memsz` end | `cave_unused_audit(original, patched, …)` audits the **extended** RX segment (`inside_extended_rx_load`, `cave_within_extended_memsz`), proves the cave was beyond the original `p_filesz` (`cave_not_file_backed_before_extension`), and adds `cave_inside_one_page` |
| B5 | no-op diff test expectation | explicit `candidate_differs_from_original` check; `test_unpatched_binary_fails_candidate_differs` asserts that check and `redirect_bytes_written` fail for `original == patched`, not the residue audit |
| B6 | VM helper hardcoded old identity | `scripts/routea_vm_check.sh` rewritten for `ad1a1f8`, `c4a159…`, `24bfe568…`, and `python -m routea.gate3 bundle`; it stops before executing the candidate |

## 3. Added files (additive)

```text
routea/byteaudit.py     dependency-free interval/residue audit (pure, no ELF)
routea/facts.py         read-only ELF facts (segments/sections/symbols/relocs/dynamic/CET/tools)
routea/audit.py         independent static audit + optional readelf cross-view
routea/evidence.py      static evidence bundle (items 4-5 always not_run)
routea/gate3.py         CLI: python -m routea.gate3 audit|bundle
tests/test_routea_byteaudit.py   pure-byte tests
tests/test_routea_audit.py      canonical-candidate audit tests (B4/B5 regressions)
scripts/routea_vm_check.sh      guest static-half runner
docs/route-a/06-m4-independent-audit.md
```

No existing main file is modified by the patch. The only candidate it can build is the canonical
`c4a159…` (golden asserted); it creates no second contract and no competing gate-3 evidence.

## 4. Test status and how to review

**On the review host (needs pyelftools + capstone):**

```bash
git fetch origin member-4-routea-gate3
git checkout 2ac0f66
git apply --check docs/route-a/m4-patches/0002-member-4-routea-gate3-canonical-audit.patch
python -m pytest tests/test_routea_byteaudit.py tests/test_routea_manifest.py \
  tests/test_routea_cave.py tests/test_routea_audit.py -q -p no:cacheprovider
python -m routea.gate3 bundle \
  --original fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf \
  --contract fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json \
  --out-dir var/jobs/m5-review/gate3
```

Record the **actual** test count and bundle hash; do not assert a target count. The bundle must
show candidate `c4a159…`, contract `24bfe568…`, `SHA256SUMS` verified, and items 4-5 `not_run`.

**On the M4 host:** only `py_compile` and the pure `tests/test_routea_byteaudit.py` (9 passed)
were run. The ELF-dependent files were **not executed** here (no pyelftools/capstone), consistent
with the earlier review; the VM/review-host run is the evidence.

## 5. Request

1. Confirm base `ad1a1f8` and patch SHA-256 `b68aabcd…cab8`; re-review the additive tooling.
2. If accepted, decide whether it is (a) merged as an independent verification helper, or (b)
   kept on the branch for M4's `handoff 17` runbook use. It does not change the canonical
   candidate/contract either way.
3. If more changes are needed, list them with the same B-number style; M4 will re-submit a new
   base/patch hash.

**Boundaries:** no candidate execution, no gate-3 pass claim, no oracle/manifest/contract change;
M4 does not approve its own evidence.

**Confirmation log.** 2026-10-22 — M4 re-submits the retargeted audit tooling after B1–B6; base
`ad1a1f8`, branch `2ac0f66`, patch `b68aabcd…cab8`; pure tests run on the M4 host, ELF tests
pending the review host/VM. No gate status changed.
