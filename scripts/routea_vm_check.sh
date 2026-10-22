#!/usr/bin/env bash
# Route A Gate 3 static check - M4 independent audit of the canonical candidate.
#
# Runs on the canonical tree (main `ad1a1f8`): candidate c4a159..., contract
# 24bfe568..., write(2)/exit_group code shape. It never executes the candidate;
# the six-case run and isolation evidence are separate guest steps.
#
# Retargeted per M5 review B1-B6. Unverified until the VM run; a missing tool or
# a failed check is an error, never a pass.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
CASE="fixtures/public/CWE121_src_char_declare_cpy_51b"
CONTRACT="$CASE/contract.json"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT="${OUT:-$ROOT/var/jobs/m4-gate3/$RUN_ID/static}"

EXPECTED_ORIGINAL="aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393"
EXPECTED_CANDIDATE="c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82"
EXPECTED_CONTRACT="24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37"

echo "== environment =="
uname -a; python3 --version
python3 - <<'PY'
import elftools, capstone
print("pyelftools", elftools.__version__)
print("capstone", capstone.__version__)
try:
    import lief
    print("lief", lief.__version__)
except Exception as exc:
    print("lief missing:", exc)
PY
for tool in readelf objdump; do
  command -v "$tool" >/dev/null || { echo "ERROR: $tool missing" >&2; exit 2; }
  "$tool" --version | head -1
done

echo "== frozen identity =="
sha256sum "$CASE/original.elf" "$CASE/tests/valid.json" "$CASE/tests/invalid.json"
python3 - "$CONTRACT" <<'PY'
import json, sys
sys.path.insert(0, ".")
from app.domain.contracts import contract_sha256
print("contract", contract_sha256(json.load(open(sys.argv[1], encoding="utf-8"))))
PY

echo "== tests (guest/CI only) =="
python3 -m pytest \
  tests/test_routea_byteaudit.py \
  tests/test_routea_manifest.py \
  tests/test_routea_cave.py \
  tests/test_routea_audit.py \
  -q -p no:cacheprovider

echo "== static audit + reproducibility + evidence bundle =="
mkdir -p "$OUT"
python3 -m routea.gate3 bundle \
  --original "$CASE/original.elf" --contract "$CONTRACT" --out-dir "$OUT"

echo "== candidate identity =="
sha256sum "$OUT/candidate.elf"
echo "expected candidate: $EXPECTED_CANDIDATE"
echo "expected contract:  $EXPECTED_CONTRACT"

cat <<'NEXT'
== still manual: the runtime half of Gate 3 ==
1. Runtime cave probe under the isolation wrapper: 0x401000-0x401fff r-xp,
   memory at 0x4018e9 == candidate file bytes, cave entry executes.
   Breakpoints: 0x401304 (site), 0x4018e9 (cave), 0x401309 (resume).
2. Six frozen cases on the candidate from a reverted snapshot, no egress, uid 1003:
   python3 routeb/run_manifest_repaired.py --binary <candidate> \
     --tests fixtures/public/CWE121_src_char_declare_cpy_51b/tests \
     --out var/jobs/m4-gate3/<run-id>/manifest-repaired.json
3. Original V0 shape (documented 4/6) on the same session.
4. Record candidate SHA-256 before/after, wrapper attestation, chain manifest,
   guest fingerprint and revert log. Items 4-5 stay not_run until then.
NEXT