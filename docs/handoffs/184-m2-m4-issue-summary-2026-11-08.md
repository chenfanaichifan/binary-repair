# 184 — M2 / M4 issue summary

Date: 2026-11-08  
Source head: `56e11ca`  
Public v1.1.0 head: `1e30bd5` (source `b61774d`)

## P0 — must fix before v1.1.1

### M4-1 v1.1.0 lacks the repaired-ELF upload feature

```text
v1.1.0 source: b61774d
current source: 56e11ca
grep deliverables app tests -> nothing in v1.1.0
```

The teacher-facing upload/download entry added in `56e11ca` is not in the
curated release. Re-curate from `56e11ca` before v1.1.1.

### M4-2 v1.1.0 full suite fails

Clean clone of v1.1.0:

```text
pytest -q -> 18 failed/error
```

Not 56 targeted, not 714.

Causes:

```text
tests still reference delivery/ (moved to artifacts/)
tests still reference dist/m5-evidence/P3A, P3B (not in curated tree)
```

Fix: update test paths to `artifacts/` equivalents, or include the compatibility
packages. Re-run full suite.

### M4-3 CRLF SHA256SUMS

```text
artifacts/m4/v4-2026-11-07/SHA256SUMS
```

Direct `shasum -a 256 -c` fails for 15 entries because filenames carry `\r`.
Normalized (`tr -d '\r'`) -> 192/192.

Fix: rewrite all `SHA256SUMS` with LF; publish v1.1.1 (do not move v1.1.0).

## P1 — M2 package hardening

### M2-1 MANIFEST.sha256 is CRLF

```text
shasum -a 256 -c MANIFEST.sha256 -> 16 files unreadable
tr -d '\r' -> 16/16 OK
```

Fix: regenerate LF manifest, zip, SHA-256.

### M2-2 run-m2-tests.sh selects system Python

On this Mac, no `.venv` in the extracted package; script falls back to
`python3` = Anaconda pydantic 1.x:

```text
ImportError: cannot import name 'field_validator'
```

Fix: require/accept explicit interpreter, or detect pydantic >=2; document venv.

### M2-3 Test count claim

M2 says 62; current merged source collects/passes 131 in the same four files.
Update the package README/status to the actual count and command.

### M2-4 Review merged UI

M2's 8 commits are merged at `2501120`; Review 12 PASS (source/test).
M2 should review the later upload form added by M1 in `56e11ca`, because it
touches `agent.js`, `agent.html`, and the download panel tests.

## P2 — M4 provenance / independence

### M4-4 Review 9–12 original

Original not recovered; M4 confirmed canonical reconstruction. Keep the
provenance sentence; do not label it verbatim.

### M4-5 Review 12 / T7.7 / T8.5 evidence level

```text
Review 12 PASS: source + unit/HTTP; browser DOM not specifically exercised
T7.7 PASS: source/test
T8.5 PASS: backend no-key tests
M4 = Lead same operator
```

If v1.1.1 claims browser verification, add a browser test that opens the P1 job
and checks `scope：unknown` / `bounded：unknown`.

## P3 — M3/M5

```text
V5 16/16, 8/8, 65/65: PASS
M3 executor self-test: 9/9
M5 adapters/assistant: pass in current source
No new M3/M5 blocker for v1.1.1.
```

## Acceptance for v1.1.1

```text
clean clone
pytest -q -> 717 passed / 2 Linux-only skipped / 0 failed
shasum -a 256 -c artifacts/**/SHA256SUMS -> direct pass
agent upload repaired ELF -> artifact + download link
Review 12 browser check (or explicitly source/test only)
tag v1.1.1 annotated; v1.1.0 untouched
```
