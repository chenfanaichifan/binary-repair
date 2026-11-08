# Member 2 merge report — controller-backed GUI slice

**Date:** 2026-10-29
**Owner:** m2-integrator (task-5)
**Main worktree:** `D:\BinaryRepair_Project`, branch `integration/consolidation-2026-10-29` (never modified by this task except this report)
**Merge clone:** `D:\BinaryRepair_Project\_scratch\m2-merge`, branch `merge/m2-main`
**Merge commit:** `381e4ef1fc91776dd518b531bdafef1fb67a84d5` (`381e4ef`), parents `036328d` (M2 tip) and `4107836` (main tip)
**Import bundle (verified):** `D:\BinaryRepair_Project\_scratch\m2-merge-import.bundle`

## 1. Summary

The member-2 GUI/controller-adapter slice merges into main cleanly: only **6 files
actually conflicted**, not the large set the task estimated, because `main` never
touched the GUI files after the merge base. The merge keeps main's canonical
controller/API/acceptance semantics and lands M2's three-screen controller-backed
GUI, adapter, launchers, acceptance tools, browser e2e suite and screenshots
unchanged on top of them.

Measured on the merge commit:

| Check | Result |
|---|---|
| Collectable test suite (192 items, host `tmp_path` workaround) | **190 passed, 2 skipped, 0 failed** (exit 0) |
| Same suite without the workaround | 138 passed, 2 skipped, **52 errors** — all 52 are the host `tmp_path` bug, not merge defects |
| `tools/p0_acceptance.py` against live GUI (`http` mode) + canonical controller | **17/17 PASS** (exit 0) |
| `tools/p2_acceptance.py` | **exit 2 BLOCKED**, phase `queued` (honest: no result bundle reaches the worker) |
| Route A/B ELF test modules (5) | **not_run** — `capstone`/`pyelftools` absent on this Python 3.14 host |
| Browser e2e (`tests/e2e`, 7 tests) | **not_run** — Edge DevTools endpoint cannot start in this sandbox |

## 2. What the M2 branch holds

`origin/member2-backend-adapter` (`036328d`, merge base `453fe95`): **50 unique
commits, 66 files, +7788/−479 lines**. The slice is the missing user-visible
product:

- **Controller-backed GUI** — `app/main.py` (setup / comparison / evidence /
  landing / dry-run routes, local session token + CSRF, host and Origin checks),
  `app/backend.py` (one adapter with `mock` / `http` / `local` modes, CJK-response
  rejection, 409/404/network error mapping), `app/status.py` (derived display
  labels only), `app/visuals.py` (synthetic code-view payload), `app/demo.py`,
  `app/i18n.py`, Jinja templates and static assets (landing page, setup wizard,
  code view, polling).
- **Honest rendering** — the GUI never computes an outcome: overall success is
  derived only from the controller's two route outcomes; `finished` is a phase,
  not a verdict; cancel renders `已取消`, never success; `not_run` is shown
  verbatim.
- **Launchers** — `start.ps1` / `run.bat` / `open.bat` / `open.ps1` (stable
  `var/session.token`, one-time `?token=` URL, browser auto-open) and
  `start-controller.ps1` / `.bat`.
- **Acceptance tools** — `tools/p0_acceptance.py` (live GUI↔controller journey),
  `tools/p2_acceptance.py` (verdict/obligation gate, `2 BLOCKED` while the
  pipeline cannot finish), `tools/routea_bundle_to_attempt.py` (Route A bundle →
  per-attempt worker JSON), `tools/stub_backend.py` (synthetic HTTP stub),
  `tools/controller_service.py` (legacy bridge over the real job store).
- **Tests** — `tests/conftest.py`, `test_backend_contract.py`,
  `test_contract_revision.py`, `test_controller_service.py`, `test_dryrun_view.py`,
  `test_local_backend.py`, `test_routea_adapter.py`, `test_security.py`,
  `test_status_honesty.py`, `test_verdict_view.py`, `test_visuals.py`,
  `tests/e2e/` (headless Edge over the DevTools protocol).
