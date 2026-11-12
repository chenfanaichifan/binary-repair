"""Compile-check the 12 seeds and their generated patches.

This validates C syntax/linking only. It does not execute the vulnerable
programs and does not prove a patch correct. A separate dynamic/symbolic gate
is still required.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.code_repair import repair_code  # noqa: E402

CORPUS = ROOT / "data" / "overflow-corpus"
UNSAFE = ("strcpy", "strcat", "sprintf", "memcpy", "printf", "malloc", "gets")


def compile_c(source: str, out: Path) -> dict:
    proc = subprocess.run(
        ["clang", "-fsanitize=address", "-g", "-O0", "-w", "-x", "c", "-", "-o", str(out)],
        input=source, text=True, capture_output=True, timeout=30,
    )
    return {"returncode": proc.returncode, "stderr": proc.stderr.strip()[:1200]}


def symbols(binary: Path) -> list[str]:
    proc = subprocess.run(["nm", "-u", str(binary)], text=True, capture_output=True, timeout=20)
    names = []
    for line in proc.stdout.splitlines():
        token = line.strip().split()[-1] if line.strip() else ""
        token = token.lstrip("_")
        if token in UNSAFE and token not in names:
            names.append(token)
    return names


def main() -> None:
    labels = json.loads((CORPUS / "labels.json").read_text(encoding="utf-8"))
    records = []
    for item in labels:
        code = (CORPUS / "seeds" / item["file"]).read_text(encoding="utf-8")
        result = repair_code(code, "c")
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            original = compile_c(code, tmp / "original")
            patched = compile_c(result["patched_code"], tmp / "patched")
            surface = symbols(tmp / "original") if original["returncode"] == 0 else []
            patched_surface = symbols(tmp / "patched") if patched["returncode"] == 0 else []
        records.append({
            "id": item["id"], "cwe": item["cwe"], "rules": [f["rule"] for f in result["findings"]],
            "original_compile": original["returncode"] == 0,
            "patched_compile": patched["returncode"] == 0,
            "patched_changed": result["changed"],
            "unsafe_import_surface": surface,
            "patched_unsafe_import_surface": patched_surface,
        })
        print(item["id"], "OK" if original["returncode"] == 0 and patched["returncode"] == 0 else "FAIL")
    payload = {
        "schema": 1,
        "source": "data/overflow-corpus",
        "compiler": "clang -fsanitize=address -g -O0",
        "seeds": len(records),
        "original_compile_pass": sum(r["original_compile"] for r in records),
        "patched_compile_pass": sum(r["patched_compile"] for r in records),
        "records": records,
        "limits": [
            "Compile-only: no vulnerable program was executed.",
            "Unsafe imports are attack surface, not proof of vulnerability.",
            "Dynamic ASan/fuzz and symbolic checks remain required before calling a patch verified.",
        ],
    }
    (ROOT / "knowledge" / "overflow_validation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("seeds", "original_compile_pass", "patched_compile_pass")}, indent=2))


if __name__ == "__main__":
    main()
