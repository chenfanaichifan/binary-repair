import os

# readelf/objdump are only needed for the Route B static audit. A host may carry
# them outside PATH (a MinGW or LLVM install); point this at that directory
# instead of editing PATH by hand, so the bundle test is reproducible.
_binutils_dir = os.environ.get("BINARYREPAIR_BINUTILS_DIR")
if _binutils_dir:
    os.environ["PATH"] = _binutils_dir + os.pathsep + os.environ.get("PATH", "")

# Deterministic session token for the non-browser test suite. These must be set
# before app.main is imported (module-level SESSION_TOKEN is read at import).
os.environ.setdefault("BINARYREPAIR_SESSION_TOKEN", "test-session-token")