- **Docs and screenshots** — `docs/controller-integration.md`,
  `docs/integration-plan.md`, `docs/interfaces/route-a-worker-contract.md`,
  `docs/member2-notes.md`, `docs/proposal/gui-section.md`,
  `docs/screenshots/*.png` (8 labelled mock-mode screenshots).

### Why it matters

On main the GUI was still the merge-base demo UI (`app/main.py` unchanged since
`453fe95`); the adapter, session/CSRF gate, landing/setup/evidence screens,
honest verdict rendering and the P0/P2 acceptance gates existed only on the M2
branch. Without this merge the integrated tree has a controller API with no real
GUI talking to it — the product is not demonstrable.

## 3. Merge result and how to import it

Everything happened inside the clone; the shared worktree was not committed to,
not switched, and not fetched from for writes. Clone created from a bundle of the
shared repo because process-spawning transports are broken in this sandbox (see
§5).

Import commands for the Lead (from `D:\BinaryRepair_Project`):

```powershell
# Option A - normal Git host (documented form):
git fetch D:\BinaryRepair_Project\_scratch\m2-merge merge/m2-main:refs/heads/merge/m2-main

# Option B - verified in this sandbox (the local path fetch fails here with the
# cygwin sh.exe "couldn't create signal pipe" error):
git fetch D:\BinaryRepair_Project\_scratch\m2-merge-import.bundle refs/heads/merge/m2-main:refs/heads/merge/m2-main
```

Then:

```powershell
git merge --no-ff merge/m2-main
```

The merge commit's first parent is `4107836`, so a fast-forward is possible; use
`--no-ff` if the integration branch should keep an explicit merge record.

**Import caveat:** the shared worktree currently has uncommitted changes
(`README.md` modified, `tests/unit/test_acceptance.py` staged, `AGENTS.md` /
`MEMORY.md` / `agent_docs/` untracked). Commit or stash those first; `README.md`,
`requirements.txt` and `docs/controller-integration.md` are edited on both sides
and will need the same resolutions described in §4.

## 4. Conflict map and resolutions

Actual conflicts (6):

| File | Resolution |
|---|---|
| `README.md` | main's current status/architecture/tests kept as the backbone; added a "GUI slice and data-source adapter" section (modes, launchers, session/CSRF, P0/P2 helpers, e2e, screenshots), updated the GUI row, layout, quick start, test notes and doc links. M2's stale pre-cleanup README text (branch-archive era) was not carried over. |
| `docs/controller-integration.md` | M2's full document (it is a superset of main's) with the canonical-controller section rewritten: `app/controller_api.py` ships in this tree, so `start-controller.ps1` serves it directly instead of pinning a separate `origin/main` worktree; the `tools/controller_service.py` bridge is labelled a **legacy fallback**. Status paragraphs updated with the measured P0 result. |
| `requirements.txt` | Union of main's runtime/test/ELF dependencies and M2's: keeps main's pins (`httpx>=0.28,<1`, pydantic, jsonschema, capstone, lief) and raises `pyelftools` to `>=0.33` (M2's Route B bundle tools). |
| `run.bat` | M2's version (delegates to `start.ps1` so the session token and one-time URL work); main's plain demo launcher is a subset. |
| `start.ps1` | M2's version (stable session token, browser auto-open, http/local/mock modes). |
| `tools/p2_acceptance.py` | Merged gate: main's verdict/route/obligation verification is kept (valid outcome vocabulary, run verdict present, both routes' V0–V5 obligation kinds `identity/structure/interface/behaviour/symbolic/reproducibility`, demo-banner check) and M2's pipeline driver is added (create → approve → start → optional `--worker-command` → wait); `--job-id` preserves main's verification-only mode; exit codes `0/1/2` with `2 BLOCKED` while no result bundle reaches the worker. Checks were only added, never removed. |

Non-conflicting integration edits made deliberately:

| Path | Change |
|---|---|
| `start-controller.ps1` | Serves `app.controller_api:app` from this checkout with `BINARYREPAIR_DATA_DIR=var/controller`; the M2 script created a second `git worktree` of `origin/main`, which is unnecessary and fragile now that the controller is in the merged tree (and was denied in this sandbox). |
| `start-controller.bat` | Comment updated to the canonical controller. |

