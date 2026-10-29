# M2 F5 export/report evidence (T2.1)

Branch: `member2/f5-export`, based on `64c6f3e`.
Target: PR after the integration merge (main freeze); branch committed independently.

## Delivered

### JSON export v2

`GET /api/jobs/{id}/export` now returns `schema_version: 2`:

- `generated_at`, `demo`, `content_language: "en"`, `disclaimer` and
  `note: "This export is not production approval."`
- `job`: id, filename, original_sha256, phase
- `contract`: revision, sha256, reviewed_scope_sha256
- `routes.A/B`: `candidate_sha256` (or `null`), `outcome`, `reason`,
  `failing_obligation`, `verification` copied from the controller, the six
  V0-V5 obligation rows verbatim, and evidence artifact ids/hashes
- `artifacts`: name, role, sha256, size, `download` availability
- `limitations` and `not_run`: explicit missing/non-passing items; missing data
  is never reported as passed
- `manifest_sha256`: SHA-256 over the canonical JSON of the artifact list and
  obligation rows

### Human-readable report

`GET /jobs/{id}/report` renders a printable English HTML report with the same
data:

- controller outcome, candidate hash, obligations, artifacts
- limitations and not_run tables
- `SHA256SUMS` block (manifest + artifact hashes)
- "Not production approval" disclaimer; demo banner when `demo: true`
- `?download=1` returns the HTML as an attachment

The evidence screen now offers JSON download, HTML view and HTML download.

## DoD commands and observed results

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_export_bundle.py `
  tests/test_backend_contract.py tests/test_local_backend.py `
  tests/test_language_policy.py `
  --basetemp=C:\Users\linyz\Documents\deepseek-harness\default-workspace\_work\tmp_f5 `
  -p no:cacheprovider
```

Observed: `22 passed` (exit 0).

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_export_bundle.py -q
```

Observed: `8 passed` (after the evidence-screen action test was added).

Live HTTP-mode check against the real controller
(`controller-artifacts-2026-10-29`, job `f81300cb…`):

```
export=200 bytes=7284
schema=2 demo=False manifest=13229f0b8255 routes=A,B not_run=7
report=200 bytes=9516 SHA256SUMS=True
```

Screenshots:

- `docs/analysis/M2-F5-evidence.png`
- `docs/analysis/M2-F5-report.png`

## What remains `not_run` / not available

- The export **renders** the controller outcome; it never computes one.
- Route outcomes in the live job are `inconclusive`; V2/V4/V5 obligations remain
  `not_run`, and they are listed explicitly in `not_run`.
- No candidate binary is invented; if the controller does not return one,
  `candidate_sha256` is `null` and `limitations` says so.
- Artifact download is marked `download: false` when the backend has no
  registered artifact id; the UI shows `not_available` with the hash.
- Guest execution, Gate 4 and symbolic evidence remain outside M2 scope.

## Scope compliance

Edited only: `app/backend.py`, `app/main.py`, `app/templates/evidence.html`,
new `app/templates/report.html`, new `tests/test_export_bundle.py`, this report.
No changes to controller, worker, acceptance/domain, tools, fixtures, README or
MEMORY.
