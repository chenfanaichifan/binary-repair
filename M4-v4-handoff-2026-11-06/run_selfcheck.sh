#!/bin/sh
# Environment self-check, with its result compared against the recorded one.
#
#   sh run_selfcheck.sh
#
# Exit 0 only when every check passes and the normalised result equals
# expected/selfcheck.expected.json. Works from any working directory and from a
# freshly extracted copy of this handoff.
set -u

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PY=${PY:-/opt/angr-venv/bin/python}

if [ ! -x "$PY" ]; then
    echo "no interpreter at $PY" >&2
    echo "this handoff expects the venv built by provision_angr_venv.sh" >&2
    exit 2
fi

TMP=$(mktemp -d 2>/dev/null || mktemp -d -t selfcheck) || exit 2
trap 'rm -rf "$TMP"' EXIT INT TERM

echo "\$ $PY scripts/selfcheck.py --json $TMP/selfcheck.json"
"$PY" "$HERE/scripts/selfcheck.py" --json "$TMP/selfcheck.json"
rc=$?
echo

if [ "$rc" -ne 0 ]; then
    echo "FAIL: the self-check itself exited $rc"
    exit "$rc"
fi

echo "\$ compare with expected/selfcheck.expected.json"
"$PY" - "$TMP/selfcheck.json" "$HERE/expected/selfcheck.expected.json" <<'PY'
import json
import sys

got_path, want_path = sys.argv[1], sys.argv[2]
got = json.load(open(got_path, encoding="utf-8"))
want = json.load(open(want_path, encoding="utf-8"))


def walk(a, b, path=""):
    """Yield the first difference as (path, got, want), depth first."""
    if type(a) is not type(b):
        return [(path or "<root>", a, b)]
    if isinstance(a, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a:
                return [(f"{path}.{key}", "<missing>", b[key])]
            if key not in b:
                return [(f"{path}.{key}", a[key], "<missing>")]
            diff = walk(a[key], b[key], f"{path}.{key}")
            if diff:
                return diff
        return []
    if isinstance(a, list):
        if len(a) != len(b):
            return [(f"{path}.length", len(a), len(b))]
        for index, (x, y) in enumerate(zip(a, b)):
            diff = walk(x, y, f"{path}[{index}]")
            if diff:
                return diff
        return []
    return [] if a == b else [(path or "<root>", a, b)]


diff = walk(got, want)
if not diff:
    print(f"  identical: {got['passed']}/{got['total']} checks, same engine block")
    print()
    print("PASS: this machine matches the recorded environment")
    sys.exit(0)

path, mine, theirs = diff[0]
print(f"  first difference at {path}")
print(f"    measured {mine!r}")
print(f"    recorded {theirs!r}")
print()
print("FAIL: the measured environment is not the recorded one")
sys.exit(1)
PY