Why there were no `app/*` conflicts: `git diff 453fe95 main` shows **no changes**
to `app/main.py`, `app/demo.py`, `app/i18n.py`, `app/templates/`, `app/static/`,
`tests/test_smoke.py`, `tests/test_language_policy.py`; and M2 changed **nothing**
under `app/controller_api.py`, `app/domain/`, `app/services/`, `app/db/`. Each
side therefore owns disjoint paths and both sets survive intact. `main`'s 57
post-base commits (controller API, domain, services, db, routea/routeb, docs)
flow in untouched; 49 of the 66 merged files are new (M2) additions.

**Semantics after merge:** GUI (`app/main.py`) → `app/backend.py` (`HttpBackend`)
→ `app/controller_api.py` (canonical: persisted job store, canonical approvals,
runs/attempts, canonical 409s) — or `LocalBackend` straight to
`app/services/jobs.py`. Outcomes are still decided only by
`app/domain/acceptance.py`; `app/status.py`, templates and route handlers only
render controller data. No acceptance rule, oracle or check was weakened.

## 5. Exact commands and observed results

Environment: Windows, Python 3.14.6, pytest 9.1.1, FastAPI 0.141.1, httpx 0.28.1,
jsonschema installed; `capstone` and `pyelftools` **not** installed; `pip install`
is blocked in this sandbox.

Clone (spawning a transport process is refused by the sandbox):

```powershell
# in D:\BinaryRepair_Project (writes only under _scratch/)
git bundle create _scratch\m2-src.bundle --all
git clone _scratch\m2-src.bundle _scratch\m2-merge
# in the clone
git fetch origin "refs/remotes/origin/main:refs/remotes/src/main" `
               "refs/remotes/origin/member2-backend-adapter:refs/remotes/src/m2"
git checkout -b merge/m2-main src/m2
git merge --no-commit --no-ff src/main
# resolve the 6 files, git add, then:
git commit   # 8cad74e, then amended after a docs-only update (381e4ef)
```

`git clone D:\BinaryRepair_Project ...` and `git fetch D:\...` both fail on this
host with `sh.exe: *** fatal error - couldn't create signal pipe, Win32 error 5`;
the bundle path avoids that. The same host bug affects importing (`Option B`
above is the verified path).

Tests (all against commit `381e4ef`, from the clone, basetemp pre-created):

```powershell
New-Item -ItemType Directory pytest_tmp_m2 -Force
python -m pytest -q --basetemp=pytest_tmp_m2 -p no:cacheprovider
# -> "Interrupted: 5 errors during collection" (exit non-zero); 0 tests executed.
#    3 modules: ModuleNotFoundError: capstone; 2 modules: ModuleNotFoundError: elftools
#    (tests/test_routea_cave.py, test_routea_manifest.py, test_routea_worker.py,
#     test_routeb_attempt_writer.py, test_routeb_executor.py)  => not_run on this host
```

```powershell
python -m pytest -q --basetemp=... -p no:cacheprovider `
  --ignore=tests/e2e --ignore=tests/test_routea_cave.py --ignore=tests/test_routea_manifest.py `
  --ignore=tests/test_routea_worker.py --ignore=tests/test_routeb_attempt_writer.py `
  --ignore=tests/test_routeb_executor.py
