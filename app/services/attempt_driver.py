"""Host-side attempt driver: dispatch one attempt to its route adapter.

The worker never executes binaries. It invokes ``BINARYREPAIR_ATTEMPT_CMD``
once per attempt with a fixed environment and expects a worker result bundle at
``BINARYREPAIR_RESULT_PATH``. This module is that command for the integrated
host: it reads the environment, locates the route evidence the guest produced,
and delegates to :mod:`app.services.attempt_writer`.

What this module does **not** do:

* it never runs, loads, or links the candidate or the original;
* it never manufactures a gate result 鈥?every value comes from measured
  evidence, and an absent check stays ``not_run``;
* it never falls back to a different route's evidence.

Exit codes (a non-zero status makes the worker persist ``error / tool_failed``
with this message as the detail, which is the intended fail-closed path):

* ``2`` 鈥?the worker environment is incomplete or names an unknown route;
* ``3`` 鈥?the route evidence directory is missing or incomplete;
* ``4`` 鈥?no adapter input exists for this route yet.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping

from app.services import attempt_writer

REQUIRED_ENV = (
    "BINARYREPAIR_DATA_DIR",
    "BINARYREPAIR_JOB_ID",
    "BINARYREPAIR_RUN_ID",
    "BINARYREPAIR_ATTEMPT_ID",
    "BINARYREPAIR_ROUTE",
    "BINARYREPAIR_RESULT_PATH",
)

ROUTE_B = "route_b"
ROUTE_A = "route_a"


def _fail(code: int, message: str) -> None:
    """Exit with a documented status and a single-line reason on stderr.

    The worker keeps the last stderr line as the attempt detail, so the message
    must stay readable on one line.
    """
    print(message, file=sys.stderr)
    raise SystemExit(code)


def routeb_bundle_dir(
    data_dir: str | Path, job_id: str, run_id: str, attempt_id: str
) -> Path:
    """Canonical staging directory for one attempt's Route B static bundle.

    The guest writes the bundle here; the host only reads it. Keeping the path
    derived from the attempt id makes it reproducible from the environment the
    worker already passes, so a wrapper needs no extra configuration.
    """
    return (
        Path(data_dir)
        / "jobs"
        / job_id
        / "runs"
        / run_id
        / "attempts"
        / f"{attempt_id}.routeb"
    )


def _missing(env: Mapping[str, str]) -> list[str]:
    return [name for name in REQUIRED_ENV if not env.get(name)]


def resolve_routeb_bundle(env: Mapping[str, str]) -> Path:
    """Return the Route B bundle directory: explicit override, else canonical."""
    raw = env.get("BINARYREPAIR_ROUTEB_BUNDLE")
    if raw:
        return Path(raw)
    return routeb_bundle_dir(
        env["BINARYREPAIR_DATA_DIR"],
        env["BINARYREPAIR_JOB_ID"],
        env["BINARYREPAIR_RUN_ID"],
        env["BINARYREPAIR_ATTEMPT_ID"],
    )


def _route_b(env: Mapping[str, str]) -> int:
    bundle = resolve_routeb_bundle(env)
    if not bundle.is_dir():
        _fail(3, f"route_b evidence directory is missing: {bundle} (the guest writes it; the host will not synthesise one)")
    if not (bundle / "candidate.elf").is_file():
        _fail(3, f"route_b evidence has no candidate.elf: {bundle}")
    return attempt_writer.main(["--routeb-bundle", str(bundle)])


def _route_a(env: Mapping[str, str]) -> int:
    raw = env.get("BINARYREPAIR_ATTEMPT_INPUT")
    if not raw:
        _fail(4, "route_a has no host adapter input yet; set BINARYREPAIR_ATTEMPT_INPUT to the generic result JSON")
    source = Path(raw)
    if not source.is_file():
        _fail(4, f"route_a adapter input is missing: {source}")
    return attempt_writer.main(["--input", str(source)])


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    """Run the driver. ``argv`` is accepted for ``python -m`` symmetry only."""
    if argv:
        _fail(2, f"attempt_driver takes no arguments, got: {argv}")
    current = os.environ if env is None else env

    missing = _missing(current)
    if missing:
        _fail(2, "worker environment is incomplete: " + ", ".join(missing))

    route = current["BINARYREPAIR_ROUTE"]
    if route == ROUTE_B:
        return _route_b(current)
    if route == ROUTE_A:
        return _route_a(current)
    _fail(2, f"unknown attempt route: {route!r}")


if __name__ == "__main__":
    raise SystemExit(main())

