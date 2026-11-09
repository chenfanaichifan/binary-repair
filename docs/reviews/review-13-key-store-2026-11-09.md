# Review 13 — v1.2.1 assistant key store / API (independent security review)

- **Date:** 2026-11-09 (Asia/Shanghai)
- **Reviewer role:** M3 (reviewer role), independent of M2 (producer of the key feature)
- **Review target:** branch `release/v1.2.1`
  - code state reviewed: `b7ee9a882a6860751fcb89a46f2aa589ebe8b9da` ("docs: record v1.2.1 rc1 candidate and M5 confirmation")
  - branch head at review close: `8f0908af5e0fb319db4dccd2c0428758ce9e69b1` ("fix(assistant): honor llm mode for jobless and job plans")
  - the branch moved while the review was running; every delta commit was reviewed (see §2). All key-scope files are **byte-identical** between `b7ee9a8` and `8f0908a` **except `agent.js`**, which changed only in `97c565d` (page reload after a successful key test; behavior-only, reviewed — no key handling change). The other code deltas (`backend.py`, `controller_api.py`, `8f0908a`) do not touch the key store/API; their key-consumption paths were reviewed and add no echo/log/prompt path.
- **Review worktree:** `D:\BinRepair\.tmp\review-v121` (detached HEAD at `8f0908a`; `git status --porcelain` empty before and after).
- **Host:** Windows, workspace-write sandbox; Python 3.12.15 (`D:\Binary_Repair\.venv\Scripts\python.exe`), pytest 9.2.0, FastAPI 0.162.0, httpx 0.28.1.
- **Fake keys only.** No real provider key was read, written, logged, or transmitted by this review. No provider call was completed; the one attempted call was blocked by the probe's egress guard. No P1/V5 run was repeated, no binary was executed, no VM was started.
- **Conclusion up front:** **PASS WITH LIMITATION** — no full-key disclosure was found in the reviewed store/API/UI/export paths, but two MEDIUM findings (mask policy, bundle-evidence path containment), one MEDIUM concurrency/atomicity defect, and several LOW findings are recorded, and the POSIX 0600 fallback was not executed on a POSIX host.
- **Fix re-review (same day, reviewed source `0d5791a`):** M5 fixed F1/A-1/F3 and partially mitigated F2; independent re-verification found **F2 not fixed** (HIGH residual bypasses) plus residual F1/A-1 edges. See **§9 addendum** — it supersedes the per-finding statuses above but not the original evidence.

---

## 1. Review scope (审查范围)

### 1.1 Files reviewed line by line

| File | Blob (git SHA-1, `8f0908a`) | Focus |
|---|---|---|
| `app/services/assistant_key_store.py` (241 lines) | `6982474de524afc928ca51f7bf97abf056c6461a` | whole file: path, DPAPI, 0600 fallback, atomic write, validation, masking, status, load/clear |
| `app/services/assistant_llm.py` (704 lines) | `992cbfd019247ed4042b918af911d39996242244` | key read/precedence, `Authorization` header, `repr`, error mapping, `test_provider_connection`, `.env` loader |
| `app/main.py` (1021 lines) | `542b48e74a5d106d1e8f5291bb863caab9dcd96f` | the 4 key routes (`822-890`), session/CSRF middleware (`46-178`), export/report/artifact routes (`893-1008`) as needed for item 3 |
| `app/static/js/agent.js` (1746 lines) | `c366541bdeed6a0ea634cce32ccff457bd3c893a` | key panel `1608-1697`, `setText`, storage/history/URL use, CSRF header wiring |
| `app/templates/agent.html` (10,394 B) | `7a3ce91a15e9b0490ed863276ff2a846d3e33eef` | key panel `170-181`, `data-csrf` at line 21, password input `173-176` |
| `tests/test_assistant_key_store.py` (40 lines) | `4734876e99f5b8a599077c9d328c337143c6f45a` | what the committed tests actually assert |
| `tests/test_assistant_key_api.py` (96 lines) | `e2f45147ed97429297d50a1452ceb2ab231aa2d0` | same, at the HTTP boundary |

`tests/test_agent_console.py` (56 tests) was run as required and read for relevant key-panel assertions.

### 1.2 Adjacent paths inspected because a checklist item requires them

- Export/report/artifact: `app/main.py:893-908, 940-1008`, `app/backend.py:75-260` (`build_export_bundle` and all backend variants).
- Bundle/evidence ingestion (handoff path): `app/services/attempt_writer.py:49-142`, `tools/routea_bundle_to_attempt.py:95-140`, `workers/route_a/attempt_from_bundle.py:28-110`, `app/controller_api.py:178-265`.
- Key precedence consumer: `app/services/assistant_llm.py:531-563` (`client_from_env`).
- Delta commits added during the review: `97c565d` (`agent.js` reload after key test), `8f0908a` (`backend.py` mode passthrough; `controller_api.py` LLM plan path now builds `client_from_env()`).

### 1.3 Out of scope / not re-run

- P1 and V5 were **not** re-run; no P1/V5 evidence file was modified (verified empty diff since `b7ee9a8`; see §8 and the evidence transcript).
- No real provider call, no real key, no browser journey replay, no POSIX host, no VM.
- Public `main` and any tag were not touched by this review.

---

## 2. Method and independence

