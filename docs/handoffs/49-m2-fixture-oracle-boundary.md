# 49 — M2 fixture/oracle boundary (binding) and current audit

**From:** Lead (scope owner)
**To:** M2 (GUI owner), cc M1/M3/M4/M5
**Date:** 2026-10-29 (Asia/Hong_Kong)
**Status:** **BINDING SCOPE RULE** — the fixture, the oracle, the frozen manifests/contract and the
acceptance/verification rules are **off-limits to M2**. This note does not change any gate
status (Gate 4 NOT RUN, Gate 5 pending, Gate 6 partial, fixture NOT FROZEN).
**Basis:** `docs/handoffs/41` §2 and §7, `AGENTS.md` (never weaken a test/oracle/gate; missing is
not passing), `docs/handoffs/48` (freeze deferred), `docs_BinaryRepair/verification-design.md`.

## 1. The rule

**M2 may work only on the GUI slice.** M2 must not modify the fixture, the oracle, the frozen
test manifests, the contract, the acceptance engine, or the verification tests — not even a
comment, docstring, formatting change, or "cleanup". These files are the team's measurement
instrument; a cosmetic edit still invalidates a pinned hash and creates a second success rule.

**Allowed for M2 (per 41 §2):** GUI/backend/status/visuals code, templates and static files,
GUI tools (`tools/p0_acceptance.py`, `tools/p2_acceptance.py`, launchers), GUI tests (not the
fixture/oracle tests below), `docs/screenshots/`, and GUI documentation. Chinese UI text may
stay; code comments/docstrings are being translated to English, but **only in M2's own files**.

**Forbidden to M2 (no exceptions):**

```text
fixtures/**                                              (all fixture bytes, manifests, contract)
tests/test_fixture_v3_manifest.py                        (frozen V3/V0 oracle assertions)
tests/unit/test_acceptance.py                            (acceptance-rule negative suite)
app/domain/acceptance.py                                 (the only outcome decision path)
app/domain/outcomes.py                                   (outcome vocabulary)
any oracle constant, expected rc/stdout/stderr, case id, manifest/contract hash
routeb/** , routea/** core, app/services/worker.py , app/services/attempt_writer.py
```

If M2 believes a change in a forbidden area is required, M2 stops and asks the Lead in writing
(artifact first, not chat-only). Only the Lead can authorize an oracle/contract change, and any
such change requires a new frozen version + new record hash + re-verification. M2 never approves
or "fixes" its own boundary crossing.

## 2. Current state (measured by Lead, 2026-10-29)

- Current branch (`integration/consolidation-2026-10-29` @ `64c6f3e`) fixture surface is
  unchanged since the verified state `986a49f`:
  `git diff --stat 986a49f HEAD -- fixtures tests/test_fixture_v3_manifest.py
  tests/unit/test_acceptance.py app/domain/acceptance.py app/domain/outcomes.py` → **empty**.
- Frozen values still match: original `aa428157…8393`, valid `17b2ee39…e76`,
  invalid `d493f370…90d`, manifest set `a564f039…3a78`, contract file `15f6b492…8df`,
  canonical contract `24bfe568…4e37`, tests sums file `f8f9b024…f97`.
- `docs/handoffs/evidence/` contains only `README.md` → Gate 4 evidence is still absent.
- No commit authored by the M2 merge after the verified state touches the fixture surface;
  M2 GUI commits are inside the already-merged `381e4ef` baseline.

## 3. Remote M2 branches audit (fetched 2026-10-29)

Compared against the frozen state `986a49f` (fixture/oracle paths only):

| Branch | Fixture/oracle diff vs frozen | Verdict |
|---|---|---|
| `origin/member2/demo-pack` | empty | **clean** (no fixture/oracle change) |
| `origin/member2/f5-export` | empty | **clean** |
| `origin/member2/i18n-cleanup` | `tests/test_fixture_v3_manifest.py` 11 lines: module docstring replaced with `"""Module documentation."""` (no assertion/constant change detected) | **VIOLATION — must be reverted before any merge.** The rule is absolute: no M2 edit to a verification test, even cosmetic |
| `origin/member2-backend-adapter` | branch is on an older base whose tree has no `fixtures/...` files; merging it as-is would *delete* fixture files | **do not merge as-is** — retarget/rebase onto current `main`; not a boundary edit, but an integration hazard |

Re-run before merging any M2 branch:

```bash
git diff --stat 986a49f <m2-branch> -- \
  fixtures tests/test_fixture_v3_manifest.py tests/unit/test_acceptance.py \
  app/domain/acceptance.py app/domain/outcomes.py
# expected: NOTHING. Any output = stop, do not merge, report the exact file/lines to M2.
git diff --stat <m2-branch> -- fixtures tests/test_fixture_v3_manifest.py \
  tests/unit/test_acceptance.py app/domain/acceptance.py app/domain/outcomes.py
# for the branch's own delta; any fixture/oracle entry = violation
```

Additionally, if a branch is based on an older tree, compare the **fixture files themselves**
(`sha256sum`/`Get-FileHash` of original.elf, valid.json, invalid.json, contract.json,
tests/SHA256SUMS) against the §2 frozen values, not only the diff.

## 4. M2's required actions

1. Revert the `tests/test_fixture_v3_manifest.py` edit in `member2/i18n-cleanup` (all 11 changed
   lines) before requesting a merge; keep the original module docstring byte-identical.
2. Confirm in M2's next handoff that no branch ready for merge contains a fixture/oracle diff.
3. Continue only with the 41 §2 GUI scope (language cleanup in M2 files, desktop e2e, live `http`
   walkthrough, screenshots/docs, legacy-bridge decision).

## 5. Confirmation

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead (scope decision) | Lead | 2026-10-29 | **M2 must not touch fixture/oracle; `i18n-cleanup` verification-test edit must be reverted before merge** |
| M2 (acknowledgement) | M2 | — | pending acknowledgement |
