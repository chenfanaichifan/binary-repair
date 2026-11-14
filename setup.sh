#!/usr/bin/env bash
# Minimal local setup for the feature line. Never consumes a model key and
# never installs anything without printing the command first.
set -euo pipefail
cd "$(dirname "$0")"
python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ required")
print("python", sys.version.split()[0])
PY
if [ ! -d .venv ]; then
  echo "next: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
else
  echo ".venv present"
fi
for tool in clang cc; do
  if command -v "$tool" >/dev/null 2>&1; then echo "$tool: $(command -v "$tool")"; else echo "$tool: missing (needed for assembly/Route A compile)"; fi
done
if command -v .venv/bin/python >/dev/null 2>&1; then
  .venv/bin/python -m pytest -q tests/test_ai_assembly_calls.py tests/test_symbol_resolver.py 2>/dev/null || true
fi
echo "Ghidra is optional; set BINARYREPAIR_GHIDRA_HOME to use export_with_callees.py."
