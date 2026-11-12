import os
import tempfile

# readelf/objdump are only needed for the Route B static audit. A host may carry
# them outside PATH (a MinGW or LLVM install); point this at that directory
# instead of editing PATH by hand, so the bundle test is reproducible.
_binutils_dir = os.environ.get("BINARYREPAIR_BINUTILS_DIR")
if _binutils_dir:
    os.environ["PATH"] = _binutils_dir + os.pathsep + os.environ.get("PATH", "")

# Never inherit the operator's real stored key for session-scoped E2E servers.
_no_key = os.path.join(tempfile.gettempdir(), "binaryrepair-test-no-key")
try:
    os.unlink(_no_key)
except OSError:
    pass
os.environ["BINARYREPAIR_ASSISTANT_KEY_FILE"] = _no_key

# Deterministic session token for the non-browser test suite. These must be set
# before app.main is imported (module-level SESSION_TOKEN is read at import).
os.environ.setdefault("BINARYREPAIR_SESSION_TOKEN", "test-session-token")


import pytest


@pytest.fixture(autouse=True)
def _isolate_assistant_key(tmp_path, monkeypatch):
    """Never let an operator's real stored key leak into tests."""
    monkeypatch.setenv("BINARYREPAIR_ASSISTANT_KEY_FILE", str(tmp_path / "assistant.key"))
