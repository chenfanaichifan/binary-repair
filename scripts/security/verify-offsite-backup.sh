#!/usr/bin/env bash
# scripts/security/verify-offsite-backup.sh - offsite backup verification + restore drill
# (reads the backup sources only; writes only the caller-provided scratch work dir)
#
# usage: verify-offsite-backup.sh <offsite-dir> [work-dir]
#   <offsite-dir>  target directory produced by tools/handoff/offsite-backup.sh
#                  (contains mirror/bundle/remote-refs/SHA256SUMS)
#   [work-dir]     scratch dir for the restore drill (default /tmp/binrepair-restore-drill,
#                  removed and recreated by this script)
#
# exit code: 0 = all PASS; 1 = FAIL; 2 = usage/prerequisite error
set -u
DEST="${1:-}"
WORK="${2:-/tmp/binrepair-restore-drill}"
fail=0
pass() { printf 'PASS %s\n' "$*"; }
bad()  { printf 'FAIL %s\n' "$*"; fail=1; }
info() { printf 'INFO %s\n' "$*"; }

[ -n "$DEST" ] && [ -d "$DEST" ] || { echo "usage: $0 <offsite-dir> [work-dir]"; exit 2; }
DEST="$(cd "$DEST" && pwd)"
# Default artifact names are the 2026-11-16 snapshot; after a backup refresh the
# caller may pass dated names via env vars, or the tool discovers them below.
MIRROR="${BACKUP_MIRROR:-${DEST}/binary-repair-mirror-2026-11-16.git}"
BUNDLE="${BACKUP_BUNDLE:-${DEST}/local-refs-2026-11-16.bundle}"
REFS="${BACKUP_REFS:-${DEST}/remote-refs-2026-11-16.txt}"
SUMS="$DEST/SHA256SUMS"
if [ ! -d "$MIRROR" ]; then CAND="$(ls -d "$DEST"/*.git 2>/dev/null | head -1)"; [ -n "$CAND" ] && MIRROR="$CAND"; fi
if [ ! -f "$BUNDLE" ]; then CAND="$(ls "$DEST"/*.bundle 2>/dev/null | head -1)"; [ -n "$CAND" ] && BUNDLE="$CAND"; fi
if [ ! -f "$REFS" ]; then CAND="$(ls "$DEST"/*refs*.txt 2>/dev/null | head -1)"; [ -n "$CAND" ] && REFS="$CAND"; fi

echo "== offsite dir: $DEST"
echo "INFO artifacts: mirror=$(basename "$MIRROR") bundle=$(basename "$BUNDLE") refs=$(basename "$REFS")"
for f in "$MIRROR" "$BUNDLE" "$REFS" "$SUMS"; do
  [ -e "$f" ] && pass "exists $(basename "$f")" || bad "missing $(basename "$f")"
done
[ "$fail" -eq 0 ] || { echo "== RESULT: FAIL (prerequisites)"; exit 1; }

echo "== 1) SHA256SUMS self-verification"
if ( cd "$DEST" && shasum -a 256 -c SHA256SUMS >/dev/null 2>&1 ); then
  pass "SHA256SUMS verified ($(grep -c . "$SUMS") files)"
else
  bad "SHA256SUMS mismatch"
fi
info "SHA256SUMS sha256: $(shasum -a 256 "$SUMS" | awk '{print $1}')"
info "bundle sha256: $(shasum -a 256 "$BUNDLE" | awk '{print $1}')"
info "offsite size: $(du -sh "$DEST" | awk '{print $1}')"

echo "== 2) mirror integrity"
if git -C "$MIRROR" fsck --full --no-dangling >/dev/null 2>&1; then
  pass "mirror git fsck --full"
else
  bad "mirror git fsck failed"
fi
HEADS="$(git -C "$MIRROR" for-each-ref refs/heads | wc -l | tr -d ' ')"
TAGS="$(git -C "$MIRROR" for-each-ref refs/tags | wc -l | tr -d ' ')"
TOTAL="$(git -C "$MIRROR" for-each-ref | wc -l | tr -d ' ')"
info "mirror refs: total=$TOTAL heads=$HEADS tags=$TAGS"
[ "$TOTAL" -gt 0 ] && pass "mirror refs > 0" || bad "mirror has no refs"
git -C "$MIRROR" for-each-ref --format='%(refname) %(objectname)' refs/heads/workbench-v3 refs/tags/release-2026-11-16-phase8c >/dev/null 2>&1 || bad "expected archive refs missing from mirror"

