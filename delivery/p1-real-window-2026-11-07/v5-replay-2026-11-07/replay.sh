#!/usr/bin/env bash
# P1 V5 replay — guest only. Compiles the fixture twice and replays the patch
# twice; does not execute the candidate. Run as the unprivileged guest user.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="${1:-$ROOT/work-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$WORK"
cd "$ROOT"

{
  echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "uname=$(uname -a)"
  echo "gcc=$(gcc --version | head -1)"
  echo "python=$(python3 --version 2>&1)"
  echo "sha256sum=$(sha256sum --version | head -1)"
  echo "user=$(id)"
} > "$WORK/environment.txt"

BUILD="$ROOT/build.sh"
PATCH="$ROOT/patch_candidate.py"
ORIG_EXPECTED="c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9"
CAND_EXPECTED="46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0"

for i in 1 2; do
  JULIET_ROOT="$ROOT/juliet" bash "$BUILD" "$WORK/original-$i.elf" \
    > "$WORK/build-$i.log" 2>&1
  python3 "$PATCH" --original "$WORK/original-$i.elf" \
    --out "$WORK/candidate-$i.elf" --report "$WORK/patch-$i.json" \
    > "$WORK/patch-$i.log" 2>&1
done

O1=$(sha256sum "$WORK/original-1.elf" | cut -d' ' -f1)
O2=$(sha256sum "$WORK/original-2.elf" | cut -d' ' -f1)
C1=$(sha256sum "$WORK/candidate-1.elf" | cut -d' ' -f1)
C2=$(sha256sum "$WORK/candidate-2.elf" | cut -d' ' -f1)
P1C=$(sha256sum "$ROOT/p1-candidate.elf" | cut -d' ' -f1)

python3 - "$WORK" "$O1" "$O2" "$C1" "$C2" "$ORIG_EXPECTED" "$CAND_EXPECTED" "$P1C" <<'PY'
import json, sys
work, o1, o2, c1, c2, oe, ce, p1 = sys.argv[1:]
ok = (o1 == o2 == oe) and (c1 == c2 == ce == p1)
payload = {
  "gate": "V5",
  "kind": "reproducibility",
  "state": "measured",
  "runs": 2,
  "source_rebuild": {"command": "JULIET_ROOT=<kit>/juliet bash build.sh <out>",
                     "sha256": [o1, o2], "expected": oe,
                     "byte_identical": o1 == o2},
  "patch_replay": {"command": "python3 patch_candidate.py --original <orig> --out <cand>",
                   "sha256": [c1, c2], "expected": ce, "p1_candidate": p1,
                   "byte_identical": c1 == c2, "matches_p1_candidate": c1 == p1},
  "pass": ok,
  "does_not_prove": ["bit-identical rebuild on a different toolchain/libc",
                     "anything about candidate behaviour; this is build reproducibility only"]
}
open(work + "/V5-replay.json", "w", encoding="utf-8").write(json.dumps(payload, indent=2) + "\n")
print(json.dumps(payload, indent=2))
raise SystemExit(0 if ok else 1)
PY
rc=$?

cd "$WORK"
sha256sum original-1.elf original-2.elf candidate-1.elf candidate-2.elf \
  patch-1.json patch-2.json environment.txt V5-replay.json > SHA256SUMS
sha256sum SHA256SUMS
exit "$rc"
