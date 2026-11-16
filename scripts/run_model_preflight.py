#!/usr/bin/env python3
"""Offline-safe preflight for the unified LLM gateway.

No request is sent unless ``--live`` is explicitly supplied.  The default is a
configuration/identity check only, because a missing key or quota must never be
mistaken for a successful model run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.llm_gateway import gateway_from_env  # noqa: E402
from app.services.llm_gateway.errors import LLMGatewayError  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="mock")
    ap.add_argument("--model", default="mock-model")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = {"provider": args.provider, "model": args.model,
              "live": bool(args.live), "status": "NOT_RUN", "errors": []}
    try:
        gateway = gateway_from_env({"BINARYREPAIR_LLM_PROVIDER": args.provider,
                                    "BINARYREPAIR_ASSISTANT_MODEL": args.model})
        result["status"] = "CONFIGURED"
        if args.live:
            response = gateway.generate_text("reply with JSON", model=args.model,
                                              response_format="json")
            result["status"] = "COMPLETED"
            result["model_returned"] = response.model
            result["identity_ok"] = response.identity_ok
    except Exception as exc:  # noqa: BLE001 - preflight reports typed failure
        result["status"] = "BLOCKED"
        result["errors"].append({"type": type(exc).__name__,
                                 "message": str(exc)[:300]})
    print(json.dumps(result, indent=2) if args.json else json.dumps(result))
    return 0 if result["status"] in {"CONFIGURED", "COMPLETED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
