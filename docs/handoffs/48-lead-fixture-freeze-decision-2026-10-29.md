# 48 — Lead fixture-freeze decision record (item 16): DEFERRED — fixture NOT FROZEN

**From:** Lead (decision owner; `docs/handoffs/41` §6 item 3)
**To:** M1, M2, M3, M4, M5
**Date:** 2026-10-29 (Asia/Hong_Kong)
**Status:** **DECISION — the fixture is NOT FROZEN.** This is the written item-16 record for
the current state: the freeze is **deferred** because its hard preconditions (Gates 4 and 5)
are not met. This document is **not** a freeze record and must not be cited as one.
**Basis:** `docs/handoffs/34` §5 and `docs/handoffs/41` §6/§8 ("fixture-freeze decision only
after gates 3-5; it stays NOT FROZEN until then"), `BOARD.md`, `docs/route-a/gate3-record.md`,
`docs/handoffs/evidence/README.md`, `docs/analysis/VERIFICATION.md`.

## 1. Why the freeze cannot happen today

| Gate | Required state before freezing | Measured state (2026-10-29) | Evidence |
|---|---|---|---|
| Gate 3 (Route A feasibility) | closed/approved | **CLOSED / APPROVED** 2026-10-22 | `docs/route-a/gate3-record.md`, 14,082 B, SHA-256 `0b3b51e49f24c5759ff5d37a0569d44149af989dd4e72af6e51b279f0901f2da` (re-hashed by Lead today) |
| Gate 4 (Route B formal guest run) | formal PASS record with M5 record row + M4 verifier row + Lead approval row | **NOT RUN** — no `P4` package, no Gate 4 record, no real p2 job | `docs/handoffs/evidence/` contains only `README.md`; `BOARD.md` Gate 4 = NOT RUN; M4 JOIN-1 not started |
| Gate 5 (safe placement, both routes) | Route A runtime PASS (M4) + Route B half PASS (M5), guest-evidenced | **PENDING** — Route A runtime `not_run`; no M4 runtime record; no M5 Route B runtime proof | `docs/handoffs/43` (plan only); no `P4`/`P3A`/`P3B` |
| Gate 6 (not a freeze precondition, recorded) | — | partial (concrete crash accepted; V4 `not_run`) | `docs/route-b/06-gate6-evidence.md` |

Gate 3 alone does not permit a freeze: 41 §6 says the decision happens only after gates 3-5,
and 34 §5 puts the same dependency on the freeze. Freezing now would silently convert
"missing evidence" into "frozen accepted input", which the project rules forbid.

## 2. Frozen-value inventory (measured now, for the eventual freeze)

These are the exact values that would be frozen. They are re-measured from the current tree
(no producer value is copied):

| Item | File | Size | SHA-256 |
|---|---|---:|---|
| Original ELF | `fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf` | 26,792 B | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| Valid manifest | `fixtures/public/CWE121_src_char_declare_cpy_51b/tests/valid.json` | 1,951 B | `17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76` |
| Invalid manifest | `fixtures/public/CWE121_src_char_declare_cpy_51b/tests/invalid.json` | 1,460 B | `d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d` |
| Manifest set (canonical rule) | valid + invalid + original identity | — | `a564f0397a741b1a4fc386a3149d54550c1bfe7c02958309e021fb6f03333a78` |
| Contract file | `fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json` | 1,998 B | `15f6b492608e8c137f2612058bf43b90173284aec86d8c51b25d09903d0ad8df` |
| Contract canonical hash | `SecurityContract` rule | — | `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37` |
| Test sums file | `fixtures/public/CWE121_src_char_declare_cpy_51b/tests/SHA256SUMS` | — | `f8f9b024563e947bdf07f02d453be637f5620db6edb63939ffec793c926c2f97` |
| Verified code state | commit `986a49f` (product/tests); current branch tip at record time `64c6f3e` | — | later commits are docs/scripts only |

Re-measurement commands (recorded, host-only, no execution):

```powershell
Get-FileHash -Algorithm SHA256 fixtures\public\CWE121_src_char_declare_cpy_51b\original.elf, `
  fixtures\public\CWE121_src_char_declare_cpy_51b\tests\valid.json, `
  fixtures\public\CWE121_src_char_declare_cpy_51b\tests\invalid.json, `
  fixtures\public\CWE121_src_char_declare_cpy_51b\contract.json, `
  fixtures\public\CWE121_src_char_declare_cpy_51b\tests\SHA256SUMS
git diff --stat 986a49f HEAD -- fixtures tests/test_fixture_v3_manifest.py tests/unit/test_acceptance.py app/domain/acceptance.py app/domain/outcomes.py
# -> empty (no post-verification change to the freeze surface)
```

## 3. Freeze-readiness checklist (execute only when Gates 4-5 pass)

- [ ] **F1 — Gate 4 record exists and is signed**: `P4` package checker-PASS; `gate4-status.json`
      pass; six cases 6/6; isolation attestation; M5 record row, M4 verifier row, Lead approval
      row all signed; record SHA-256 pinned.
- [ ] **F2 — Gate 5 records exist**: Route A runtime placement PASS (M4, guest) and Route B half
      PASS (M5), each with commands/observed values and record hashes.
- [ ] **F3 — frozen bytes unchanged**: the values in §2 re-hashed on the candidate freeze commit;
      `git diff --stat 986a49f <freeze-commit> -- fixtures tests/test_fixture_v3_manifest.py
      tests/unit/test_acceptance.py app/domain/acceptance.py app/domain/outcomes.py` empty.
- [ ] **F4 — acceptance/tests measured on the freeze commit**: `tests/unit/test_acceptance.py`
      29 passed; full-suite state recorded with its environment (the known Windows `tmp_path`
      environment errors stay `not_run`, never passed).
- [ ] **F5 — environment/guest record**: toolchain versions and snapshot/guest identity for the
      runs that justify Gates 4-5; no host execution anywhere.
- [ ] **F6 — this document replaced by a real freeze record**: new signed record naming the
      freeze commit, the §2 values, its own SHA-256, and a sorted `SHA256SUMS`; Lead signature
      is the decision, and the record is committed and hash-pinned.
- [ ] **F7 — post-freeze change policy stated**: any change to the frozen surface requires a
      written Lead approval + new freeze version + new record hash; silent edits are prohibited.

## 4. What this record does and does not decide

- It decides: **the fixture remains `NOT FROZEN`; item 16 is deferred, not passed.**
- It does not decide: Gate 4/5 status, candidate acceptance, repair success, or any change to
  the oracle/contract/manifests. Those remain exactly as recorded above.
- The next Lead action is to re-open this record when F1-F5 exist; until then the `BOARD.md`
  fixture row stays `NOT FROZEN`.

## 5. M2 boundary (also binding — see `docs/handoffs/49`)

M2 must not touch `fixtures/**`, the oracle/manifest/contract constants,
`tests/test_fixture_v3_manifest.py`, or `tests/unit/test_acceptance.py` /
`app/domain/acceptance.py` / `app/domain/outcomes.py`. A current M2 branch
(`origin/member2/i18n-cleanup`) changes `tests/test_fixture_v3_manifest.py` (docstring only,
no assertion change) — that is **outside M2's scope** and must be reverted before any merge.
No M2 merge may carry a fixture/oracle diff.

## 6. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead (fixture-freeze decision) | Lead | 2026-10-29 | **DEFERRED — fixture NOT FROZEN**; freeze only after Gates 4-5 and F1-F5; not a freeze record |
| M4 (verifier, read-only measurement) | M4 | — | fixture values independently re-hashed; no gate/record signature (M4 does not sign this decision) |
| M5 (Gate 4 DRI) | M5 | — | pending F1 |
| M2 (GUI owner) | M2 | — | boundary acknowledged; no fixture/oracle edits allowed |
