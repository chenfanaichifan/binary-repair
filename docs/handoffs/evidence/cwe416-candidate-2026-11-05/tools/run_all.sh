#!/bin/sh
# Produce the CWE416 no-input repair candidate and its V0-V5 evidence.
#
# Runs inside the disposable Ubuntu guest as uid 1000. Reads the fixture from
# kit/, writes every artifact under bundle/. Nothing outside bundle/ is claimed.
#
#   sh run_all.sh
#
set -eu

ROOT=$HOME/cwe416-cand
KIT=$ROOT/kit
FIX=$KIT/fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput
WORK=$ROOT/work
BUNDLE=$ROOT/bundle
TOOLS=$KIT/tools
FUNC=CWE416_Use_After_Free__malloc_free_char_01_bad

rm -rf "$WORK" "$BUNDLE"
mkdir -p "$WORK" "$BUNDLE/independent-views"

say() { printf '\n=== %s ===\n' "$*"; }

say "window"
date -u '+utc %Y-%m-%dT%H:%M:%SZ'
uptime
id
uname -a
echo "randomize_va_space=$(cat /proc/sys/kernel/randomize_va_space)"
gcc --version | head -1
ldd --version | head -1
python3 -V
readelf --version | head -1
objdump --version | head -1
setarch --version 2>&1 | head -1

say "fixture hashes (must match the committed fixture)"
cd "$FIX"
sha256sum original.elf original.c src.c harness.c support/io.c support/std_testcase.h support/std_testcase_io.h
echo "--- contract ---"
sha256sum contract.json tests/valid.json
grep -c 'invalid_' contract.json || true
python3 - <<'PY'
import json, pathlib
c = json.loads(pathlib.Path("contract.json").read_text())
print("schema_version:", c["schema_version"])
print("input_mode:", c["input_mode"])
print("forbidden keys present:", sorted(set(c) & {"invalid_input_response","invalid_exit_code","invalid_stdout","invalid_stderr","max_valid_input_bytes"}))
print("trigger_case:", json.loads(pathlib.Path("defect.json").read_text()).get("trigger_case"))
PY

say "step 1: copy the original and apply the five-byte edit"
cp "$FIX/original.elf" "$WORK/original.elf"
chmod 755 "$WORK/original.elf"
cd "$WORK"
python3 "$TOOLS/patch_candidate.py" --original original.elf --out candidate.elf \
    --report patch-report.json
chmod 755 candidate.elf
sha256sum original.elf candidate.elf
ls -l original.elf candidate.elf
echo "--- the edited instruction, before ---"
objdump -d --start-address=0x4012fe --stop-address=0x40131a -M intel original.elf | sed -n '/4012fe/,$p'
echo "--- the edited instruction, after ---"
objdump -d --start-address=0x4012fe --stop-address=0x40131a -M intel candidate.elf | sed -n '/4012fe/,$p'
echo "--- cmp -l (byte level) ---"
cmp -l original.elf candidate.elf || true

say "step 2: static audit (V1) and interface observation (V2)"
python3 "$TOOLS/audit_interface.py" --original original.elf --candidate candidate.elf \
    --audit "$BUNDLE/audit.json" --interface "$BUNDLE/v2-interface.json" --symbol "$FUNC"

say "step 3: rebuild the original twice from source"
SUPPORT="$FIX/support" sh "$FIX/build.sh" "$WORK/rebuild-1.elf" > "$WORK/build-1.log" 2>&1
SUPPORT="$FIX/support" sh "$FIX/build.sh" "$WORK/rebuild-2.elf" > "$WORK/build-2.log" 2>&1
sha256sum rebuild-1.elf rebuild-2.elf original.elf
echo "--- -Wuse-after-free is expected and recorded, not suppressed ---"
grep -c 'Wuse-after-free' "$WORK/build-1.log" || true
grep 'Wuse-after-free' "$WORK/build-1.log" || true

say "step 4: apply the edit a second time from the same input"
python3 "$TOOLS/patch_candidate.py" --original original.elf --out patch-1.elf --report "$WORK/patch-1.json" >/dev/null
python3 "$TOOLS/patch_candidate.py" --original original.elf --out patch-2.elf --report "$WORK/patch-2.json" >/dev/null
python3 "$TOOLS/write_repro.py" --fixture-original "$FIX/original.elf" \
    --rebuild-1 rebuild-1.elf --rebuild-2 rebuild-2.elf \
    --patch-1 patch-1.elf --patch-2 patch-2.elf --out "$BUNDLE/reproducibility.json"

