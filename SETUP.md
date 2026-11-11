# BinaryRepair candidate setup and smoke checks

Pinned candidate:

```text
version       v1.2.1-rc1
source        3418491  (chenfanaichifan/binary-repair)
public        d7d20f4  (leesirleesirlee-star/Binary_Repair)
public tag    v1.2.1-rc1 -> f5346978... -> d7d20f4
```

This guide starts the controller and GUI from one checkout and reproduces the
documented smoke checks. It does not publish a tag, move `main`, or write a real
API key.

## 0. Choose the checkout

For a teammate, the public candidate is the simplest reproducible tree:

```bash
git clone https://github.com/leesirleesirlee-star/Binary_Repair.git
cd Binary_Repair
git checkout d7d20f4ff2f920b5cfec5e81e3c4377529a9885a
```

The source delivery tree is:

```bash
git clone https://github.com/chenfanaichifan/binary-repair.git
cd binary-repair
git checkout 3418491
```

`3418491` is the source/docs head; `d7d20f4` is the public candidate. The
source-only N-11 wording correction is not a public code change.

## 1. Python environment

Windows PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Do not commit `.venv`, `.env`, `var/`, or any API key.

## 2. Start the backend

Terminal A:

```powershell
.\start-controller.ps1
```

Expected:

```text
http://127.0.0.1:8000/healthz
```

Linux:

```bash
.venv/bin/python -m uvicorn app.controller_api:app --host 127.0.0.1 --port 8000
```

If the port is occupied, use another loopback port and set
`BINARYREPAIR_API_BASE` accordingly.

## 3. Start the GUI

Terminal B:

```powershell
$env:BINARYREPAIR_BACKEND = "http"
$env:BINARYREPAIR_API_BASE = "http://127.0.0.1:8000"
.\start.ps1
```

The script prints a one-time URL with a local session token:

```text
http://127.0.0.1:8123/?token=...
```

Open it. The setup screen should render and the controller health check should
be green. The GUI is renderer-only; it must not decide the verdict.

Linux:

```bash
export BINARYREPAIR_BACKEND=http
export BINARYREPAIR_API_BASE=http://127.0.0.1:8000
./start.sh
```

## 4. Smoke checks

### 4.1 Offline provider plumbing

No API key, no network:

```bash
.venv/bin/python scripts/smoke.py --mock
```

Windows:

```powershell
.\.venv\Scripts\python.exe scripts\smoke.py --mock
```

Expected: configuration is printed redacted and the mock response contains a
`summary` and `word_count`.

### 4.2 Targeted tests

```bash
.venv/bin/python -m pytest -q \
  tests/test_assistant_key_store.py \
  tests/test_assistant_key_api.py \
  tests/test_agent_console.py
```

Expected (public rc1): `66 passed`.

### 4.3 Full suite, excluding browser e2e

```bash
.venv/bin/python -m pytest -q --ignore=tests/e2e
```

Expected on the pinned public candidate:

```text
741 collected / 739 passed / 2 Linux-only skipped / 0 failed
```

On Windows, the recorded public-tree result is:

```text
741 collected / 0 failed / 13 skipped
```

### 4.4 P0 GUI + controller acceptance

With both servers running and the GUI token printed:

```bash
.venv/bin/python tools/p0_acceptance.py \
  --gui http://127.0.0.1:8123 \
  --controller http://127.0.0.1:8000
```

If the token is not in `var/session.token`, pass `--token <printed token>`.
Expected: `P0 ACCEPTANCE PASSED` with 17 checks.

### 4.5 Browser e2e

Requires the browser test dependency and a local browser:

```bash
.venv/bin/python -m pytest -q tests/e2e
```

Expected: `12 passed`. If the dependency is missing, record `NOT RUN
(ModuleNotFoundError)`; do not rewrite it as passed.

## 5. Stop and clean

Stop both terminals with `Ctrl+C`. Delete `var/` if you want a fresh controller
store. Never delete `.git` or a checked-out candidate file.

## 6. What this verifies

```text
one checkout       source 3418491 or public d7d20f4
one backend        controller on 127.0.0.1:8000
one UI             GUI on 127.0.0.1:8123 in http mode
one smoke path     mock provider + targeted tests + P0
one pinned test    full suite / e2e numbers above
```

It does not verify a new public release, move `v1.2.1-rc1`, or approve v1.2.1
stable.
