# BinaryRepair MVP · GUI Skeleton (Member 2)

This is the first GUI step for Project 11: AI-driven binary vulnerability repair and correctness verification.
It brings up the three screens (create/review → progress/comparison → evidence/export) and fixes the
status semantics and field names with **clearly labelled demo data**. The real execution chain
(VM, Route A/B, angr checks) will be wired in by the other members.

> **Important:** every phase transition and outcome on these screens is a demo fixture, and a banner
> at the top of the page says so. It is not a repair result and must not be treated as evidence that
> a patch is verified. The banner disappears when real data is connected.

## 0. Language policy (important; team decision, 2026-10-18)

- **The UI may use Chinese**: titles, buttons, status badges, and explanatory text are Chinese.
- **Uploaded data, API payloads, and exports must be English ASCII**: defect description, reproduction
  input, environment, the four contract fields, obligations, outcome reasons, changed regions,
  artifact roles, and export JSON are all English.
- Server-side validation: non-ASCII form content returns `422`; the browser also blocks it before submission.
- Uploaded filenames are converted to ASCII-safe names (for example, a Chinese filename becomes
  `sample.bin`) so non-ASCII characters never enter export data.
- Tests guard this: `/api/jobs/{id}` and export JSON are scanned for CJK characters, while the UI stays
  Chinese (see `tests/test_language_policy.py`).

## 1. Quick start (Windows)

Prerequisite: Python 3.13 (installed locally) and a `.venv` in the project directory.

Open a terminal in the **project directory** (PowerShell or Command Prompt), then choose one:

```powershell
.\start.ps1          # one-command PowerShell start
```

```bat
run.bat              :: double-click also works
```

Or manually:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
```

Then open **<http://127.0.0.1:8123>** in a browser (it listens on localhost only; other machines
cannot reach it).

If `.venv` does not exist (new machine or reinstall):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 2. What you will see (first demo run)

1. The app opens on **① Create job and review contract**: choose any file as the sample (the demo only
   hashes it), enter the defect description, and view/edit the security contract.
2. Click **Register job and continue to review** → **② Progress and comparison**: both routes are shown
   side by side, initially as "draft".
3. Click **Approve and start (demo)** → the phase advances about every 1.2 seconds, and the page
   refreshes every 2 seconds.
4. When it finishes: Route A shows **rejected** (valid-input regression failed) and Route B shows
   **inconclusive** (bounded symbolic budget exhausted). This is deliberate: it demonstrates that
   "not finished / not passed" must never be displayed as success.
5. Click **View evidence** → **③ Evidence and export**: V0–V5 obligations, scope, artifact hashes,
   diagnostic-candidate label, and export JSON.
6. The file downloaded by **Export evidence JSON** also carries `demo: true` and a note that export is
   not production approval.

## 3. The three screens and the requirements they cover

| Screen | Requirement | Implemented in this skeleton |
|---|---|---|
| ① `setup.html` | PRD **F1** graphical job creation and contract review | Upload, SHA-256 registration, defect/test/environment inputs, editable contract, pre-run validation (empty file 422, oversized 413) |
| ② `comparison.html` | PRD **F5**, UI/UX Direction | Side-by-side routes, independent stage indicators, six outcome badges, test/verification/compatibility/duration/human-intervention/AI-usage fields, cancel, polling |
| ③ `evidence.html` | PRD **F4/F5** | V0–V5 obligation table, scope and assumptions, artifact hashes, diagnostic-candidate label, export, replay notes |

Status semantics follow the technical design: `phase`
(draft/screening/analyzing/roundtrip/generating/applying/validating/finished) and `outcome`
(success_within_scope/unsupported/rejected/inconclusive/error/cancelled) are displayed on **two separate
axes**; `not_run` is never counted as passed.

## 4. Directory layout

```text
binaryrepair-mvp/
├─ app/
│  ├─ main.py            # FastAPI entry, three-screen routes, status API, export API
│  ├─ demo.py            # demo data (phase progression, V0–V5 obligations, artifacts); replace when the real backend is connected
│  ├─ i18n.py            # Chinese display labels (templates/frontend only; never enter API or exports)
│  ├─ templates/         # base + three-screen templates (Jinja2)
│  └─ static/            # css/app.css, js/poll.js
├─ tests/test_smoke.py   # smoke tests (three screens 200, host check, export)
├─ fixtures/public/      # public samples only (rules in that directory's README)
├─ docs/                 # documentation (including the member-2 notes)
├─ var/jobs/             # runtime artifacts, ignored by .gitignore
├─ requirements.txt
├─ start.ps1 / run.bat
└─ README.md
```

## 5. Running the tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Coverage: the three screens open; the host check rejects foreign domains; a created job has a
64-character hash; the phase is no longer `draft` after start; the evidence page contains V0 and a
diagnostic candidate; the export is an attachment with `demo: true`; a cancelled job reports `cancelled`.
Separate language-policy tests: API/export contain no CJK characters, Chinese form content returns 422,
Chinese filenames are converted to ASCII, and the UI stays Chinese.

## 6. FAQ

| Symptom | Cause / fix |
|---|---|
| `uvicorn: command not found` | Do not call `uvicorn` directly; use `.\.venv\Scripts\python.exe -m uvicorn ...` |
| Port already in use | Change `8123` to `8124` etc. in the command |
| `start.ps1 cannot be loaded because running scripts is disabled` | PowerShell execution policy; use `run.bat`, or run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` and retry |
| Page returns 403 | Open `localhost` / `127.0.0.1`; the host check rejects other domains |
| Dependency install is slow or fails | Use a mirror: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| `.py` changes do not take effect | uvicorn is not in reload mode; restart, or add `--reload` for development |

## 7. Next steps (dependency order)

1. **Align the API contract with Member 1**: replace the fields from `demo.py` with the real
   `/api/jobs/{id}` response; the pages and polling logic do not change.
2. **Get the acceptance rules from Member 4**: the six outcome decisions, `not_run` display, and
   negative-case list; calibrate this page's badges/obligation table to those rules.
3. **Connect Member 3's fixture and provenance**: upload validation (architecture/format) and source fields.
4. **GitHub**: this GUI slice is archived under `agent/member2-gui/` in the shared repository; do not
   run `git init` here. Use the shared branch/PR flow, and keep `.gitignore` effective (`.venv` and
   `var/jobs` do not enter the repository).
5. Then fill in PRD F1/F5: contract revision and 409 stale approval, CSRF/session, real export bundle.

## 8. Confidentiality and data boundary (required reading)

- Put only **public samples / self-built samples** in `fixtures/public/`.
- **Do not** commit client binaries, confidential derived content, API keys, or `.env` to GitHub.
- The three project documents (PRD/research/technical design) are internal team material; ask the team
  before committing them.
- Exported artifacts are for review only and do not represent production approval.

## 9. Document sources

- PRD (v1.0, 2026-10-15): F1, F4, F5, UI/UX Direction, Success Metrics
- TechDesign (v1.0, 2026-10-15): §6 state and lifecycle, §7 three views and API, §9 verification ladder,
  §11 local service security, §12 directory and dev mode, §13 tests, §14 roles
- Roles and collaboration boundaries: `docs/member2-notes.md` (2026-10-18 team division version)
