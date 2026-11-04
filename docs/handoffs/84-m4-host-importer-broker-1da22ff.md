# 80 — M4 verification row: host importer/broker head `1da22ff` — PASS (targeted scope)

**From:** M4 (independent verifier; same operator as Lead — role-separated, not human-independent)
**To:** Lead, M1, M5
**Date:** 2026-11-03 12:15 (Asia/Hong_Kong)
**Branch:** `post-final/host-importer-broker`
**Head:** `1da22ff01ecfe99da5f235c210959dc2e272750b`
**Base:** `a9196d9efdc148563fbbb8888fcc8b262b6abfcb` (worker env `63b6eb8` + M5 adapter)
**Verdict:** **PASS for the changed host-tool scope** (targeted verification). Not a gate
decision, not a final-tag approval.

## 1. Identity / scope — PASS

- Head and base exist; `a9196d9` is the direct parent of `1da22ff`.
- `git diff --name-status a9196d9..1da22ff` contains exactly four additions:
  `tools/host_importer.py`, `tools/host_broker.py`,
  `tests/integration/test_host_broker.py`, `docs/host-importer-broker.md`.
- No existing production/test/docs file is modified; no main/tag ref is moved by this head.
- New files: LF, CR=0, no BOM.

## 2. Code review — PASS

`tools/host_importer.py`:
- validates bundle object, route, 64-hex candidate hash, results object;
- verifies attempt belongs to run, run belongs to job, route matches the persisted attempt;
- atomic write in the target directory (temp + `fsync` + `os.replace`);
- identical bytes → idempotent (`changed=False`); different existing bytes → `ValueError`
  without overwrite;
- optionally triggers `worker.run_once` after import.

`tools/host_broker.py`:
- validates envelope identity/route and requires `bundle` or `bundle_path`;
- imports each envelope with `trigger=False`, moves success to `processed/`, failure to
  `failed/` with an `.error.txt`;
- triggers the worker once per successful batch; `--once` returns 1 on any failure.

Residual limitations (not blockers for the intended host-side use):
- envelopes are not signed/authenticated; the inbox is a trusted host boundary;
- concurrent importer processes are not locked; single broker/CLI use is assumed;
- `bundle_path` can point outside the inbox; trusted-host assumption.

## 3. Tests / checks observed

- Direct `pytest` run hit the workspace sandbox temp ACL (`PermissionError [WinError 5]`),
  not a code failure; this is an environment limitation.
- Both test functions were executed directly with a workspace test directory:
  - `test_broker_imports_atomically_and_triggers_worker` → **PASS**
  - `test_broker_rejects_wrong_route_without_writing` → **PASS**
- Additional manual check: import bundle A (`changed=True`), then different bundle B →
  **rejected**, original A bytes remained unchanged.
- M1-reported broader subset: **273/269/3/1** (the one failure is Windows binutils,
  environment-only); the commit adds only four files and does not touch that path. Full
  suite was **not independently reproduced here** because of the pytest temp ACL.

## 4. M4 verification row

| Head | Base | Scope | M4 verdict | Evidence |
|---|---|---|---|---|
| `1da22ff` | `a9196d9` | host importer + inbox broker + tests/docs | **PASS (targeted)** | ancestry/diff PASS; code review PASS; 2/2 targeted tests PASS; conflict-overwrite check PASS; full-suite claim M1-reported (273/269/3/1, Windows binutils) not independently reproduced; residual trust/concurrency limitations recorded |

No gate status changes, no main/tag movement, no final-tag authorization.

## 5. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| M4 verifier | M4 | 2026-11-03 | **PASS (targeted)**; same-person limitation; no gate/final-tag approval |
