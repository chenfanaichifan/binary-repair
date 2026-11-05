#!/bin/sh
# Contract-sync pass: does the *tree* fixture drive V3?
# Runs in the gate4-harness guest as uid 1000. Writes only under ~/cwe416-sync.
set -e

R=$HOME/cwe416-sync
KIT=$R/kit
FIX=$KIT/fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput
TOOLS=$KIT/tools

echo "## guest"
echo "\$ uname -sr                -> $(uname -sr)"
echo "\$ id -u                    -> $(id -u)"
echo "\$ gcc --version | head -1  -> $(gcc --version | head -1)"
echo "\$ date -u                  -> $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

echo "## the fixture as it came out of the tree tarball"
echo "\$ find \$FIX -type f | sort"
(cd "$FIX" && find . -type f | sort | sed 's|^\./||')
echo
echo "\$ sha256sum contract.json"
(cd "$FIX" && sha256sum contract.json)
echo
echo "\$ python3 - <<'PY'  (SecurityContract.from_dict -> canonical hash)"
cd "$KIT"
python3 - "$FIX/contract.json" <<'PY'
import json, sys
sys.path.insert(0, ".")
from app.domain.contracts import SecurityContract
d = json.load(open(sys.argv[1], encoding="utf-8"))
c = SecurityContract.from_dict(d)
print("  schema_version  :", d["schema_version"])
print("  input_mode      :", d["input_mode"])
print("  canonical sha256:", c.sha256())
print("  field count     :", len(d))
print("  fields          :", ",".join(sorted(d)))
missing = [k for k in ("invalid_input_response", "invalid_exit_code", "invalid_stdout",
                       "invalid_stderr", "max_valid_input_bytes") if k in d]
print("  v2 reject fields present:", missing or "none")
PY
echo

echo "## V3 — the runner resolves the mode from that contract"
echo "\$ python3 routeb/run_manifest_repaired.py --binary \$R/candidate.elf \\"
echo "      --tests \$FIX/tests --contract \$FIX/contract.json --out \$R/v3-candidate.json"
python3 routeb/run_manifest_repaired.py --binary "$R/candidate.elf" \
    --tests "$FIX/tests" --contract "$FIX/contract.json" \
    --out "$R/v3-candidate.json"
echo "runner exit=$?"
python3 - "$R/v3-candidate.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print("  input_mode     :", d["input_mode"])
print("  invalid        :", d["invalid"])
print("  valid          :", d["valid"])
print("  passed/total   : %d/%d" % (d["passed"], d["total"]))
print("  repaired_pass  :", d["repaired_pass"])
print("  binary_sha256  :", d["binary_sha256"])
print("  case           :", d["cases"][0]["id"], "ok =", d["cases"][0]["ok"])
print("  stdout_hex     :", d["cases"][0]["got"]["stdout_hex"][:48] + "...")
PY
echo

echo "## control — same runner, same manifest, the unrepaired original"
set +e
python3 routeb/run_manifest_repaired.py --binary "$R/original.elf" \
    --tests "$FIX/tests" --contract "$FIX/contract.json" \
    --out "$R/v3-original.json"
rc=$?
set -e
echo "runner exit=$rc  (non-zero is the expected answer for the unrepaired binary)"
python3 - "$R/v3-original.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print("  valid          :", d["valid"])
print("  passed/total   : %d/%d" % (d["passed"], d["total"]))
print("  repaired_pass  :", d["repaired_pass"])
print("  stdout_hex     :", d["cases"][0]["got"]["stdout_hex"],
      "(allocator residue, not the 100-byte block)")
PY
echo

echo "## V5 — rebuild the original twice, replay the patch twice"
echo "\$ SUPPORT=\$FIX/support sh \$FIX/build.sh /tmp/rb-1.elf   (twice)"
SUPPORT=$FIX/support sh "$FIX/build.sh" /tmp/rb-1.elf >/dev/null 2>&1
SUPPORT=$FIX/support sh "$FIX/build.sh" /tmp/rb-2.elf >/dev/null 2>&1
sha256sum /tmp/rb-1.elf /tmp/rb-2.elf | sed 's|/tmp/||'
echo
echo "\$ python3 tools/patch_candidate.py --original \$FIX/original.elf --out /tmp/pc-1.elf  (twice)"
python3 "$TOOLS/patch_candidate.py" --original "$FIX/original.elf" --out /tmp/pc-1.elf --report /tmp/pr-1.json
python3 "$TOOLS/patch_candidate.py" --original "$FIX/original.elf" --out /tmp/pc-2.elf --report /tmp/pr-2.json
sha256sum /tmp/pc-1.elf /tmp/pc-2.elf | sed 's|/tmp/||'
echo
echo "\$ sha256sum \$FIX/original.elf \$R/candidate.elf"
sha256sum "$FIX/original.elf" "$R/candidate.elf"
echo

echo "## V4 — an engine is present, and it was not run"
echo "\$ command -v z3                                   -> $(command -v z3 || echo absent)"
echo "\$ /opt/angr-venv/bin/python -c 'import angr, z3'  -> $(/opt/angr-venv/bin/python -c 'import angr, z3; print("angr", angr.__version__, "z3", z3.get_version_string())' 2>&1 | tail -1)"
echo
echo "So this is not \"no engine available\" — angr is installed. The reason V4 is"
echo "not_run is that a real V4 needs a symbolic harness with exact solver"
echo "accounting (sat/unsat/unknown/eval per run) and a bound that cannot hide a"
echo "timeout behind \"proven\"; earlier V4 submissions were rejected for concrete"
echo "inputs and silent max_steps (docs/handoffs/63, 64, 66, 67). Writing a quick"
echo "one here would produce a claim with no accounting behind it, which is worse"
echo "than not_run. So: V4 stays not_run, claimed_scope null, no binary-level claim."
