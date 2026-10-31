# P0-1 — M4 verification of PR #10 exact head `aab162a` (2026-10-30)

**Head:** `aab162a4b74a526f9f37bba3a99ccc061160870c`
**Tag:** `m1-pr10-head-aab162a` (same commit)
**Worktree:** extracted exact commit with `git archive`; tests run from that tree,
not from the current working tree.
**Identity limitation:** M4 and Lead are the same operator; this row is not an
independent two-person review.

## Commands and observed results

| Check | Command | Observed | Verdict |
|---|---|---|---|
| p2 negative tests | `python -m pytest -q tests/integration/test_p2_acceptance.py -p pytest_rt_report -p no:tmpdir` | `collected=5 passed=5 collection_errors=0 pytest_exitstatus=0` | **PASS** |
| attempt-writer | same for `tests/integration/test_attempt_writer.py` | `collected=6 passed=6 collection_errors=0 pytest_exitstatus=0` | **PASS** |
| full suite | `python -m pytest tests/ --ignore=tests/e2e --continue-on-collection-errors -p pytest_rt_report -p no:tmpdir` | `collected=244 passed=242 skipped=2 collection_errors=5 pytest_exitstatus=1` | **PASS on verifiable subset; full suite NOT VERIFIED** |
| demo | `python scripts/demo_e2e.py` | exit 0; `DEMO OK`; synthetic V1–V5 labelled | **PASS** |
| gate honesty | `git show aab162a:docs/route-b/23-gate4-record.md` | `Status: DRAFT / NOT RUN`; no fake approval | **PASS** |
| frozen surfaces | diff `7fea795..aab162a` for fixtures/acceptance/outcomes/fixture test | only BOM removal in `acceptance.py`/`outcomes.py`, added tests and fixture README; no semantic oracle change | **PASS** |
| secrets/client binaries | `git grep` for private-key/token patterns, excluding PNGs | no matches | **PASS** |

Full-suite collection errors (environment, not test failures):

```text
tests/test_routea_cave.py        ModuleNotFoundError: capstone
tests/test_routea_manifest.py    ModuleNotFoundError: capstone
tests/test_routea_worker.py      ModuleNotFoundError: capstone
tests/test_routeb_attempt_writer.py  ModuleNotFoundError: elftools
tests/test_routeb_executor.py    ModuleNotFoundError: elftools
```

This host's Python lacks `pyelftools`/`capstone`; the package index is unreachable
(`pip install` reports no versions), so those 13 ELF-dependent tests cannot be
collected here. **0 assertion failures** were observed.

## Verdict

**PASS (verifiable subset) / full-suite completeness NOT VERIFIED.**
The two targeted suites pass (5 and 6); demo, gate honesty, frozen-surface diff
and secret scan pass. The full suite cannot be completed on this host because
`pyelftools`/`capstone` are absent; it must be run where those deps exist.

**Merge status caveat:** `aab162a` was already merged into `main bcf2537` before
this row existed. This row does not retroactively satisfy “only PASS allows
merge”; the merge should be recorded as integration-only unless a full-suite PASS
on the exact head is supplied.
