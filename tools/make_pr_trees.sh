#!/usr/bin/env bash
# Rebuild the firmware trees of the replayed PRs under OUT/trees/{base,<PR>}. Read-only on GitHub and on the local checkout.
#   make_pr_trees.sh OUT FIRMWARE_CHECKOUT
# base = git archive of the checkout's HEAD; PR trees = base + `gh pr diff` (hunks that do not apply are dropped and
# counted in OUT/trees/<PR>.rejected); PR 955 = its spindle files at the commit the maintainer reviewed (1a5819e).
set -eu
[ $# -eq 2 ] || { echo "usage: make_pr_trees.sh OUT FIRMWARE_CHECKOUT" >&2; exit 2; }
OUT=$1; FW=$2
REPO=Smoothieware/Smoothieware; T=$OUT/trees; mkdir -p "$T/base"
git -C "$FW" archive HEAD | tar -x -C "$T/base"
for n in 620 633 1219 1227 1447 1488; do
  rm -rf "$T/$n"; cp -a "$T/base" "$T/$n"
  gh pr diff "$n" --repo $REPO > "$OUT/pr$n.diff"
  ( cd "$T/$n" && patch -p1 -s -N -r - --no-backup-if-mismatch < "$OUT/pr$n.diff" > "$T/$n.patchlog" 2>&1 ) || true
  grep -c "^Hunk .*FAILED\|hunks\? ignored\|FAILED" "$T/$n.patchlog" > "$T/$n.rejected" || true
done
SHA=1a5819efbc5ac6e6a79c59964dc2e4dab1e5bd6f
rm -rf "$T/955"; cp -a "$T/base" "$T/955"; rm -rf "$T/955/src/modules/tools/spindle"
gh api "repos/$REPO/git/trees/$SHA?recursive=1" --jq '.tree[]|select(.type=="blob" and (.path|startswith("src/modules/tools/spindle")))|.path' | while read -r f; do
  mkdir -p "$T/955/$(dirname "$f")"; gh api -H "Accept: application/vnd.github.raw" "repos/$REPO/contents/$f?ref=$SHA" > "$T/955/$f"
done
echo "trees ready in $T"
