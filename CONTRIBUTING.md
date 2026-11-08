# Contributing

Thanks for helping improve BinaryRepair.

## Ground rules

- Repairs are for **one known public fixture vulnerability**. Do not expand the
  scope silently.
- The host must never execute uploaded or repaired binaries. All execution,
  compilation and symbolic analysis belongs to the disposable guest under the
  broker.
- A model explanation is never evidence. Acceptance decisions come only from the
  deterministic V0–V5 engine.
- Missing checks stay `not_run`; never promote an unrun check to `passed`.
- Keep client binaries, private keys, credentials and private logs out of the
  repository.

## Development setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Checks before a pull request

```bash
python -m pytest -q
```

The recorded acceptance environment is Linux with Chrome CDP for browser e2e.
Windows hosts skip Linux-only and POSIX-fixture tests; mention that clearly if
you could not run the Linux record.

If you change acceptance evidence:

```bash
# verify every delivery package checksum
python - <<'PY'
import hashlib
from pathlib import Path
for sums in Path("artifacts").rglob("SHA256SUMS"):
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, rel = line.split(None, 1)
        path = sums.parent / rel.lstrip("* ")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, (sums, rel)
print("artifacts sums OK")
PY
```

Do not rewrite or regenerate a canonical V5 log to make a checksum pass.

## Pull requests

- Keep changes focused and describe the user-visible or acceptance impact.
- Link the relevant record under `docs/development/` or the relevant section of
  `docs/README.md`.
- For evidence changes, include the command used and the observed result.
- Do not move an existing release tag; create a new version instead.
- By contributing, you agree that your contribution is licensed under the
  repository's MIT license.