- **Lead review:** full static read of the files above; independent replay of the security-critical claims (DPAPI, validation matrix, CSRF/session, env precedence, save failure, masking, real-uvicorn log capture, repository key scans) with fake keys only.
- **Three independent focused reviews**, each with its own evidence file (kept out of git because they contain machine transcripts; paths under `D:\BinRepair\.tmp\review-findings\`):
  1. `backend-findings.md` — key store, provider-key handling, routes, committed tests (static + focused probes).
  2. `frontend-export-findings.md` — `agent.js`/template panel, browser-storage/DOM, export/handoff/report/download paths, repository key scan.
  3. `probe/probe-results.md` + `probe/probe.py` — in-process adversarial probe of the four routes (CSRF matrix, echo sink scan, env precedence, DPAPI at rest, save failure, masking, concurrency), with an egress guard and no uvicorn process.
- **Independence statement:** the reviewer is a different role/window from M2, who produced the feature. This is role separation, not human-independent review: all role windows are AI agents operated by the same owner. It is recorded here so no two-person-signature claim is inferred.
- The reviewer re-verified the material claims made by the focused reviews; where a verdict differs it is called out (item 1 and item 8 in §3).

---

## 3. Test commands and numbers (测试命令/数字)

### 3.1 Required command, as given

```bash
BINARYREPAIR_BINUTILS_DIR=/opt/homebrew/opt/binutils/bin \
python -m pytest -q \
  tests/test_assistant_key_store.py \
  tests/test_assistant_key_api.py \
  tests/test_agent_console.py
```

**This exact form cannot run on the review host:** `/opt/homebrew/opt/binutils/bin` is a macOS path and does not exist on this Windows host; the host Python is 3.12.15 in `D:\Binary_Repair\.venv`. The equivalent Windows form was run; `BINARYREPAIR_BINUTILS_DIR` was set to the Windows binutils directory documented in `docs/fixtures.md` (absent on this host, but none of the three files invokes `readelf`/`objdump` — verified by grep — so the variable is inert for these files).

### 3.2 Environment defect found first (recorded, not hidden)

The plain run fails at pytest fixture setup, before any app code runs:

```text
ERROR tests/test_assistant_key_store.py::test_key_round_trip_is_masked_and_removable
ERROR ...
E   PermissionError: [WinError 5] 拒绝访问:
    '...\pytest-of-<user>'
```

Cause: pytest's `tmp_path` factory creates its temp directories with POSIX mode `0o700`; this DSH Windows sandbox maps the mode onto the directory ACL in a way that makes the same confined token unable to list/scan them. This is a **host sandbox defect, not an application defect**: CPython documents that the `mode` argument is ignored on Windows. A scratch-only pytest plugin (`D:\BinRepair\.tmp\review-findings\hostshim\dshenv_win_temp.py`) restores the documented Windows behavior for the test process (ignores the POSIX mode on `os.mkdir`/`Path.mkdir`). No project file, no test, and no assertion was modified.

### 3.3 Required suite — observed result at final head `8f0908a`

```text
D:\Binary_Repair\.venv\Scripts\python.exe -m pytest -q -o addopts= \
  -p dshenv_win_temp -p no:cacheprovider \
  tests/test_assistant_key_store.py tests/test_assistant_key_api.py tests/test_agent_console.py
-> exit 0
-> 63 passed, 1 warning in 1.38s

per file:
  tests/test_assistant_key_store.py   2 passed
  tests/test_assistant_key_api.py     5 passed
  tests/test_agent_console.py        56 passed
```

`-o addopts=` overrides `pytest.ini`'s `addopts = -q`; the literal required command form would otherwise run at `-qq` and print no summary line (the test-planet dots are then the count).

### 3.4 Required grep check

```bash
grep -RIn "BINARYREPAIR_ASSISTANT_PROVIDER_KEY\|sk-" \
  app tests docs delivery --exclude='*.pyc' | head
```

Windows equivalent (`git grep` over the tracked tree; `-RIn` over the working tree is equivalent here because the worktree was clean):

```text
git grep -In -E 'BINARYREPAIR_ASSISTANT_PROVIDER_KEY|sk-' -- app tests docs delivery
-> 92 hits, exit 0 (first hits shown in §5/testing evidence file)
```

Every hit was classified; the classes are: the environment-variable **identifier** in code/docs/tests, obviously fake test keys (`sk-test-…`, `sk-api-…`, `sk-env-…`, `sk-stored-…`, `sk-csrf-…`, `sk-probe-…`, `sk-SENTINEL-DO-NOT-LEAK`), the `.env.example` placeholder `sk-your-key-here`, and false positives where `sk-` occurs inside words such as `task-`, `disk-`, `risk-`. **No real key.**

Additional independent scans (both by a focused review and re-run by the Lead):

```text
git grep -In -E 'sk-[0-9a-fA-F]{24,}' -- . ':!*.pyc'        -> 0 hits  (no DeepSeek-shaped key)
git grep -In -E 'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}' -> 0 hits
tracked byte scan: 1,370 tracked files + 85 zip archives (members scanned, incl. delivery/) 
                   -> 49 raw pattern hits, all placeholder/fake; no key-like token inside any zip
git check-ignore -v var/assistant.key                         -> .gitignore:20:var/
git ls-files 'var/*' '.env'                                   -> empty
Test-Path var/assistant.key / .env in the review worktree     -> False / False
```

### 3.5 Adversarial probe of the four routes (in-process, fake keys, egress guarded)

Required probes `(a)`–`(g)` of the probe review: **(a)–(f) PASS, (g) FAIL.**

| Probe | Result |
|---|---|
| (a) CSRF/session on save/test/delete | PASS — 6/6 missing/wrong-token calls → `403 {"detail":"CSRF token missing or invalid."}`; no state change; correct token → save 200, test 503 (`llm_client_not_configured`, no provider call), delete 200; GET 200 with cookie / 401 without; foreign `Host`/`Origin` → 403 |
| (b) key never echoed/logged | PASS — invalid JSON/array/string/non-string/empty/whitespace/513-char/newline → 422 fixed strings; 512-char accepted; 0 full-key leaks across 148 bodies/headers/log/stdout sinks and 248 logging records |
| (c) environment precedence | PASS — POST/DELETE → 409, stored file absent or byte-unchanged; GET `source=environment`, `can_clear=false` |
| (d) Windows DPAPI at rest | PASS — 313-byte file starts `BRKEY1\n`; plaintext and base64 of the fake key absent; `protection=dpapi-user`; `load_key()` round-trips |
| (e) save failure | PASS — 500 `{"detail":"could not persist the key."}`, no key in body/logs, no `*.tmp`, previous key unchanged (same sha256) |
| (f) masking measurement | PASS as measurement — 9-char key exposes 7 literal chars (`sk-…ke99`), 12-char exposes 7, ≤8-char exposes 0 (finding F1) |
| (g) atomicity under concurrent saves | **FAIL** — see A-1: with one fixed `<key>.tmp`, 8/8 concurrent HTTP rounds had at least one 500; 2/8 had both 500; one captured round returned **HTTP 200 while no key file existed** (interleaving trace in `probe-raw.json`). A pre-existing stale `.tmp` also makes the next save 500 once (A-3) |

Lead's independent reruns of the security-critical claims agreed with the probe: DPAPI file shape/round-trip, `BRKEY1` magic and no plaintext; validation matrix (`422` paths); env 409s; save-failure 500 with no tmp/no key; CSRF 403s; `Host`/`Origin` 403s; GET read-only.

### 3.6 Real-server log check (supplement, Lead)

A real `uvicorn` process was started on `127.0.0.1:8817` with a scratch key file, a fixed session token, and deterministic mode; save/status/oversize/whitespace/clear requests were sent with a fake key. Observed:

```text
access log lines: only method/path/status, e.g.
  "POST /api/assistant/key HTTP/1.1" 200 OK
fake-key occurrences in stdout+stderr: 0
validation: oversize -> 422 "API key is too long"; whitespace -> 422 "API key must not contain whitespace"
```

The API key does not enter the server logs. **However** the access log does record the login URL including the session token (`GET /?token=<session-token> ...`), which is a session-boundary finding recorded as F8 (not an API-key finding).

### 3.7 Committed-test coverage (what the two target test files do not catch)

The 7 committed key tests pass and exercise real code, but they would **not** catch several regressions found or simulated during this review (finding F9):

- a Windows DPAPI → base64 downgrade: the store test asserts only that the raw key bytes are absent, never that the file starts `BRKEY1\n` or that `saved["protection"] == "dpapi-user"`, and a simulated downgrade passes every assertion;
- the short-key mask over-reveal (F1) passes all mask assertions;
- no negative tests for wrong/absent CSRF on DELETE or `/test` (only missing-token POST), empty/whitespace/oversized/non-string keys at the API, route-level env 409s, save-failure paths, corrupt key file, POSIX 0600/atomicity, or key absence in logs.

---

## 4. Findings (发现)

Severity scale: HIGH = full secret exposure or exploitable authorization break; MEDIUM = security-relevant weakness with preconditions, or integrity/failure under realistic use; LOW = hardening/robustness; INFO = design note. Evidence paths are relative to the reviewed commit unless stated.

### F1 — MEDIUM — Masked status over-reveals short keys; no minimum key length

- `mask_key()` returns `key[:3] + "…" + key[-4:]` for any key longer than 8 (`assistant_key_store.py:212-217`). That is 7 literal characters; for a 9-character key it exposes **7/9 = 78%** (`sk-…ke99`), for 12 characters 7/12. For a real DeepSeek-style ~35-character key it exposes 7/35 = 20% (prefix is the known `sk-`).
- The mask is returned by `GET /api/assistant/key` (`main.py:822-825`, via `key_status()` at `assistant_key_store.py:236`) and by the POST save response, and is rendered in the panel (`agent.js:1608-1626`). The full key is never returned.
- No minimum length/format check exists (`assistant_key_store.py:169-176`; `main.py:842-844`), so a short value — a misconfigured key, or a valid short key from a future adapter — can be saved and then mostly disclosed in the authenticated local page.
- No cross-origin read path: the app has no CORS middleware, the session gate and CSRF/Origin checks apply, and all rendered text goes through `textContent`.
- **Why not scored higher:** the disclosure is to the authenticated same local session that typed the key (the key owner), and realistic DeepSeek keys are long. The backend reviewer scored this item FAIL; the Lead records it as a release-relevant MEDIUM hardening defect rather than a full-key leak.
- **Recommendation (before a stable v1.2.1 tag):** mask to a fixed short tail (e.g. `sk-…` + last 4 only for keys of plausible length, otherwise bullets), and require a plausible minimum length/format before accepting a key. Do not commit key-derived text to records (see F3).
- **Evidence:** backend-findings.md §2 item 1/F1; probe result (f); Lead probe (`masking of short keys: 9-char → 7 visible, 13-char → 7 visible`).

### F2 — MEDIUM — Bundle-evidence ingestion can copy `var/assistant.key` into the artifact/export path

- The GUI/API export paths are clean (§3 checklist item 3). But two host-side bundle adapters accept a path declared by a **result bundle** and copy it into `data_dir/jobs/<job>/artifacts/...` with a DB artifact row, without containing the source path:
  - `app/services/attempt_writer.py:113-134` (`evidence_files`; relative paths resolved against the input file's parent, absolute paths used as-is) → `_register()` copies (`:49-85`);
  - `tools/routea_bundle_to_attempt.py:116-120` (`(evidence_root / relative_path).resolve()` with no `relative_to()` check) → `_register()`;
  - pass-through: `workers/route_a/attempt_from_bundle.py:33-45` returns an absolute bundle path unchanged.
- A crafted/compromised bundle (guest/worker output is explicitly untrusted data) can therefore name the on-disk key file; it gets copied, hashed and registered, and is then listable/downloadable through the controller artifact endpoint and referenced (name/`content_url`, not bytes) in the GUI export. The focused review demonstrated the `_register` primitive copying a scratch `var/assistant.key` into the artifact store; this was not driven through the full guest→GUI wiring (the pipeline is not wired end-to-end at this commit).
- Impact depends on the fallback: on Windows the copy is DPAPI ciphertext (not usable by another user without the same DPAPI context); on the POSIX `mode-0600` fallback the file is `BRKEY0` + **base64, i.e. plaintext** to anyone who can read the exported artifact or handoff package. Preconditions: operator runs a host adapter on an untrusted bundle.
- **Recommendation:** add the containment checks already used elsewhere (`tools/route_bundle_ingest.py:73-87`, `workers/executor/run_job.py:173-189`) to both adapters, reject absolute bundle-declared paths, and/or keep the key file outside the `data_dir` tree. Until then, the handoff claim “key never exported” must be read with this limitation.
- **Evidence:** frontend-export-findings.md §3.2/§3.3, §7 (`evidence_path_probe.py`); Lead code re-read of the three files.

### A-1 — MEDIUM — Concurrent saves are not atomic; one captured round returned HTTP 200 with no key persisted

- Root cause: `_atomic_write()` uses one fixed temp path `path.with_name(path.name + ".tmp")` with `O_EXCL`; the losing writer's unconditional `finally: tmp.unlink()` deletes the winner's in-flight temp file (`assistant_key_store.py:143-166`). Consequences under two simultaneous saves (double-click, two tabs, script):
  - one request reliably fails with HTTP 500 (`FileExistsError`/`PermissionError`/`FileNotFoundError`);
  - both can fail (observed 5/25 store rounds, 2/8 HTTP rounds), leaving no key configured;
  - one captured round returned **HTTP 200 while the key file did not exist** afterwards (interleaving trace in `probe-raw.json`); the route has no “did the destination appear” check.
- No full-key leak and no corruption of a previously stored key were observed; this is an availability/integrity-of-report defect.
- **Recommendation:** unique temp name per writer (`tempfile.mkstemp(dir=path.parent, ...)`), unlink only that writer's own temp path, serialise `save_key`/`clear_key` with a process-wide lock (single local process), and/or verify the destination after `os.replace`.
- **Evidence:** probe-results.md §4.7/§5 A-1, `probe-raw.json`; complements backend-findings.md F3 (stale-temp first-save 500).

### F3 — LOW — Masked tails of real provider keys are committed in handoff records

- `docs/handoffs/218-v1.2.1-real-key-ui-journey-2026-11-09.md:21` records the panel status from a **real-key** journey including the mask tail (4 trailing characters of the real key); `docs/handoffs/216-real-deepseek-smoke-2026-11-09.md:22` records a masked tail as well (its own wording describes the UI path as fake-key-only). The values are deliberately not reproduced in this review.
- Four characters of a long random key are not enough to authenticate, and the repository is the project's own; but “no key material in committed records” is the team's rule, and the same mask policy is F1.
- **Recommendation:** scrub the masked tails from those records in a follow-up docs commit (or state explicitly that the displayed key was a fake fixture where that is the fact), and adopt “no key-derived characters in committed records” as a record rule.

### F4 — LOW — Plaintext envelope is accepted on Windows and status mislabels its protection

- `load_key()` accepts the `BRKEY0\n` + base64 envelope unconditionally (`assistant_key_store.py:195-197`), and `key_status()` decides the `protection` label from the platform, not from the stored envelope (`:227-229`). Verified on this host: writing a plaintext `BRKEY0` file (fake key) and calling `GET /api/assistant/key` yields `source=stored`, `protection="dpapi-user"`, `configured=true`.
- Requires write access to the key file (a local compromise/downgrade) and does not disclose the key; it is a truthful-reporting and defense-in-depth gap: a plaintext or tampered key file can be used and is reported as DPAPI-protected.
- **Recommendation:** derive the protection label from the envelope magic, and on Windows reject or re-protect a plaintext envelope (or clearly report `mode-0600`).

### F5 — LOW — Stale `.tmp` blocks the next save once

- A once-crashed/interrupted write can leave `assistant.key.tmp`; the next valid save fails with HTTP 500 once because of `O_EXCL`, then the function's own cleanup removes the stale file and a retry succeeds. Same fix as A-1.
- **Evidence:** probe S2; backend F3.

### F6 — LOW — Validation accepts control characters and non-ASCII; no minimum length

- Only whitespace (`ch.isspace()`) and >512 characters are rejected (`assistant_key_store.py:169-176`). `"\x00"`, embedded NUL, and non-ASCII keys were accepted with 200 in the probe. A NUL cannot be placed in an HTTP header, so the provider call fails safely and nothing is echoed; this is a validation-contract gap, related to F1's missing minimum length.
- **Recommendation:** restrict to printable ASCII (the documented provider-key alphabet), add a minimum/maximum plausible-length check.

### F7 — LOW — Save/clear override the environment-provided assistant mode

- POST save forces `BINARYREPAIR_ASSISTANT_MODE=llm` and DELETE forces `deterministic` (`main.py:857-860, 889`), although the comment says “an explicit env value wins”. Probe flipped an env-provided mode both ways. This changes process-global behavior, not the key itself; record it because it contradicts the in-code contract.

### F8 — LOW (session/CSRF boundary, adjacent to the key routes) — session token handling is weaker than the key file

- `var/session.token` is written with `token_file.write_text(...)` and default permissions (`main.py:55-66`), unlike the key file which is created 0600; the CSRF token is a process-lifetime static HMAC of it (`main.py:70`); and the real-server check observed the login token in the uvicorn **access log** (`GET /?token=<session-token>`), which follows the documented `?token=` bootstrap design.
- Impact: a local user/log reader who obtains the session token can mint the session cookie and CSRF token, then read the masked status and replace/clear the stored key — but cannot recover the DPAPI/0600-protected full key through the UI. The app's documented threat model is a single local operator, so this is recorded as an adjacent limitation, not a key-store defect.
- **Recommendation:** create `var/session.token` 0600 like the key file, and filter/redact the `token` query parameter in access logging; consider deriving CSRF per-request.

### F9 — LOW — Test coverage gaps

- See §3.7. The committed tests do not assert the DPAPI magic/protection label, the masking policy, or most negative paths; a simulated DPAPI→base64 downgrade passes all 7 tests. Add negative tests when fixing F1/F4/A-1, including POSIX 0600/atomicity coverage where a POSIX runner exists.

### INFO observations (no action required for rc1)

- `POST /api/assistant/key/test` has no try/except (`main.py:870-875`); the called function is designed never to raise, and a raise would yield a generic 500 without the key.
- `GET /api/assistant/key` sets no `Cache-Control`; the response contains only the masked status, never the key.
- The key file lives at `<repo>/var/assistant.key`, inside the default `data_dir` root (`app/backend.py:28`, `assistant_key_store.py:34-36`); all current artifact writers use `jobs/...` paths, so it is not reachable today (defense-in-depth: move it out of `data_dir` or deny-list non-`jobs/` artifact paths).
- The non-Windows fallback is base64, not encryption, and the status says `mode-0600` honestly; if POSIX ever becomes production, this needs a decision.
- `agent.js:6` still says the file “does not read or write the API key”, which is stale after this feature; the code itself is safe.
- `BINARYREPAIR_ASSISTANT_MODE=deterministic` does not gate `POST /api/assistant/key/test`: with a stored key the route builds a provider client and attempts the network by design (the probe blocked it). Deterministic mode is not an offline guarantee — relevant for offline demos, not a secret leak.
- During the review the branch added an LLM plan path (`8f0908a`, `app/controller_api.py`) that uses the same `client_from_env()` resolution (env key first, stored key second). No key is put in the plan, prompt, response, or log; reviewed as part of the delta.
- `97c565d` changed `agent.js` behavior only (page reload after a successful key test); no key handling change, no new echo/log/storage.

---

## 5. Checklist verdicts for the task's 10 items

| # | Item | Verdict | Basis |
|---|------|---------|-------|
| 1 | Can the key be echoed back? | **PASS for full-key echo; MEDIUM finding F1 on the mask** | Full key never in a response; only `masked`; mask over-reveals 7 chars for >8-char keys (78% for 9-char); no cross-origin read path |
| 2 | Can the key enter logs or error messages? | **PASS** | No `logging`/`print` in the key paths; error strings fixed; provider error keeps status only; `repr` hides the key; probe scanned 148 sinks/248 log records → 0 leaks; real uvicorn log scan → 0 occurrences |
| 3 | Can the key enter export/handoff? | **PASS for GUI export/report/download; LIMITATION via F2 + F3** | Export bundle is controller data only, no filesystem walk; `var/` gitignored; but bundle-evidence adapters can copy the key file into the artifact store (F2), and one real-key handoff record commits a masked tail (F3) |
| 4 | Does CSRF cover POST/DELETE? | **PASS** | All three unsafe routes require `X-CSRF-Token` (`main.py:835, 873, 881`; `_require_csrf` `:173-177`); missing/wrong → 403 with no state change; unauthenticated → 401 first; foreign `Origin` → 403; GET is read-only (session-boundary caveat F8) |
| 5 | Can the env key be overwritten/cleared from the UI? | **PASS** | `source=environment`, `can_clear=false`; POST/DELETE → 409 before any write; stored file untouched; status truthful (mode-override caveat F7) |
| 6 | Is non-Windows storage 0600? | **LIMITATION (not executed on POSIX)** | Code creates the temp 0600 (`O_CREAT|O_EXCL, 0o600`), replaces it, then `chmod 0o600`; faked-platform execution confirmed the exact calls; no POSIX host available (no WSL; VM unavailable) and `chmod` failure is swallowed |
| 7 | Is Windows storage DPAPI? | **PASS (executed on this Windows host)** | `BRKEY1\n` envelope, `CryptProtectData`/`CryptUnprotectData` with explicit ctypes signatures, current-user scope (no `LOCAL_MACHINE`), plaintext absent, round trip verified; cross-user refusal not tested (LIMITATION) |
| 8 | Is the file written atomically? | **PASS for a single writer; MEDIUM A-1 under concurrency** | temp in same dir, `O_EXCL`, `fsync`, `os.replace`, 0600; failed replacement preserves the old key and leaves no temp; concurrent saves can fail and once returned 200 with no file; stale temp blocks one save (F5); no directory fsync |
| 9 | Are empty/oversize/whitespace keys rejected? | **PASS** | Empty/whitespace-only/non-string → 422; internal whitespace/newline → 422; 513-char → 422, 512 accepted; store repeats the checks; control chars/non-ASCII/min-length gap = F6 |
| 10 | Does a save failure leak the key? | **PASS** | HTTP 500 fixed detail; no key in response/logs; no `*.tmp` leftovers; previous key bytes unchanged; stale-temp and blocked-path cases probed |

---

## 6. Not verified (未验证项)

1. **POSIX runtime behavior** — 0600 enforcement on a real POSIX filesystem, umask variants, chmod failure behavior. Host is Windows; WSL is not installed and the VMware guest could not be started from this session (`vmrun` unavailable). Only static analysis plus a faked-platform execution were done.
2. **DPAPI cross-user refusal / NTFS ACL isolation** — no second Windows user/administrator available. Same-user round trip is verified; that a different user cannot decrypt is inferred from current-user scope, not measured.
3. **Browser-level execution** — Node.js is absent on this host, so the panel was reviewed statically (textContent-only, no console/innerHTML, password input, cleared value) and the server side was exercised with `TestClient` and a real uvicorn process; no actual browser/DOM/Edge/Chrome run was replayed by this reviewer. The M2 records (docs 218/222) report such runs; they were not independently re-executed here.
4. **Real provider behavior** — no real key, no live DeepSeek request. Provider error-body behavior is covered by mock transports only; provider-side logging/retention is out of scope.
5. **Full F2 pipeline** — demonstrated at the `_register`/adapter level (the pipeline is not wired end-to-end at this commit), not by driving a crafted guest bundle through a live worker to a GUI download.
6. **Git history** — the key-material scan covers the tracked tree and all tracked zip members at the reviewed head; earlier commits were not scanned.
7. **Concurrency frequencies** — the A-1 failure modes are stable across >15 probe runs, but the exact per-run mix of errors and the 200-without-file rate are scheduler-dependent.
8. **Out-of-app handoff tooling beyond the files named in §1.2** — audited by reading the named scripts, not all scripts in the repository.

---

## 7. Conclusion (结论)

**PASS WITH LIMITATION.**

Rationale: across the reviewed store/API/UI/export paths, the full provider key is never returned to the browser, never logged, never put in a plan/prompt, never included in a GUI export/report/download, and cannot be overwritten or cleared while an environment key is active. On this Windows host the storage is genuinely DPAPI (magic, opaque bytes, round trip), single-writer atomic replacement is correct, validation rejects the required cases, and a save failure neither leaks the key nor destroys the previous key. The required targeted suite passes (63 passed, exit 0), and the required grep/scan finds no real key material.

The PASS is limited by the recorded findings, of which the following should be dispositioned before a stable `v1.2.1` tag (none of them blocks a prerelease candidate provided these limitations are disclosed with it):

1. **F1 (MEDIUM)** mask over-reveal for short keys and missing minimum key length — fix mask policy and validation, or explicitly accept for rc1.
2. **F2 (MEDIUM)** bundle-evidence path containment — fix before host bundle ingestion is used with untrusted packages, especially on the POSIX plaintext fallback.
3. **A-1 (MEDIUM)** concurrent-save atomicity — unique temp name + process lock + destination check; otherwise a double-click/two-tab save can report success while persisting nothing.
4. **F3 (LOW)** scrub the masked real-key tail from `docs/handoffs/218` (and 216) and adopt a no-key-derived-text-in-records rule.

The review does **not** certify: POSIX 0600 at runtime, browser DOM behavior, real-provider behavior, full bundle-ingestion pipeline. It also does not change any gate status: P1/V5 were not re-run and their evidence is unmodified; public `main` (`472aa94b8d931e03a2b20a8e4f671ba64f832230`) and tags were not moved; v1.2.1 remains a candidate branch.

---

## 8. Submission gates (提交门槛)

| Gate | Status | Evidence |
|---|---|---|
| Code review completed | **PASS** | 6 target files read line by line by the Lead, plus 3 independent focused reviews; all delta commits during the review reviewed |
| Security tests passed, or failure stated explicitly | **PASS (with environment adaptation disclosed)** | Required suite 63 passed / exit 0 on `8f0908a`; plain form is blocked by a host-sandbox `tmp_path` ACL defect (documented, reproduced); adversarial probe required (a)–(f) PASS, (g) FAIL, reported as A-1 |
| No key leakage | **PASS for full keys; LIMITATION F3** | No real key in tracked tree, delivered zips, tests, docs scan, logs, responses, or exports; masked 4-char tail of a real key committed in `docs/handoffs/218` (and a tail in 216) — values not reproduced here; fix recommended |
| P1/V5 evidence not modified | **PASS** | `git diff --stat b7ee9a8 8f0908a -- T8.3-evidence-* T8.3-refresh-* T8.3-supplement-* M4-v4-handoff-* delivery/p1-*` → empty; no P1/V5 run was repeated |
| Tags/main not moved | **PASS** | `origin/main` before and after: `472aa94b8d931e03a2b20a8e4f671ba64f832230`; no `v1.2.1` tag created; review is on a separate branch |
| Unverified items written out | **PASS** | §6 lists 8 explicit unverified items |

**Disposition for the team:** accept as the M3 independent review of v1.2.1 rc1 with the limitations above; open follow-up fixes for F1, F2, A-1 and the F3 docs scrub before a stable tag. No gate/tag/main change is requested or made by this review.

---

## Appendix A — Commands actually run (review-close head `8f0908a`)

```text
git -C D:\BinRepair fetch origin release/v1.2.1 (https, sslBackend=openssl)
git -C D:\BinRepair\.tmp\review-v121 checkout --detach 8f0908af5e0fb319db4dccd2c0428758ce9e69b1
D:\Binary_Repair\.venv\Scripts\python.exe -m pytest -q -o addopts= -p dshenv_win_temp \
  -p no:cacheprovider tests/test_assistant_key_store.py tests/test_assistant_key_api.py \
  tests/test_agent_console.py          -> 63 passed, exit 0
git grep -In -E 'BINARYREPAIR_ASSISTANT_PROVIDER_KEY|sk-' -- app tests docs delivery  -> 92 hits, classified
git grep -In -E 'sk-[0-9a-fA-F]{24,}' -- . ':!*.pyc'                                   -> 0 hits
git grep -In -E 'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}'     -> 0 hits
python lead-verify.py   (27 probes: session, CSRF/Origin/Host, validation, DPAPI, env, failure, masking)
uvicorn app.main:app --host 127.0.0.1 --port 8817 --log-level debug + fake-key HTTP client
python probe.py         (required CSRF/echo/env/DPAPI/failure/mask/concurrency matrix; egress guarded)
git diff --stat b7ee9a8 8f0908a -- T8.3-evidence-2026-11-06 T8.3-refresh-2026-11-06 \
  T8.3-supplement-2026-11-06 M4-v4-handoff-2026-11-06 delivery/p1-real-window-2026-11-07  -> empty
```

Detailed transcript excerpts: `docs/reviews/evidence/review-13-key-store-2026-11-09.txt`.
Reviewer working evidence (not committed; machine transcripts): `D:\BinRepair\.tmp\review-findings\` (`backend-findings.md`, `frontend-export-findings.md`, `probe/probe-results.md`, `probe/probe.py`, `lead-verify.py`, `lead-verify.log`).

## Appendix B — Independence statement

This review was produced by the M3 role, separate from the M2 role that implemented the key feature, and was supplemented by three independently-run focused reviews whose raw evidence was kept separate. All role windows are AI agents operated by the same human owner, and all ran on the same host. This is role-separated review, **not** a human-independent two-person signature; no such claim is made.

---

## 9. Fix re-review addendum — M5 fix commit `0d5791a` (2026-11-09)

**reviewed source `0d5791a317d0e6d06dd6de7a818dfc65f7378bdf`** ("fix(m5): harden key masking, atomic save, and evidence copy", M5, 2026-11-09 22:00 +0800).

- Release branch head at re-review close: `c495656` (docs-only delta over `0d5791a`: the `docs/handoffs/222` final verification/key-cleanup record; the reviewed code files are byte-identical between `0d5791a` and `c495656` — `git diff --stat 0d5791a c495656 -- <scope files>` is empty).
- Reviewed diff: `git diff 8f0908a 0d5791a` for `app/services/assistant_key_store.py`, `app/services/attempt_writer.py`, `tools/routea_bundle_to_attempt.py`, `tests/test_assistant_key_store.py`, plus docs 216/218/222/226. `tools/route_bundle_ingest.py` was unchanged by the fix and was re-checked.
- Method: Lead static review + dynamic probes, plus one independent adversarial verifier (`fix-verifier`, Team task `task-4`) with separate raw logs. Fake keys only; no provider/network call; no tracked file modified; no P1/V5 rerun.

### 9.1 Fix verdicts

```text
reviewed source 0d5791a
F1:  FIXED (stored/API path) / PARTIAL (environment-key residual = new finding N-1)
A-1: FIXED (original defects) / PARTIAL (residual N-2 MEDIUM: spurious concurrent-save 500 on Windows)
F2:  NOT FIXED (partial mitigation only; bypasses N-3 HIGH)
F3:  FIXED
new echo/log path: NONE (PASS)
```

- **F1 — mask/validation — FIXED for the stored/API path.** `mask_key` now returns `"*"*(len-4)+key[-4:]` (`app/services/assistant_key_store.py:228-231`): verified for lengths 5/8/15/16/33/512 — only the last 4 characters visible, no prefix leak. `_validate_key` (`:175-183`) enforces min 16, max 512, no whitespace, printable ASCII; API mapping verified: 15→422 `API key is too short`; 16→200; 512→200; 513→422 `API key is too long`; non-ASCII/NUL→422 `API key must be printable ASCII`; tab/newline→422 `API key must not contain whitespace`; empty/whitespace/non-string→422 `key is required.`. **Residual (N-1 LOW):** environment keys bypass `save_key` validation entirely and `mask_key` reveals the whole value when `len<=4` (verified: `BINARYREPAIR_ASSISTANT_PROVIDER_KEY=abcd` → `GET /api/assistant/key` masked `"abcd"`); 5–8-char env keys reveal 4 characters; a hand-written `BRKEY0` file is equally unvalidated.
- **A-1 — atomicity/concurrency — FIXED for the original defects; PARTIAL residual (N-2 MEDIUM).** Implemented: `tempfile.mkstemp` unique temp per writer (`:149`), `_SAVE_LOCK` around `save_key`/`clear_key` (`:31,194,220`), post-`os.replace` existence check (`:161-163`), `fchmod 0600` (`:152-155`). Verified: 20/20 rounds of two concurrent `save_key()` threads → no errors, final key is one complete input, no `*.tmp`; stale `assistant.key.tmp` no longer blocks; injected `os.replace` failure → OSError, old key preserved, no temp, generic HTTP 500, no key echo; replace-then-vanish → post-replace check raises, HTTP 500 instead of a false 200. **Residual N-2:** two simultaneous `POST /api/assistant/key` (two event loops, as in the two-`TestClient` harness) still give one spurious HTTP 500 per round (8/8 here; 9/10 and 10/10 in the verifier's runs) with `PermissionError [WinError 5]` on `os.replace`, because the competing request's `key_status()`/`load_key()` read holds `assistant.key` open on Windows. No corruption, no leak, the winner's key is complete, retry succeeds. In the documented single-process uvicorn configuration the async handlers serialise after their single `await request.json()`, so the residual needs multi-event-loop / multi-worker / cross-process callers; it is recorded as a limitation, not a security defect.
- **F2 — secret-path rejection — NOT FIXED (partial mitigation).** The exact basenames `assistant.key`, `.env`, `session.token` are now refused before copying in `app/services/attempt_writer.py:57-58` and `tools/routea_bundle_to_attempt.py:46-47` (verified). Bypasses that still copy the stored key are demonstrated in N-3: the fix is a three-name denylist, not containment.
- **F3 — masked real-key tails — FIXED.** `docs/handoffs/216…:22` and `docs/handoffs/218…:21` now read `sk-…<masked>`; no real-key tail remains in the current tracked tree. INFO: git history is append-only here — commit `8f0d728` still contains the old `…6789`/`…27d8` tails (rewriting history is the team's decision); the fake-key tail in `docs/handoffs/222` was removed by the final `c495656` docs commit.
- **No new echo/log path — PASS.** The fix commit adds no `print`/logging line (all 92 added lines scanned); save/status/delete and error responses, headers, 24 captured logging records, stdout/stderr contain no full fake key; the stored file remains DPAPI (`BRKEY1`, plaintext absent, round trip OK).

### 9.2 New findings

- **N-1 (LOW) — environment/hand-written keys bypass the new mask/validation policy.** `_env_key()` accepts any non-empty stripped string, `mask_key` reveals the entire value for `len<=4`, and non-ASCII env keys are accepted. Only reachable through operator-set env vars or a hand-written key file, never through `save_key`/POST. Recommendation: apply the same printable-ASCII/min-length policy to env keys, or mask anything shorter than the validation minimum with bullets only.
- **N-2 (MEDIUM, availability) — residual concurrent-save 500 on Windows.** See A-1; reachable only with multi-event-loop/process callers, not the documented single-process uvicorn. Recommendation if multi-process support is ever claimed: take the read path under the same lock, or briefly retry `os.replace` on `PermissionError`.
- **N-3 (HIGH — the unfixed part of F2) — the three-name denylist is bypassable, and one code path skips it.** Demonstrated by the Lead and independently by the verifier (fake keys, copied bytes verified in the artifact store):
  - **Windows filename aliases** pass the name check while reaching the same file: `ASSISTANT.KEY`, `Assistant.Key`, `assistant.key.`, `assistant.key `, `assistant.key::$DATA`, and a hardlink with a different basename (all copied by `attempt_writer`; it does not canonicalise the source path). An absolute/relative alias declared by a bundle is copied end-to-end into `jobs/<job>/artifacts/...` and is then downloadable/exported.
  - **Route A multi-evidence branch skips the per-source check entirely:** `tools/routea_bundle_to_attempt.py:123-136` zips all evidence for a gate first and only calls `_register()` on the archive (`V0-evidence.zip`), whose basename is not on the denylist. Lead reproduction: a V0 gate with two evidence paths (`assistant.key` + an innocuous file) produced a registered artifact whose ZIP contains `assistant.key` in plaintext. Single-evidence paths are blocked only because `convert()` canonicalises with `Path.resolve()` (`:119`).
  - **Operator-custom key filenames** (`BINARYREPAIR_ASSISTANT_KEY_FILE=…\mykey.dat`) are copied by both writers — the key store's configured path is not what the denylist checks. On this Windows host the copied bytes are DPAPI ciphertext; on the POSIX `mode-0600` fallback the same copy is base64 plaintext, i.e. direct key exposure.
  - `tools/route_bundle_ingest.py` remains safe (unchanged by the fix): `_safe_file` (`:73-89`) rejects absolute paths, `..` escapes, symlinks, and missing files (verified: absolute/`..`/missing rejected). Symlink and 8.3-short-name vectors could not be executed on this host (symlink privilege unavailable; 8.3 names disabled) — recorded as unverified, not passed.
- **N-4 (LOW) — committed tests do not cover the fix's risk areas.** The new tests cover mask/validation/stale-temp only; no committed test covers F2 rejection (or its bypasses), concurrent saves/lock behaviour, replace failure, POSIX mode, or the environment-key mask edge. `test_short_and_non_ascii_keys_are_rejected` actually tests a NUL character, not a non-ASCII key.
- **N-5 (INFO) — documentation residuals after F3.** Old masked real-key tails remain in git history (`8f0d728`); the fake-key tail in `docs/handoffs/222` was removed at `c495656`; this review's own files contain fake-key mask examples only.
- **N-6 (INFO) — M5's `docs/handoffs/226` says "full suite: pass" without numbers.** This re-review ran the required target suite (66 passed, exit 0) and the verifier ran a focused 5-file subset (32 collected / 31 passed / 1 skipped; skip = symlink creation unavailable). The 740-test full-suite count in `docs/handoffs/222` was not independently reproduced.
- **N-7 (unchanged prior findings, not in the fix scope):** F4 plaintext `BRKEY0` envelope still accepted on Windows and reported as `protection="dpapi-user"`; F7 save/clear still override `BINARYREPAIR_ASSISTANT_MODE`; F8 session-token file permissions/access-log exposure unchanged; old probe finding H (DELETE with `KEY_FILE` pointing at a directory → unhandled 500) unchanged; deterministic mode still does not gate `POST /api/assistant/key/test`.

### 9.3 Tests and commands (re-review)

```text
required command (adapted as in §3: the macOS path does not exist here; sandbox tmp_path shim used):
D:\Binary_Repair\.venv\Scripts\python.exe -m pytest -q -o addopts= \
  -p dshenv_win_temp -p no:cacheprovider \
  tests/test_assistant_key_store.py tests/test_assistant_key_api.py tests/test_agent_console.py
-> exit 0; 66 passed, 1 warning in 1.40s
   (store 5 passed / api 5 passed / agent console 56 passed)

git diff --stat 8f0908a 0d5791a -- <reviewed files>  -> store 52 lines, attempt_writer +2,
                                                        routea +2, tests +24, docs 216/218/222/226
git diff --stat 0d5791a c495656 -- <scope files>     -> empty (docs-only branch movement after the fix)

Lead probes: mask matrix, validation matrix, DPAPI, 20-round store concurrency, 8-round route
  concurrency, replace-failure + false-success simulation, F2 alias/ZIP/custom-name bypasses,
  echo/log scan, P1/V5 + main/tag checks.
Verifier (independent): mask, validation, DPAPI, concurrency, secret-path, no-echo probes and a
  focused pytest subset; raw logs under D:\BinRepair\.tmp\review-fix\logs\ (not committed).
```

Full re-review transcript excerpts: `docs/reviews/evidence/review-13-fix-rereview-0d5791a-2026-11-09.txt`.

### 9.4 Limitations of this re-review

1. The POSIX `mode-0600`/`fchmod` path was not executed (Windows host; same limitation as §6). The F2 plaintext-copy impact on POSIX is inferred from code and earlier static analysis, not observed on POSIX.
2. Symlink and 8.3 short-name bypasses could not be executed here (Windows symlink privilege unavailable; 8.3 names disabled). The denylist logic suggests both would bypass; recorded as unverified.
3. The N-2 concurrent-save 500 was reproduced with two event loops (`TestClient` threads), not against a real multi-worker uvicorn deployment; production exposure under the documented single-process configuration is unverified.
4. No browser run and no real provider call in this re-review; the fake-key UI/API paths were driven with `TestClient`/direct calls.
5. `docs/handoffs/226`'s "full suite: pass" and `docs/handoffs/222`'s 740-test count were not independently reproduced (only the required target suite and the verifier's focused subset).
6. Git history was not rewritten or re-audited beyond noting the residual masked tails (N-5).

### 9.5 Updated disposition

- F1, A-1 and F3 are **substantially fixed and independently verified**; the F1 and A-1 residuals are LOW/MEDIUM non-confidentiality robustness edges (N-1, N-2).
- **F2 remains open and is release-relevant.** A crafted/compromised result bundle plus a host adapter can still copy the stored key file into the artifact store/export path (plaintext on the POSIX fallback, DPAPI ciphertext on Windows). The three-name denylist blocks only the default names; the containment fix recommended under F2 is still required, especially before any stable tag on a POSIX host.
- Suggested disposition: v1.2.1 may remain an **rc prerelease candidate** with these limitations disclosed; **hold the stable `v1.2.1` tag** until F2 is fixed (or explicitly accepted by the Lead with the POSIX plaintext constraint stated), and preferably address N-1/N-2 and the N-4 test gaps in the same follow-up. This is consistent with M2/M5's own "hold stable" recommendation in `docs/handoffs/222`.

### 9.6 Submission gates (提交门槛)

| Gate | Status | Evidence |
|---|---|---|
| Fix re-review completed | **PASS** | Lead static + dynamic probes + independent verifier (task-4); all four findings adjudicated; residuals recorded |
| No key leakage | **NOT CLEAN (F2 residual)** | No full key in committed files/logs/responses (scanned); but F2's host-side copy path can still copy the stored key file into artifacts/exports under a crafted bundle (N-3) — plaintext on the POSIX fallback; F3 real-key tails removed from docs 216/218 |
| Unverified items explicit | **PASS** | §9.4 (6 items) |
| P1/V5 evidence unmodified | **PASS** | `git diff --stat 8f0908a 0d5791a -- T8.3-* M4-v4-handoff-* delivery/p1-*` empty; no P1/V5 run repeated |
| Tags/main not moved | **PASS** | `origin/main` still `472aa94b8d931e03a2b20a8e4f671ba64f832230`; no `v1.2.1` tag; release branch moved by M2/M5 (`0d5791a`→`c495656`, docs-only), not by this review |
