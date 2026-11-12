"""Generate deterministic, labeled C variants for the overflow corpus.

The seeds are small hand-written reproductions of known bug shapes. Variants
change identifiers, array sizes and formatting while preserving the bug class;
they are training/regression data, not claims about real-world prevalence.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "overflow-corpus"

REUSABLE_NAMES = [
    "buffer", "name", "input", "data", "src", "dest", "username", "content",
    "heap_buf", "buf", "new_node", "global_buf", "static_log", "local_buf",
    "log_buf", "base", "event",
]


def load_seeds() -> tuple[list[dict], dict[str, str]]:
    labels = json.loads((CORPUS / "labels.json").read_text(encoding="utf-8"))
    codes = {item["id"]: (CORPUS / "seeds" / item["file"]).read_text(encoding="utf-8") for item in labels}
    return labels, codes


def mutate(code: str, idx: int, rng: random.Random) -> str:
    suffix = f"_{idx:04d}"
    for name in sorted(REUSABLE_NAMES, key=len, reverse=True):
        code = re.sub(rf"\b{re.escape(name)}\b", f"{name}{suffix}", code)
    # Keep capacity relationships but vary concrete bounds.
    sizes = [16, 24, 32, 48, 64, 96, 128, 256, 512]
    def size_repl(match: re.Match[str]) -> str:
        return f"[{rng.choice(sizes)}]"
    code = re.sub(r"\[\s*\d+\s*\]", size_repl, code, count=2)
    # Rename the primary function without touching main.
    code = re.sub(r"\b(void|int)\s+(vulnerable_copy|check_permission|process_data|add_node|set_data|log_event|read_data|append_data|copy_string|process_heap_string|vulnerable_printf|log_error)\b",
                  lambda m: f"{m.group(1)} fn{suffix}", code, count=1)
    if rng.random() < 0.4:
        code = "\n/* generated variant " + str(idx) + " */\n" + code
    return code


def generate(count_per_seed: int = 100, seed: int = 20261112) -> list[dict]:
    labels, codes = load_seeds()
    rng = random.Random(seed)
    rows = []
    for item in labels:
        for index in range(count_per_seed):
            rows.append({
                "id": f"{item['id']}-{index:04d}",
                "seed": item["id"],
                "group": item["group"],
                "cwe": item["cwe"],
                "rule": item["expected_rule"],
                "code": mutate(codes[item["id"]], index, rng),
            })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "var" / "overflow-corpus")
    parser.add_argument("--count", type=int, default=100, help="variants per seed")
    args = parser.parse_args()
    rows = generate(args.count)
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "variants.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = {
        "schema": 1,
        "seed_count": len({row["seed"] for row in rows}),
        "variant_count": len(rows),
        "count_per_seed": args.count,
        "generator": "scripts/generate_overflow_corpus.py",
        "note": "Synthetic mutations of 12 seeds; labels are inherited from the seed.",
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} variants to {args.out}")


if __name__ == "__main__":
    main()
