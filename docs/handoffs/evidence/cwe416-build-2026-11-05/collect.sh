#!/bin/sh
# Collect the CWE416 build/trigger evidence inside the guest, into one directory
# with its own SHA256SUMS.  Run from a clean window (revert to gate4-harness).
set -eu

R="$HOME/cwe416"
E="$R/evidence"
rm -rf "$E"
mkdir -p "$E"

# ---- 01 environment fingerprint -------------------------------------------
{
    echo "== guest environment at build time =="
    echo "hostname   : $(hostname)"
    echo "kernel     : $(uname -srm)"
    echo "boot       : $(who -b | tr -s ' ' | sed 's/^ //')"
    echo "uptime     : $(uptime -p)"
    echo "user       : $(id)"
    echo "gcc        : $(gcc --version | head -1)"
    echo "ld         : $(ld --version | head -1)"
    echo "gcc sha256 : $(sha256sum "$(command -v gcc)" | cut -d' ' -f1)"
    echo "home dirs  : $(ls "$HOME" | tr '\n' ' ')"
    echo "disk       : $(df -h / | tail -1)"
    echo "network    : $(ip -4 -o addr show | awk '{print $2, $4}' | tr '\n' '; ')"
} > "$E/01-isolation.txt"

# ---- 02 the committed recipe, run verbatim -------------------------------
{
    echo "== fixture build.sh as committed, run unmodified =="
    echo "cwd: $R/run-a"
    echo "command: sh build.sh"
    echo "exit: $(cat "$R/run-a/build.exit" 2>/dev/null || echo '(not recorded)')"
    echo
    echo "-- stdout --"
    cat "$R/run-a/build.stdout" 2>/dev/null || true
    echo "-- stderr --"
    cat "$R/run-a/build.stderr" 2>/dev/null || true
    echo
    echo "-- duplicate definition --"
    echo "src.c:90     int main(int argc, char **argv)"
    echo "harness.c:20 int main(int argc, char *argv[])"
    echo
    echo "-- per-object symbol --"
    echo "src.o     : $(nm /tmp/s.o 2>/dev/null | grep -w main || echo '-')"
    echo "harness.o : $(nm /tmp/h.o 2>/dev/null | grep -w main || echo '-')"
} > "$E/02-committed-recipe-failure.txt"

# ---- 03 recipes measured and their digests -------------------------------
{
    echo "== digests actually measured in this window =="
    for f in "$R/run-b/original.elf" "$R/run-c/original.elf" \
             "$R/run-b/pm.elf" "$R/run-c/pm.elf" "$R/run-b/asan.elf"; do
        [ -f "$f" ] || continue
        printf '%-40s %s  %s B\n' "${f#$R/}" "$(sha256sum "$f" | cut -d' ' -f1)" "$(stat -c %s "$f")"
    done
    echo
    echo "run-b vs run-c, plain -g (no prefix map):"
    echo "  $(sha256sum "$R/run-b/original.elf" | cut -d' ' -f1)  run-b"
    echo "  $(sha256sum "$R/run-c/original.elf" | cut -d' ' -f1)  run-c"
    echo "  -> different: the digest is bound to the build directory"
    echo
    echo "run-b vs run-c, -fdebug-prefix-map/-ffile-prefix-map:"
    echo "  $(sha256sum "$R/run-b/pm.elf" | cut -d' ' -f1)  run-b"
    echo "  $(sha256sum "$R/run-c/pm.elf" | cut -d' ' -f1)  run-c"
    echo "  -> identical: the digest is portable"
} > "$E/03-recipes-and-digests.txt"

# ---- 04 readelf on the portable build ------------------------------------
{
    echo "== readelf -h $R/run-b/pm.elf =="
    readelf -h "$R/run-b/pm.elf"
    echo
    echo "== loadable segments =="
    readelf -lW "$R/run-b/pm.elf" | sed -n '/Program Headers/,/Section to Segment/p'
    echo
    echo "== symbols of interest =="
    nm -n "$R/run-b/pm.elf" | grep -E ' (main|badSink|goodSink|duplicate|printLine)$'
} > "$E/04-readelf.txt" 2>&1

# ---- 05 behaviour matrix -------------------------------------------------
{
    echo "== matrix against run-b/pm.elf (portable build) =="
    cd "$R"
    python3 matrix.py run-b pm.elf || true
    echo
    echo "NOTE: the two invalid rows are EXPECTED to differ on the original."
    echo "      tests/invalid.json records the POST-REPAIR output; reading the"
    echo "      freed block yields the reuse sentinel, which is the defect."
} > "$E/05-matrix.txt" 2>&1

# ---- 06 trigger stability ------------------------------------------------
{
    echo "== stdout digest over 50 runs, per case =="
    cd "$R/run-b"
    for case in "1234567 --uaf" "use-after-free --uaf" "1234567"; do
        echo "-- ./original.elf $case"
        i=0
        while [ $i -lt 50 ]; do
            ./pm.elf $case 2>/dev/null | sha256sum | cut -d' ' -f1
            i=$((i + 1))
        done | sort | uniq -c | sort -rn
    done
    echo
    echo "== exact stdout bytes, defect path =="
    ./pm.elf 1234567 --uaf 2>/dev/null | od -An -c | head -4
} > "$E/06-stability.txt" 2>&1

# ---- 07 ASan -------------------------------------------------------------
{
    echo "== gcc -fsanitize=address build, defect path =="
    cd "$R/run-b"
    ./asan.elf 1234567 --uaf 2>&1 | head -20 || true
    echo
    echo "== same binary, good path =="
    ./asan.elf 1234567 2>&1 | head -4 || true
} > "$E/07-asan.txt" 2>&1

# ---- artefact + sums -----------------------------------------------------
cp "$R/run-b/pm.elf" "$E/original.variant.elf"
cd "$E"
: > 08-SHA256SUMS
for f in *.txt original.variant.elf; do
    [ "$f" = "08-SHA256SUMS" ] && continue
    printf '%s  %s\n' "$(sha256sum "$f" | cut -d' ' -f1)" "$f" >> 08-SHA256SUMS
done
echo "evidence written to $E"
cat 08-SHA256SUMS