say "step 5: behaviour, with ASLR off, original then candidate"
echo "--- original ---"
setarch -R ./original.elf > "$WORK/original.out" 2> "$WORK/original.err" && echo "exit=0" || echo "exit=$?"
xxd "$WORK/original.out"
wc -c < "$WORK/original.out"
xxd "$WORK/original.err"
echo "--- candidate ---"
setarch -R ./candidate.elf > "$WORK/candidate.out" 2> "$WORK/candidate.err" && echo "exit=0" || echo "exit=$?"
xxd "$WORK/candidate.out" | head -8
wc -c < "$WORK/candidate.out"
xxd "$WORK/candidate.err"

say "step 6: V3 runner, no-input contract"
cd "$KIT"
python3 routeb/run_manifest_repaired.py --binary "$WORK/candidate.elf" \
    --tests "$FIX/tests" --contract "$FIX/contract.json" \
    --out "$BUNDLE/manifest-repaired.json" && echo "runner exit=0" || echo "runner exit=$?"

say "step 7: control - the same runner and manifest against the unrepaired original"
if python3 routeb/run_manifest_repaired.py --binary "$WORK/original.elf" \
    --tests "$FIX/tests" --contract "$FIX/contract.json" \
    --out "$BUNDLE/manifest-repaired-original.json"; then
    echo "UNEXPECTED: the original passed the repaired expectation"
else
    rc=$?
    echo "control runner exit=$rc (1 = expectation not met, 2 = runner error)"
fi

say "step 8: independent views"
cd "$WORK"
readelf -lW candidate.elf > "$BUNDLE/independent-views/readelf-program-headers.txt"
readelf -SW candidate.elf > "$BUNDLE/independent-views/readelf-section-headers.txt"
readelf -dW candidate.elf > "$BUNDLE/independent-views/readelf-dynamic.txt"
readelf -rW candidate.elf > "$BUNDLE/independent-views/readelf-relocations.txt"
readelf --dyn-syms -W candidate.elf > "$BUNDLE/independent-views/readelf-dynsyms.txt"
readelf -sW candidate.elf > "$BUNDLE/independent-views/readelf-symtab.txt"
objdump -d -M intel candidate.elf > "$BUNDLE/independent-views/objdump-disassembly.txt"
objdump -d --disassemble=$FUNC -M intel candidate.elf > "$BUNDLE/independent-views/objdump-target-function.txt"

say "step 9: copy the two binaries and write the manifests"
cp original.elf "$BUNDLE/original.elf"
cp candidate.elf "$BUNDLE/candidate.elf"
python3 "$TOOLS/write_bundle_meta.py" --original "$BUNDLE/original.elf" \
    --candidate "$BUNDLE/candidate.elf" --patch-report "$WORK/patch-report.json" \
    --audit "$BUNDLE/audit.json" --interface "$BUNDLE/v2-interface.json" \
    --manifest-repaired "$BUNDLE/manifest-repaired.json" \
    --manifest-control "$BUNDLE/manifest-repaired-original.json" \
    --contract "$FIX/contract.json" --valid "$FIX/tests/valid.json" \
    --repro "$BUNDLE/reproducibility.json" --function "$FUNC" --out-dir "$BUNDLE"

cat > "$BUNDLE/environment.json" <<EOF
{
  "checked_at": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "user": "$(id -un) uid=$(id -u)",
  "kernel": "$(uname -r)",
  "arch": "$(uname -m)",
  "gcc": "$(gcc --version | head -1)",
  "libc": "$(ldd --version | head -1)",
  "python": "$(python3 -V 2>&1)",
  "readelf": "$(readelf --version | head -1)",
  "objdump": "$(objdump --version | head -1)",
  "randomize_va_space": $(cat /proc/sys/kernel/randomize_va_space),
  "network": "no route used; nothing here fetched anything"
}
EOF

say "step 10: manifest the bundle"
cd "$BUNDLE"
find . -type f ! -name SHA256SUMS ! -name bundle-sha256.txt | sort | sed 's|^\./||' > /tmp/list.txt
while read -r f; do sha256sum "$f"; done < /tmp/list.txt > SHA256SUMS
cat SHA256SUMS
sha256sum SHA256SUMS | cut -d' ' -f1 > bundle-sha256.txt
echo "--- bundle-sha256 ---"
cat bundle-sha256.txt
echo "--- files ---"
wc -l < SHA256SUMS

say "done"
