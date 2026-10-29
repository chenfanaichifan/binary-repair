# M2 i18n cleanup report (T2.2)

Branch: `member2/i18n-cleanup` (based on `64c6f3e`; no integration-branch commits).

## What changed

Python comments/docstrings in the M2 slice were rewritten in English or removed.
Chinese UI string literals and `app/i18n.py` label dictionaries were **not**
changed.

Files changed (12):

- `app/__init__.py`
- `app/backend.py`
- `app/demo.py`
- `app/i18n.py`
- `app/main.py`
- `tools/__init__.py`
- `tools/stub_backend.py`
- `tests/test_backend_contract.py`
- `tests/test_language_policy.py`
- `tests/test_smoke.py`
- `tests/test_ai_boundary_contract.py` (non-ASCII section sign in docstring)
- `tests/test_fixture_v3_manifest.py` (non-ASCII section sign in docstring)

Added `scripts/check_language_policy.py`: scans Python comments and
module/class/function docstrings in `app/backend.py`, `app/main.py`,
`app/demo.py`, `app/status.py`, `app/visuals.py`, `app/i18n.py`, `tools/`, and
`tests/`; fails on any non-ASCII character. UI string literals are out of scope.

## Commands and observed output

```powershell
.\.venv\Scripts\python.exe scripts\check_language_policy.py
```

Observed:

```
PASS 0 non-ASCII comments/docstrings in app/tools/tests
```

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_language_policy.py `
  tests/test_backend_contract.py tests/test_local_backend.py `
  tests/test_status_honesty.py tests/test_verdict_view.py
```

Observed: `21 passed` (the five files selected by the assignment).

```powershell
.\.venv\Scripts\python.exe -m compileall -q app tools tests
```

Observed: exit 0.

## Notes

- The assignment mentioned 42 files / 494 non-ASCII lines in the whole tree; the
  language policy applies to **comments/docstrings**, and the checker covers the
  GUI-owned Python scope. Remaining non-ASCII in UI strings and i18n labels is
  intentional.
- `app/domain/`, `app/services/`, `app/controller_api.py`, `tools/p2_acceptance.py`,
  `tools/routea_bundle_to_attempt.py` were not edited (other owners / scope).