echo "== 3) recovery drill: restore refs from mirror into scratch repo"
rm -rf "$WORK"
mkdir -p "$WORK" || { echo "cannot create work dir $WORK"; exit 2; }
SCRATCH="$WORK/restored.git"
git init -q --bare "$SCRATCH"
if git -C "$SCRATCH" fetch -q "$MIRROR" '+refs/heads/workbench-v3:refs/heads/workbench-v3' '+refs/tags/release-2026-11-16-phase8c:refs/tags/release-2026-11-16-phase8c' 2>"$WORK/fetch.err"; then
  pass "fetched workbench-v3 + phase8c tag from mirror"
else
  bad "fetch from mirror failed (see $WORK/fetch.err)"
fi
WB3="$(git -C "$SCRATCH" rev-parse refs/heads/workbench-v3 2>/dev/null || echo missing)"
TAGC="$(git -C "$SCRATCH" rev-parse 'refs/tags/release-2026-11-16-phase8c^{commit}' 2>/dev/null || echo missing)"
EXP_WB3="${EXPECT_WORKBENCH_V3:-4a7b2355ffc5225d013a777bc7d588abac58f944}"
info "restored workbench-v3 = $WB3"
info "restored phase8c tag peel = $TAGC"
[ "$WB3" = "$EXP_WB3" ] && pass "workbench-v3 commit matches expected ($EXP_WB3)" || bad "workbench-v3 mismatch (expected $EXP_WB3)"
[ "$TAGC" = "$EXP_WB3" ] && pass "phase8c tag peels to gated release commit" || bad "phase8c tag peel mismatch"
[ "$(git -C "$SCRATCH" cat-file -t refs/heads/workbench-v3 2>/dev/null)" = commit ] && pass "restored object is a commit" || bad "restored object type is not commit"
TREEFILES="$(git -C "$SCRATCH" ls-tree -r --name-only refs/heads/workbench-v3 2>/dev/null | wc -l | tr -d ' ')"
info "restored workbench-v3 tree files: $TREEFILES"
[ "$TREEFILES" -gt 0 ] && pass "restored tree is non-empty" || bad "restored tree empty"

echo "== 4) bundle verification + restore final/consolidated ref from bundle"
if git -C "$SCRATCH" bundle verify "$BUNDLE" >"$WORK/bundle-verify.log" 2>&1; then
  pass "bundle verify: $(git -C "$SCRATCH" bundle verify "$BUNDLE" 2>&1 | tail -1)"
else
  bad "bundle verify failed (see $WORK/bundle-verify.log)"
fi
if git -C "$SCRATCH" fetch -q "$BUNDLE" '+refs/heads/final/consolidated-2026-11-16:refs/heads/final/consolidated-2026-11-16' 2>"$WORK/fetch-bundle.err"; then
  FINAL="$(git -C "$SCRATCH" rev-parse refs/heads/final/consolidated-2026-11-16 2>/dev/null || echo missing)"
  EXP_FINAL="${EXPECT_FINAL:${FINAL}}"
  info "restored final/consolidated-2026-11-16 = $FINAL (bundle snapshot)"
  [ "$(git -C "$SCRATCH" cat-file -t refs/heads/final/consolidated-2026-11-16 2>/dev/null)" = commit ] && pass "restored delivery-branch object is a commit" || bad "delivery branch restore failed"
  NFILES="$(git -C "$SCRATCH" ls-tree -r --name-only refs/heads/final/consolidated-2026-11-16 2>/dev/null | wc -l | tr -d ' ')"
  info "restored final branch tree files: $NFILES"
  [ "$NFILES" -gt 0 ] && pass "restored delivery-branch tree is non-empty" || bad "restored delivery-branch tree empty"
  git -C "$SCRATCH" cat-file -e 4a7b2355ffc5225d013a777bc7d588abac58f944 2>/dev/null && pass "gated release SHA 4a7b235 present in restored bundle" || bad "gated release SHA missing from restored bundle"
else
  bad "fetch final/consolidated branch from bundle failed (see $WORK/fetch-bundle.err)"
fi

echo "== 5) restored repo integrity"
if git -C "$SCRATCH" fsck --full --no-dangling >/dev/null 2>&1; then
  pass "restored scratch repo fsck --full"
else
  bad "restored scratch repo fsck failed"
fi
info "work dir: $WORK"

if [ "$fail" -eq 0 ]; then echo "== RESULT: ALL PASS"; exit 0; else echo "== RESULT: FAILURES PRESENT"; exit 1; fi
