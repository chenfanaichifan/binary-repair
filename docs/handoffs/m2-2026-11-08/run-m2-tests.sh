#!/usr/bin/env bash
# 跑 M2 的测试子集。
#
#   bash run-m2-tests.sh /path/to/binaryrepair-mvp
#
# 必须使用项目自己的 Python（pydantic >= 2）。
# 系统 Anaconda 的 pydantic 1.x 会在导入阶段直接报
#   ImportError: cannot import name 'field_validator'
# 所以本脚本不会盲目使用 PATH 上的 python。
#
# 解释器选择顺序：
#   1. $M2_PYTHON（显式指定，最高优先级）
#   2. <repo>/.venv/bin/python 或 <repo>/.venv/Scripts/python.exe
#   3. python3 / python，但必须通过 pydantic >= 2 探测
#
# 预期（交付分支 b6d110b）：
#   test_agent_console      54
#   test_agent_honesty       9
#   test_assistant_llm      59
#   test_assistant_tools    10
#   合计                   132 passed
set -euo pipefail

repo="${1:-.}"
cd "$repo"

has_pydantic_v2() {
  local cand="$1"
  "$cand" - <<'PY' >/dev/null 2>&1
import sys
try:
    import pydantic
except Exception:
    sys.exit(1)
parts = pydantic.VERSION.split(".")
sys.exit(0 if int(parts[0]) >= 2 else 1)
PY
}

PY=""
if [ -n "${M2_PYTHON:-}" ]; then
  if [ ! -x "$M2_PYTHON" ]; then
    echo "M2_PYTHON is set but not executable: $M2_PYTHON" >&2
    exit 2
  fi
  PY="$M2_PYTHON"
elif [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
elif [ -x ".venv/Scripts/python.exe" ]; then
  PY=".venv/Scripts/python.exe"
else
  for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1 && has_pydantic_v2 "$cand"; then
      PY="$cand"
      break
    fi
  done
fi

if [ -z "$PY" ]; then
  cat >&2 <<'MSG'
No usable Python found.

M2 tests need pydantic >= 2. Create and use the project venv:

  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
  bash run-m2-tests.sh /path/to/binaryrepair-mvp

Or point at an interpreter that already has pydantic >= 2:

  M2_PYTHON=/path/to/python bash run-m2-tests.sh /path/to/binaryrepair-mvp

Do not use a system Anaconda python with pydantic 1.x: it fails with
ImportError: cannot import name 'field_validator'.
MSG
  exit 2
fi

if ! has_pydantic_v2 "$PY"; then
  echo "python: $PY" >&2
  echo "This interpreter does not satisfy pydantic >= 2:" >&2
  "$PY" -c 'import pydantic; print("  pydantic", pydantic.VERSION)' >&2 2>&1 || true
  echo "Use the project .venv or set M2_PYTHON to a Python with pydantic >= 2." >&2
  exit 2
fi

# Windows 上默认临时目录路径太长会让 pytest 建 basetemp 失败，
# 优先用短的根路径。
if [ -n "${M2_BASETEMP:-}" ]; then
  BASE="$M2_BASETEMP"
  mkdir -p "$BASE"
elif [ -d "/c" ]; then
  BASE="C:/pt-m2"
  mkdir -p "$BASE"
else
  BASE="$(mktemp -d)"
fi

echo "python: $PY"
echo "pydantic: $("$PY" -c 'import pydantic; print(pydantic.VERSION)')"
echo "basetemp: $BASE"

exec "$PY" -m pytest --basetemp="$BASE" -q \
  tests/test_agent_console.py \
  tests/test_agent_honesty.py \
  tests/test_assistant_llm.py \
  tests/test_assistant_tools.py
