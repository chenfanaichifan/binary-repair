#!/usr/bin/env python3
"""Probe configured multi-model providers and verify returned model identity.

This script intentionally does not invent results when a key is absent.  It is
the bridge between the provider abstraction and the hard-case benchmark:
first prove each provider/model pair answers with the requested identity, then
run the benchmark matrix with the same environment.

Example:
  SILICONFLOW_API_KEY=... python scripts/run_multi_model_matrix.py \
    --out artifacts/multi-model-probe-2026-11-14 \
    --models siliconflow:Qwen/Qwen3-8B siliconflow:deepseek-ai/DeepSeek-V3 \
              dashscope:qwen-plus
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.assistant_llm import (  # noqa: E402
    PROVIDER_PROFILES,
    client_from_env,
    model_identity_ok,
    provider_config,
)

PROMPT = "Return exactly this JSON object: {\"ok\":true}"


def _parse(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        raise ValueError(f"model spec must be provider:model, got {spec!r}")
    provider, model = spec.split(":", 1)
    provider = provider.strip().lower()
    model = model.strip()
    if provider not in PROVIDER_PROFILES or not model:
        raise ValueError(f"unknown provider or empty model in {spec!r}")
    return provider, model


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--models", nargs="+", required=True,
                    help="provider:model entries, e.g. siliconflow:Qwen/Qwen3-8B")
    ap.add_argument("--benchmark", action="store_true",
                    help="also run the hard-case benchmark per model (requires native PoC host)")
    ap.add_argument("--contract-level", choices=("full", "generic", "none"), default="full")
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for spec in args.models:
        try:
            provider, model = _parse(spec)
        except ValueError as exc:
            records.append({"spec": spec, "status": "invalid_spec", "error": str(exc)})
            continue
        env = dict(__import__("os").environ)
        env["BINARYREPAIR_PROVIDER"] = provider
        env["BINARYREPAIR_ASSISTANT_MODEL"] = model
        env["BINARYREPAIR_STRICT_MODEL_IDENTITY"] = "1"
        cfg = provider_config(env)
        record = {
            "spec": spec,
            "provider": provider,
            "model_requested": model,
            "base_url": cfg.get("base_url"),
            "configured": cfg.get("configured"),
            "errors": list(cfg.get("errors") or []),
        }
        client = client_from_env(env)
        if client is None:
            record["status"] = "unconfigured"
            records.append(record)
            continue
        try:
            raw = client.chat_json(
                [{"role": "system", "content": "Return only JSON."},
                 {"role": "user", "content": PROMPT}],
                max_tokens=16, thinking=False,
            )
            returned = getattr(raw, "model", None)
            record.update({
                "status": "ok" if model_identity_ok(model, returned) else "identity_mismatch",
                "model_returned": returned,
                "model_identity_ok": model_identity_ok(model, returned),
                "latency_ms": getattr(raw, "usage", {}).get("latency_ms")
                if isinstance(getattr(raw, "usage", None), dict) else None,
                "usage": getattr(raw, "usage", None),
                "request_id": getattr(raw, "request_id", None),
            })
        except Exception as exc:  # noqa: BLE001
            record.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
        if args.benchmark and record.get("status") == "ok":
            import os
            import subprocess
            slug = f"{provider}-{model}".replace("/", "_").replace(":", "_")
            bench_out = out / "benchmarks" / slug
            env = dict(os.environ)
            env.update({
                "BINARYREPAIR_PROVIDER": provider,
                "BINARYREPAIR_ASSISTANT_MODEL": model,
                "BINARYREPAIR_STRICT_MODEL_IDENTITY": "1",
            })
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "run_hard_benchmark.py"),
                 "--out", str(bench_out), "--client", "real",
                 "--contract-level", args.contract_level],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=1800,
            )
            record["benchmark"] = {
                "returncode": proc.returncode,
                "stdout_tail": proc.stdout[-1000:],
                "stderr_tail": proc.stderr[-1000:],
                "summary_path": str(bench_out / "summary.json"),
            }
            try:
                summary = json.loads((bench_out / "summary.json").read_text())
                record["benchmark"].update({
                    "baseline_verified": summary.get("baseline_verified"),
                    "ai_verified": summary.get("ai_verified"),
                    "ai_increment": summary.get("ai_increment"),
                    "contract_level": summary.get("contract_level"),
                    "cases": len(summary.get("cases", [])),
                })
            except (OSError, json.JSONDecodeError):
                pass
        records.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
    summary = {
        "schema_version": 1,
        "records": records,
        "ok": sum(1 for r in records if r.get("status") == "ok"),
        "identity_mismatch": sum(1 for r in records if r.get("status") == "identity_mismatch"),
        "unconfigured": sum(1 for r in records if r.get("status") == "unconfigured"),
        "benchmarks": {
            r["spec"]: {
                "returncode": r.get("benchmark", {}).get("returncode"),
                "ai_verified": r.get("benchmark", {}).get("ai_verified"),
                "ai_increment": r.get("benchmark", {}).get("ai_increment"),
            }
            for r in records if "benchmark" in r
        },
        "note": "No key, prompt, or raw response is stored; exact model identity is mandatory.",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    sums = []
    for p in sorted(out.iterdir()):
        if p.is_file() and p.name != "SHA256SUMS":
            sums.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    print(json.dumps({"out": str(out), "ok": summary["ok"],
                      "identity_mismatch": summary["identity_mismatch"],
                      "unconfigured": summary["unconfigured"]}, ensure_ascii=False))
    return 0 if summary["ok"] == len(records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
