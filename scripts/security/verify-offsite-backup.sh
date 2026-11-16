#!/usr/bin/env bash
# scripts/security/verify-offsite-backup.sh - offsite backup verification + restore drill
# usage: verify-offsite-backup.sh <backup-dir> [work-dir]
# post-consolidation expectations: refs/heads/final/consolidated-2026-11-16 is the
# delivery branch; the gated release SHA 4a7b2355... must still exist as an object.
set -u
DEST="${1:-}"
WORK="${2:-/tmp/binrepair-restore-drill}"
GATED="${EXPECT_GATED:-4a7b2355ffc5225d013a777bc7d588abac58f944}"
fail=0
pass() { printf 'PASS %s\n' "$*"; }
bad()  { printf 'FAIL %s\n' "$*"; fail=1; }
info() { printf 'INFO %s\n' "$*"; }
[ -n "$DEST" ] && [ -d "$DEST" ] || { echo "usage: $0 <backup-dir> [work-dir]"; exit 2; }
DEST="$(cd "$DEST" && pwd)"
MIRROR="${BACKUP_MIRROR:-${DEST}/binary-repair-mirror-2026-11-16.git}"
BUNDLE="${BACKUP_BUNDLE:-${DEST}/local-refs-2026-11-16.bundle}"
REFS="${BACKUP_REFS:-${DEST}/remote-refs-2026-11-16.txt}"
SUMS="$DEST/SHA256SUMS"
[ -d "$MIRROR" ] || { CAND="$(ls -d "$DEST"/*.git 2>/dev/null | head -1)"; [ -n "${CAND:-}" ] && MIRROR="$CAND"; }
[ -f "$BUNDLE" ] || { CAND="$(ls "$DEST"/*.bundle 2>/dev/null | head -1)"; [ -n "${CAND:-}" ] && BUNDLE="$CAND"; }
[ -f "$REFS" ] || { CAND="$(ls "$DEST"/*refs*.txt 2>/dev/null | head -1)"; [ -n "${CAND:-}" ] && REFS="$CAND"; }
echo "== backup dir: $DEST"
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
info "bundle size: $(du -h "$BUNDLE" | awk '{print $1}')  mirror size: $(du -sh "$MIRROR" | awk '{print $1}')"
echo "== 2) mirror integrity"
if git -C "$MIRROR" fsck --full --no-dangling >/dev/null 2>&1; then pass "mirror git fsck --full"; else bad "mirror git fsck failed"; fi
HEADS="$(git -C "$MIRROR" for-each-ref refs/heads | wc -l | tr -d ' ')"
TAGS="$(git -C "$MIRROR" for-each-ref refs/tags | wc -l | tr -d ' ')"
TOTAL="$(git -C "$MIRROR" for-each-ref | wc -l | tr -d ' ')"
info "mirror refs: total=$TOTAL heads=$HEADS tags=$TAGS"
[ "$TOTAL" -gt 0 ] && pass "mirror refs > 0" || bad "mirror has no refs"
MIRROR_FINAL="$(git -C "$MIRROR" rev-parse refs/heads/final/consolidated-2026-11-16 2>/dev/null || echo missing)"
[ "$MIRROR_FINAL" != missing ] && pass "delivery branch present in mirror ($MIRROR_FINAL)" || bad "delivery branch missing from mirror"
git -C "$MIRROR" cat-file -e "$GATED" 2>/dev/null && pass "gated release SHA present in mirror ($GATED)" || bad "gated release SHA missing from mirror"
echo "== 3) recovery drill: restore delivery branch from mirror"
rm -rf "$WORK"; mkdir -p "$WORK" || { echo "cannot create $WORK"; exit 2; }
SCRATCH="$WORK/restored.git"; git init -q --bare "$SCRATCH"
if git -C "$SCRATCH" fetch -q "$MIRROR" '+refs/heads/final/consolidated-2026-11-16:refs/heads/final/consolidated-2026-11-16' 2>"$WORK/fetch.err"; then
  pass "fetched delivery branch from mirror"
else bad "fetch from mirror failed (see $WORK/fetch.err)"; fi
FINAL="$(git -C "$SCRATCH" rev-parse refs/heads/final/consolidated-2026-11-16 2>/dev/null || echo missing)"
EXPECT_FINAL="${EXPECT_FINAL:-$MIRROR_FINAL}"
info "restored delivery branch = $FINAL (expected $EXPECT_FINAL)"
[ "$FINAL" = "$EXPECT_FINAL" ] && pass "delivery branch commit matches mirror" || bad "delivery branch mismatch"
[ "$(git -C "$SCRATCH" cat-file -t refs/heads/final/consolidated-2026-11-16 2>/dev/null)" = commit ] && pass "restored object is a commit" || bad "restored object type is not commit"
TREEFILES="$(git -C "$SCRATCH" ls-tree -r --name-only refs/heads/final/consolidated-2026-11-16 2>/dev/null | wc -l | tr -d ' ')"
info "restored delivery-branch tree files: $TREEFILES"
[ "$TREEFILES" -gt 0 ] && pass "restored tree is non-empty" || bad "restored tree empty"
git -C "$SCRATCH" cat-file -e "$GATED" 2>/dev/null && pass "gated release SHA present after restore" || bad "gated release SHA missing after restore"
echo "== 4) bundle verification + restore delivery branch from bundle"
if git -C "$SCRATCH" bundle verify "$BUNDLE" >"$WORK/bundle-verify.log" 2>&1; then
  pass "bundle verify ok"
else bad "bundle verify failed (see $WORK/bundle-verify.log)"; fi
if git -C "$SCRATCH" fetch -q "$BUNDLE" '+refs/heads/final/consolidated-2026-11-16:refs/heads/final/consolidated-2026-11-16' 2>"$WORK/fetch-bundle.err"; then
  FINAL_B="$(git -C "$SCRATCH" rev-parse refs/heads/final/consolidated-2026-11-16 2>/dev/null || echo missing)"
  info "restored delivery branch from bundle = $FINAL_B"
  [ "$(git -C "$SCRATCH" cat-file -t refs/heads/final/consolidated-2026-11-16 2>/dev/null)" = commit ] && pass "bundle restore object is a commit" || bad "bundle restore failed"
else bad "fetch delivery branch from bundle failed (see $WORK/fetch-bundle.err)"; fi
echo "== 5) restored repo integrity"
if git -C "$SCRATCH" fsck --full --no-dangling >/dev/null 2>&1; then pass "restored scratch repo fsck --full"; else bad "restored scratch repo fsck failed"; fi
info "work dir: $WORK"
if [ "$fail" -eq 0 ]; then echo "== RESULT: ALL PASS"; exit 0; else echo "== RESULT: FAILURES PRESENT"; exit 1; fi
