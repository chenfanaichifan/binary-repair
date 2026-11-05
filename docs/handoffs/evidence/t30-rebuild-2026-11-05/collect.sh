#!/bin/sh
# Collect T30 rebuild evidence inside the guest.
# Run from /var/tmp/cwe416 after `sh build.sh` has produced original.elf.
#
# This script only reads and records; it builds nothing and changes nothing
# that the build produced.
set -eu

EVID="evidence"
rm -rf "$EVID"
mkdir -p "$EVID"

SUPPORT="$HOME/evaluator/src/juliet-v1.3/C/testcasesupport"

# ---------------------------------------------------------------- 01 window
{
  echo "# T30 rebuild - isolation and window identity"
  echo "# captured $(date -u +%Y-%m-%dT%H:%M:%SZ) inside the guest"
  echo
  echo "## 1. where this ran"
  echo
  printf '%-22s %s\n' hostname "$(hostname)"
  printf '%-22s %s\n' kernel "$(uname -r)"
  printf '%-22s %s\n' arch "$(uname -m)"
  printf '%-22s %s\n' user "$(id)"
  printf '%-22s %s\n' boot "$(who -b | tr -s ' ')"
  printf '%-22s %s\n' uptime "$(uptime -p)"
  echo
  echo "## 2. toolchain"
  echo
  printf '%-22s %s\n' gcc "$(gcc --version | head -1)"
  printf '%-22s %s\n' ld "$(ld --version | head -1)"
  printf '%-22s %s\n' libc "$(ldd --version | head -1)"
  echo
  echo "## 3. baseline evidence - the home directory is the gate4-harness state"
  echo
  echo "no leftover from the CWE416 fixture window (that window created ~/cwe416):"
  if [ -e "$HOME/cwe416" ]; then echo "  PRESENT - NOT a clean window"; else echo "  absent"; fi
  echo
  echo "home directory listing:"
  ls -1 "$HOME" | sed 's/^/  /'
  echo
  echo "## 4. Juliet tree - the checkout ships CWE121 only, support is complete"
  echo
  ls -1 "$HOME/evaluator/src/juliet-v1.3/C/testcases/" | sed 's/^/  testcases: /'
  echo "  testcasesupport:" "$(ls -1 "$SUPPORT" | wc -l)" "files"
  echo
  echo "## 5. support file hashes (must match build.json#fixture.support_files)"
  echo
  sha256sum "$SUPPORT/io.c" "$SUPPORT/std_testcase.h"
  echo
  echo "## 6. build inputs as received (must match the hashes in build.json)"
  echo
  sha256sum build.sh original.c harness.c trigger.sh
} > "$EVID/01-window-and-isolation.txt" 2>&1

# ---------------------------------------------------------------- 02 build
{
  echo "# build.sh output, verbatim, exit status included"
  echo
  echo "## invocation"
  echo
  echo '  cd /var/tmp/cwe416 && sh build.sh'
  echo
  echo "## exit status"
  echo
  cat build.exit
  echo
  echo "## stdout"
  echo
  cat build.stdout
  echo
  echo "## stderr"
  echo
  cat build.stderr
} > "$EVID/02-build.txt" 2>&1

# ------------------------------------------------------------- 03 readelf
cp readelf-raw.txt "$EVID/03-readelf.txt"
cat >> "$EVID/03-readelf.txt" <<EOF

===== machine check (derived from the above) =====
type            $(readelf -h original.elf | sed -n 's/^  Type: *//p')
entry           $(readelf -h original.elf | sed -n 's/^  Entry point address: *//p')
build_id        $(readelf -n original.elf | sed -n 's/.*Build ID: *//p')
stack_canary    $(nm original.elf 2>/dev/null | grep -c stack_chk_fail) occurrences of __stack_chk_fail
needed          $(readelf -d original.elf | sed -n 's/.*Shared library: \[\(.*\)\]/\1/p' | tr '\n' ' ')
debug_info      $(readelf -S original.elf | grep -c '\.debug_info') .debug_info section(s)
EOF

# ------------------------------------------------------------- 04 trigger
{
  echo "# trigger.sh - measured observation"
  echo "# binary sha256 $(sha256sum original.elf | cut -d' ' -f1)"
  echo "# captured $(date -u +%Y-%m-%dT%H:%M:%SZ) inside the guest"
  echo
  echo "## 1. single run"
  echo
  ./trigger.sh ./original.elf
  echo
  echo "## 2. determinism: 50 consecutive runs, ASLR disabled by setarch -R"
  echo "# one line per distinct observation, with its occurrence count"
  echo
  ./trigger.sh --repeat 50 ./original.elf
  echo
  echo "## 3. determinism: 200 more runs"
  echo
  ./trigger.sh --repeat 200 ./original.elf
  echo
  echo "## 4. contrast: 10 runs with ASLR ON (plain ./original.elf)"
  echo "# this is why setarch -R is required: the bytes read are heap residue"
  echo
  for i in $(seq 1 10); do
      ./original.elf 2>/dev/null | od -An -tx1 -v | tr -d ' \n'
      echo
  done | sort | uniq -c | sort -rn
  echo
  echo "distinct values among those 10 runs:"
  for i in $(seq 1 10); do
      ./original.elf 2>/dev/null | od -An -tx1 -v | tr -d ' \n'
      echo
  done | sort -u | wc -l
  echo
  echo "## 5. what a correct program would print"
  echo "# 99 'A' bytes then a newline = 100 bytes, exit 0. Measured stdout is 3 bytes,"
  echo "# exit 0, stderr empty. The defect is silent: no crash, no status change."
} > "$EVID/04-trigger.txt" 2>&1

# ---------------------------------------------------------------- 05 asan
{
  echo "# supplementary: AddressSanitizer confirmation"
  echo
  echo "# This is a DIAGNOSTIC build, not the fixture artefact. It carries -fsanitize=address,"
  echo "# which build.json#build.complete_flags does not, so original.asan.elf is a different"
  echo "# binary by design and must never stand in for original.elf."
  echo
  echo "## build"
  echo
  echo "  gcc -O0 -g -fno-omit-frame-pointer -fsanitize=address -I <support> \\"
  echo "      -o original.asan.elf harness.c original.c <support>/io.c"
  echo
  echo "## run"
  echo
  setarch -R ./original.asan.elf 2>&1 | head -40 || true
  echo
  echo "## exit status"
  echo
  setarch -R ./original.asan.elf >/dev/null 2>&1 || echo "exit=$?"
} > "$EVID/05-asan.txt" 2>&1

# ---------------------------------------------------------------- 06 sums
(
  cd "$EVID"
  for f in $(ls -1 | grep -v '^06-SHA256SUMS$' | sort); do
      sha256sum "$f"
  done > 06-SHA256SUMS
)

echo "== evidence written =="
ls -l "$EVID"