# without the local workaround: 192 items -> 138 passed, 2 skipped, 52 errors.
#   All 52 errors are PermissionError [WinError 5] inside the pytest `tmp_path`
#   fixture (host creates mode-0o700 directories that it then cannot list);
#   pytest also crashes in its sessionfinish basetemp listing.
# with the local host workaround (a plugin that is NOT committed to the repo,
# forces Path.mkdir to the default mode):
#   192 items -> 190 passed, 2 skipped, 0 failed, exit 0.
```

The 2 skips are `tests/test_fixture_v3_manifest.py` cases that need a candidate
ELF (`not_run`, not a pass). The workaround plugin lives in the clone only
(`_scratch/m2-merge/.merge/m2_tmpfix_plugin.py`); it changes no repository file —
the host bug is documented in the main README measured section.

P0 acceptance against the live pair (servers started only for the check, then
stopped; ports confirmed released):

```powershell
# terminal 1 (clone, BINARYREPAIR_DATA_DIR=<clone>\var\controller)
python -m uvicorn app.controller_api:app --host 127.0.0.1 --port 8000
# terminal 2 (clone, BINARYREPAIR_BACKEND=http, BINARYREPAIR_API_BASE=http://127.0.0.1:8000)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8123
python tools\p0_acceptance.py
# -> 17/17 checks PASS, "P0 ACCEPTANCE PASSED", exit 0
#    (session, controller health, real job creation, demo:false, no demo banner,
#     contract edit+revision, approval, start -> queued, cancel -> cancelled,
#     cancelled page shows 已取消 and is not labelled success)
```

```powershell
python tools\p2_acceptance.py --timeout 6
# -> job created and started, phase stays 'queued', "BLOCKED pipeline did not finish",
#    exit 2. This is the designed honest state while no result bundle exists.
```

```powershell
python -m pytest -q tests/e2e --basetemp=... -p no:cacheprovider
# -> 7 errors: "Edge DevTools endpoint did not become ready" (one controller
#    ConnectionRefused). Browser e2e cannot run in this sandbox => not_run.
```

No uploaded or repaired ELF and no model-generated C was executed. P0/P2 only
post a 25-byte synthetic payload to the controller; the controller has no
executor, and the worker was never started with a result bundle.

## 6. Remaining work

1. **Import the branch** using §3 after the shared worktree's local changes are
   committed/stashed, resolving `README.md` / `requirements.txt` /
   `docs/controller-integration.md` against the consolidation edits. The
   consolidation worktree's `README.md` measured-test section and the staged
   `tests/unit/test_acceptance.py` (29 tests) are not in the merged refs and
   should be committed by their owner.
2. **Real execution is still missing** (not a GUI/merge issue): the controller
   queues runs but no Route A/B result bundle reaches the worker, so a run cannot
   reach `finished` with persisted V0–V5 obligations. `tools/p2_acceptance.py`
   will stay at `2 BLOCKED` until the M3 Route A executor and the M5 Route B
   bundle→attempt adapter land.
3. **Run the skipped checks in a capable environment:** the 5 routea/routeb test
   modules need `capstone`/`pyelftools` (Ubuntu/Python 3.12 target), the 2
   fixture-V3 tests need a candidate ELF, and `tests/e2e` needs a desktop session
   where headless Edge can start. All three are `not_run` here.
4. **M2 decision still open:** `tools/controller_service.py` is now a legacy
   bridge that duplicates the canonical controller with different semantics
   (`/start` always 409). It is kept for its tests, the fallback path and the e2e
   fixtures; plan to delete it (and repoint `tests/e2e/conftest.py` +
   `tests/test_controller_service.py`) once the canonical controller is the only
   development target.
5. **Language-policy cleanup in the M2 slice** (follow-up, deliberately not done
   in this merge to keep the slice reviewable): several `app/*.py`
   docstrings/comments and some test docstrings are Chinese, while the project
   rule asks for English project files (the Chinese UI text itself is intended).
   `app/main.py`'s docstring also contains a personal absolute path
   (`C:\Users\linyz\...`); replace it with a generic instruction.
6. **Optional tidy-up:** `pyelftools>=0.33` is now required by
   `tools/routea_bundle_to_attempt.py`/`routeb`; keep requirements as merged if
   the Route B tooling stays.

## 7. Notes on isolation and rollback

- The shared worktree was only read, never written, except this report file.
- The clone can be deleted at any time (`_scratch/m2-merge`); the merge branch
  then disappears. `_scratch/m2-merge-import.bundle` is a self-contained import
  artifact. The host leaves a few unreadable pending-delete `pytest_tmp_*` /
  `perm_t1` directories in the clone (same `mkdir(mode=0o700)` host bug); they
  are untracked and harmless, and the import bundle is unaffected.
- A handful of temporary helper scripts and logs live under
  `_scratch/m2-merge/.merge/` (test-report plugin, host workaround plugin, run
  logs). They are not part of the commit.
