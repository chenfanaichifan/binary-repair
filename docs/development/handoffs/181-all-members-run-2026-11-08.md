# 181 — All-member code run

Date: 2026-11-08  
Head: 1710784 + merge 2501120

## Result

```text
pytest -q: 716 collected / 714 passed / 2 skipped / 0 failed
compileall: 0
M3 executor self-test: 9/9 passed
M2 subset: 131 passed
e2e: 12 passed (Chrome CDP fallback)
```

Skips:

```text
2 ELF execution: requires Linux
```

## P2 post-merge

```text
exit 0
synthetic false
verdict success_within_scope
route A/B 6/6
```

## Logs

```text
artifacts/logs/all-members-full-2026-11-08.txt
artifacts/logs/m2-all-2026-11-08.txt
artifacts/logs/e2e-all-2026-11-08.txt
artifacts/logs/e2e-chrome-2026-11-08.txt
artifacts/logs/all-members-full-chrome-2026-11-08.txt
artifacts/logs/compileall-2026-11-08.txt
artifacts/logs/p2-post-merge-2026-11-08.txt
artifacts/logs/m3-self-test-2026-11-08.txt
```

## M2 script caveat

`run-m2-tests.sh` uses system `python3` when no `.venv` is present; on this
machine that resolves to Anaconda pydantic 1.x and fails. Running the same
subset with the project venv passes 131 tests. The script is not a code failure;
it is a Python-environment selection issue.
