#!/usr/bin/env bash
# 只读核验 V5 replay 与顶层清单，不修改任何文件。
#
#   bash verify-v5.sh /path/to/binaryrepair-mvp
#
# 预期结果：
#   HOST-SHA256SUMS      => ok=16 bad=0 missing=0
#   v5/SHA256SUMS        => ok=8  bad=0 missing=0
#   top-level SHA256SUMS => ok=65 bad=0 missing=0
set -uo pipefail

repo="${1:-.}"
root="$repo/delivery/p1-real-window-2026-11-07"
v5="$root/v5-replay-2026-11-07"
fail=0

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

check() {
  local base="$1" list="$2" label="$3"
  local ok=0 bad=0 miss=0
  if [ ! -f "$list" ]; then
    echo "$label => LIST MISSING: $list"
    fail=1
    return
  fi
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    case "$line" in \#*) continue;; esac
    local hash="${line%% *}"
    local path="${line#* }"
    path="${path# }"
    path="${path#\*}"
    [ "$hash" = "$path" ] && continue
    if [ -f "$base/$path" ]; then
      local actual
      actual=$(sha256_of "$base/$path")
      if [ "$actual" = "$hash" ]; then
        ok=$((ok + 1))
      else
        bad=$((bad + 1))
        echo "  BAD  $path"
      fi
    else
      miss=$((miss + 1))
      echo "  MISS $path"
    fi
  done < "$list"
  echo "$label => ok=$ok bad=$bad missing=$miss"
  if [ "$bad" -ne 0 ] || [ "$miss" -ne 0 ]; then fail=1; fi
}

check "$v5"   "$v5/HOST-SHA256SUMS" "HOST-SHA256SUMS     "
check "$v5"   "$v5/SHA256SUMS"      "v5/SHA256SUMS       "
check "$root" "$root/SHA256SUMS"    "top-level SHA256SUMS"

if [ "$fail" -ne 0 ]; then
  echo "RESULT: FAIL"
  exit 1
fi
echo "RESULT: PASS"
